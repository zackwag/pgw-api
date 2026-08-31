"""Shared fixtures for PGW API tests."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_response(status=200, text="", headers=None):
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.headers = headers or {}
    return resp


def make_webmethod_response(payload):
    """Wrap a dict as a PGW WebMethod JSON response."""
    return json.dumps({"d": json.dumps(payload)})


def make_login_success():
    """Return a successful login response body."""
    return make_webmethod_response(
        [{"AccountNumber": "1234567890", "STATUS": 1}]
    )


CSRF_HTML = '<input type="hidden" id="hdnCSRFToken" value="test-csrf-token" />'


@pytest.fixture
def mock_session():
    """Create a mock aiohttp.ClientSession that handles the auth flow."""
    session = MagicMock()

    responses = []
    call_count = {"n": 0}

    ctx = MagicMock()

    def context_manager(resp):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    def get_side_effect(url, **kwargs):
        return context_manager(responses[call_count["n"] - 1])

    def post_side_effect(url, **kwargs):
        return context_manager(responses[call_count["n"] - 1])

    session._responses = responses
    session._call_count = call_count
    session._context_manager = context_manager
    return session
