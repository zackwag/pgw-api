# pgw-api

Python API client for [Philadelphia Gas Works (PGW)](https://www.pgworks.com/). Fetches natural gas usage data (monthly, daily, and hourly) from the PGW customer portal.

## Installation

```bash
pip install pgw-api
```

## Usage

```python
import asyncio
import aiohttp
from pgw_api import PGWApiClient

async def main():
    client = PGWApiClient("your-email@example.com", "your-password")

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        usage = await client.async_get_usage(session)

        for entry in usage:
            print(f"{entry.month:%B %Y}: {entry.ccf} CCF ({entry.cf} ft³)")
            if entry.period_start and entry.period_end:
                print(f"  Period: {entry.period_start} to {entry.period_end}")

asyncio.run(main())
```

## API

### `PGWApiClient(username, password)`

Creates a client instance with PGW portal credentials.

### `await client.async_get_usage(session)`

Authenticates and returns a list of `GasUsage` objects sorted by month (newest first).

### `await client.async_get_daily_usage(session, start, end)`

Authenticates and returns a list of `DailyGasUsage` objects for the given date range (newest first). Requires a smart meter — most residential accounts only have monthly data and will return an empty list.

```python
from datetime import date

daily = await client.async_get_daily_usage(session, date(2024, 1, 1), date(2024, 1, 31))
for entry in daily:
    print(f"{entry.date}: {entry.ccf} CCF")
```

### `await client.async_get_hourly_usage(session, usage_date)`

Authenticates and returns a list of `HourlyGasUsage` objects for a single day (newest first). Requires a smart meter that reports interval data. Most residential accounts only have monthly data and will return an empty list.

```python
from datetime import date

hourly = await client.async_get_hourly_usage(session, date(2024, 1, 15))
for entry in hourly:
    print(f"{entry.timestamp}: {entry.ccf} CCF")
```

### `await client.async_validate_credentials(session)`

Validates credentials without fetching usage data. Returns `True` or raises `PGWAuthError`.

### `GasUsage`

| Property | Type | Description |
|----------|------|-------------|
| `month` | `date` | First of the billing month |
| `ccf` | `float` | Usage in hundreds of cubic feet |
| `cf` | `float` | Usage in cubic feet (CCF × 100) |
| `period_start` | `date \| None` | Meter read start date |
| `period_end` | `date \| None` | Meter read end date |

### `DailyGasUsage`

| Property | Type | Description |
|----------|------|-------------|
| `date` | `date` | Usage date |
| `ccf` | `float` | Usage in hundreds of cubic feet |
| `cf` | `float` | Usage in cubic feet (CCF × 100) |

### `HourlyGasUsage`

| Property | Type | Description |
|----------|------|-------------|
| `timestamp` | `datetime` | Usage timestamp |
| `ccf` | `float` | Usage in hundreds of cubic feet |
| `cf` | `float` | Usage in cubic feet (CCF × 100) |

### Exceptions

- `PGWAuthError` — invalid credentials or expired session
- `PGWConnectionError` — network or portal issues
- `PGWError` — base exception class
