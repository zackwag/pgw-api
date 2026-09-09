"""Tests for billing HTML parsing and the BillingSummary model."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from pgw_api.client import PGWApiClient
from pgw_api.models import BillingSummary
from tests.conftest import make_response, make_login_success, make_webmethod_response


BILLING_HTML = """
<input type="hidden" id="hdnTotalBillOFCurrentMonth" value="$120.50" />
<input type="hidden" id="hdnGasUsageOFCurrentMonth" value="85.0" />
<input type="hidden" id="hdnnumOfDaysCurrentMonth" value="32" />
<input type="hidden" id="hdnTotalBillOFPreviousMonth" value="$95.00" />
<input type="hidden" id="hdnGasUsageOFPreviousMonth" value="60.0" />
<input type="hidden" id="hdnnumOfDaysPreviousMonth" value="30" />
<input type="hidden" id="hdnTotalBillOFPreviousYearPreviousMonth" value="$110.00" />
<input type="hidden" id="hdnGasUsageOFPreviousYearPreviousMonth" value="80.0" />
<input type="hidden" id="hdnPrevAmount" value="$120.50" />
<input type="hidden" id="hdnbillComparisionOFCurrentMonth" value="[{&quot;Periodfrom&quot;:&quot;2024-01-15T00:00:00&quot;,&quot;PeriodTo&quot;:&quot;2024-02-14T00:00:00&quot;}]" />
"""


def _setup_session(responses):
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


class TestBillingParsing:
    @pytest.mark.asyncio
    async def test_parses_all_fields(self):
        session = _setup_session([
            make_response(),                           # GET login page
            make_response(text=make_login_success()),  # POST validateLogin
            make_response(),                           # GET Dashboard
            make_response(text=BILLING_HTML),           # GET BillDashboard
        ])

        client = PGWApiClient("user", "pass")
        billing = await client.async_get_billing(session)

        assert billing.current_bill == 120.50
        assert billing.current_usage_ccf == 85.0
        assert billing.current_period_days == 32
        assert billing.previous_bill == 95.00
        assert billing.previous_usage_ccf == 60.0
        assert billing.previous_period_days == 30
        assert billing.previous_year_bill == 110.00
        assert billing.previous_year_usage_ccf == 80.0
        assert billing.balance_due == 120.50
        assert billing.period_start == date(2024, 1, 15)
        assert billing.period_end == date(2024, 2, 14)

    @pytest.mark.asyncio
    async def test_missing_fields_default_to_zero(self):
        html = "<html><body>no hidden fields here</body></html>"
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=html),
        ])

        client = PGWApiClient("user", "pass")
        billing = await client.async_get_billing(session)

        assert billing.current_bill == 0.0
        assert billing.current_usage_ccf == 0.0
        assert billing.current_period_days == 0
        assert billing.period_start is None
        assert billing.period_end is None

    @pytest.mark.asyncio
    async def test_malformed_period_json(self):
        html = '<input type="hidden" id="hdnbillComparisionOFCurrentMonth" value="not json" />'
        session = _setup_session([
            make_response(),
            make_response(text=make_login_success()),
            make_response(),
            make_response(text=html),
        ])

        client = PGWApiClient("user", "pass")
        billing = await client.async_get_billing(session)
        assert billing.period_start is None
        assert billing.period_end is None


class TestBillingSummaryModel:
    def test_current_usage_cf(self):
        b = BillingSummary(
            current_bill=100, current_usage_ccf=50, current_period_days=30,
            previous_bill=80, previous_usage_ccf=40, previous_period_days=30,
            previous_year_bill=90, previous_year_usage_ccf=45, balance_due=100,
        )
        assert b.current_usage_cf == 5000.0

    def test_previous_usage_cf(self):
        b = BillingSummary(
            current_bill=100, current_usage_ccf=50, current_period_days=30,
            previous_bill=80, previous_usage_ccf=40, previous_period_days=30,
            previous_year_bill=90, previous_year_usage_ccf=45, balance_due=100,
        )
        assert b.previous_usage_cf == 4000.0

    def test_current_rate(self):
        b = BillingSummary(
            current_bill=200, current_usage_ccf=100, current_period_days=30,
            previous_bill=80, previous_usage_ccf=40, previous_period_days=30,
            previous_year_bill=90, previous_year_usage_ccf=45, balance_due=200,
        )
        assert b.current_rate == 2.0

    def test_current_rate_zero_usage(self):
        b = BillingSummary(
            current_bill=0, current_usage_ccf=0, current_period_days=0,
            previous_bill=0, previous_usage_ccf=0, previous_period_days=0,
            previous_year_bill=0, previous_year_usage_ccf=0, balance_due=0,
        )
        assert b.current_rate is None
