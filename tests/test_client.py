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


class TestGetAll:
    @pytest.mark.asyncio
    async def test_returns_usage_and_billing(self):
        billing_html = """
        <input type="hidden" id="hdnTotalBillOFCurrentMonth" value="$120.50" />
        <input type="hidden" id="hdnGasUsageOFCurrentMonth" value="85.0" />
        <input type="hidden" id="hdnnumOfDaysCurrentMonth" value="32" />
        <input type="hidden" id="hdnTotalBillOFPreviousMonth" value="$95.00" />
        <input type="hidden" id="hdnGasUsageOFPreviousMonth" value="60.0" />
        <input type="hidden" id="hdnnumOfDaysPreviousMonth" value="30" />
        <input type="hidden" id="hdnTotalBillOFPreviousYearPreviousMonth" value="$110.00" />
        <input type="hidden" id="hdnGasUsageOFPreviousYearPreviousMonth" value="80.0" />
        <input type="hidden" id="hdnPrevAmount" value="$120.50" />
        """
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"Month": 1, "Year": 2024, "UsageValue": 85.0, "FromDate": "12/15/23", "ToDate": "01/16/24"},
            ]
        })
        session = _setup_session([
            make_response(),                           # GET login page
            make_response(text=make_login_success()),  # POST validateLogin
            make_response(),                           # GET Dashboard (billing)
            make_response(text=billing_html),           # GET BillDashboard
            make_response(),                           # GET Dashboard (usage)
            make_response(text=CSRF_HTML),              # GET usage page
            make_response(text=usage_payload),          # POST LoadGasUsage
        ])

        client = PGWApiClient("user", "pass")
        usage, billing = await client.async_get_all(session)

        assert len(usage) == 1
        assert usage[0].ccf == 85.0
        assert billing.current_bill == 120.50
        assert billing.balance_due == 120.50


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
        ])

        client = PGWApiClient("user", "pass")
        assert await client.async_validate_credentials(session) is True


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

    @pytest.mark.asyncio
    async def test_login_exception_response(self):
        login_err = make_webmethod_response(
            {"dtException": [{"MessageInformation": "Account locked"}]}
        )
        session = _setup_session([
            make_response(),
            make_response(text=login_err),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWAuthError, match="Account locked"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_login_empty_response(self):
        login_empty = make_webmethod_response([])
        session = _setup_session([
            make_response(),
            make_response(text=login_empty),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWAuthError, match="unexpected response"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_login_non_200(self):
        session = _setup_session([
            make_response(),
            make_response(status=500),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWAuthError, match="status 500"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_login_page_non_200(self):
        session = _setup_session([
            make_response(status=503),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="status 503"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_missing_csrf_token(self):
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text="<html>no token here</html>"),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="CSRF token"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_usage_page_non_200(self):
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(status=500),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="status 500"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_load_usage_non_200(self):
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(status=500),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="status 500"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_load_usage_malformed_json(self):
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text="not json"),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="Unexpected response"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_general_exception_in_usage(self):
        error_payload = make_webmethod_response({
            "dtException": [{"MessageInformation": "Something went wrong"}]
        })
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=CSRF_HTML),
            make_response(text=error_payload),
        ])

        client = PGWApiClient("user", "pass")
        with pytest.raises(PGWConnectionError, match="Something went wrong"):
            await client.async_get_usage(session)

    @pytest.mark.asyncio
    async def test_skips_monthly_entries_missing_fields(self):
        usage_payload = make_webmethod_response({
            "objUsageGenerationResultSetTwo": [
                {"Month": 1, "Year": 2024, "UsageValue": 85.0, "FromDate": "12/15/23", "ToDate": "01/16/24"},
                {"Month": None, "Year": 2024, "UsageValue": 50.0},
                {"Month": 2, "Year": None, "UsageValue": 50.0},
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
        result = await client.async_get_usage(session)
        assert len(result) == 1
