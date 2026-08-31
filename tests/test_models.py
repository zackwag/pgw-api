"""Tests for data models."""

from datetime import date, datetime

from pgw_api.models import DailyGasUsage, GasUsage, HourlyGasUsage


class TestGasUsage:
    def test_cf_conversion(self):
        entry = GasUsage(month=date(2024, 1, 1), ccf=85.0)
        assert entry.cf == 8500.0

    def test_optional_fields_default_none(self):
        entry = GasUsage(month=date(2024, 1, 1), ccf=10.0)
        assert entry.period_start is None
        assert entry.period_end is None


class TestDailyGasUsage:
    def test_cf_conversion(self):
        entry = DailyGasUsage(date=date(2024, 1, 15), ccf=5.0)
        assert entry.cf == 500.0

    def test_zero_usage(self):
        entry = DailyGasUsage(date=date(2024, 7, 1), ccf=0.0)
        assert entry.cf == 0.0


class TestHourlyGasUsage:
    def test_cf_conversion(self):
        entry = HourlyGasUsage(timestamp=datetime(2024, 1, 15, 14, 0), ccf=0.5)
        assert entry.cf == 50.0

    def test_zero_usage(self):
        entry = HourlyGasUsage(timestamp=datetime(2024, 7, 1, 12, 0), ccf=0.0)
        assert entry.cf == 0.0
