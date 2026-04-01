"""Test fixtures for the Space Data API.

Uses the local Docker Postgres (docker-compose.yml) as the test database.
Tables are created fresh per session and each test runs in a rolled-back transaction.
"""

import hashlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.db.models import (
    ApiKey,
    Base,
    Launch,
    Operator,
    Orbit,
    Satellite,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://spacedata:spacedata_dev@localhost:5432/spacedata_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)

# A known test API key
TEST_API_KEY_RAW = "test_key_0000000000000000000000000000000000000000000000000000"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY_RAW.encode()).hexdigest()
TEST_API_KEY_PREFIX = TEST_API_KEY_RAW[:12]


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Yield a DB session wrapped in a transaction that rolls back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """FastAPI test client with DB and auth overrides."""
    from src.api.main import app
    from src.api.rate_limit import rate_limit
    from src.db.connection import get_db

    def override_get_db():
        yield db

    def override_rate_limit():
        # Return a dummy ApiKey so routes work without real rate limiting
        return ApiKey(
            id=0,
            key_hash=TEST_API_KEY_HASH,
            key_prefix=TEST_API_KEY_PREFIX,
            owner="test",
            tier="team",
            is_active=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[rate_limit] = override_rate_limit

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def seed_data(db):
    """Seed the test database with representative data."""
    # Operators
    spacex = Operator(name="SpaceX", country="US", operator_type="Commercial")
    esa = Operator(name="ESA", country="EU", operator_type="Government")
    country_op = Operator(name="US", country="US")
    db.add_all([spacex, esa, country_op])
    db.flush()

    # Launches
    historical = Launch(
        launch_date="2024-03-15",
        launch_site="Cape Canaveral, Florida",
        vehicle="Falcon 9",
        operator_id=spacex.id,
        status="launched",
        payload_description="Starlink Group 6-42",
        source="space_track",
        source_id="2024-042",
    )
    upcoming = Launch(
        launch_date="2027-06-01",
        launch_site="Kennedy Space Center, Florida",
        vehicle="Falcon Heavy",
        operator_id=spacex.id,
        status="scheduled",
        payload_description="Europa Clipper",
        launch_window="Window opens at 1200 UTC",
        source="spaceflight_now",
        source_id="upcoming-001",
    )
    upcoming_no_date = Launch(
        launch_date=None,
        launch_site=None,
        vehicle="Ariane 6",
        operator_id=esa.id,
        status="scheduled",
        payload_description="Earth observation mission",
        launch_window="No earlier than Q4 2027",
        source="spaceflight_now",
        source_id="upcoming-002",
    )
    db.add_all([historical, upcoming, upcoming_no_date])
    db.flush()

    # Satellites
    sat1 = Satellite(
        name="STARLINK-1000",
        norad_id=44001,
        intl_designator="2024-042A",
        operator_id=spacex.id,
        launch_id=historical.id,
        object_type="PAYLOAD",
        purpose="Communications",
        constellation="Starlink",
        status="active",
        source="space_track",
        source_id="44001",
    )
    sat2 = Satellite(
        name="STARLINK-1001",
        norad_id=44002,
        intl_designator="2024-042B",
        operator_id=spacex.id,
        launch_id=historical.id,
        object_type="PAYLOAD",
        purpose="Communications",
        constellation="Starlink",
        status="active",
        source="space_track",
        source_id="44002",
    )
    sat3 = Satellite(
        name="SENTINEL-6A",
        norad_id=44003,
        operator_id=esa.id,
        object_type="PAYLOAD",
        purpose="Earth Observation",
        constellation=None,
        status="active",
        source="space_track",
        source_id="44003",
    )
    debris = Satellite(
        name="STARLINK-1000 DEB",
        norad_id=44004,
        operator_id=spacex.id,
        object_type="DEBRIS",
        status="active",
        source="space_track",
        source_id="44004",
    )
    db.add_all([sat1, sat2, sat3, debris])
    db.flush()

    # Orbits
    orbit1 = Orbit(
        satellite_id=sat1.id,
        orbit_class="LEO",
        apogee_km=550.0,
        perigee_km=540.0,
        inclination_deg=53.0,
        period_min=95.5,
    )
    orbit2 = Orbit(
        satellite_id=sat2.id,
        orbit_class="LEO",
        apogee_km=550.0,
        perigee_km=540.0,
        inclination_deg=53.0,
        period_min=95.5,
    )
    orbit3 = Orbit(
        satellite_id=sat3.id,
        orbit_class="LEO",
        apogee_km=1336.0,
        perigee_km=1322.0,
        inclination_deg=66.0,
        period_min=112.4,
    )
    db.add_all([orbit1, orbit2, orbit3])
    db.flush()

    return {
        "operators": {"spacex": spacex, "esa": esa, "country": country_op},
        "launches": {
            "historical": historical,
            "upcoming": upcoming,
            "upcoming_no_date": upcoming_no_date,
        },
        "satellites": {
            "starlink1": sat1,
            "starlink2": sat2,
            "sentinel": sat3,
            "debris": debris,
        },
        "orbits": {"orbit1": orbit1, "orbit2": orbit2, "orbit3": orbit3},
    }
