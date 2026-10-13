"""Temporary bridge: dispatch the collector on the cron slots while GitHub's scheduler
is not firing for this repository (observed 2026-10-13: manual runs work, zero
`schedule` runs in 4+ hours after two re-registrations).

Same slots as .github/workflows/collector.yml. TomTom slots dispatch a full run;
every other slot dispatches `mode=bus-only`, so the TomTom budget is unchanged
(tests/test_budget.py). Before dispatching, the bridge checks whether GitHub already
ran that slot via `schedule`; if the scheduler starts working, the bridge stands down.

The token is read from GH_TOKEN in the environment and kept in memory only.

    set GH_TOKEN=...   (PowerShell: $env:GH_TOKEN="...")
    python scripts/dispatch_bridge.py
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "Dias0202/Transito_bh"
API = f"https://api.github.com/repos/{REPO}/actions"
PEAK_HOURS = set(range(9, 13)) | set(range(19, 23))
OFFPEAK_HOURS = set(range(0, 9)) | set(range(13, 19)) | {23}


def slot(now: datetime) -> str | None:
    """'' (full run), 'bus-only' or None, mirroring the workflow crons (UTC)."""
    wd, h, m = now.weekday() < 5, now.hour, now.minute
    if wd and h in PEAK_HOURS and m in (7, 37):
        return ""
    if wd and h in PEAK_HOURS and m in (22, 52):
        return "bus-only"
    if wd and h in OFFPEAK_HOURS and m == 37:
        return "bus-only"
    if not wd and m == 37:
        return "bus-only"
    return None


def call(token: str, method: str, url: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def scheduled_since(token: str, since: datetime) -> bool:
    runs = call(token, "GET", f"{API}/runs?event=schedule&per_page=5").get("workflow_runs", [])
    return any(datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= since for r in runs)


def main() -> None:
    token = os.environ["GH_TOKEN"]
    done: set[str] = set()
    print("bridge up", flush=True)
    while True:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        mode = slot(now)
        key = now.isoformat()
        if mode is not None and key not in done:
            # Give GitHub's own scheduler 2 minutes; dispatch only if it did not run.
            time.sleep(120)
            try:
                if scheduled_since(token, now - timedelta(minutes=1)):
                    print(f"{key} scheduler ran it, standing down", flush=True)
                else:
                    call(token, "POST", f"{API}/workflows/collector.yml/dispatches", {"ref": "main", "inputs": {"mode": mode}})
                    print(f"{key} dispatched mode={mode or 'full'}", flush=True)
            except Exception as e:  # network hiccup: log and keep going
                print(f"{key} error {e!r}", flush=True)
            done.add(key)
        time.sleep(20)


if __name__ == "__main__":
    main()
