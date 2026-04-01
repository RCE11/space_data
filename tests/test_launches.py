"""Integration tests for launch API endpoints."""


class TestUpcomingLaunches:
    def test_returns_scheduled(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2  # upcoming + upcoming_no_date
        for launch in data["results"]:
            assert launch["status"] == "scheduled"

    def test_excludes_historical(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        data = resp.json()
        descriptions = [r["payload_description"] for r in data["results"]]
        assert "Starlink Group 6-42" not in descriptions

    def test_includes_null_date(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        data = resp.json()
        descriptions = [r["payload_description"] for r in data["results"]]
        assert "Earth observation mission" in descriptions

    def test_null_date_sorted_last(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        data = resp.json()
        # The null-date launch should come after the dated one
        assert data["results"][-1]["launch_date"] is None

    def test_includes_operator(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        data = resp.json()
        first = data["results"][0]
        assert first["operator"] is not None
        assert first["operator"]["name"] == "SpaceX"

    def test_includes_launch_window(self, client, seed_data):
        resp = client.get("/launches/upcoming")
        data = resp.json()
        windows = [r["launch_window"] for r in data["results"]]
        assert "Window opens at 1200 UTC" in windows

    def test_pagination(self, client, seed_data):
        resp = client.get("/launches/upcoming?limit=1&offset=0")
        data = resp.json()
        assert data["total"] == 2
        assert data["limit"] == 1
        assert len(data["results"]) == 1

    def test_empty_results(self, client, db):
        # No seed data — should return empty
        resp = client.get("/launches/upcoming")
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []


class TestLaunchHistory:
    def test_returns_launched(self, client, seed_data):
        resp = client.get("/launches/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["status"] == "launched"

    def test_excludes_scheduled(self, client, seed_data):
        resp = client.get("/launches/history")
        data = resp.json()
        descriptions = [r["payload_description"] for r in data["results"]]
        assert "Europa Clipper" not in descriptions

    def test_year_filter(self, client, seed_data):
        resp = client.get("/launches/history?year=2024")
        data = resp.json()
        assert data["total"] == 1

    def test_year_filter_no_results(self, client, seed_data):
        resp = client.get("/launches/history?year=2020")
        data = resp.json()
        assert data["total"] == 0

    def test_site_filter(self, client, seed_data):
        resp = client.get("/launches/history?site=canaveral")
        data = resp.json()
        assert data["total"] == 1

    def test_site_filter_no_match(self, client, seed_data):
        resp = client.get("/launches/history?site=vandenberg")
        data = resp.json()
        assert data["total"] == 0

    def test_pagination(self, client, seed_data):
        resp = client.get("/launches/history?limit=1&offset=0")
        data = resp.json()
        assert data["limit"] == 1
        assert len(data["results"]) <= 1
