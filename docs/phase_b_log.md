# Phase B: API Layer — Engineering Log

**Started:** 2026-03-16

---

## Objective

Build a thin REST API on top of the Phase A database. No business logic in the API — it reads from the database and returns JSON. The gate for this phase: someone with an API key can hit our endpoints and get back clean, accurate JSON.

---

## Decisions

### Framework: FastAPI

Confirmed the Phase A technical default. FastAPI auto-generates OpenAPI/Swagger docs from type annotations, supports async if we need it later, and has minimal boilerplate. The interactive docs at `/docs` double as a demo tool for prospect calls.

**Implementation:** `src/api/main.py`

### Authentication: API Key via Header

Simple API key table in the database. Keys are checked on every request via the `X-API-Key` header.

- **`api_keys` table** — key (64-char hex), owner name, tier (free/individual/team), active flag, created_at
- Keys are 256-bit random hex strings generated with `secrets.token_hex(32)`
- No expiration, no scoping — keys are either active or inactive. Complexity can be added when needed.
- Alembic migration: `5e6422da0f8c_add_api_keys_table.py`

Alternatives considered:
- **OAuth2 / JWT** — overkill for an API-key-only product at this stage. Adds token refresh complexity with no benefit when our users are machines, not browsers.
- **Key in query string** — keys leak into server logs and browser history. Header-based is standard for API products.

**Implementation:** `src/api/auth.py`

### Rate Limiting: In-Memory Sliding Window

Per-key sliding window rate limiter. Tracks request timestamps in memory and rejects requests that exceed the tier limit within a 60-second window.

| Tier | Requests/minute |
|---|---|
| Free / trial | 30 |
| Individual ($99–299/mo) | 100 |
| Team / Enterprise ($500–1,000/mo) | 500 |

Starting conservative — easy to raise limits later, harder to lower them without breaking integrations. These numbers are generous enough for any reasonable human or script usage while protecting against accidental infinite loops.

**Limitation:** In-memory state means rate limit counters reset on server restart and don't share across multiple server instances. Acceptable for single-instance deployment. If we scale to multiple instances, move to Redis-backed rate limiting.

**Implementation:** `src/api/rate_limit.py`

### Pagination: Offset/Limit

All list endpoints return paginated responses with `total`, `limit`, `offset`, and `results`. Default limit is 50, max is 200.

```json
{
  "total": 3500,
  "limit": 50,
  "offset": 0,
  "results": [...]
}
```

This is the simplest pattern that gives callers everything they need to paginate through results. Cursor-based pagination would be more efficient for very deep pages but adds complexity we don't need — our largest result sets (satellites by operator) are in the low thousands, not millions.

### Response Schemas: Pydantic Models

Pydantic models define the JSON shape for every endpoint. This serves three purposes:
- Validates what we return (catches bugs where a query returns unexpected nulls or types)
- Auto-generates accurate OpenAPI docs (prospects see exact field names and types in Swagger)
- Decouples the API response from the database model (we can change internal schema without breaking the API contract)

**Implementation:** `src/api/schemas.py`

---

## Endpoints

### 1. `GET /launches/upcoming` — Scheduled launches

**What it returns:** Launches with status `scheduled` and launch date in the future, ordered by launch date ascending.

**Implementation:** `src/api/routes/launches.py`

- Filters on `status == "scheduled"` and `launch_date > now`
- Eager-loads operator relationship to avoid N+1 queries
- Paginated with offset/limit (default 50, max 200)

**Result:** Returns empty results (`total: 0`) — expected, since no upcoming launch data exists yet (Phase C priority). The endpoint is live and the contract is complete; it will start returning data automatically once scheduled launches are ingested.

**Query parameters:** `limit` (1–200, default 50), `offset` (>= 0, default 0)

### 2. `GET /launches/history` — Past launches

**What it returns:** Launches with status `launched`, ordered by launch date descending (most recent first).

**Implementation:** `src/api/routes/launches.py`

- Filters on `status == "launched"`
- Optional `year` filter narrows to a single calendar year
- Optional `site` filter does partial match on launch site name
- Eager-loads operator relationship

**Result:** 254 launches returned for 2024 (after launch coverage fix — see below). Data includes launch date, site, payload description, and operator where available.

**Query parameters:** `year` (optional, 1957–2100), `site` (optional, partial match), `limit`, `offset`

### 3. `GET /satellites/by-operator` — Satellites filtered by operator

**What it returns:** Satellites belonging to a given operator, with orbit data included.

**Implementation:** `src/api/routes/satellites.py`

- Joins to operator table, filters by partial name match (case-insensitive)
- Optional `object_type` filter (PAYLOAD, DEBRIS, ROCKET BODY, UNKNOWN)
- Eager-loads operator and orbit relationships
- Ordered alphabetically by satellite name

**Result:** 2,975 satellites returned for "SpaceX", each with orbit class, apogee/perigee, inclination, and period.

