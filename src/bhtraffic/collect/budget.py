"""Zero-cost policy: every external service must stay inside its free tier.

This project must never generate a charge. Limits below were read from the
providers' own pages on 2026-10-13; re-check them before raising any cadence.
`tests/test_budget.py` expands the workflow crons over real calendars and fails
if the worst-case month would exceed SAFETY x the free allowance.
"""
from __future__ import annotations

# Use at most this fraction of any free allowance (headroom for retries/manual runs).
SAFETY = 0.75

FREE_TIER = {
    # Private repo, GitHub Free plan. Account budget for Actions is $0 with
    # "usage blocked", so overage stops jobs instead of billing.
    "github_actions_minutes_month": 2000,
    # docs.tomtom.com/pricing: Routing API free 20K requests/month, no card on file.
    "tomtom_routing_requests_month": 20_000,
}

# Providers that must not be called at all. HERE requires a credit card on the
# account and offers no hard spending cap, so any request is a billing risk.
BLOCKED = {
    "here": "HERE account has a credit card and no hard spending cap (zero-cost policy)",
}

# Only the schedule whose cron string is exactly this one calls TomTom
# (weekday peaks every 30 min). The workflow passes github.event.schedule in
# BHTRAFFIC_SCHEDULE, so a delayed run can never be double-counted.
TOMTOM_CRON = "7,37 9-12,19-22 * * 1-5"


BUS_ONLY = "bus-only"  # workflow_dispatch input used by off-peak dispatches


def tomtom_due(schedule: str | None) -> bool:
    """TomTom runs on its own cron line or on a full manual dispatch (schedule unset).
    Any other cron line, and dispatches with mode 'bus-only', skip it."""
    return not schedule or schedule == TOMTOM_CRON
