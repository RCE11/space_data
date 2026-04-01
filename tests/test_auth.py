"""Tests for API key authentication."""

import hashlib

from src.db.models import ApiKey
from tests.conftest import TEST_API_KEY_HASH, TEST_API_KEY_PREFIX, TEST_API_KEY_RAW


class TestAuth:
    def _setup_key(self, db, active=True):
        key = ApiKey(
            key_hash=TEST_API_KEY_HASH,
            key_prefix=TEST_API_KEY_PREFIX,
            owner="test",
            tier="free",
            is_active=active,
        )
        db.add(key)
        db.flush()
        return key

    def test_valid_key(self, db):
        """Valid key should authenticate successfully."""
        from fastapi.testclient import TestClient

        from src.api.main import app
        from src.db.connection import get_db

        self._setup_key(db)

        app.dependency_overrides[get_db] = lambda: (yield db).__next__() or db
        # Use a simpler override
        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            resp = c.get(
                "/launches/upcoming",
                headers={"X-API-Key": TEST_API_KEY_RAW},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_invalid_key(self, db):
        """Invalid key should return 401."""
        from fastapi.testclient import TestClient

        from src.api.main import app
        from src.db.connection import get_db

        self._setup_key(db)

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            resp = c.get(
                "/launches/upcoming",
                headers={"X-API-Key": "wrong_key_000000000000000000000000"},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 401

    def test_inactive_key(self, db):
        """Inactive key should return 401."""
        from fastapi.testclient import TestClient

        from src.api.main import app
        from src.db.connection import get_db

        self._setup_key(db, active=False)

        def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as c:
            resp = c.get(
                "/launches/upcoming",
                headers={"X-API-Key": TEST_API_KEY_RAW},
            )
        app.dependency_overrides.clear()
        assert resp.status_code == 401

    def test_missing_header(self, db):
        """Missing X-API-Key header should return 401 or 403."""
        from fastapi.testclient import TestClient

        from src.api.main import app

        with TestClient(app) as c:
            resp = c.get("/launches/upcoming")
        assert resp.status_code in (401, 403)
