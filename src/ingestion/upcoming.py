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
                op = Operator(name=op_name)
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


def run():
    load_upcoming_launches()
    print("Upcoming launch ingestion complete.")


if __name__ == "__main__":
    run()
