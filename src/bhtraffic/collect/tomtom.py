"""TomTom Routing API: live travel time per corridor direction.

Only Routing is used (not Flow Segment) to stay inside the free tier.
Docs: https://developer.tomtom.com/routing-api/documentation/routing/calculate-route
"""
from __future__ import annotations

from bhtraffic.collect.http import get_json
from bhtraffic.geo.corridors import Corridor, LatLon

BASE = "https://api.tomtom.com/routing/1/calculateRoute"

FIELDS = (
    "lengthInMeters",
    "travelTimeInSeconds",
    "trafficDelayInSeconds",
    "trafficLengthInMeters",
    "noTrafficTravelTimeInSeconds",
    "historicTrafficTravelTimeInSeconds",
    "liveTrafficIncidentsTravelTimeInSeconds",
)


def route_url(path: tuple[LatLon, ...]) -> str:
    locs = ":".join(f"{lat:.5f},{lon:.5f}" for lat, lon in path)
    return f"{BASE}/{locs}/json"


def fetch_route(path: tuple[LatLon, ...], key: str) -> dict:
    return get_json(
        route_url(path),
        {
            "key": key,
            "traffic": "true",
            "travelMode": "car",
            "routeType": "fastest",
            "computeTravelTimeFor": "all",
            "routeRepresentation": "summaryOnly",
        },
    )


def parse_route(payload: dict) -> dict:
    summary = payload["routes"][0]["summary"]
    return {f: summary.get(f) for f in FIELDS}


def collect(corridors: list[Corridor], key: str, ts: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    for c in corridors:
        for direction, path in c.directions().items():
            try:
                rec = parse_route(fetch_route(path, key))
            except Exception as e:  # one corridor failing must not kill the run
                errors.append(f"tomtom {c.id}/{direction}: {type(e).__name__}: {e}")
                continue
            rows.append({"ts_utc": ts, "corridor_id": c.id, "direction": direction, **rec})
    return rows, errors
