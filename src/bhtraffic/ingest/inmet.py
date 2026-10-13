"""INMET automatic-station hourly weather for Belo Horizonte (free open data).

Source: https://portal.inmet.gov.br/dadoshistoricos — one ZIP per year with a CSV
per station. We keep only station A521 (BELO HORIZONTE - PAMPULHA). Times in the
files are UTC; output is converted to BRT (America/Sao_Paulo) to match crashes.

    python -m bhtraffic.ingest.inmet 2011 2024   # -> processed/weather/inmet_A521.parquet
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

from bhtraffic.config import HTTP_USER_AGENT, processed_dir, raw_dir

BASE = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
STATION = "A521"

# Column prefixes are stable across years even though full names vary slightly.
COLS = {
    "PRECIPITA": "rain_mm",
    "TEMPERATURA DO AR - BULBO SECO": "temp_c",
    "UMIDADE RELATIVA DO AR, HORARIA": "rh_pct",
}


def download(year: int) -> Path:
    dest = raw_dir("inmet") / f"{year}.zip"
    if dest.exists():
        return dest
    tmp = dest.with_suffix(".part")
    with requests.get(BASE.format(year=year), headers={"User-Agent": HTTP_USER_AGENT}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    tmp.replace(dest)
    return dest


def parse_station_csv(text: str) -> pd.DataFrame:
    """Parse one INMET station CSV (8 metadata lines, ';' separated, ',' decimals)."""
    df = pd.read_csv(io.StringIO(text), sep=";", skiprows=8, decimal=",", dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    date_col = next(c for c in df.columns if c.startswith("DATA"))
    hour_col = next(c for c in df.columns if c.startswith("HORA"))
    # Dates are "2019/01/01" or "2011-01-01"; hours "0000 UTC" or "00:00".
    date = df[date_col].str.replace("/", "-", regex=False)
    hour = df[hour_col].str.extract(r"(\d{2}):?(\d{2})").agg(":".join, axis=1)
    ts = pd.to_datetime(date + " " + hour, errors="coerce", utc=True)
    out = pd.DataFrame({"ts": ts.dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)})
    for prefix, name in COLS.items():
        col = next((c for c in df.columns if c.startswith(prefix)), None)
        v = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce") if col else pd.NA
        out[name] = v
    out = out.dropna(subset=["ts"])
    # INMET uses -9999 for missing.
    for name in COLS.values():
        out.loc[out[name] <= -9999, name] = pd.NA
    return out


def station_year(year: int) -> pd.DataFrame:
    with zipfile.ZipFile(download(year)) as z:
        names = [n for n in z.namelist() if f"_{STATION}_" in n.upper()]
        if not names:
            return pd.DataFrame()
        return parse_station_csv(z.read(names[0]).decode("latin-1"))


def build(years: range) -> Path:
    df = pd.concat([station_year(y) for y in years], ignore_index=True)
    df = df.drop_duplicates("ts").sort_values("ts")
    out = processed_dir("weather") / f"inmet_{STATION}.parquet"
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    a, b = (int(x) for x in sys.argv[1:3])
    print(build(range(a, b + 1)))
