"""Unit tests for pure functions in the ingestion pipeline.

No database or external services needed.
"""

import pytest

from src.ingestion.spacetrack import (
    _parse_epoch,
    _safe_float,
    _safe_int,
    classify_orbit,
)
from src.ingestion.constellations import _match_constellation
from src.ingestion.launches import _designator_prefix, _parse_date


# ---------------------------------------------------------------------------
# classify_orbit
# ---------------------------------------------------------------------------
class TestClassifyOrbit:
    def test_leo(self):
        assert classify_orbit(95.0, 53.0) == "LEO"

    def test_sso(self):
        assert classify_orbit(95.0, 97.5) == "SSO"

    def test_sso_lower_bound(self):
        assert classify_orbit(95.0, 96.0) == "SSO"

    def test_sso_upper_bound(self):
        assert classify_orbit(95.0, 100.0) == "SSO"

    def test_not_sso_below_range(self):
        assert classify_orbit(95.0, 95.9) == "LEO"

    def test_meo(self):
        assert classify_orbit(400.0, 55.0) == "MEO"

    def test_geo(self):
        assert classify_orbit(1000.0, 0.1) == "GEO"

    def test_heo(self):
        assert classify_orbit(1500.0, 63.0) == "HEO"

    def test_none_period(self):
        assert classify_orbit(None, 53.0) == "UNKNOWN"

    def test_none_inclination_leo(self):
        assert classify_orbit(95.0, None) == "LEO"

    def test_boundary_leo_meo(self):
        assert classify_orbit(200.0, 53.0) == "LEO"
        assert classify_orbit(200.1, 53.0) == "MEO"

    def test_boundary_meo_geo(self):
        assert classify_orbit(600.0, 53.0) == "MEO"
        assert classify_orbit(600.1, 53.0) == "GEO"

    def test_boundary_geo_heo(self):
        assert classify_orbit(1400.0, 0.0) == "GEO"
        assert classify_orbit(1400.1, 63.0) == "HEO"


# ---------------------------------------------------------------------------
# _safe_float / _safe_int
# ---------------------------------------------------------------------------
class TestSafeConversions:
    def test_safe_float_valid(self):
        assert _safe_float("3.14") == 3.14

    def test_safe_float_int_string(self):
        assert _safe_float("42") == 42.0

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_garbage(self):
        assert _safe_float("abc") is None

    def test_safe_float_empty(self):
        assert _safe_float("") is None

    def test_safe_int_valid(self):
        assert _safe_int("42") == 42

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_garbage(self):
        assert _safe_int("abc") is None

    def test_safe_int_float_string(self):
        assert _safe_int("3.14") is None


# ---------------------------------------------------------------------------
# _parse_epoch
# ---------------------------------------------------------------------------
class TestParseEpoch:
    def test_iso_format(self):
        result = _parse_epoch("2024-03-15T12:30:00")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3

    def test_z_suffix(self):
        result = _parse_epoch("2024-03-15T12:30:00Z")
        assert result is not None

    def test_none(self):
        assert _parse_epoch(None) is None

    def test_empty(self):
        assert _parse_epoch("") is None

    def test_garbage(self):
        assert _parse_epoch("not-a-date") is None


# ---------------------------------------------------------------------------
# _match_constellation
# ---------------------------------------------------------------------------
class TestMatchConstellation:
    def test_starlink(self):
        assert _match_constellation("STARLINK-1234") == "Starlink"

    def test_oneweb(self):
        assert _match_constellation("ONEWEB-0621") == "OneWeb"

    def test_kuiper(self):
        assert _match_constellation("KUIPER-001") == "Kuiper"

    def test_gps(self):
        assert _match_constellation("NAVSTAR 78 (USA 319)") == "GPS"

    def test_case_insensitive(self):
        assert _match_constellation("starlink-5000") == "Starlink"

    def test_no_match(self):
        assert _match_constellation("RANDOM SATELLITE") is None

    def test_planet_flock(self):
        assert _match_constellation("FLOCK 4BE 11") == "Planet (Flock)"

    def test_iridium(self):
        assert _match_constellation("IRIDIUM 180") == "Iridium"

    def test_glonass(self):
        assert _match_constellation("GLONASS-K2 19L") == "GLONASS"


# ---------------------------------------------------------------------------
# _designator_prefix
# ---------------------------------------------------------------------------
class TestDesignatorPrefix:
    def test_standard(self):
        assert _designator_prefix("2024-001A") == "2024-001"

    def test_multi_letter_piece(self):
        assert _designator_prefix("1998-067QM") == "1998-067"

    def test_no_match(self):
        assert _designator_prefix("GARBAGE") is None

    def test_just_prefix(self):
        assert _designator_prefix("2024-001") == "2024-001"


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------
class TestParseDate:
    def test_valid(self):
        result = _parse_date("2024-03-15")
        assert result is not None
        assert result.year == 2024
        assert result.day == 15

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_wrong_format(self):
        assert _parse_date("15/03/2024") is None

    def test_iso_with_time(self):
        # Only accepts YYYY-MM-DD
        assert _parse_date("2024-03-15T12:00:00") is None
