"""HERE Traffic Flow API v7: per-segment speed/jam factor inside bounding boxes.

Docs: https://www.here.com/docs/bundle/traffic-api-v7-api-reference/page/index.html
"""
from __future__ import annotations

from bhtraffic.collect.http import get_json
from bhtraffic.geo.corridors import BBox

URL = "https://data.traffic.hereapi.com/v7/flow"


def fetch_flow(b: BBox, key: str) -> dict:
    return get_json(
        URL,
        {
            "apiKey": key,
            "in": f"bbox:{b.west},{b.south},{b.east},{b.north}",
            "locationReferencing": "shape",
        },
        timeout=30,
    )


def _centroid(location: dict) -> tuple[float | None, float | None]:
    pts = [p for link in location.get("shape", {}).get("links", []) for p in link.get("points", [])]
    if not pts:
        return None, None
    return (
        round(sum(p["lat"] for p in pts) / len(pts), 6),
        round(sum(p["lng"] for p in pts) / len(pts), 6),
    )


def parse_flow(payload: dict, bbox_id: str, ts: str) -> list[dict]:
    rows = []
    for r in payload.get("results", []):
        loc, flow = r.get("location", {}), r.get("currentFlow", {})
        lat, lon = _centroid(loc)
        rows.append(
            {
                "ts_utc": ts,
                "bbox_id": bbox_id,
                "description": loc.get("description"),
                "length_m": loc.get("length"),
                "lat": lat,
                "lon": lon,
                "speed_ms": flow.get("speed"),
                "speed_uncapped_ms": flow.get("speedUncapped"),
                "free_flow_ms": flow.get("freeFlow"),
                "jam_factor": flow.get("jamFactor"),
                "confidence": flow.get("confidence"),
                "traversability": flow.get("traversability"),
            }
        )
    return rows


def collect(bboxes: list[BBox], key: str, ts: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    for b in bboxes:
        try:
            rows.extend(parse_flow(fetch_flow(b, key), b.id, ts))
        except Exception as e:
            errors.append(f"here {b.id}: {type(e).__name__}: {e}")
    return rows, errors
