"""PBH real-time bus positions (no key). The source keeps no history,
so polling it is the only way to build a time series.

Dataset: dados.pbh.gov.br "Tempo Real Onibus - Coordenada atualizada".
Columns: EV event code, HR timestamp YYYYMMDDhhmmss, LT/LG lat/lon (comma
decimal), NV vehicle id, VL speed km/h, NL line id, DG heading degrees,
SV direction, DT distance travelled. Check the official data dictionary.
"""
from __future__ import annotations

import csv
import io

from bhtraffic.collect.http import get

URL = "https://temporeal.pbh.gov.br"


def fetch_csv() -> str:
    return get(URL, {"param": "C"}, timeout=30).decode("latin-1")


def _num(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.strip().replace(",", "."))
    except ValueError:
        return None


def parse_csv(text: str, ts: str) -> list[dict]:
    reader = csv.reader(io.StringIO(text), delimiter=";")
    header = [h.strip() for h in next(reader)]
    rows = []
    for raw in reader:
        if len(raw) != len(header):
            continue
        r = dict(zip(header, (v.strip() for v in raw)))
        rows.append(
            {
                "ts_utc": ts,
                "event": r.get("EV"),
                "gps_time": r.get("HR"),
                "lat": _num(r.get("LT")),
                "lon": _num(r.get("LG")),
                "vehicle": r.get("NV"),
                "speed_kmh": _num(r.get("VL")),
                "line": r.get("NL"),
                "heading": _num(r.get("DG")),
                "direction": r.get("SV"),
                "distance": _num(r.get("DT")),
            }
        )
    return rows


def collect(ts: str) -> tuple[list[dict], list[str]]:
    try:
        return parse_csv(fetch_csv(), ts), []
    except Exception as e:
        return [], [f"bus: {type(e).__name__}: {e}"]
