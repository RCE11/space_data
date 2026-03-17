# Space Data Intelligence Platform

API for querying launch manifests, satellite registries, and orbital data. Answers the question: **"Who is launching what satellites, when, and to what orbit?"**

## Data Sources

| Source | What it provides | Update frequency |
|---|---|---|
| [Space-Track](https://www.space-track.org/) GP | Orbital elements, TLEs, object tracking for all active satellites | Daily (automated) |
| [Space-Track](https://www.space-track.org/) SATCAT | Authoritative satellite names, country codes, launch metadata | Daily (automated) |
| [UCS Satellite Database](https://www.ucsusa.org/resources/satellite-database) | Real operator names, satellite purpose, user type | Manual (updated ~annually) |

Historical launches are derived from satellite international designators in the Space-Track catalog.

## Database

Four core tables in PostgreSQL:

- **operators** — companies and countries that own satellites (544 records, 441 with real company names)
- **satellites** — tracked space objects: payloads, debris, rocket bodies (29,730 records)
- **orbits** — latest TLE and derived orbital parameters per satellite, classified as LEO/MEO/GEO/HEO/SSO
- **launches** — historical launch events with date, site, and linked payloads (3,500+ records)

## Project Structure

```
src/
  db/
    models.py          # SQLAlchemy models (Operator, Launch, Satellite, Orbit)
    connection.py      # Database engine/session configuration
  ingestion/
    spacetrack.py      # Space-Track GP bulk ingestion
    satcat.py          # SATCAT metadata enrichment
    ucs.py             # UCS satellite database enrichment
    launches.py        # Historical launch derivation from international designators
    refresh.py         # Daily refresh pipeline (GP -> SATCAT -> launches)
alembic/               # Database migrations
data/                  # Local data files (UCS Excel, etc.)
docs/                  # Project planning and engineering logs
```

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for local PostgreSQL)
- A [Space-Track](https://www.space-track.org/) account

### Install

```bash
uv pip install -e .
```

### Local Database

```bash
docker compose up -d
```

This starts PostgreSQL 16 on `localhost:5432` (user: `spacedata`, password: `spacedata_dev`, database: `spacedata`).

### Environment Variables

Create a `.env` file in the project root:

```
DATABASE_URL=postgresql://spacedata:spacedata_dev@localhost:5432/spacedata
SPACETRACK_USER=your_email
SPACETRACK_PASSWORD=your_password
```

For production (Supabase), set `SUPABASE_DATABASE_URL` instead — it takes priority over `DATABASE_URL`.

### Run Migrations

```bash
alembic upgrade head
```

### Ingest Data

Run the full pipeline on a fresh database (order matters):

```bash
python -m src.ingestion.spacetrack    # ~29k satellites + orbits
python -m src.ingestion.ucs           # operator/purpose enrichment
python -m src.ingestion.satcat        # authoritative metadata
python -m src.ingestion.launches      # derive historical launches
```

For daily updates:

```bash
python -m src.ingestion.refresh
```

## Automated Refresh

A GitHub Actions workflow (`.github/workflows/daily_refresh.yml`) runs the refresh pipeline daily at 18:00 UTC against the Supabase production database. It can also be triggered manually via `workflow_dispatch`.

Required GitHub Actions secrets: `SUPABASE_DATABASE_URL`, `SPACETRACK_USER`, `SPACETRACK_PASSWORD`.
