"""Constellation enrichment.

Maps satellites to known constellations based on name patterns and
operator associations. Runs against existing satellite records in the
database — safe to re-run without creating duplicates.
"""

from datetime import datetime

from sqlalchemy import select, update

from src.db.connection import SessionLocal
from src.db.models import Satellite

BATCH_SIZE = 500

# Constellation mapping rules.
# Each entry: (constellation_name, name_patterns)
# - name_patterns: matched against satellite name (case-insensitive, contains)
#
# Order matters — first match wins. Put specific patterns before broad ones.
CONSTELLATION_RULES = [
    # --- Mega-constellations (broadband) ---
    ("Starlink", ["STARLINK"]),
    ("OneWeb", ["ONEWEB"]),
    ("Kuiper", ["KUIPER"]),
    ("Qianfan (G60)", ["QIANFAN"]),
    ("Guowang", ["GUOWANG"]),

    # --- Navigation ---
    ("GPS", ["NAVSTAR", "GPS "]),
    ("GLONASS", ["GLONASS"]),
    ("Galileo", ["GALILEO"]),
    ("BeiDou", ["BEIDOU"]),

    # --- Communications (legacy/medium constellations) ---
    ("Iridium", ["IRIDIUM"]),
    ("Globalstar", ["GLOBALSTAR"]),
    ("Orbcomm", ["ORBCOMM"]),
    ("O3b", ["O3B"]),
    ("Gonets", ["GONETS"]),
    ("Inmarsat", ["INMARSAT"]),
    ("Intelsat", ["INTELSAT"]),
    ("SES", ["SES-", "ASTRA "]),
    ("Telesat", ["TELESAT"]),

    # --- Earth observation ---
    ("Planet (Flock)", ["FLOCK", "SUPERDOVE"]),
    ("Planet (SkySat)", ["SKYSAT"]),
    ("Planet (Pelican)", ["PELICAN"]),
    ("Spire", ["LEMUR", "SPIRE"]),
    ("Hawk (HawkEye 360)", ["HAWK"]),
    ("ICEYE", ["ICEYE"]),
    ("Capella", ["CAPELLA"]),
    ("Umbra", ["UMBRA-"]),
    ("Jilin-01", ["JILIN"]),
    ("Gaofen", ["GAOFEN"]),
    ("Yaogan", ["YAOGAN"]),

    # --- IoT / M2M ---
    ("Swarm", ["SPACEBEE", "SWARM"]),
    ("Astrocast", ["ASTROCAST"]),
    ("Kineis", ["KINEIS"]),
    ("Connecta IoT", ["CONNECTA"]),
    ("Tianqi", ["TIANQI"]),
    ("Lynk", ["LYNK"]),

    # --- Weather / Met ---
    ("Tianmu", ["TIANMU"]),
    ("CentiSpace", ["CENTISPACE"]),

    # --- Military/Gov reconnaissance (by name pattern) ---
    ("USA (classified)", ["USA "]),
]


def _match_constellation(name: str) -> str | None:
    """Return the constellation name if the satellite name matches a rule."""
    name_upper = name.upper()
    for constellation, name_patterns in CONSTELLATION_RULES:
        for pattern in name_patterns:
            if pattern in name_upper:
                return constellation
    return None


def enrich_constellations():
    """Set the constellation field on satellites that match known patterns."""
    db = SessionLocal()
    updated = 0
    already_set = 0

    # Lightweight query — only fetch the columns we need
    rows = db.execute(
        select(Satellite.id, Satellite.name, Satellite.constellation)
        .where(Satellite.object_type == "PAYLOAD")
    ).all()
    print(f"Checking {len(rows)} payloads for constellation matches...")

    pending_updates = []
    try:
        for row in rows:
            sat_id, name, constellation = row

            if constellation:
                already_set += 1
                continue

            match = _match_constellation(name)
            if match:
                pending_updates.append({"sat_id": sat_id, "constellation": match})
                updated += 1

            if len(pending_updates) >= BATCH_SIZE:
                _flush_updates(db, pending_updates)
                pending_updates.clear()
                print(f"    ...updated {updated} so far")

        if pending_updates:
            _flush_updates(db, pending_updates)

        print(f"  Updated: {updated}, Already set: {already_set}, "
              f"Unmatched: {len(rows) - updated - already_set}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _flush_updates(db, updates: list[dict]):
    """Batch UPDATE constellation values."""
    now = datetime.now(tz=None)
    for item in updates:
        db.execute(
            update(Satellite)
            .where(Satellite.id == item["sat_id"])
            .values(constellation=item["constellation"], updated_at=now)
        )
    db.commit()


def run():
    enrich_constellations()
    print("Constellation enrichment complete.")


if __name__ == "__main__":
    run()
