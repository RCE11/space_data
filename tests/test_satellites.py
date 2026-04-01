"""Integration tests for satellite API endpoints."""


class TestByOperator:
    def test_partial_match(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX")
        assert resp.status_code == 200
        data = resp.json()
        # 2 Starlink payloads (debris excluded by default PAYLOAD filter)
        assert data["total"] == 2

    def test_case_insensitive(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=spacex")
        data = resp.json()
        assert data["total"] == 2

    def test_default_filters_debris(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX")
        data = resp.json()
        names = [r["name"] for r in data["results"]]
        assert "STARLINK-1000 DEB" not in names

    def test_object_type_debris(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX&object_type=DEBRIS")
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["name"] == "STARLINK-1000 DEB"

    def test_constellation_filter(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX&constellation=Starlink")
        data = resp.json()
        assert data["total"] == 2

    def test_includes_orbit(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX")
        data = resp.json()
        orbit = data["results"][0]["orbit"]
        assert orbit is not None
        assert orbit["orbit_class"] == "LEO"
        assert orbit["apogee_km"] == 550.0

    def test_includes_operator(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX")
        data = resp.json()
        op = data["results"][0]["operator"]
        assert op["name"] == "SpaceX"
        assert op["country"] == "US"

    def test_no_match(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=Boeing")
        data = resp.json()
        assert data["total"] == 0

    def test_pagination(self, client, seed_data):
        resp = client.get("/satellites/by-operator?operator=SpaceX&limit=1")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["results"]) == 1


class TestByOrbit:
    def test_orbit_class(self, client, seed_data):
        resp = client.get("/satellites/by-orbit?orbit_class=LEO")
        assert resp.status_code == 200
        data = resp.json()
        # 2 Starlink + 1 Sentinel (all LEO payloads)
        assert data["total"] == 3

    def test_case_insensitive(self, client, seed_data):
        resp = client.get("/satellites/by-orbit?orbit_class=leo")
        data = resp.json()
        assert data["total"] == 3

    def test_operator_cross_filter(self, client, seed_data):
        resp = client.get("/satellites/by-orbit?orbit_class=LEO&operator=ESA")
        data = resp.json()
        assert data["total"] == 1
        assert data["results"][0]["name"] == "SENTINEL-6A"

    def test_no_results(self, client, seed_data):
        resp = client.get("/satellites/by-orbit?orbit_class=GEO")
        data = resp.json()
        assert data["total"] == 0


class TestByConstellation:
    def test_constellation_match(self, client, seed_data):
        resp = client.get("/satellites/by-constellation?constellation=Starlink")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_partial_match(self, client, seed_data):
        resp = client.get("/satellites/by-constellation?constellation=Star")
        data = resp.json()
        assert data["total"] == 2

    def test_operator_cross_filter(self, client, seed_data):
        resp = client.get("/satellites/by-constellation?constellation=Starlink&operator=SpaceX")
        data = resp.json()
        assert data["total"] == 2

    def test_no_match(self, client, seed_data):
        resp = client.get("/satellites/by-constellation?constellation=OneWeb")
        data = resp.json()
        assert data["total"] == 0
