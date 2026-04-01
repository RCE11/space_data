# Test Coverage

**Last updated:** 2026-03-31
**Total tests:** 81 (all passing)
**Test runner:** pytest with PostgreSQL (docker-compose)
**CI:** `.github/workflows/tests.yml` — runs on push to main and PRs

---

## Current Tests

### `tests/test_utils.py` — 45 unit tests

Pure function tests. No database or network required.

| Class | Tests | Source Function | Source File |
|---|---|---|---|
| `TestClassifyOrbit` | 13 | `classify_orbit()` | `src/ingestion/spacetrack.py` |
| `TestSafeConversions` | 9 | `_safe_float()`, `_safe_int()` | `src/ingestion/spacetrack.py` |
| `TestParseEpoch` | 5 | `_parse_epoch()` | `src/ingestion/spacetrack.py` |
| `TestMatchConstellation` | 9 | `_match_constellation()` | `src/ingestion/constellations.py` |
| `TestDesignatorPrefix` | 4 | `_designator_prefix()` | `src/ingestion/launches.py` |
| `TestParseDate` | 5 | `_parse_date()` | `src/ingestion/launches.py` |

### `tests/test_launches.py` — 15 integration tests

API endpoint tests against a test PostgreSQL database with seeded data.

| Class | Tests | Endpoint |
|---|---|---|
| `TestUpcomingLaunches` | 8 | `GET /launches/upcoming` |
| `TestLaunchHistory` | 7 | `GET /launches/history` |

Covers: status filtering, null date handling (nullslast), operator eager loading, launch_window field, year/site filters (ilike), pagination, empty results.

### `tests/test_satellites.py` — 17 integration tests

| Class | Tests | Endpoint |
|---|---|---|
| `TestByOperator` | 9 | `GET /satellites/by-operator` |
| `TestByOrbit` | 4 | `GET /satellites/by-orbit` |
| `TestByConstellation` | 4 | `GET /satellites/by-constellation` |

Covers: partial name match (ilike), case-insensitive search, default PAYLOAD filter, debris filter, constellation cross-filter, operator cross-filter, nested orbit/operator response objects, pagination, no-match results.

### `tests/test_auth.py` — 4 tests

Tests API key authentication with the hashed key model.

| Test | What it verifies |
|---|---|
| `test_valid_key` | SHA-256 hashed key authenticates, returns 200 |
| `test_invalid_key` | Wrong key returns 401 |
| `test_inactive_key` | Deactivated key returns 401 |
| `test_missing_header` | No X-API-Key header returns 401/403 |

### `tests/conftest.py` — Test infrastructure

- PostgreSQL test database (`spacedata_test` on local docker-compose)
- Session-scoped table creation/teardown
- Per-test transaction rollback (no data leaks between tests)
- FastAPI `TestClient` with `get_db` and `rate_limit` dependency overrides
- `seed_data` fixture with operators, launches, satellites, and orbits

---

## Coverage Map

### Tested

| Source File | What's Tested |
|---|---|
| `src/api/routes/launches.py` | Both endpoints, all query params, pagination |
| `src/api/routes/satellites.py` | All 3 endpoints, all query params, cross-filters |
| `src/api/auth.py` | `get_api_key()` — valid, invalid, inactive, missing |
| `src/api/schemas.py` | Implicitly via endpoint response validation |
| `src/api/main.py` | Implicitly via TestClient (app setup, router registration) |
| `src/db/models.py` | Implicitly via all integration tests |
| `src/db/connection.py` | Implicitly via test fixture override pattern |
| `src/ingestion/spacetrack.py` | Pure functions only: `classify_orbit`, `_safe_float`, `_safe_int`, `_parse_epoch` |
| `src/ingestion/constellations.py` | Pure function only: `_match_constellation` |
| `src/ingestion/launches.py` | Pure functions only: `_designator_prefix`, `_parse_date` |

### Not Tested

| Source File | What's Missing |
|---|---|
| `src/api/rate_limit.py` | Sliding window logic, tier enforcement, 429 response |
| `src/api/logging_middleware.py` | Request logging to `request_log` table |
| `src/ingestion/spacetrack.py` | `SpaceTrackClient` (login, query, rate limiting, retry), `ingest_satellite_catalog()` |
| `src/ingestion/satcat.py` | `ingest_satcat()` — SATCAT enrichment pipeline |
| `src/ingestion/launches.py` | `fetch_launch_data()`, `ingest_launches()` — launch derivation pipeline |
| `src/ingestion/ucs.py` | `ingest_ucs()` — Excel parsing, operator creation, satellite enrichment |
| `src/ingestion/upcoming.py` | `ingest_upcoming()` — JSON loading, operator lookup, launch upsert |
| `src/ingestion/constellations.py` | `enrich_constellations()` — DB mutation, batch update logic |
| `src/ingestion/operators.py` | `consolidate()` — reassignment, merge, orphan cleanup |
| `src/ingestion/purposes.py` | `enrich_purposes()` — constellation-to-purpose mapping |
| `src/ingestion/refresh.py` | `run()` — pipeline orchestration |
| `src/admin.py` | All 9 CLI commands (stats, search, keys, operator, constellation, flag, flags, usage) |

