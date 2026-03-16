"""Space-Track SATCAT ingestion.

Enriches satellite and operator records with authoritative catalog data.
Per Space-Track guidelines: query SATCAT at most once per day after 1700 UTC.
"""

from datetime import datetime

from sqlalchemy import select

from src.db.connection import SessionLocal
from src.db.models import Operator, Satellite
from src.ingestion.spacetrack import SpaceTrackClient

BATCH_SIZE = 200


def ingest_satcat(client: SpaceTrackClient):
    """Pull the full SATCAT for active objects and enrich operator data."""
    print("Fetching SATCAT (active payloads)...")
    records = client.query(
        "satcat",
        CURRENT="Y",
        DECAY="null-val",  # on-orbit only
        orderby="NORAD_CAT_ID asc",
    )
    print(f"  Got {len(records)} SATCAT records.")

    db = SessionLocal()
    enriched = 0
    skipped = 0
    operators_created = 0

    # Cache satellites by norad_id
    satellite_cache = {}
    for sat in db.execute(select(Satellite)).scalars().all():
        if sat.norad_id:
            satellite_cache[sat.norad_id] = sat

    # Cache operators by id and by name
    operator_by_id = {}
    operator_by_name = {}
    for op in db.execute(select(Operator)).scalars().all():
        operator_by_id[op.id] = op
        operator_by_name[op.name] = op

    try:
        for i, rec in enumerate(records):
            norad_id = rec.get("NORAD_CAT_ID")
            if norad_id is None:
                continue
            try:
                norad_id = int(norad_id)
            except (TypeError, ValueError):
                continue

            satellite = satellite_cache.get(norad_id)
            if not satellite:
                skipped += 1
                continue

            # Check if this satellite already has a real operator (from UCS)
            has_real_operator = False
            if satellite.operator_id:
                current_operator = operator_by_id.get(satellite.operator_id)
                has_real_operator = (
                    current_operator is not None
                    and current_operator.operator_type is not None
                )

            if not has_real_operator:
                country = rec.get("COUNTRY")
                operator_name = country or "Unknown"

                operator = operator_by_name.get(operator_name)
                if not operator:
                    operator = Operator(name=operator_name, country=country)
                    db.add(operator)
                    db.flush()
                    operator_by_name[operator_name] = operator
                    operator_by_id[operator.id] = operator
                    operators_created += 1
                satellite.operator_id = operator.id

            # Enrich satellite metadata from SATCAT regardless
            sat_name = rec.get("SATNAME")
            if sat_name:
                satellite.name = sat_name

            intldes = rec.get("OBJECT_ID")
            if intldes:
                satellite.intl_designator = intldes

            object_type = rec.get("OBJECT_TYPE")
            if object_type:
                satellite.object_type = object_type

            satellite.updated_at = datetime.now(tz=None)
            enriched += 1

            if (i + 1) % BATCH_SIZE == 0:
                db.commit()
                print(f"    ...processed {i + 1} / {len(records)}")

        db.commit()
        print(f"  Enriched: {enriched}, Skipped (not in DB): {skipped}")
        print(f"  New operators created: {operators_created}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    client = SpaceTrackClient()
    try:
        ingest_satcat(client)
        print("SATCAT ingestion complete.")
    finally:
        client.close()


if __name__ == "__main__":
    run()
