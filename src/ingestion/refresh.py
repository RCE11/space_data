"""Daily data refresh script.

Runs the ingestion pipeline in the correct order:
1. Space-Track GP — new objects, updated orbits
2. SATCAT — refreshed names, metadata
3. Launch derivation — new launch events

UCS is excluded from daily refresh — run manually when a new version is released.

Designed to be called by GitHub Actions or cron.
"""

from src.ingestion.launches import ingest_launches
from src.ingestion.satcat import ingest_satcat
from src.ingestion.spacetrack import SpaceTrackClient, ingest_satellite_catalog


def run():
    client = SpaceTrackClient()
    try:
        print("=== Daily Refresh ===")
        print()

        print("Step 1: Space-Track GP")
        ingest_satellite_catalog(client)
        print()

        print("Step 2: SATCAT Enrichment")
        ingest_satcat(client)
        print()

        print("Step 3: Launch Derivation")
        ingest_launches(client)
        print()

        print("=== Refresh complete ===")
    finally:
        client.close()


if __name__ == "__main__":
    run()
