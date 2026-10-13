"""Zero-cost policy: the collector schedule must fit every free tier, worst-case month."""
import calendar
import re

from bhtraffic.collect import budget, run
from bhtraffic.config import REPO_ROOT
from bhtraffic.geo import corridors as corridors_mod

WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "collector.yml").read_text("utf-8")
YEARS = range(2026, 2036)


def _field(spec: str, lo: int, hi: int) -> set[int]:
    if spec == "*":
        return set(range(lo, hi + 1))
    out: set[int] = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def _crons() -> list[str]:
    return re.findall(r'-\s*cron:\s*"([^"]+)"', WORKFLOW)


def _expand(cron: str) -> tuple[set[int], set[int], set[int]]:
    minute, hour, dom, month, dow = cron.split()
    assert dom == "*" and month == "*", "budget test only handles day-of-week crons"
    return _field(minute, 0, 59), _field(hour, 0, 23), _field(dow, 0, 6)


def _runs_per_month(cron: str) -> list[int]:
    mins, hours, dows = _expand(cron)
    counts = []
    for y in YEARS:
        for m in range(1, 13):
            days = calendar.monthrange(y, m)[1]
            # calendar.weekday: Mon=0..Sun=6; cron: Sun=0..Sat=6
            n = sum(1 for d in range(1, days + 1) if (calendar.weekday(y, m, d) + 1) % 7 in dows)
            counts.append(n * len(mins) * len(hours))
    return counts


def test_crons_never_overlap():
    seen: set[tuple[int, int, int]] = set()
    for cron in _crons():
        mins, hours, dows = _expand(cron)
        slots = {(mi, h, d) for mi in mins for h in hours for d in dows}
        assert not (slots & seen), f"{cron} overlaps another schedule (double billing)"
        seen |= slots


def test_actions_minutes_fit_free_tier():
    per_cron = [_runs_per_month(c) for c in _crons()]
    worst = max(sum(month) for month in zip(*per_cron))  # each run billed as 1 minute
    assert worst <= budget.SAFETY * budget.FREE_TIER["github_actions_minutes_month"], worst


def test_tomtom_requests_fit_free_tier():
    assert budget.TOMTOM_CRON in _crons()
    corridors, _ = corridors_mod.load()
    per_run = 2 * len(corridors)  # inbound + outbound
    worst = max(_runs_per_month(budget.TOMTOM_CRON)) * per_run
    assert worst <= budget.SAFETY * budget.FREE_TIER["tomtom_routing_requests_month"], worst


def test_tomtom_skipped_off_budget_schedule():
    assert budget.tomtom_due(None)
    assert budget.tomtom_due(budget.TOMTOM_CRON)
    assert not any(budget.tomtom_due(c) for c in _crons() if c != budget.TOMTOM_CRON)


def test_here_blocked_and_key_not_passed(tmp_path, monkeypatch):
    assert "here" in budget.BLOCKED
    assert "HERE_API_KEY" not in WORKFLOW
    called = []
    monkeypatch.setenv("HERE_API_KEY", "dummy")
    monkeypatch.setattr(run.here, "collect", lambda *a, **k: called.append(1) or ([], []))
    run.main(["--sources", "here", "--out", str(tmp_path)])
    assert not called
