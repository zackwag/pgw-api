# pgw-api

Python API client for [Philadelphia Gas Works (PGW)](https://www.pgworks.com/). Fetches monthly natural gas usage data from the PGW customer portal.

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

### Exceptions

- `PGWAuthError` — invalid credentials or expired session
- `PGWConnectionError` — network or portal issues
- `PGWError` — base exception class
