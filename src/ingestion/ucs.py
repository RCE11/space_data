"""UCS Satellite Database ingestion.

Enriches existing satellite records with operator names, purpose,
and other metadata from the Union of Concerned Scientists database.
Source: https://www.ucs.org/resources/satellite-database

The UCS database is an Excel file that must be downloaded manually
and placed at data/ucs_satellites.xlsx.
"""

from datetime import datetime
from pathlib import Path

import openpyxl
from sqlalchemy import select

from src.db.connection import SessionLocal
from src.db.models import Operator, Satellite

DATA_PATH = Path(__file__).parent.parent.parent / "data" / "ucs_satellites.xlsx"

BATCH_SIZE = 200

# Column indices in the UCS spreadsheet
COL_NAME = 0
COL_OPERATOR = 4
COL_USERS = 5
COL_PURPOSE = 6
COL_DETAILED_PURPOSE = 7
COL_ORBIT_CLASS = 8
COL_COSPAR = 25
COL_NORAD = 26


def parse_ucs_rows(path: Path) -> list[dict]:
    """Read the UCS Excel file and return a list of record dicts."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Skip header row
    records = []
    for row in rows[1:]:
        norad = row[COL_NORAD]
        if norad is None:
            continue
        try:
            norad_id = int(norad)
        except (TypeError, ValueError):
            continue

        records.append({
            "norad_id": norad_id,
            "name": row[COL_NAME],
            "operator_name": row[COL_OPERATOR],
            "users": row[COL_USERS],
            "purpose": row[COL_PURPOSE],
            "detailed_purpose": row[COL_DETAILED_PURPOSE],
            "orbit_class": row[COL_ORBIT_CLASS],
            "cospar": row[COL_COSPAR],
        })

    return records


def ingest(path: Path = DATA_PATH):
    print(f"Reading UCS database from {path}...")
    records = parse_ucs_rows(path)
    print(f"  Parsed {len(records)} records.")

    db = SessionLocal()
    matched = 0
    unmatched = 0
    operators_created = 0

    # Cache satellites by norad_id
    satellite_cache = {}
    for sat in db.execute(select(Satellite)).scalars().all():
        if sat.norad_id:
            satellite_cache[sat.norad_id] = sat

    # Cache operators by name
    operator_cache = {}
    for op in db.execute(select(Operator)).scalars().all():
        operator_cache[op.name] = op

    try:
        for i, rec in enumerate(records):
            satellite = satellite_cache.get(rec["norad_id"])

            if not satellite:
                unmatched += 1
                continue

            # Upsert operator with real name
            operator_name = rec["operator_name"]
            if operator_name:
                operator = operator_cache.get(operator_name)
                if not operator:
                    operator = Operator(
                        name=operator_name,
                        operator_type=rec["users"],  # Commercial, Government, etc.
                    )
                    db.add(operator)
                    db.flush()
                    operator_cache[operator_name] = operator
                    operators_created += 1
                satellite.operator_id = operator.id

            # Enrich satellite fields
            if rec["purpose"]:
                satellite.purpose = rec["purpose"]
            if rec["cospar"]:
                satellite.intl_designator = rec["cospar"]
            satellite.updated_at = datetime.now(tz=None)

            matched += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                print(f"    ...processed {i + 1} / {len(records)}")

        db.commit()
        print(f"  Matched: {matched}, Unmatched: {unmatched}")
        print(f"  New operators created: {operators_created}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    if not DATA_PATH.exists():
        print(f"UCS database not found at {DATA_PATH}")
        print("Download it from https://www.ucs.org/resources/satellite-database")
        return
    ingest()
    print("UCS ingestion complete.")


if __name__ == "__main__":
    run()
