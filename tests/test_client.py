"""Tests for PGWApiClient using mocked HTTP responses."""

import json
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from pgw_api.client import PGWApiClient
from pgw_api.exceptions import PGWAuthError, PGWConnectionError
from tests.conftest import CSRF_HTML, make_login_success, make_response, make_webmethod_response


def _setup_session(responses):
    """Wire up a mock session with a sequence of responses."""
    session = MagicMock()
    idx = {"i": 0}

    def _ctx(resp):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    def _next(*args, **kwargs):
        r = responses[idx["i"]]
        idx["i"] += 1
        return _ctx(r)

    session.get = MagicMock(side_effect=_next)
    session.post = MagicMock(side_effect=_next)
    return session


class TestMonthlyUsage:
    @pytest.mark.asyncio
    async def test_parses_monthly_entries(self):
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"Month": 1, "Year": 2024, "UsageValue": 85.0, "FromDate": "12/15/23", "ToDate": "01/16/24"},
                {"Month": 12, "Year": 2023, "UsageValue": 72.0, "FromDate": "11/14/23", "ToDate": "12/15/23"},
            ]
        })
        session = _setup_session([
            make_response(),                      # GET login page
            make_response(text=make_login_success()),  # POST validateLogin
            make_response(),                      # GET Dashboard
            make_response(text=CSRF_HTML),         # GET usage page
            make_response(text=usage_payload),     # POST LoadGasUsage
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_usage(session)

        assert len(result) == 2
        assert result[0].month == date(2024, 1, 1)
        assert result[0].ccf == 85.0
        assert result[1].month == date(2023, 12, 1)

    @pytest.mark.asyncio
    async def test_empty_usage(self):
        usage_payload = make_webmethod_response({"objUsageGenerationResultSetTwo": []})
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=usage_payload),
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_usage(session)
        assert result == []


class TestDailyUsage:
    @pytest.mark.asyncio
    async def test_parses_daily_entries(self):
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"FromDate": "01/15/24", "UsageValue": 3.2},
                {"FromDate": "01/14/24", "UsageValue": 4.1},
                {"FromDate": "01/16/24", "UsageValue": 2.8},
            ]
        })
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=usage_payload),
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_daily_usage(
            session, date(2024, 1, 14), date(2024, 1, 16)
        )

        assert len(result) == 3
        assert result[0].date == date(2024, 1, 16)
        assert result[0].ccf == 2.8
        assert result[-1].date == date(2024, 1, 14)

    @pytest.mark.asyncio
    async def test_skips_entries_missing_date(self):
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"FromDate": "01/15/24", "UsageValue": 3.2},
                {"FromDate": None, "UsageValue": 4.1},
            ]
        })
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=usage_payload),
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_daily_usage(
            session, date(2024, 1, 1), date(2024, 1, 31)
        )
        assert len(result) == 1


class TestHourlyUsage:
    @pytest.mark.asyncio
    async def test_parses_hourly_entries(self):
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"FromDate": "01/15/2024 01:00:00 AM", "UsageValue": 0.3},
                {"FromDate": "01/15/2024 02:00:00 AM", "UsageValue": 0.4},
                {"FromDate": "01/15/2024 12:00:00 PM", "UsageValue": 0.1},
            ]
        })
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=usage_payload),
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_hourly_usage(session, date(2024, 1, 15))

        assert len(result) == 3
        assert result[0].timestamp == datetime(2024, 1, 15, 12, 0, 0)
        assert result[0].ccf == 0.1
        assert result[-1].timestamp == datetime(2024, 1, 15, 1, 0, 0)

    @pytest.mark.asyncio
    async def test_empty_hourly(self):
        usage_payload = make_webmethod_response({"objUsageGenerationResultSetTwo": []})
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=usage_payload),
        ])

        client = PGWApiClient("user", "pass")
        result = await client.async_get_hourly_usage(session, date(2024, 1, 15))
        assert result == []


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_csrf_error_raises_auth_error(self):
        error_payload = make_webmethod_response({
            "dtException": [{"MessageInformation": "Invalid CSRF Token"}]
        })
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=error_payload),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWAuthError, match="CSRF"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_bad_credentials(self):
        login_fail = make_webmethod_response(
            [{"STATUS": 0, "Message": "Invalid username or password"}]
        )
        session = _setup_session([
            make_response(),
            make_response(text=login_fail),
        ])

        client = PGWApiClient("user", "wrong")
        with pytest.raises(PGWAuthError, match="Invalid username"):
            await client.async_get_usage(session)
