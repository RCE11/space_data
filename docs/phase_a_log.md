# Phase A: Data Foundation — Engineering Log

**Started:** 2026-03-14

---

## Objective

Build a normalized PostgreSQL database with automated ingestion from public space data sources. The gate for this phase: we can query our own database and accurately answer "What is launching in the next 90 days, and who operates those satellites?"

---

## Decisions

### Database: PostgreSQL

Our data is relational — launches have satellites, satellites have operators, operators have multiple satellites across orbits. Postgres handles this naturally with strong query performance. Alternatives considered:

- **SQLite** — too limited for concurrent access and deployment
- **MongoDB** — our schema is well-defined, not a fit for document stores
- **DuckDB** — optimized for analytics, but we're serving an API

Local dev runs Postgres 16 via Docker. Production runs on Supabase (free tier, PostgreSQL 17, session pooler connection via `aws-1-us-east-2.pooler.supabase.com`).

### Python Environment: uv + src layout

- **uv** for dependency management — fast, handles venv and deps in one tool, `pyproject.toml`-based
- **src/ layout** — keeps ingestion, API, and database code separated without overengineering
- **Alembic** for database migrations — tracks schema changes as versioned scripts so the database can be reproduced from scratch on any machine

### Schema Design

Four core tables:

| Table | Purpose | Key Fields |
|---|---|---|
| `operators` | Companies/countries that own satellites | name, country, operator_type |
| `launches` | Launch events (past and scheduled) | launch_date, vehicle, operator, status |
| `satellites` | Individual space objects | norad_id, operator, object_type, purpose, constellation |
| `orbits` | Latest orbital parameters per satellite | orbit_class, apogee/perigee, inclination, TLE lines |

Design choices:
- **`source` + `source_id`** on launches and satellites enables deduplication when multiple sources reference the same object
- **`orbit_class`** (LEO/MEO/GEO/HEO/SSO) is derived from period and inclination, stored as a string (not enum) so new classifications don't require a migration
- **`object_type`** on satellites distinguishes PAYLOAD, DEBRIS, ROCKET BODY, and UNKNOWN — we store all types because debris data is valuable for conjunction risk (a future expansion layer), and API consumers can filter by type
- **`Orbit` is one-to-one with `Satellite`** — stores only the latest TLE and derived parameters, not historical data

---

## Data Sources

### 1. Space-Track GP (General Perturbations) — Primary orbital + satellite catalog

**What it gives us:** Every tracked object on orbit with latest TLE, orbital elements, country code, object type.

**Implementation:** `src/ingestion/spacetrack.py`

- Single bulk query using the `gp` class with `decay_date/null-val` (active only) and `epoch/>now-10` (propagable ephemerides only), per Space-Track's recommended approach
- Authenticates via POST to `/ajaxauth/login`, logs out on close
- Rate limited to 2.5s between requests (~24/min), well within Space-Track's 30/min limit
- Upserts operators, satellites, and orbits — safe to re-run without creating duplicates
- Orbit classification derived from period: LEO (<200 min), MEO (200–600), GEO (600–1400), HEO (>1400), with SSO detected by inclination (96–100°) within LEO
- Fallback logic: if `OBJECT_TYPE` is missing, infers from name conventions ("DEB" → DEBRIS, "R/B" → ROCKET BODY)

**Result:** 29,599 objects ingested (16,910 payloads, 9,537 debris, 2,174 rocket bodies, 977 unknown). 103 operators (country codes at this stage).

**Limitations:** GP class only provides country codes, not company names. No satellite purpose or constellation data.

### 2. UCS Satellite Database — Operator and purpose enrichment

**What it gives us:** Real operator names (SpaceX, OneWeb, etc.), satellite purpose (Communications, Earth Observation), user type (Commercial, Government, Military).

**Implementation:** `src/ingestion/ucs.py`

- Reads a manually downloaded Excel file (`data/ucs_satellites.xlsx`) from the Union of Concerned Scientists
- Joins to existing satellites on NORAD ID
- Creates new operator records with real company names and types
- Enriches purpose and international designator fields

