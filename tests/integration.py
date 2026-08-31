#!/usr/bin/env python3
"""Integration test — run against the real PGW portal.

Usage:
    PGW_USERNAME=you@email.com PGW_PASSWORD=secret python tests/integration.py

Authenticates once, then fires monthly/daily/hourly requests
in the same session to avoid CSRF invalidation.
"""

import asyncio
import json
import os
import re
import sys
from datetime import date, timedelta

import aiohttp

from pgw_api.client import (
    DASHBOARD_URL,
    LOAD_GAS_URL,
    LOGIN_URL,
    USAGE_URL,
    VALIDATE_LOGIN_URL,
    _HEADERS,
)


async def main():
    username = os.environ.get("PGW_USERNAME")
    password = os.environ.get("PGW_PASSWORD")

    if not username or not password:
        print("Set PGW_USERNAME and PGW_PASSWORD environment variables.")
        sys.exit(1)

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        # --- Authenticate once ---
        print("Authenticating...")
        async with session.get(LOGIN_URL, allow_redirects=True) as resp:
            await resp.text()

        payload = {"username": username, "password": password, "rememberme": False}
        headers = {**_HEADERS, "Referer": LOGIN_URL}
        async with session.post(VALIDATE_LOGIN_URL, json=payload, headers=headers) as resp:
            body = await resp.text()
            data = json.loads(body)
            inner = json.loads(data["d"])
            if isinstance(inner, dict) and "dtException" in inner:
                print(f"  Auth error: {inner}")
                sys.exit(1)
            if isinstance(inner, list) and inner and inner[0].get("STATUS") == 0:
                print(f"  Auth failed: {inner[0].get('Message')}")
                sys.exit(1)
        print("  OK")

        # Navigate to dashboard (required before usage page)
        async with session.get(DASHBOARD_URL, allow_redirects=True) as resp:
            await resp.text()

        # --- Monthly ---
        print()
        print("=" * 60)
        print("MONTHLY USAGE (Mode=M)")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "M", "strDate": "", "hourlyType": "",
            "seasonId": "", "weatherOverlay": "0", "usageyear": "",
            "MeterNumber": "", "DateFromDaily": "", "DateToDaily": "",
            "HistID": "0", "requiredDataType": 0,
        })

        # --- Daily ---
        end = date.today()
        start = end - timedelta(days=30)
        print()
        print("=" * 60)
        print(f"DAILY USAGE (Mode=D, {start} to {end})")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "D", "strDate": "", "hourlyType": "",
            "seasonId": "", "weatherOverlay": "0", "usageyear": "",
            "MeterNumber": "",
            "DateFromDaily": start.strftime("%m/%d/%Y"),
            "DateToDaily": end.strftime("%m/%d/%Y"),
            "HistID": "0", "requiredDataType": 0,
        })

        # --- Daily variation: short year format (MM/DD/YY) ---
        print()
        print("=" * 60)
        print(f"DAILY v2 (DateFrom/To in MM/DD/YY)")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "D", "strDate": "", "hourlyType": "",
            "seasonId": "", "weatherOverlay": "0", "usageyear": "",
            "MeterNumber": "",
            "DateFromDaily": start.strftime("%m/%d/%y"),
            "DateToDaily": end.strftime("%m/%d/%y"),
            "HistID": "0", "requiredDataType": 0,
        })

        # --- Daily variation: use strDate instead ---
        print()
        print("=" * 60)
        print(f"DAILY v3 (strDate instead of DateFrom/To)")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "D",
            "strDate": start.strftime("%m/%d/%Y"),
            "hourlyType": "",
            "seasonId": "", "weatherOverlay": "0", "usageyear": "",
            "MeterNumber": "", "DateFromDaily": "", "DateToDaily": "",
            "HistID": "0", "requiredDataType": 0,
        })

        # --- Daily variation: with usageyear ---
        print()
        print("=" * 60)
        print(f"DAILY v4 (with usageyear={end.year})")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "D", "strDate": "", "hourlyType": "",
            "seasonId": "", "weatherOverlay": "0",
            "usageyear": str(end.year),
            "MeterNumber": "",
            "DateFromDaily": start.strftime("%m/%d/%Y"),
            "DateToDaily": end.strftime("%m/%d/%Y"),
            "HistID": "0", "requiredDataType": 0,
        })

        # --- Hourly (hourlyType=H) ---
        yesterday = end - timedelta(days=1)
        print()
        print("=" * 60)
        print(f"HOURLY (Mode=D, hourlyType=H, {yesterday})")
        print("=" * 60)
        csrf = await _get_csrf(session)
        await _fire(session, csrf, {
            "Type": "C", "Mode": "D",
            "strDate": yesterday.strftime("%m/%d/%Y"),
            "hourlyType": "H",
            "seasonId": "", "weatherOverlay": "0", "usageyear": "",
            "MeterNumber": "", "DateFromDaily": "", "DateToDaily": "",
            "HistID": "0", "requiredDataType": 0,
        })


async def _get_csrf(session):
    """Navigate to usage page and extract a fresh CSRF token."""
    async with session.get(USAGE_URL, params={"type": "GU"}, allow_redirects=True) as resp:
        html = await resp.text()
    match = re.search(r'id="hdnCSRFToken"[^>]*value="([^"]+)"', html)
    if not match:
        print("  WARNING: Could not extract CSRF token")
        return "MISSING"
    token = match.group(1)
    print(f"  CSRF: {token[:16]}...")
    return token


async def _fire(session, csrf, payload):
    """Send a LoadGasUsage request and print the response."""
    headers = {
        **_HEADERS,
        "Referer": f"{USAGE_URL}?type=GU",
        "CSRFToken": csrf,
    }
    async with session.post(LOAD_GAS_URL, json=payload, headers=headers) as resp:
        body = await resp.text()

    try:
        data = json.loads(body)
        inner = json.loads(data["d"])
    except Exception:
        print(f"  Raw (first 500): {body[:500]}")
        return

    entries = inner.get("objUsageGenerationResultSetTwo", [])
    if entries:
        print(f"  {len(entries)} entries")
        print(f"  Keys: {list(entries[0].keys())}")
        print(f"  First: {json.dumps(entries[0], indent=4)}")
        if len(entries) > 1:
            print(f"  Second: {json.dumps(entries[1], indent=4)}")
    else:
        print(f"  No usage entries. Full response:")
        print(f"  {json.dumps(inner, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
