"""Historical launch derivation from Space-Track SATCAT.

Derives launch events by grouping satellites by international designator
prefix (e.g., all 2024-001* objects came from the same launch). Pulls
launch date and site from SATCAT, creates launch records, and links
satellites to their launches.
"""

import re
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select

from src.db.connection import SessionLocal
from src.db.models import Launch, Satellite
from src.ingestion.spacetrack import SpaceTrackClient

BATCH_SIZE = 500

# Space-Track SATCAT site codes → human-readable names.
SITE_NAMES = {
    "PKMTR": "Plesetsk Cosmodrome, Russia",
    "TTMTR": "Tyuratam/Baikonur Cosmodrome, Kazakhstan",
    "AFETR": "Cape Canaveral, Florida",
    "AFWTR": "Vandenberg SFB, California",
    "FRGUI": "Guiana Space Centre, French Guiana",
    "JSC": "Jiuquan Satellite Launch Center, China",
    "XSC": "Xichang Satellite Launch Center, China",
    "TSC": "Tanegashima Space Center, Japan",
    "TNSTA": "Baikonur Cosmodrome, Kazakhstan",
    "SRI": "Satish Dhawan Space Centre, India",
    "KYMTR": "Kapustin Yar, Russia",
    "RLLC": "Rocket Lab LC-1, Mahia Peninsula, New Zealand",
    "WSC": "Wenchang Space Launch Site, China",
    "WLPIS": "Wallops Flight Facility, Virginia",
    "SEAL": "Sea Launch Platform, Pacific Ocean",
    "OREN": "Dombarovsky/Yasny Launch Base, Russia",
    "KODAK": "Pacific Spaceport Complex, Kodiak Island, Alaska",
    "SNMLP": "Palmachim Airbase, Israel",
    "SMTS": "Semnan Spaceport, Iran",
    "KWAJ": "Kwajalein Atoll, Marshall Islands",
    "YUN": "Naro Space Center, South Korea",
    "KSCUT": "Uchinoura Space Center, Japan",
    "DLS": "Jiuquan Satellite Launch Center, China",
    "SVOB": "Svobodny Cosmodrome, Russia",
    "HGSTR": "Hammaguir, Algeria",
    "WOMRA": "Woomera, Australia",
    "TAISC": "Taiyuan Satellite Launch Center, China",
}


def _designator_prefix(intl_des: str) -> str | None:
    """Extract launch identifier from international designator.
    '2024-001A' -> '2024-001', '1998-067QM' -> '1998-067'
    """
    match = re.match(r"(\d{4}-\d{3})", intl_des)
    return match.group(1) if match else None


def _parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def fetch_launch_data(client: SpaceTrackClient) -> dict[str, dict]:
    """Fetch SATCAT and group by launch prefix to get date, site, and vehicle.
    Returns a dict keyed by designator prefix."""
    print("Fetching SATCAT for launch derivation...")
    records = client.query(
        "satcat",
        LAUNCH_PIECE="A",  # primary payload only — one per launch
        orderby="LAUNCH desc",
        predicates="OBJECT_ID,SATNAME,LAUNCH,SITE,COUNTRY",
    )
    print(f"  Got {len(records)} primary payload records.")

    launches = {}
    for rec in records:
        object_id = rec.get("OBJECT_ID")
        if not object_id:
            continue
        prefix = _designator_prefix(object_id)
        if not prefix:
            continue

        raw_site = rec.get("SITE")
        launches[prefix] = {
            "launch_date": _parse_date(rec.get("LAUNCH")),
            "launch_site": SITE_NAMES.get(raw_site, raw_site),
            "payload_name": rec.get("SATNAME"),
            "country": rec.get("COUNTRY"),
        }

    return launches


def ingest_launches(client: SpaceTrackClient):
    launch_data = fetch_launch_data(client)
    print(f"  Derived {len(launch_data)} launch events.")

    db = SessionLocal()
    created = 0
    linked = 0

    # Cache existing launches by source_id
    launch_cache = {}
    for launch in db.execute(select(Launch)).scalars().all():
        if launch.source_id:
            launch_cache[launch.source_id] = launch

    # Cache satellites grouped by designator prefix
    sat_by_prefix = defaultdict(list)
    for sat in db.execute(select(Satellite)).scalars().all():
        if sat.intl_designator:
            prefix = _designator_prefix(sat.intl_designator)
            if prefix:
                sat_by_prefix[prefix].append(sat)

    try:
        for i, (prefix, data) in enumerate(launch_data.items()):
            launch = launch_cache.get(prefix)

            if not launch:
                launch = Launch(
                    launch_date=data["launch_date"],
                    launch_site=data["launch_site"],
                    payload_description=data["payload_name"],
                    status="launched",
                    source="space_track",
                    source_id=prefix,
                )
                db.add(launch)
                db.flush()
                launch_cache[prefix] = launch
                created += 1

            # Link all satellites with this designator prefix
            for sat in sat_by_prefix.get(prefix, []):
                if sat.launch_id != launch.id:
                    sat.launch_id = launch.id
                    linked += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                print(f"    ...processed {i + 1} / {len(launch_data)}")

        db.commit()
        print(f"  Launches created: {created}")
        print(f"  Satellites linked to launches: {linked}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    client = SpaceTrackClient()
    try:
        ingest_launches(client)
        print("Launch derivation complete.")
    finally:
        client.close()


if __name__ == "__main__":
    run()
