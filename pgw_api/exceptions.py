"""Exceptions for the PGW API client."""


class PGWError(Exception):
    """Base exception for PGW API errors."""


class PGWAuthError(PGWError):
    """Raised when authentication fails."""


class PGWConnectionError(PGWError):
    """Raised when connection to PGW fails."""
