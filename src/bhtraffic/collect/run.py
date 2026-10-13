"""Collect one traffic snapshot and write gzip CSVs.

    python -m bhtraffic.collect.run --out out/
    python -m bhtraffic.collect.run --dry-run   # parse fixtures, no network

Output layout (mirrored to Google Drive by the workflow via rclone):
    <out>/<source>/date=YYYY-MM-DD/<source>_<HHMMSS>Z.csv.gz

CSV + gzip instead of parquet keeps this module stdlib-only, so the
GitHub Actions job runs without installing packages (each run must stay
under 60 s of billed time). Notebooks convert to parquet downstream.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from bhtraffic.collect import budget, bus, here, tomtom
from bhtraffic.config import REPO_ROOT
from bhtraffic.geo import corridors as corridors_mod

FIXTURES = REPO_ROOT / "tests" / "fixtures"
SOURCES = ("tomtom", "here", "bus")


def write_csv_gz(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _dry_run(ts: str) -> dict[str, tuple[list[dict], list[str]]]:
    tt = tomtom.parse_route(json.loads((FIXTURES / "tomtom_route.json").read_text("utf-8")))
    return {
        "tomtom": ([{"ts_utc": ts, "corridor_id": "fixture", "direction": "inbound", **tt}], []),
        "here": (here.parse_flow(json.loads((FIXTURES / "here_flow.json").read_text("utf-8")), "fixture", ts), []),
        "bus": (bus.parse_csv((FIXTURES / "bus.csv").read_text("latin-1"), ts), []),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "out")
    ap.add_argument("--sources", default=",".join(SOURCES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts = now.isoformat()
    wanted = set(args.sources.split(","))

    if args.dry_run:
        results = _dry_run(ts)
    else:
        corridors, bboxes = corridors_mod.load()
        results: dict[str, tuple[list[dict], list[str]]] = {}
        tt_key, here_key = os.environ.get("TOMTOM_API_KEY"), os.environ.get("HERE_API_KEY")
        schedule = os.environ.get("BHTRAFFIC_SCHEDULE")
        if "tomtom" in wanted:
            if not budget.tomtom_due(schedule):
                results["tomtom"] = ([], [f"tomtom: not on budget schedule ({schedule}), skipped"])
            else:
                results["tomtom"] = tomtom.collect(corridors, tt_key, ts) if tt_key else ([], ["tomtom: TOMTOM_API_KEY not set, skipped"])
        if "here" in wanted:
            if "here" in budget.BLOCKED:
                results["here"] = ([], [f"here: blocked, {budget.BLOCKED['here']}"])
            else:
                results["here"] = here.collect(bboxes, here_key, ts) if here_key else ([], ["here: HERE_API_KEY not set, skipped"])
        if "bus" in wanted:
            results["bus"] = bus.collect(ts)

    total = 0
    stamp = now.strftime("%H%M%S")
    for source, (rows, errors) in results.items():
        for e in errors:
            print(f"WARN {e}", file=sys.stderr)
        if rows:
            path = args.out / source / f"date={now:%Y-%m-%d}" / f"{source}_{stamp}Z.csv.gz"
            write_csv_gz(rows, path)
            print(f"{source}: {len(rows)} rows -> {path}")
            total += len(rows)
        else:
            print(f"{source}: 0 rows")

    # Fail the job only when nothing at all was collected.
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
