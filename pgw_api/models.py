"""Data models for PGW API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


CCF_TO_CF = 100.0


@dataclass
class GasUsage:
    """A single month of gas usage data."""

    month: date
    ccf: float
    period_start: date | None = None
    period_end: date | None = None

    @property
    def cf(self) -> float:
        """Usage in cubic feet."""
        return self.ccf * CCF_TO_CF
