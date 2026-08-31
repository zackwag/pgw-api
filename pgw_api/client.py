"""API client for Philadelphia Gas Works (PGW) portal."""

from __future__ import annotations

import json
import re
from datetime import date

import aiohttp

from .exceptions import PGWAuthError, PGWConnectionError
from .models import BillingSummary, DailyGasUsage, GasUsage, HourlyGasUsage

BASE_URL = "https://myaccount.pgworks.com/portal"
LOGIN_URL = f"{BASE_URL}/"
VALIDATE_LOGIN_URL = f"{BASE_URL}/Default.aspx/validateLogin"
DASHBOARD_URL = f"{BASE_URL}/Dashboard.aspx"
BILL_DASHBOARD_URL = f"{BASE_URL}/BillDashboard.aspx"
USAGE_URL = f"{BASE_URL}/usages.aspx"
LOAD_GAS_URL = f"{BASE_URL}/Usages.aspx/LoadGasUsage"

_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://myaccount.pgworks.com",
}


class PGWApiClient:
    """Client for interacting with the PGW portal."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    async def async_get_usage(
        self, session: aiohttp.ClientSession
    ) -> list[GasUsage]:
        """Authenticate and fetch gas usage data from PGW."""
        await self._establish_session(session)
        await self._authenticate(session)
        csrf_token = await self._get_csrf_token(session)
        return await self._load_gas_usage(session, csrf_token)

    async def async_get_billing(
        self, session: aiohttp.ClientSession
    ) -> BillingSummary:
        """Authenticate and fetch billing summary from PGW."""
        await self._establish_session(session)
        await self._authenticate(session)
        return await self._load_billing(session)

    async def async_get_daily_usage(
        self,
        session: aiohttp.ClientSession,
        start: date,
        end: date,
    ) -> list[DailyGasUsage]:
        """Authenticate and fetch daily gas usage for a date range."""
        await self._establish_session(session)
        await self._authenticate(session)
        csrf_token = await self._get_csrf_token(session)
        return await self._load_daily_gas_usage(session, csrf_token, start, end)

    async def async_get_hourly_usage(
        self,
        session: aiohttp.ClientSession,
        usage_date: date,
    ) -> list[HourlyGasUsage]:
        """Authenticate and fetch hourly gas usage for a single day."""
        await self._establish_session(session)
        await self._authenticate(session)
        csrf_token = await self._get_csrf_token(session)
        return await self._load_hourly_gas_usage(session, csrf_token, usage_date)

    async def async_get_all(
        self, session: aiohttp.ClientSession
    ) -> tuple[list[GasUsage], BillingSummary]:
        """Authenticate and fetch both usage and billing data in one session."""
        await self._establish_session(session)
        await self._authenticate(session)
        billing = await self._load_billing(session)
        csrf_token = await self._get_csrf_token(session)
        usage = await self._load_gas_usage(session, csrf_token)
        return usage, billing

    async def async_validate_credentials(
        self, session: aiohttp.ClientSession
    ) -> bool:
        """Validate credentials without fetching usage data."""
        await self._establish_session(session)
        await self._authenticate(session)
        return True

    async def _establish_session(self, session: aiohttp.ClientSession) -> None:
        """GET the login page to establish ASP.NET session cookies."""
        try:
            async with session.get(LOGIN_URL, allow_redirects=True) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"Login page returned status {resp.status}"
                    )
                await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(f"Failed to connect to PGW: {err}") from err

    async def _authenticate(self, session: aiohttp.ClientSession) -> None:
        """Authenticate via the AJAX login endpoint."""
        payload = {
            "username": self._username,
            "password": self._password,
            "rememberme": False,
        }
        headers = {**_HEADERS, "Referer": LOGIN_URL}

        try:
            async with session.post(
                VALIDATE_LOGIN_URL, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    raise PGWAuthError(
                        f"Login endpoint returned status {resp.status}"
                    )
                body = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed during authentication: {err}"
            ) from err

        try:
            data = json.loads(body)
            inner = json.loads(data["d"])
        except (json.JSONDecodeError, KeyError) as err:
            raise PGWConnectionError(
                "Unexpected response from login endpoint"
            ) from err

        if isinstance(inner, dict) and "dtException" in inner:
            msg = inner["dtException"][0].get("MessageInformation", "Unknown error")
            raise PGWAuthError(msg)

        if not isinstance(inner, list) or not inner:
            raise PGWAuthError("Authentication failed - unexpected response")

        first = inner[0]
        if isinstance(first, dict) and first.get("STATUS") == 0:
            raise PGWAuthError(
                first.get("Message", "Invalid username or password")
            )

    async def _get_csrf_token(self, session: aiohttp.ClientSession) -> str:
        """Navigate to the usage page and extract the CSRF token."""
        try:
            async with session.get(DASHBOARD_URL, allow_redirects=True) as resp:
                await resp.text()

            async with session.get(
                USAGE_URL, params={"type": "GU"}, allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"Usage page returned status {resp.status}"
                    )
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed to fetch usage page: {err}"
            ) from err

        match = re.search(r'id="hdnCSRFToken"[^>]*value="([^"]+)"', html)
        if not match:
            raise PGWConnectionError("Could not extract CSRF token from usage page")

        return match.group(1)

    async def _load_billing(
        self, session: aiohttp.ClientSession
    ) -> BillingSummary:
        """Fetch billing summary from the BillDashboard page."""
        try:
            async with session.get(DASHBOARD_URL, allow_redirects=True) as resp:
                await resp.text()

            async with session.get(
                BILL_DASHBOARD_URL, allow_redirects=True
            ) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"BillDashboard returned status {resp.status}"
                    )
                html = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed to fetch billing data: {err}"
            ) from err

        def field(name: str, default: str = "0") -> str:
            match = re.search(
                rf'id="{name}"[^>]*value="([^"]*)"', html
            )
            return match.group(1) if match else default

        current_bill = _parse_dollar(field("hdnTotalBillOFCurrentMonth"))
        current_usage = _parse_float(field("hdnGasUsageOFCurrentMonth"))
        current_days = _parse_int(field("hdnnumOfDaysCurrentMonth"))
        previous_bill = _parse_dollar(field("hdnTotalBillOFPreviousMonth"))
        previous_usage = _parse_float(field("hdnGasUsageOFPreviousMonth"))
        previous_days = _parse_int(field("hdnnumOfDaysPreviousMonth"))
        prev_year_bill = _parse_dollar(
            field("hdnTotalBillOFPreviousYearPreviousMonth")
        )
        prev_year_usage = _parse_float(
            field("hdnGasUsageOFPreviousYearPreviousMonth")
        )
        balance = _parse_dollar(field("hdnPrevAmount"))

        # Parse period from billing comparison JSON
        period_start = None
        period_end = None
        comparison = field("hdnbillComparisionOFCurrentMonth", "")
        if comparison:
            comparison = comparison.replace("&quot;", '"')
            try:
                entries = json.loads(comparison)
                if entries:
                    ps = entries[0].get("Periodfrom")
                    pe = entries[0].get("PeriodTo")
                    if ps:
                        period_start = date.fromisoformat(ps.split("T")[0])
                    if pe:
                        period_end = date.fromisoformat(pe.split("T")[0])
            except (json.JSONDecodeError, ValueError, IndexError):
                pass

        return BillingSummary(
            current_bill=current_bill,
            current_usage_ccf=current_usage,
            current_period_days=current_days,
            previous_bill=previous_bill,
            previous_usage_ccf=previous_usage,
            previous_period_days=previous_days,
            previous_year_bill=prev_year_bill,
            previous_year_usage_ccf=prev_year_usage,
            balance_due=balance,
            period_start=period_start,
            period_end=period_end,
        )

    async def _load_gas_usage(
        self, session: aiohttp.ClientSession, csrf_token: str
    ) -> list[GasUsage]:
        """Call the LoadGasUsage WebMethod to get monthly usage data."""
        payload = {
            "Type": "C",
            "Mode": "M",
            "strDate": "",
            "hourlyType": "",
            "seasonId": "",
            "weatherOverlay": "0",
            "usageyear": "",
            "MeterNumber": "",
            "DateFromDaily": "",
            "DateToDaily": "",
            "HistID": "0",
            "requiredDataType": 0,
        }
        headers = {
            **_HEADERS,
            "Referer": f"{USAGE_URL}?type=GU",
            "CSRFToken": csrf_token,
        }

        try:
            async with session.post(
                LOAD_GAS_URL, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"LoadGasUsage returned status {resp.status}"
                    )
                body = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed to fetch gas usage: {err}"
            ) from err

        try:
            data = json.loads(body)
            inner = json.loads(data["d"])
        except (json.JSONDecodeError, KeyError) as err:
            raise PGWConnectionError(
                "Unexpected response from LoadGasUsage"
            ) from err

        if isinstance(inner, dict) and "dtException" in inner:
            msg = inner["dtException"][0].get("MessageInformation", "Unknown error")
            if "CSRF" in msg:
                raise PGWAuthError("CSRF token invalid - session may have expired")
            raise PGWConnectionError(msg)

        usage_entries = inner.get("objUsageGenerationResultSetTwo", [])
        if not usage_entries:
            return []

        results: list[GasUsage] = []
        for entry in usage_entries:
            month_num = entry.get("Month")
            year = entry.get("Year")
            ccf = entry.get("UsageValue")

            if not all((month_num, year, ccf is not None)):
                continue

            month_date = date(year, month_num, 1)

            period_start = _parse_date(entry.get("FromDate"))
            period_end = _parse_date(entry.get("ToDate"))

            results.append(
                GasUsage(
                    month=month_date,
                    ccf=float(ccf),
                    period_start=period_start,
                    period_end=period_end,
                )
            )

        return sorted(results, key=lambda u: u.month, reverse=True)

    async def _load_daily_gas_usage(
        self,
        session: aiohttp.ClientSession,
        csrf_token: str,
        start: date,
        end: date,
    ) -> list[DailyGasUsage]:
        """Call LoadGasUsage in daily mode for a date range."""
        payload = {
            "Type": "C",
            "Mode": "D",
            "strDate": "",
            "hourlyType": "",
            "seasonId": "",
            "weatherOverlay": "0",
            "usageyear": "",
            "MeterNumber": "",
            "DateFromDaily": start.strftime("%m/%d/%y"),
            "DateToDaily": end.strftime("%m/%d/%y"),
            "HistID": "0",
            "requiredDataType": 0,
        }
        headers = {
            **_HEADERS,
            "Referer": f"{USAGE_URL}?type=GU",
            "CSRFToken": csrf_token,
        }

        try:
            async with session.post(
                LOAD_GAS_URL, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"LoadGasUsage (daily) returned status {resp.status}"
                    )
                body = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed to fetch daily gas usage: {err}"
            ) from err

        try:
            data = json.loads(body)
            inner = json.loads(data["d"])
        except (json.JSONDecodeError, KeyError) as err:
            raise PGWConnectionError(
                "Unexpected response from LoadGasUsage (daily)"
            ) from err

        if isinstance(inner, dict) and "dtException" in inner:
            msg = inner["dtException"][0].get("MessageInformation", "Unknown error")
            if "CSRF" in msg:
                raise PGWAuthError("CSRF token invalid - session may have expired")
            raise PGWConnectionError(msg)

        usage_entries = inner.get("objUsageGenerationResultSetTwo", [])
        if not usage_entries:
            return []

        results: list[DailyGasUsage] = []
        for entry in usage_entries:
            entry_date = _parse_date(entry.get("FromDate"))
            ccf = entry.get("UsageValue")

            if entry_date is None or ccf is None:
                continue

            results.append(DailyGasUsage(date=entry_date, ccf=float(ccf)))

        return sorted(results, key=lambda u: u.date, reverse=True)

    async def _load_hourly_gas_usage(
        self,
        session: aiohttp.ClientSession,
        csrf_token: str,
        usage_date: date,
    ) -> list[HourlyGasUsage]:
        """Call LoadGasUsage in daily mode with hourlyType to get hourly data."""
        from datetime import datetime

        payload = {
            "Type": "C",
            "Mode": "D",
            "strDate": usage_date.strftime("%m/%d/%y"),
            "hourlyType": "H",
            "seasonId": "",
            "weatherOverlay": "0",
            "usageyear": "",
            "MeterNumber": "",
            "DateFromDaily": "",
            "DateToDaily": "",
            "HistID": "0",
            "requiredDataType": 0,
        }
        headers = {
            **_HEADERS,
            "Referer": f"{USAGE_URL}?type=GU",
            "CSRFToken": csrf_token,
        }

        try:
            async with session.post(
                LOAD_GAS_URL, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    raise PGWConnectionError(
                        f"LoadGasUsage (hourly) returned status {resp.status}"
                    )
                body = await resp.text()
        except aiohttp.ClientError as err:
            raise PGWConnectionError(
                f"Failed to fetch hourly gas usage: {err}"
            ) from err

        try:
            data = json.loads(body)
            inner = json.loads(data["d"])
        except (json.JSONDecodeError, KeyError) as err:
            raise PGWConnectionError(
                "Unexpected response from LoadGasUsage (hourly)"
            ) from err

        if isinstance(inner, dict) and "dtException" in inner:
            msg = inner["dtException"][0].get("MessageInformation", "Unknown error")
            if "CSRF" in msg:
                raise PGWAuthError("CSRF token invalid - session may have expired")
            raise PGWConnectionError(msg)

        usage_entries = inner.get("objUsageGenerationResultSetTwo", [])
        if not usage_entries:
            return []

        results: list[HourlyGasUsage] = []
        for entry in usage_entries:
            ts = _parse_datetime(entry.get("FromDate"))
            ccf = entry.get("UsageValue")

            if ts is None or ccf is None:
                continue

            results.append(HourlyGasUsage(timestamp=ts, ccf=float(ccf)))

        return sorted(results, key=lambda u: u.timestamp, reverse=True)


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse a datetime string from the portal (various formats)."""
    if not dt_str:
        return None
    from datetime import datetime

    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%y %I:%M:%S %p", "%m/%d/%y"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    parsed_date = _parse_date(dt_str)
    if parsed_date:
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day)
    return None


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string in MM/DD/YY format."""
    if not date_str:
        return None
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            month = int(parts[0])
            day = int(parts[1])
            year = int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
    except (ValueError, IndexError):
        pass
    return None


def _parse_dollar(value: str) -> float:
    """Parse a dollar amount string like '$37.52' or '37.52'."""
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_float(value: str) -> float:
    """Parse a float string."""
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_int(value: str) -> int:
    """Parse an int string."""
    try:
        return int(value)
    except ValueError:
        return 0