---

## Future Tests

### Priority 1: Rate Limiting

**File:** `tests/test_rate_limit.py`
**Prerequisite:** None — can test by not overriding `rate_limit` dependency.

| Test | What it verifies |
|---|---|
| Free tier 429 after 30 requests | Sliding window rejects at limit |
| Individual tier allows 100 | Higher tier gets higher limit |
| Window resets after 60s | Requests allowed again after window passes |
| Different keys tracked independently | One key's usage doesn't affect another |

### Priority 2: Ingestion Pure Functions (remaining)

**File:** `tests/test_utils.py` (extend existing)
**Prerequisite:** None.

| Function | Source File | Tests Needed |
|---|---|---|
| `SITE_NAMES` lookup | `src/ingestion/launches.py` | Verify known site codes map correctly |
| `CONSTELLATION_RULES` completeness | `src/ingestion/constellations.py` | Test all 38 rules, verify ordering doesn't cause mismatches |
| `OPERATOR_METADATA` lookup | `src/ingestion/upcoming.py` | Verify known operators return correct type/country |

### Priority 3: Ingestion Pipelines

**File:** `tests/test_ingestion.py`
**Prerequisite:** Refactor ingestion functions to accept a `Session` parameter instead of opening their own `SessionLocal()`. Currently all ingestion functions (`ingest_satellite_catalog`, `ingest_satcat`, `ingest_launches`, `enrich_constellations`, `consolidate`, `enrich_purposes`) create their own sessions internally, making them untestable without hitting the real database.

**Refactor pattern:**
```python
# Before (untestable)
def enrich_constellations():
    db = SessionLocal()
    ...

# After (testable)
def enrich_constellations(db: Session | None = None):
    close_on_exit = db is None
    if db is None:
        db = SessionLocal()
    ...
```

| Test | Source Function | What it verifies |
|---|---|---|
| GP upsert creates satellite + orbit | `ingest_satellite_catalog()` | New record creation, operator assignment |
| GP upsert updates existing satellite | `ingest_satellite_catalog()` | Update without duplicate, preserves real operator |
| SATCAT preserves UCS operator | `ingest_satcat()` | Doesn't overwrite operator_type-bearing assignments |
| Launch derivation groups by designator | `ingest_launches()` | Correct prefix grouping, date parsing, satellite linking |
| Constellation enrichment skips existing | `enrich_constellations()` | Doesn't overwrite, batch update works |
| Operator consolidation reassigns | `consolidate()` | Constellation-to-operator mapping, merge dedup, orphan cleanup |
| Purpose enrichment fills gaps | `enrich_purposes()` | Maps constellation to purpose, preserves UCS values |
| Upcoming loader upserts | `ingest_upcoming()` | Creates launches, links operators, deduplicates on source_id |

### Priority 4: SpaceTrack Client

**File:** `tests/test_spacetrack_client.py`
**Prerequisite:** Mock HTTP responses (use `pytest-httpx` or `respx`).

| Test | What it verifies |
|---|---|
| Login sends credentials, sets authenticated flag | Auth flow |
| Query builds correct URL from class + filters | URL construction |
| 401 triggers re-auth and retry | Session expiry recovery |
| Rate limiting delays between requests | `MIN_REQUEST_INTERVAL` enforcement |
| Logout clears authenticated flag | Cleanup |

### Priority 5: Admin CLI

**File:** `tests/test_admin.py`
**Prerequisite:** Refactor CLI commands to accept a session parameter (same pattern as ingestion).

| Test | What it verifies |
|---|---|
| `keys create` stores hash, not plaintext | Key security |
| `keys create` shows full key once | User can copy the key |
| `keys list` shows prefix only | No key leakage |
| `keys deactivate` by prefix | Correct prefix matching |
| `search` by NORAD ID | Single result detail |
| `search` by name | Partial match, max 25 results |
| `operator reassign` moves satellite | Foreign key update |
| `flag` / `flags resolve` roundtrip | Flag set and clear |
| `usage` filters by user and days | Correct log filtering |

### Priority 6: Logging Middleware

**File:** `tests/test_middleware.py`
**Prerequisite:** Middleware opens its own `SessionLocal()`, bypassing test session override. Either mock `SessionLocal` in tests or refactor middleware to accept a session factory.

| Test | What it verifies |
|---|---|
| Authenticated request creates log entry | Log written with correct endpoint, owner, status |
| Unauthenticated request not logged | No log entry for missing key |
| Non-API paths not logged | `/docs`, `/` skipped |
| Logging failure doesn't break request | Silent exception handling |

---

## Test Infrastructure Notes

- **Database:** Tests require local PostgreSQL via `docker compose up -d`. Test DB is `spacedata_test` on `localhost:5432`.
- **CI:** GitHub Actions workflow uses a Postgres 16 service container. No Docker-in-Docker needed.
- **Isolation:** Each test runs in a rolled-back transaction. No data persists between tests.
- **Overrides:** `get_db` is overridden to use the test session. `rate_limit` is overridden to skip rate limiting (returns a dummy ApiKey). Both are cleared after each test via `app.dependency_overrides.clear()`.
- **Env var:** `TEST_DATABASE_URL` overrides the default test connection string if set.
