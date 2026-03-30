# Phase C: Enrichment Layer — Engineering Log

**Started:** 2026-03-17

---

## Objective

Make our data usable without cross-referencing other sources. Raw data from Space-Track is noisy — satellites are identified by country codes instead of companies, constellations aren't labeled, and there's no way to correct errors without writing SQL. The gate for this phase: a non-technical user (investor, analyst) can look at our API output and immediately understand it.

---

## Decisions

### Constellation Enrichment: Pattern Matching over Manual Tagging

The `constellation` field existed on the `satellites` table since Phase A but was unpopulated except for partial UCS data (~5,500 satellites). We needed to tag ~17,000 payloads.

Alternatives considered:
- **Manual tagging** — accurate but impractical at scale. 17,000 payloads would take days.
- **UCS data only** — covers ~5,400 satellites but is 3 years stale and doesn't cover newer launches (Kuiper, Qianfan, recent Starlink batches).
- **Name-based pattern matching** — satellite names follow consistent conventions per constellation (e.g., `STARLINK-31286`, `ONEWEB-0621`, `FLOCK 4BE 11`). Fast to implement, covers the majority, and is deterministic.

**Decision:** Pattern matching as the primary method, with the admin CLI for manual corrections on edge cases.

**Implementation:** `src/ingestion/constellations.py`

- 38 constellation rules covering mega-constellations, navigation, communications, earth observation, IoT, and military programs
- Rules are ordered by specificity — first match wins. Specific patterns (e.g., `SKYSAT`) come before broad ones (e.g., `USA `)
- Matches against satellite name only (case-insensitive contains). Operator-based matching was considered but adds complexity without improving accuracy — name patterns are unambiguous for all major constellations
- Lightweight query approach: fetches only `(id, name, constellation)` columns instead of full ORM objects, then does batch UPDATEs. This avoids the 120s statement timeout that killed the initial full-ORM approach over Supabase

**Result:** 12,539 of 16,916 payloads (74.1%) tagged across 38 constellations. Top 5: Starlink (9,940), OneWeb (654), Kuiper (210), GLONASS (209), Yaogan (162).

The ~4,400 unmatched payloads are standalone satellites that don't belong to constellations (weather sats, science missions, individual commsats, military one-offs). This is expected — not every satellite is part of a constellation.

### Data Fix: Spire vs. Planet (Lemur)

**Problem:** 30 Lemur satellites were tagged as "Planet (Lemur)" by UCS data. Lemur is Spire Global's constellation, not Planet Labs'. Planet's constellations are Flock (Doves/SuperDoves), SkySat, and Pelican.

**Fix:** Corrected all 30 records from "Planet (Lemur)" to "Spire" via direct UPDATE. Updated the enrichment rules to match `LEMUR` → Spire going forward.

---

### Operator Consolidation: Constellation-Based Reassignment

Phase A left us with 544 operators — 441 real company names from UCS and 103 country-code placeholders from Space-Track. But the real names had 0 satellites each because the daily GP refresh was overwriting UCS assignments back to country codes.

Two root causes:
1. **GP refresh bug** — `src/ingestion/spacetrack.py` unconditionally set `satellite.operator_id` to the country-code operator on every run, clobbering real operator assignments from UCS. SATCAT already had a guard for this (checking `operator_type`), but GP did not.
2. **No constellation-to-operator mapping** — even after fixing the GP bug, the 9,940 Starlink satellites would still sit under "US" because UCS only covered ~5,400 payloads.

**Decision:** Fix the GP refresh to preserve real operators, then map constellations to their known operating companies. This is a reliable approach because constellation membership is unambiguous — every Starlink satellite is operated by SpaceX, every OneWeb satellite by OneWeb, etc.

**Implementation:** `src/ingestion/operators.py`

Three-step pipeline:

**Step 1: Constellation-to-operator reassignment.** 35 mapping rules that assign satellites from country-code operators to real companies based on their constellation tag. Examples:

| Constellation | Operator | Type | Country |
|---|---|---|---|
| Starlink | SpaceX | Commercial | US |
| OneWeb | OneWeb | Commercial | UK |
| Kuiper | Amazon Kuiper | Commercial | US |
| GPS | US Space Force | Military | US |
| GLONASS | Russian Aerospace Forces (VKS) | Military | RU |
| Planet (Flock/SkySat/Pelican) | Planet Labs | Commercial | US |
| Yaogan | People's Liberation Army (PLA) | Military | CN |
| BeiDou | China National Space Administration (CNSA) | Government | CN |

