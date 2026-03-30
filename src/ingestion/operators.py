"""Operator consolidation.

Reassigns satellites from country-code placeholder operators to real
company operators based on constellation membership, merges duplicate
operator name variants, and cleans up orphaned operator records.

Safe to re-run — uses upsert-style logic throughout.
"""

from datetime import datetime

from sqlalchemy import delete, func, select, update

from src.db.connection import SessionLocal
from src.db.models import Launch, Operator, Satellite

BATCH_SIZE = 500

# Maps constellation names to their canonical operator.
# (operator_name, operator_type, country)
CONSTELLATION_OPERATORS = {
    "Starlink": ("SpaceX", "Commercial", "US"),
    "OneWeb": ("OneWeb", "Commercial", "UK"),
    "Kuiper": ("Amazon Kuiper", "Commercial", "US"),
    "Qianfan (G60)": ("Shanghai Spacecom Satellite Technology (SSST)", "Commercial", "CN"),
    "Guowang": ("China SatNet", "Commercial", "CN"),
    "GPS": ("US Space Force", "Military", "US"),
    "GLONASS": ("Russian Aerospace Forces (VKS)", "Military", "RU"),
    "Galileo": ("European Space Agency (ESA)", "Government", "EU"),
    "BeiDou": ("China National Space Administration (CNSA)", "Government", "CN"),
    "Iridium": ("Iridium Communications", "Commercial", "US"),
    "Globalstar": ("Globalstar", "Commercial", "US"),
    "Orbcomm": ("ORBCOMM", "Commercial", "US"),
    "O3b": ("SES", "Commercial", "LU"),
    "Gonets": ("Gonets Satellite System", "Government", "RU"),
    "Inmarsat": ("Inmarsat", "Commercial", "UK"),
    "Intelsat": ("Intelsat", "Commercial", "US"),
    "SES": ("SES", "Commercial", "LU"),
    "Telesat": ("Telesat", "Commercial", "CA"),
    "Planet (Flock)": ("Planet Labs", "Commercial", "US"),
    "Planet (SkySat)": ("Planet Labs", "Commercial", "US"),
    "Planet (Pelican)": ("Planet Labs", "Commercial", "US"),
    "Spire": ("Spire Global", "Commercial", "US"),
    "Hawk (HawkEye 360)": ("HawkEye 360", "Commercial", "US"),
    "ICEYE": ("ICEYE", "Commercial", "FI"),
    "Capella": ("Capella Space", "Commercial", "US"),
    "Umbra": ("Umbra Lab", "Commercial", "US"),
    "Jilin-01": ("Chang Guang Satellite Technology", "Commercial", "CN"),
    "Gaofen": ("China National Space Administration (CNSA)", "Government", "CN"),
    "Yaogan": ("People's Liberation Army (PLA)", "Military", "CN"),
    "Swarm": ("Swarm Technologies (SpaceX)", "Commercial", "US"),
    "Astrocast": ("Astrocast", "Commercial", "CH"),
    "Kineis": ("Kinéis", "Commercial", "FR"),
    "Connecta IoT": ("Sateliot", "Commercial", "ES"),
    "Tianqi": ("Guodian Gaoke", "Commercial", "CN"),
    "Lynk": ("Lynk Global", "Commercial", "US"),
    "Tianmu": ("Aerospace Tianmu", "Commercial", "CN"),
    "CentiSpace": ("Future Navigation", "Commercial", "CN"),
}

# Merge rules: map variant names to a canonical name.
# All satellites under variant names get reassigned to the canonical operator.
# (canonical_name, [variant_names])
MERGE_RULES = [
    ("SpaceX", ["Spacex"]),
    ("SES", [
        "SES S.A.",
        "SES S.A. -- total capacity leased to subsidiary of EchoStar Corp. ",
        "SES S.A./EchoStar Satellite Services, LLC",
    ]),
    ("Intelsat", [
        "Intelsat S.A.",
        "Intelsat S.A. ",
        "Intelsat S.A./Sky Perfect JSAT Corp.",
        "PanAmSat (Intelsat S.A.)",
        "PanAmSat (Intelsat S.A.)/DirecTV, Inc.",
        "PanAmSat (Intelsat S.A.)/Sky Perfect JSAT Corp.",
    ]),
    ("EUTELSAT", [
        "EUTELSAT S.A.",
        "EUTELSAT S.A./Es'hailSat",
        "EUTELSAT S.A./Nilesat",
        "EUTELSAT Americas",
    ]),
    ("O3b Networks Ltd.", ["O3B"]),
    ("Airbus Defence and Space", [
        "Airbus",
        "Airbus Defense and Space",
    ]),
    ("European Space Agency (ESA)", [
        "European Space Agency (ESA) (and 250 international scientific investigators)",
        "European Space Agency (ESA)/NASA",
        "European Space Operations Centre (ESOC)",
        "European Space Operations Centre (ESOC)/NASA/Russia",
    ]),
    ("Telesat", [
        "Telesat Canada Ltd. (BCE, Inc.)",
        "Telesat Canada Ltd. (BCE, Inc.)/APT Satellite Holdings Ltd.",
    ]),
    ("EchoStar", [
        "Echostar Corporation (entire payload leased from Telesat Canada Ltd.)",
        "Echostar Satellite Services, LLC",
        "Echostar Satellite Services, LLC/Intelsat ",
    ]),
    ("Hellas-Sat", [
        "Hellas-Sat Consortium Ltd.",
        "Hellas-Sat Consortium Ltd./INMARSAT",
    ]),
    ("Inmarsat", [
        "INMARSAT, Ltd.",
        "INMARSAT, Ltd./European Space Agency (ESA)",
    ]),
    ("Korea Aerospace Research Institute (KARI)", [
        "Korea Advanced Institute of Science and Technology (KAIST)",
        "Korea Advanced Institute of Science and Technology.",
    ]),
    ("German Aerospace Center (DLR)", [
        "German Aerospace Center (DLR-IKN)/TESAT Spacecom",
        "German Aerospace Center (DLR)/Astrium",
        "German Aerospace Center (DLR)/Infoterra",
    ]),
    ("Sky Perfect JSAT Corporation", [
        "Sky Perfect JSAT Corporation/DSN Corp.",
        "Sky Perfect JSAT Corporation/Kacific",
    ]),
]


