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


@dataclass
class BillingSummary:
    """Current billing summary from the BillDashboard."""

    current_bill: float
    current_usage_ccf: float
    current_period_days: int
    previous_bill: float
    previous_usage_ccf: float
    previous_period_days: int
    previous_year_bill: float
    previous_year_usage_ccf: float
    balance_due: float
    period_start: date | None = None
    period_end: date | None = None

    @property
    def current_usage_cf(self) -> float:
        """Current month usage in cubic feet."""
        return self.current_usage_ccf * CCF_TO_CF

    @property
    def previous_usage_cf(self) -> float:
        """Previous month usage in cubic feet."""
        return self.previous_usage_ccf * CCF_TO_CF

    @property
    def current_rate(self) -> float | None:
        """Effective rate per CCF for current period."""
        if self.current_usage_ccf == 0:
            return None
        return self.current_bill / self.current_usage_ccf