Only reassigns satellites currently under country-code operators (no `operator_type`). Satellites already under real operators are left untouched.

**Step 2: Duplicate name merging.** Merge rules for operator name variants created by UCS's verbose naming conventions. Examples:
- "SES S.A.", "SES S.A. -- total capacity leased to subsidiary of EchoStar Corp. " → **SES**
- "Intelsat S.A.", "Intelsat S.A. " (trailing space) → **Intelsat**
- "Spacex" → **SpaceX**
- "EUTELSAT S.A.", "EUTELSAT Americas" → **EUTELSAT**
- "Telesat Canada Ltd. (BCE, Inc.)" → **Telesat**

Reassigns all satellites and launches from variant operators to the canonical operator.

**Step 3: Orphan cleanup.** Deletes operators with 0 satellites and 0 launches. These are stale UCS imports that were never matched or whose satellites were reassigned.

**Result:**
- 12,378 satellites reassigned to real operators
- 438 orphaned operators removed
- Operator count: 544 → 135 (34 real companies, 101 country codes)
- Payload coverage under real operators: ~0% → 73.6%

The remaining ~4,400 payloads under country codes are standalone satellites without constellation membership. They'd require individual manual mapping — a reasonable target for ongoing curation via the admin CLI.

### GP Refresh Fix: Preserving Real Operator Assignments

**Problem (2026-03-17):** The Space-Track GP ingestion (`src/ingestion/spacetrack.py`) unconditionally overwrote `satellite.operator_id` with the country-code operator on every daily refresh. This meant any operator enrichment (UCS, constellation-based, manual) was lost within 24 hours.

SATCAT ingestion already had a guard for this — it checks whether the satellite's current operator has `operator_type` set (indicating a real company, not a country code) and skips the reassignment if so. GP did not have this guard.

**Fix:** Added the same `operator_type` check to GP ingestion. On update, if the satellite's current operator has `operator_type` set, the country-code operator from GP is ignored. New satellites (first seen) still get the country-code operator as a starting point.

**Implementation:** `src/ingestion/spacetrack.py` — added `operator_by_id` cache and conditional check before setting `operator_id` on existing satellites.

---

### Admin CLI: Internal Management Tool

Prospect calls and data quality work need a faster feedback loop than writing SQL. The admin CLI provides quick access to common operations without exposing them through the public API.

Alternatives considered:
- **Web admin panel** (Django admin, Flask-Admin) — adds a framework dependency and deployment complexity for a single-user tool. Overkill at this stage.
- **FastAPI admin endpoints** — would work, but admin operations are inherently interactive (search, inspect, confirm) and better suited to a terminal workflow.
- **Direct SQL** — works but error-prone for relational operations (reassigning operators requires updating foreign keys, not just changing a string).

**Decision:** Python CLI tool invoked as `python -m src.admin <command>`. No additional dependencies. Operates directly on the production database via the same connection logic as the API.

**Implementation:** `src/admin.py`

| Command | Purpose |
|---|---|
| `stats` | Database overview — satellite counts, operator coverage, constellation coverage, API keys, flagged items |
| `search <query>` | Find satellites by name or NORAD ID. Single-match shows full detail (orbit, operator, purpose, flags). Multi-match shows summary table (max 25) |
| `keys list` | List all API keys with owner, tier, active status, created date |
| `keys create <owner> [--tier]` | Generate a new 256-bit API key |
| `keys deactivate <prefix>` | Deactivate a key by prefix match |
| `operator list [--country-only]` | List operators with satellite counts, optionally filter to country-code-only operators |
| `operator reassign <norad_id> <name>` | Move a satellite to a different operator. Creates operator if it doesn't exist (with confirmation) |
| `constellation set <norad_id> <name>` | Set or correct a satellite's constellation |
| `constellation clear <norad_id>` | Remove a constellation assignment |
| `flag <norad_id> <note>` | Flag a satellite for manual review with a text note |
| `flags list` | Show all flagged satellites |
| `flags resolve <norad_id>` | Clear a flag after fixing the data issue |

**Flagging mechanism:** Repurposes the existing `source` and `source_id` fields on satellites. Flagging sets `source = "flagged"` and `source_id = <note>`. Resolving restores `source = "space_track"`. This avoids a schema migration while providing a lightweight issue tracker for data quality problems.

---