**Query parameters:** `operator` (required, partial match), `object_type` (optional), `limit`, `offset`

### 4. `GET /satellites/by-orbit` — Satellites filtered by orbit classification

**What it returns:** Satellites in a given orbit class (LEO, MEO, GEO, HEO, SSO), with operator and orbit data included.

**Implementation:** `src/api/routes/satellites.py`

- Joins to orbit table, filters by orbit class
- Optional `operator` filter for cross-referencing (e.g., "all SpaceX satellites in LEO")
- Optional `object_type` filter
- Eager-loads operator and orbit relationships

**Result:** 1,343 GEO satellites returned. Cross-filtering works — can query e.g. all SpaceX satellites in SSO.

**Query parameters:** `orbit_class` (required: LEO/MEO/GEO/HEO/SSO), `operator` (optional, partial match), `object_type` (optional), `limit`, `offset`

---

## API Structure

```
src/api/
  main.py              # FastAPI app, router registration
  auth.py              # API key authentication (X-API-Key header)
  rate_limit.py        # Per-key sliding window rate limiter
  schemas.py           # Pydantic response models (Launch, Satellite, Orbit, Operator, paginated wrappers)
  routes/
    launches.py        # /launches/upcoming, /launches/history
    satellites.py      # /satellites/by-operator, /satellites/by-orbit
```

---

## Data Fix: Historical Launch Coverage

**Problem (2026-03-16):** `/launches/history?year=2024` returned 221 launches, but ~260 orbital launches occurred in 2024. The gap: `src/ingestion/launches.py` was querying SATCAT with `CURRENT=Y` and `DECAY=null-val`, meaning launches where the primary payload had since decayed were excluded entirely.

**Fix:** Removed the active-only filters from the launch derivation SATCAT query. We want all historical launch events regardless of whether the payload is still on orbit. Satellite-level `status` (active/decayed/deorbited) already tracks object state independently.

**Result:** 2024 launches went from 221 → 254 (close to the ~260 actual, remaining gap is likely classified payloads or SATCAT cataloging edge cases). Total launches across all years went from ~3,500 → 6,785.

---

## Deployment: Fly.io

**Decision (2026-03-16):** Deployed on Fly.io rather than Railway. Fly.io allows region selection, so the API runs in `iad` (Ashburn, Virginia) — same region as the Supabase database in `us-east-2`, keeping latency between API and database low.

**Configuration:**
- `Dockerfile` — Python 3.12 slim, installs dependencies from `pyproject.toml`, runs uvicorn on port 8080
- `fly.toml` — auto-stop machines when idle (saves cost), auto-start on incoming requests, health check against `/docs`
- `.dockerignore` — excludes `.venv`, `data/`, `docs/`, `.env`, `.git/`
- Supabase connection string stored as a Fly.io secret (`SUPABASE_DATABASE_URL`)

**Live URL:** `https://space-data-api.fly.dev`
**Swagger docs:** `https://space-data-api.fly.dev/docs`

### Alembic env.py Fix

During deployment, discovered that `alembic/env.py` was hardcoded to use `DATABASE_URL`, while the app uses `SUPABASE_DATABASE_URL` when available. This meant migrations were running against local Docker instead of Supabase. Fixed `env.py` to match the same fallback logic as `src/db/connection.py`: prefer `SUPABASE_DATABASE_URL`, fall back to `DATABASE_URL`.

---

## Completed Work

- [x] FastAPI app setup (`src/api/main.py`)
- [x] API key authentication (`src/api/auth.py`, `api_keys` table, Alembic migration)
- [x] Per-key tiered rate limiting (`src/api/rate_limit.py`)
- [x] Pydantic response schemas (`src/api/schemas.py`)
- [x] `GET /launches/upcoming` endpoint
- [x] `GET /launches/history` endpoint
- [x] `GET /satellites/by-operator` endpoint
- [x] `GET /satellites/by-orbit` endpoint
- [x] OpenAPI/Swagger docs auto-generated at `/docs`
- [x] Deployed on Fly.io (`https://space-data-api.fly.dev`)
- [x] Historical launch coverage fix (221 → 254 for 2024, ~3,500 → 6,785 total)
- [x] UCS enrichment run against Supabase (5,400 satellites with real operator names)
- [x] Alembic `env.py` fix for Supabase connection

## Gate Assessment

**Gate: Someone with an API key can hit all endpoints and get back clean, accurate JSON.**

Gate is met. All four endpoints verified against the live deployment:

| Endpoint | Result |
|---|---|
| `GET /launches/upcoming` | 0 results (expected — no scheduled launches until Phase C) |
| `GET /launches/history?year=2024` | 254 launches |
| `GET /satellites/by-operator?operator=SpaceX` | 2,975 satellites with orbit data |
| `GET /satellites/by-orbit?orbit_class=GEO` | 1,343 satellites with operator data |

**Phase B complete.** — 2026-03-16