**Result:** 7,560 records parsed, 5,400 matched to our catalog. 441 real-name operators created (SpaceX, OneWeb, Iridium, SES, etc.).

**Limitations:** Last updated May 2023 — nearly 3 years stale. Covers ~5,400 of our 16,910 payloads. Does not track debris or rocket bodies. UCS largely aggregates other public sources, so this is an enrichment layer, not a primary source.

**Decision: Use UCS as enrichment, not baseline.** UCS adds valuable purpose/operator data where it exists, but we don't depend on it for coverage. SATCAT serves as the authoritative baseline.

### 3. Space-Track SATCAT — Authoritative satellite catalog

**What it gives us:** Authoritative names, country codes, object types, launch info for the full tracked catalog. Updated daily.

**Implementation:** `src/ingestion/satcat.py`

- Queries the `satcat` class for all active on-orbit objects (`CURRENT=Y`, `DECAY=null-val`)
- Enriches satellite name, international designator, and object type
- Preserves UCS operator assignments — only updates operator for satellites that don't already have a UCS-enriched operator (detected by checking if `operator_type` is set)
- Per Space-Track guidelines: should be queried at most once per day after 1700 UTC

**Result:** 33,243 SATCAT records fetched, 29,245 matched and enriched. UCS enrichments preserved.

### 4. FAA Launch Licenses — Dropped from Phase A

**Investigation (2026-03-14):** After researching the FAA's data offerings, we determined that FAA launch licenses are not a useful data source for the MVP:

- The FAA does not publish structured launch data (no API, no CSV, no tables)
- Launch licenses are PDF documents authorizing a vehicle and site, not specific missions
- A single license (e.g., "LRLO 24-118") can cover dozens of missions with no date or payload info
- The FAA website is regulatory guidance, not a data platform

**Decision:** Drop FAA from Phase A. Historical launches will be derived from Space-Track data instead (see below). Upcoming launch tracking is documented as a priority gap to address in Phase C through manual curation of operator press releases and industry sources.

This decision is documented in `sprint_plan.md` under "Future Data Source Candidates."

### 5. Historical Launch Derivation — Complete

**Approach:** Every satellite has an international designator (e.g., `2024-123A`) that encodes the launch event. Grouping satellites by designator prefix (`2024-123`) reconstructs launch events with date, site, and all associated objects. SATCAT provides launch date and launch site for primary payloads (LAUNCH_PIECE=A).

**Implementation:** `src/ingestion/launches.py`

- Fetches SATCAT filtered to primary payloads only (`LAUNCH_PIECE=A`) to get one record per launch event
- Groups satellites by international designator prefix to link all objects from the same launch
- Creates launch records with date, site, payload description, and status ("launched")
- Links each satellite back to its launch via `launch_id` foreign key

**Result:** 3,500 launch events derived, 26,675 satellites linked to their launches.

**Limitations:** Only covers historical launches (objects already in the Space-Track catalog). No launch vehicle data (Falcon 9, Ariane 6, etc.) — SATCAT doesn't include it directly. Could be enriched in Phase C. No upcoming/scheduled launches — see Known Gaps.

---

## Ingestion Order

The scripts should be run in this order on a fresh database:

1. **Space-Track GP** — creates the baseline: all satellites, orbits, and country-code operators
2. **UCS** — enriches with real operator names and purpose (won't overwrite, only adds)
3. **SATCAT** — refreshes names and metadata, respects UCS enrichments
4. **Historical launches** — derives launch records from satellite international designators

On daily refresh, GP, SATCAT, and launch derivation run together via `src/ingestion/refresh.py`. UCS is excluded from daily refresh — run manually when they release a new version.

---

## Infrastructure

### Database Deployment: Supabase

**Decision (2026-03-15):** Moved from local-only Docker Postgres to Supabase (free tier) as the production database. Reasons:

- Enables daily refresh via GitHub Actions without dependency on local machine
- API can be demoed to prospects from anywhere, not just localhost
- Avoids a migration headache later — data layer is deployed before Phase B API work begins
- Local Docker Postgres kept for development

**Connection:** Uses session pooler (`aws-1-us-east-2.pooler.supabase.com:5432`) to avoid IPv6 issues with WSL/direct connections. Connection string stored in `.env` as `SUPABASE_DATABASE_URL`. The app prefers `SUPABASE_DATABASE_URL` over `DATABASE_URL` when both are set.

**Statement timeout:** Set to 120s on the SQLAlchemy engine (`connect_args`) to accommodate batch commits over network latency.

### Daily Refresh: GitHub Actions

**Implementation:** `.github/workflows/daily_refresh.yml`

- Runs daily at 18:00 UTC (after Space-Track's 1700 UTC update window per their guidelines)
- Can also be triggered manually via `workflow_dispatch`
- Executes `src/ingestion/refresh.py` which runs GP → SATCAT → launch derivation in order
- Credentials stored as GitHub Actions secrets: `SUPABASE_DATABASE_URL`, `SPACETRACK_USER`, `SPACETRACK_PASSWORD`

### Performance: Batch Optimization

Initial ingestion scripts did per-row database queries — fast locally but unacceptably slow over network to Supabase (~30k round trips). All ingestion scripts were optimized with:

- **In-memory caching:** Operators, satellites, and orbits loaded into dicts at start, eliminating ~90k SELECT queries per run
- **Batch commits:** Commit every 200–500 records instead of one large transaction at the end, avoiding Supabase statement timeouts
- **First run:** ~30 minutes for full pipeline (all INSERTs over network)
- **Daily refresh:** Faster since most records are UPDATEs (no flush needed for existing rows)

---

## Current Database State (Supabase)

| Table | Records | Notes |
|---|---|---|
| `satellites` | 29,673 | All active tracked objects |
| `operators` | 544 | 103 country codes + 441 real company names from UCS |
| `orbits` | 29,673 | Full TLE + derived orbit class |
| `launches` | 3,500 | Historical launches derived from SATCAT |

Enrichment coverage:
- 5,392 satellites have purpose data (from UCS)
- 26,675 satellites linked to launch events
- 441 operators with real company names (from UCS), remainder are country codes — target for Phase C manual enrichment

---

## Known Gaps

- **Upcoming launches:** No automated source exists. This is the most significant data gap. FAA licenses don't provide mission-level detail, and no public API offers reliable upcoming launch schedules. Must be addressed in Phase C through manual curation (operator press releases, Spaceflight Now, NASA Spaceflight forums). Documented in sprint_plan.md as a priority future source.

---

## Completed Work

- [x] PostgreSQL schema design (operators, launches, satellites, orbits)
- [x] Space-Track GP ingestion — 29,673 satellites + orbits
- [x] UCS enrichment — 5,400 satellites with real operator names + purpose
- [x] SATCAT enrichment — 29,301 satellites with authoritative metadata
- [x] Historical launch derivation — 3,500 launches, 26,675 satellites linked
- [x] Supabase deployment — full dataset live in production database
- [x] GitHub Actions daily refresh workflow (`.github/workflows/daily_refresh.yml`)
- [x] Batch optimization for remote database performance

## Remaining Work

- [ ] Push repo to GitHub and configure Actions secrets (`SUPABASE_DATABASE_URL`, `SPACETRACK_USER`, `SPACETRACK_PASSWORD`)
- [ ] Verify first automated daily refresh runs successfully
- [ ] Gate check: can we answer "What is launching in the next 90 days, and who operates those satellites?"

### Gate Assessment

The historical side of the gate question is met — we can query who launched what, when, from where, and to what orbit. The "next 90 days" part (upcoming launches) cannot be answered yet because no automated source for scheduled launches exists. This is documented as a Phase C priority and in `sprint_plan.md` under Future Data Source Candidates.
