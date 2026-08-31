"""Tests for parsing helpers and model construction."""

from datetime import date, datetime

from pgw_api.client import _parse_date, _parse_datetime, _parse_dollar, _parse_float, _parse_int


class TestParseDate:
    def test_mm_dd_yy(self):
        assert _parse_date("01/15/24") == date(2024, 1, 15)

    def test_mm_dd_yyyy(self):
        assert _parse_date("12/31/2023") == date(2023, 12, 31)

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_invalid(self):
        assert _parse_date("not-a-date") is None


class TestParseDatetime:
    def test_12hr_format(self):
        assert _parse_datetime("01/15/2024 02:30:00 PM") == datetime(2024, 1, 15, 14, 30, 0)

    def test_24hr_format(self):
        assert _parse_datetime("01/15/2024 14:30:00") == datetime(2024, 1, 15, 14, 30, 0)

    def test_short_year(self):
        assert _parse_datetime("01/15/24") == datetime(2024, 1, 15, 0, 0, 0)

    def test_none(self):
        assert _parse_datetime(None) is None

    def test_empty(self):
        assert _parse_datetime("") is None


class TestParseDollar:
    def test_with_symbol(self):
        assert _parse_dollar("$37.52") == 37.52

    def test_without_symbol(self):
        assert _parse_dollar("37.52") == 37.52

    def test_with_comma(self):
        assert _parse_dollar("$1,234.56") == 1234.56

    def test_invalid(self):
        assert _parse_dollar("N/A") == 0.0


class TestParseFloat:
    def test_valid(self):
        assert _parse_float("85.5") == 85.5

    def test_invalid(self):
        assert _parse_float("bad") == 0.0


class TestParseInt:
    def test_valid(self):
        assert _parse_int("30") == 30

    def test_invalid(self):
        assert _parse_int("bad") == 0
