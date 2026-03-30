"""Purpose/mission enrichment.

Maps satellites to mission classifications based on their constellation.
Since constellation tagging already covers ~12,500 payloads, keying off
constellation is more reliable than re-parsing names.

Runs against existing satellite records — safe to re-run without
creating duplicates. Does not overwrite existing purpose values (from UCS).
"""

from datetime import datetime

from sqlalchemy import select, update

from src.db.connection import SessionLocal
from src.db.models import Satellite

BATCH_SIZE = 500

# Constellation-to-purpose mapping.
# Uses the same purpose categories established by UCS data where possible.
CONSTELLATION_PURPOSE = {
    # --- Communications ---
    "Starlink": "Communications",
    "OneWeb": "Communications",
    "Kuiper": "Communications",
    "Qianfan (G60)": "Communications",
    "Guowang": "Communications",
    "Iridium": "Communications",
    "Globalstar": "Communications",
    "Orbcomm": "Communications",
    "O3b": "Communications",
    "Gonets": "Communications",
    "Inmarsat": "Communications",
    "Intelsat": "Communications",
    "SES": "Communications",
    "Telesat": "Communications",

    # --- Navigation ---
    "GPS": "Navigation/Global Positioning",
    "GLONASS": "Navigation/Global Positioning",
    "Galileo": "Navigation/Global Positioning",
    "BeiDou": "Navigation/Global Positioning",

    # --- Earth Observation ---
    "Planet (Flock)": "Earth Observation",
    "Planet (SkySat)": "Earth Observation",
    "Planet (Pelican)": "Earth Observation",
    "Spire": "Earth Observation",
    "Hawk (HawkEye 360)": "Earth Observation",
    "ICEYE": "Earth Observation",
    "Capella": "Earth Observation",
    "Umbra": "Earth Observation",
    "Jilin-01": "Earth Observation",
    "Gaofen": "Earth Observation",

    # --- Surveillance/Reconnaissance ---
    "Yaogan": "Surveillance",
    "USA (classified)": "Surveillance",

    # --- IoT / M2M ---
    "Swarm": "Communications/IoT",
    "Astrocast": "Communications/IoT",
    "Kineis": "Communications/IoT",
    "Connecta IoT": "Communications/IoT",
    "Tianqi": "Communications/IoT",
    "Lynk": "Communications/IoT",

    # --- Weather / Meteorological ---
    "Tianmu": "Meteorological",
    "CentiSpace": "Navigation/Global Positioning",
}


def enrich_purposes():
    """Set the purpose field on satellites based on their constellation."""
    db = SessionLocal()
    updated = 0
    already_set = 0
    no_match = 0

    rows = db.execute(
        select(Satellite.id, Satellite.constellation, Satellite.purpose)
        .where(Satellite.object_type == "PAYLOAD")
        .where(Satellite.constellation.isnot(None))
    ).all()
    print(f"Checking {len(rows)} constellation-tagged payloads for purpose mapping...")

    pending_updates = []
    try:
        for row in rows:
            sat_id, constellation, purpose = row

            if purpose:
                already_set += 1
                continue

            mapped_purpose = CONSTELLATION_PURPOSE.get(constellation)
            if mapped_purpose:
                pending_updates.append({"sat_id": sat_id, "purpose": mapped_purpose})
                updated += 1
            else:
                no_match += 1

            if len(pending_updates) >= BATCH_SIZE:
                _flush_updates(db, pending_updates)
                pending_updates.clear()
                print(f"    ...updated {updated} so far")

        if pending_updates:
            _flush_updates(db, pending_updates)

        print(f"  Updated: {updated}, Already set: {already_set}, "
              f"No mapping: {no_match}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _flush_updates(db, updates: list[dict]):
    """Batch UPDATE purpose values."""
    now = datetime.now(tz=None)
    for item in updates:
        db.execute(
            update(Satellite)
            .where(Satellite.id == item["sat_id"])
            .values(purpose=item["purpose"], updated_at=now)
        )
    db.commit()


def run():
    enrich_purposes()
    print("Purpose enrichment complete.")


if __name__ == "__main__":
    run()