def _get_or_create_operator(
    db, cache: dict, name: str, operator_type: str | None = None,
    country: str | None = None,
) -> "Operator":
    """Get an existing operator by name or create a new one."""
    op = cache.get(name)
    if op:
        # Update type/country if previously missing
        if operator_type and not op.operator_type:
            op.operator_type = operator_type
        if country and not op.country:
            op.country = country
        return op

    op = Operator(name=name, operator_type=operator_type, country=country)
    db.add(op)
    db.flush()
    cache[name] = op
    return op


def reassign_by_constellation(db, operator_cache: dict) -> int:
    """Reassign satellites from country-code operators to real operators
    based on their constellation membership."""
    reassigned = 0

    for constellation, (op_name, op_type, country) in CONSTELLATION_OPERATORS.items():
        operator = _get_or_create_operator(
            db, operator_cache, op_name, op_type, country
        )

        # Find satellites in this constellation still under country-code operators
        sats = db.execute(
            select(Satellite.id)
            .join(Operator, Satellite.operator_id == Operator.id)
            .where(
                Satellite.constellation == constellation,
                Operator.operator_type.is_(None),  # country-code operator
            )
        ).scalars().all()

        if not sats:
            continue

        sat_ids = list(sats)
        for i in range(0, len(sat_ids), BATCH_SIZE):
            batch = sat_ids[i:i + BATCH_SIZE]
            db.execute(
                update(Satellite)
                .where(Satellite.id.in_(batch))
                .values(operator_id=operator.id, updated_at=datetime.now(tz=None))
            )
            db.commit()

        print(f"  {constellation} -> {op_name}: {len(sat_ids)} satellites")
        reassigned += len(sat_ids)

    return reassigned


def merge_duplicates(db, operator_cache: dict) -> int:
    """Merge variant operator names into canonical names."""
    merged = 0

    for canonical_name, variants in MERGE_RULES:
        canonical = operator_cache.get(canonical_name)
        if not canonical:
            # Create canonical if it doesn't exist yet
            canonical = _get_or_create_operator(db, operator_cache, canonical_name)

        for variant_name in variants:
            variant = operator_cache.get(variant_name)
            if not variant:
                continue

            # Reassign satellites
            sat_count = db.execute(
                select(func.count(Satellite.id))
                .where(Satellite.operator_id == variant.id)
            ).scalar()

            if sat_count > 0:
                db.execute(
                    update(Satellite)
                    .where(Satellite.operator_id == variant.id)
                    .values(operator_id=canonical.id, updated_at=datetime.now(tz=None))
                )

            # Reassign launches
            launch_count = db.execute(
                select(func.count(Launch.id))
                .where(Launch.operator_id == variant.id)
            ).scalar()

            if launch_count > 0:
                db.execute(
                    update(Launch)
                    .where(Launch.operator_id == variant.id)
                    .values(operator_id=canonical.id, updated_at=datetime.now(tz=None))
                )

            db.commit()

            if sat_count > 0 or launch_count > 0:
                print(f"  {variant_name} -> {canonical_name}: "
                      f"{sat_count} sats, {launch_count} launches")
                merged += sat_count + launch_count

    return merged


def cleanup_orphans(db) -> int:
    """Delete operators with no satellites and no launches."""
    orphan_ids = db.execute(
        select(Operator.id)
        .outerjoin(Satellite, Satellite.operator_id == Operator.id)
        .outerjoin(Launch, Launch.operator_id == Operator.id)
        .group_by(Operator.id)
        .having(func.count(Satellite.id) == 0, func.count(Launch.id) == 0)
    ).scalars().all()

    if orphan_ids:
        db.execute(delete(Operator).where(Operator.id.in_(list(orphan_ids))))
        db.commit()

    return len(orphan_ids)


def consolidate():
    """Run full operator consolidation pipeline."""
    db = SessionLocal()

    # Build operator cache
    operator_cache = {}
    for op in db.execute(select(Operator)).scalars().all():
        operator_cache[op.name] = op

    try:
        print("Step 1: Reassigning satellites by constellation...")
        reassigned = reassign_by_constellation(db, operator_cache)
        print(f"  Total reassigned: {reassigned}")

        print("\nStep 2: Merging duplicate operator names...")
        merged = merge_duplicates(db, operator_cache)
        print(f"  Total merged: {merged}")

        print("\nStep 3: Cleaning up orphaned operators...")
        cleaned = cleanup_orphans(db)
        print(f"  Removed {cleaned} orphaned operators")

        # Final stats
        total_ops = db.execute(select(func.count(Operator.id))).scalar()
        with_type = db.execute(
            select(func.count(Operator.id)).where(Operator.operator_type.isnot(None))
        ).scalar()
        print(f"\nFinal: {total_ops} operators ({with_type} with type, "
              f"{total_ops - with_type} country codes)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run():
    consolidate()
    print("Operator consolidation complete.")


if __name__ == "__main__":
    run()
