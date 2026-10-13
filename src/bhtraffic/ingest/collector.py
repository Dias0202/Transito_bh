"""Consolidate collector snapshots (csv.gz on Drive) into one parquet per source.

Input layout (written by bhtraffic.collect.run, mirrored by rclone):
    <data_root>/raw/collector/<source>/date=YYYY-MM-DD/<source>_HHMMSSZ.csv.gz
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from bhtraffic.config import BRT, processed_dir, raw_dir


def files(source: str) -> list[Path]:
    return sorted(raw_dir("collector", source).glob("date=*/*.csv.gz"))


def load(source: str) -> pd.DataFrame:
    fs = files(source)
    if not fs:
        return pd.DataFrame()
    df = pd.concat((pd.read_csv(f) for f in fs), ignore_index=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["ts_brt"] = df["ts_utc"].dt.tz_convert(BRT)
    if source == "tomtom":
        df["delay_ratio"] = df["travelTimeInSeconds"] / df["noTrafficTravelTimeInSeconds"]
        df["speed_kmh"] = df["lengthInMeters"] / df["travelTimeInSeconds"] * 3.6
    if source == "here":
        df["speed_ratio"] = df["speed_ms"] / df["free_flow_ms"]
    return df


def build() -> dict[str, Path]:
    out = {}
    for source in ("tomtom", "here", "bus"):
        df = load(source)
        if df.empty:
            continue
        dest = processed_dir("collector") / f"{source}.parquet"
        df.to_parquet(dest, index=False)
        out[source] = dest
    return out


def coverage() -> pd.DataFrame:
    """Snapshots per source and day: spot gaps in the cron schedule."""
    rows = [
        {"source": s, "date": f.parent.name.removeprefix("date="), "file": f.name}
        for s in ("tomtom", "here", "bus")
        for f in files(s)
    ]
    if not rows:
        return pd.DataFrame(columns=["source", "date", "snapshots"])
    return pd.DataFrame(rows).groupby(["source", "date"]).size().rename("snapshots").reset_index()