## New API Endpoint

### `GET /satellites/by-constellation` — Satellites filtered by constellation

**What it returns:** Satellites in a given constellation, with operator and orbit data included.

**Implementation:** `src/api/routes/satellites.py`

- Filters by constellation name (case-insensitive partial match)
- Optional `operator` and `object_type` cross-filters
- Eager-loads operator and orbit relationships

**Result:** 152 satellites returned for "Planet", 9,940 for "Starlink". Cross-filtering works — e.g., all Starlink satellites in SSO orbit.

**Query parameters:** `constellation` (required, partial match), `operator` (optional), `object_type` (optional), `limit`, `offset`

Additionally, the existing `/satellites/by-operator` and `/satellites/by-orbit` endpoints gained an optional `constellation` query parameter for cross-filtering.

---

## Current Database State (Supabase)

| Table | Records | Notes |
|---|---|---|
| `satellites` | 29,935 | All active tracked objects |
| `operators` | 135 | 34 real companies + 101 country codes (down from 544) |
| `orbits` | 29,935 | Full TLE + derived orbit class |
| `launches` | 6,787 | Historical launches derived from SATCAT |

Enrichment coverage:
- 12,539 payloads tagged with constellation (74.1% of payloads, across 38 constellations)
- 12,454 payloads under real-name operators (73.6% of payloads)
- 5,392 payloads have purpose data (from UCS — unchanged)
- Daily GP refresh now preserves real operator and constellation assignments

---

## Completed Work

- [x] Constellation enrichment — 12,539 payloads tagged across 38 constellations (`src/ingestion/constellations.py`)
- [x] Spire/Lemur data fix — 30 satellites corrected from "Planet (Lemur)" to "Spire"
- [x] Operator consolidation — 12,378 satellites reassigned to real operators (`src/ingestion/operators.py`)
- [x] Orphan operator cleanup — 438 stale operators removed (544 → 135)
- [x] GP refresh fix — preserves real operator assignments on daily refresh (`src/ingestion/spacetrack.py`)
- [x] Admin CLI — stats, search, key management, operator/constellation editing, flagging (`src/admin.py`)
- [x] New API endpoint: `GET /satellites/by-constellation`
- [x] Added `constellation` filter to `/satellites/by-operator` and `/satellites/by-orbit`

### Purpose/Mission Enrichment: Constellation-Based Mapping

**Problem:** Only ~5,400 payloads (32%) had purpose/mission classification data, all from the stale UCS dataset. Mission classification (EO, satcom, navigation, ISR, etc.) is a key pain point for analysts who otherwise have to classify manually.

**Approach:** Since constellation tagging already covers ~12,500 payloads, map constellation → purpose using the same categories UCS established. Same lightweight pattern as `constellations.py`: fetch tagged payloads, skip those with existing purpose, batch update.

**Implementation:** `src/ingestion/purposes.py`

- 38 constellation-to-purpose mappings across 6 categories: Communications, Navigation/Global Positioning, Earth Observation, Surveillance, Communications/IoT, Meteorological
- Preserves existing UCS purpose values — only fills in gaps
- Batch updates in groups of 500

**Result:** 3,795 satellites newly tagged. Combined with 8,744 existing UCS values, total purpose coverage: ~12,539 payloads (74%, up from 32%).

---

### Fly.io Deploy Fix: Depot Builder Timeout

**Problem (2026-03-30):** Fly.io deploys via GitHub Actions began consistently failing with `context deadline exceeded` errors. The `--remote-only` flag sends builds to Depot (Fly's remote Docker build service), which was timing out before completing the build.

**Fix:** Switched `.github/workflows/fly-deploy.yml` from `--remote-only` to `--local-only`. This builds the Docker image on the GitHub Actions runner and pushes directly to Fly's registry, bypassing Depot entirely. No practical downside for our lightweight Dockerfile (python:3.12-slim + pip install).

---

## Remaining Work

- [ ] Upcoming launch data — curated ingestion pipeline for scheduled launches (Phase C priority gap from Phase A)
- [ ] Gate check: can a non-technical user look at API output and immediately understand it without cross-referencing?

### Gate Assessment

Pending. Constellation and operator enrichment significantly improve readability — API responses now show "SpaceX" instead of "US", "Starlink" instead of blank. The admin CLI enables rapid data corrections. The main gap is upcoming launches: `/launches/upcoming` still returns 0 results because no scheduled launch data source has been implemented yet.
