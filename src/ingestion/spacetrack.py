"""Space-Track.org data ingestion.

Pulls satellite catalog and TLE data into the local database.
Rate limits: max 30 requests/minute, 300 requests/hour.
"""

import os
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

from src.db.connection import SessionLocal
from src.db.models import Operator, Orbit, Satellite

load_dotenv()

BASE_URL = "https://www.space-track.org"
LOGIN_URL = f"{BASE_URL}/ajaxauth/login"
QUERY_URL = f"{BASE_URL}/basicspacedata/query"

# Rate limiting: stay well within 30 req/min and 300 req/hour
MIN_REQUEST_INTERVAL = 2.5  # seconds between requests (~24/min max)


class SpaceTrackClient:
    def __init__(self):
        self.client = httpx.Client(timeout=60)
        self.last_request_time = 0.0
        self.authenticated = False

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def login(self):
        resp = self.client.post(LOGIN_URL, data={
            "identity": os.environ["SPACETRACK_USER"],
            "password": os.environ["SPACETRACK_PASSWORD"],
        })
        resp.raise_for_status()
        self.authenticated = True
        self.last_request_time = time.time()
        print("Authenticated with Space-Track.")

    def query(self, class_name: str, **filters) -> list[dict]:
        if not self.authenticated:
            self.login()

        # Build query URL from filters
        parts = [QUERY_URL, "class", class_name]
        for key, value in filters.items():
            parts.extend([key, str(value)])
        parts.extend(["format", "json"])
        url = "/".join(parts)

        self._rate_limit()
        resp = self.client.get(url)

        # Session may have expired — re-authenticate and retry once
        if resp.status_code == 401:
            print("Session expired, re-authenticating...")
            self.authenticated = False
            self.login()
            self._rate_limit()
            resp = self.client.get(url)

        resp.raise_for_status()
        return resp.json()

    def logout(self):
        if self.authenticated:
            self._rate_limit()
            self.client.get(f"{BASE_URL}/ajaxauth/logout")
            self.authenticated = False
            print("Logged out of Space-Track.")

    def close(self):
        self.logout()
        self.client.close()


def classify_orbit(period_min: float | None, inclination_deg: float | None) -> str:
    """Derive orbit class from period and inclination."""
    if period_min is None:
        return "UNKNOWN"
    if period_min > 1400:
        return "HEO"
    if 1400 >= period_min > 600:
        return "GEO"
    if 600 >= period_min > 200:
        return "MEO"
    # LEO — check for sun-synchronous
    if inclination_deg and 96 <= inclination_deg <= 100:
        return "SSO"
    return "LEO"


def _safe_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_epoch(epoch_str: str | None) -> datetime | None:
    if not epoch_str:
        return None
    try:
        return datetime.fromisoformat(epoch_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def ingest_satellite_catalog(client: SpaceTrackClient):
    """Pull the GP (General Perturbations) catalog — one record per active satellite
    with the latest TLE and orbital elements."""
    print("Fetching satellite catalog (active, on-orbit)...")
    records = client.query(
        "gp",
        DECAY_DATE="null-val",  # only active (not decayed)
        epoch=">now-10",  # only propagable ephemerides (per Space-Track guidelines)
        orderby="NORAD_CAT_ID asc",
    )
    print(f"  Got {len(records)} records from Space-Track.")

    BATCH_SIZE = 500

    db = SessionLocal()
    created = 0
    updated = 0

    # Cache operators to avoid repeated queries
    operator_cache = {}
    operator_by_id = {}
    for op in db.execute(select(Operator)).scalars().all():
        operator_cache[op.name] = op
        operator_by_id[op.id] = op

    # Cache existing satellites by norad_id
    satellite_cache = {}
    for sat in db.execute(select(Satellite)).scalars().all():
        if sat.norad_id:
            satellite_cache[sat.norad_id] = sat

    # Cache existing orbits by satellite_id
    orbit_cache = {}
    for orb in db.execute(select(Orbit)).scalars().all():
        orbit_cache[orb.satellite_id] = orb

    try:
        for i, rec in enumerate(records):
            norad_id = _safe_int(rec.get("NORAD_CAT_ID"))
            if norad_id is None:
                continue

            # Upsert operator (GP class uses COUNTRY_CODE, not OWNER)
            owner_name = rec.get("COUNTRY_CODE") or "Unknown"
            operator = operator_cache.get(owner_name)
            if not operator:
                operator = Operator(
                    name=owner_name,
                    country=rec.get("COUNTRY_CODE"),
                )
                db.add(operator)
                db.flush()
                operator_cache[owner_name] = operator

            # Upsert satellite
            satellite = satellite_cache.get(norad_id)

            object_type = rec.get("OBJECT_TYPE")
            if not object_type:
                name = rec.get("OBJECT_NAME", "")
                if " DEB" in name:
                    object_type = "DEBRIS"
                elif " R/B" in name:
                    object_type = "ROCKET BODY"
                else:
                    object_type = "UNKNOWN"

            if satellite:
                satellite.name = rec.get("OBJECT_NAME", satellite.name)
                satellite.intl_designator = rec.get("INTLDES", satellite.intl_designator)
                # Preserve real operator assignments (from UCS or consolidation)
                current_op = operator_by_id.get(satellite.operator_id)
                if not current_op or current_op.operator_type is None:
                    satellite.operator_id = operator.id
                satellite.object_type = object_type
                satellite.status = "active"
                satellite.updated_at = datetime.now(tz=None)
                updated += 1
            else:
                satellite = Satellite(
                    name=rec.get("OBJECT_NAME", "UNKNOWN"),
                    norad_id=norad_id,
                    intl_designator=rec.get("INTLDES"),
                    operator_id=operator.id,
                    object_type=object_type,
                    status="active",
                    source="space_track",
                    source_id=str(norad_id),
                )
                db.add(satellite)
                db.flush()
                satellite_cache[norad_id] = satellite
                created += 1

            # Upsert orbit
            period = _safe_float(rec.get("PERIOD"))
            inclination = _safe_float(rec.get("INCLINATION"))

            orbit = orbit_cache.get(satellite.id)

            orbit_data = dict(
                apogee_km=_safe_float(rec.get("APOAPSIS")),
                perigee_km=_safe_float(rec.get("PERIAPSIS")),
                inclination_deg=inclination,
                period_min=period,
                orbit_class=classify_orbit(period, inclination),
                epoch=_parse_epoch(rec.get("EPOCH")),
                tle_line1=rec.get("TLE_LINE1"),
                tle_line2=rec.get("TLE_LINE2"),
                updated_at=datetime.now(tz=None),
            )

            if orbit:
                for key, value in orbit_data.items():
                    setattr(orbit, key, value)
            else:
                orbit = Orbit(satellite_id=satellite.id, **orbit_data)
                db.add(orbit)
                orbit_cache[satellite.id] = orbit

            # Batch commit
            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                print(f"    ...processed {i + 1} / {len(records)}")

        db.commit()
        print(f"  Satellites — created: {created}, updated: {updated}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    client = SpaceTrackClient()
    try:
        ingest_satellite_catalog(client)
        print("Space-Track ingestion complete.")
    finally:
        client.close()


if __name__ == "__main__":
    run()
