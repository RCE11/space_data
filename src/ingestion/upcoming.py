"""Upcoming launch ingestion.

Loads curated upcoming launches from data/upcoming_launches.json into the
launches table. Safe to re-run — uses source + source_id uniqueness to
upsert without creating duplicates.
"""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from src.db.connection import SessionLocal
from src.db.models import Launch, Operator

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "upcoming_launches.json"

# Metadata for operators created by the upcoming launches loader.
# Keeps operator records useful even when they don't come from Space-Track.
OPERATOR_METADATA = {
    "NASA": ("Government", "US"),
    "United Launch Alliance": ("Commercial", "US"),
    "United States Space Force": ("Military", "US"),
    "US Space Force": ("Military", "US"),
    "National Reconnaissance Office": ("Military", "US"),
    "Space Development Agency": ("Military", "US"),
    "L3Harris": ("Commercial", "US"),
    "BlackSky": ("Commercial", "US"),
    "Blue Origin": ("Commercial", "US"),
    "Boeing": ("Commercial", "US"),
    "SpaceX": ("Commercial", "US"),
    "Amazon Kuiper": ("Commercial", "US"),
    "Northrop Grumman": ("Commercial", "US"),
    "Impulse Space": ("Commercial", "US"),
    "Sierra Space": ("Commercial", "US"),
    "Firefly Aerospace": ("Commercial", "US"),
    "Relativity Space": ("Commercial", "US"),
    "Astra Space": ("Commercial", "US"),
    "Rocket Lab": ("Commercial", "NZ"),
    "ISRO": ("Government", "IN"),
    "JAXA": ("Government", "JP"),
    "Japan Cabinet Office": ("Government", "JP"),
    "KASA": ("Government", "KR"),
    "Arianespace": ("Commercial", "FR"),
    "Italian Space Agency": ("Government", "IT"),
    "EU Agency for the Space Programme": ("Government", "EU"),
    "ESA": ("Government", "EU"),
    "EUMETSAT": ("Government", "EU"),
    "Roscosmos": ("Government", "RU"),
    "Russian Aerospace Forces (VKS)": ("Military", "RU"),
    "CASC": ("Government", "CN"),
    "Space Pioneer": ("Commercial", "CN"),
    "Landspace": ("Commercial", "CN"),
    "Galactic Energy": ("Commercial", "CN"),
    "Viasat": ("Commercial", "US"),
    "MDA": ("Commercial", "CA"),
    "Isar Aerospace": ("Commercial", "DE"),
    "PLD Space": ("Commercial", "ES"),
    "Rocket Factory Augsburg": ("Commercial", "DE"),
    "Latitude Space": ("Commercial", "FR"),
    "Gilmour Space Technologies": ("Commercial", "AU"),
    "Skyroot Aerospace": ("Commercial", "IN"),
    "HawkEye 360": ("Commercial", "US"),
    "SpaceLogistics": ("Commercial", "US"),
    "Astrobotic": ("Commercial", "US"),
    "Intuitive Machines": ("Commercial", "US"),
    "Eta Space": ("Commercial", "US"),
    "Globalstar": ("Commercial", "US"),
    "AST SpaceMobile": ("Commercial", "US"),
    "Astranis": ("Commercial", "US"),
    "General Atomics": ("Commercial", "US"),
    "EOS Data Analytics": ("Commercial", "US"),
    "Cloud Constellation": ("Commercial", "US"),
    "Katalyst Space Technologies": ("Commercial", "US"),
    "Synspective": ("Commercial", "JP"),
    "R-Space": ("Commercial", "JP"),
    "Lynk Global Inc.": ("Commercial", "US"),
    "NOAA": ("Government", "US"),
    "Stoke Space": ("Commercial", "US"),
}


def load_upcoming_launches():
    db = SessionLocal()

    with open(DATA_FILE) as f:
        launches = json.load(f)

    print(f"Loading {len(launches)} upcoming launches...")

    # Cache operators by name for lookup
    operators = {op.name: op for op in db.execute(select(Operator)).scalars().all()}

    created = 0
    updated = 0

    try:
        for entry in launches:
            # Find or create operator
            op_name = entry["operator"]
            if op_name not in operators:
                meta = OPERATOR_METADATA.get(op_name, (None, None))
                op = Operator(
                    name=op_name,
                    operator_type=meta[0],
                    country=meta[1],
                )
                db.add(op)
                db.flush()
                operators[op_name] = op
                print(f"  Created operator: {op_name}")

            operator = operators[op_name]

            # Parse launch date
            launch_date = None
            if entry.get("launch_date"):
                launch_date = datetime.fromisoformat(entry["launch_date"])

            # Check if launch already exists (by source + source_id)
            existing = db.execute(
                select(Launch).where(
                    Launch.source == "spaceflight_now",
                    Launch.source_id == entry["source_id"],
                )
            ).scalar_one_or_none()

            if existing:
                existing.launch_date = launch_date
                existing.vehicle = entry["vehicle"]
                existing.launch_site = entry["launch_site"]
                existing.operator_id = operator.id
                existing.payload_description = entry["payload_description"]
                existing.launch_window = entry.get("launch_window")
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                launch = Launch(
                    launch_date=launch_date,
                    vehicle=entry["vehicle"],
                    launch_site=entry["launch_site"],
                    operator_id=operator.id,
                    status="scheduled",
                    payload_description=entry["payload_description"],
                    launch_window=entry.get("launch_window"),
                    source="spaceflight_now",
                    source_id=entry["source_id"],
                )
                db.add(launch)
                created += 1

        db.commit()
        print(f"  Created: {created}, Updated: {updated}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def backfill_operator_metadata():
    """Fill in country and operator_type for operators missing metadata."""
    db = SessionLocal()
    updated = 0
    try:
        operators = db.execute(select(Operator)).scalars().all()
        for op in operators:
            meta = OPERATOR_METADATA.get(op.name)
            if not meta:
                continue
            changed = False
            if not op.operator_type and meta[0]:
                op.operator_type = meta[0]
                changed = True
            if not op.country and meta[1]:
                op.country = meta[1]
                changed = True
            if changed:
                updated += 1
        db.commit()
        print(f"  Backfilled metadata for {updated} operators.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    load_upcoming_launches()
    backfill_operator_metadata()
    print("Upcoming launch ingestion complete.")


if __name__ == "__main__":
    run()
