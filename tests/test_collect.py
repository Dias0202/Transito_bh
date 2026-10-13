import gzip
import json
from pathlib import Path

from bhtraffic.collect import bus, here, run, tomtom
from bhtraffic.geo import corridors

FIX = Path(__file__).parent / "fixtures"
TS = "2026-10-13T21:00:00+00:00"


def test_corridors_schema():
    cs, bbs = corridors.load()
    ids = [c.id for c in cs]
    assert len(ids) == len(set(ids)), "duplicate corridor ids"
    # 2 directions per corridor must fit TomTom free tier at ~48 runs/day
    assert len(cs) * 2 * 48 < 2500
    for c in cs:
        assert len(c.path) >= 2
        for lat, lon in c.path:
            # Rough RMBH envelope
            assert -20.3 < lat < -19.4 and -44.4 < lon < -43.6, (c.id, lat, lon)
        d = c.directions()
        assert d["outbound"] == tuple(reversed(d["inbound"]))
    for b in bbs:
        assert b.west < b.east and b.south < b.north


def test_tomtom_parse_and_url():
    payload = json.loads((FIX / "tomtom_route.json").read_text("utf-8"))
    rec = tomtom.parse_route(payload)
    assert rec["travelTimeInSeconds"] == 1320
    assert rec["noTrafficTravelTimeInSeconds"] == 840
    url = tomtom.route_url(((-19.9, -43.9), (-19.8, -43.95)))
    assert url.endswith("/-19.90000,-43.90000:-19.80000,-43.95000/json")


def test_here_parse():
    payload = json.loads((FIX / "here_flow.json").read_text("utf-8"))
    rows = here.parse_flow(payload, "centro", TS)
    assert len(rows) == 2
    assert rows[0]["lat"] is not None and rows[0]["jam_factor"] == 6.8
    assert rows[1]["lat"] is None  # no shape -> no centroid


def test_bus_parse_real_snapshot():
    rows = bus.parse_csv((FIX / "bus.csv").read_text("latin-1"), TS)
    assert len(rows) == 20
    r = rows[0]
    assert -20.2 < r["lat"] < -19.6 and -44.2 < r["lon"] < -43.7
    assert r["speed_kmh"] is not None and r["vehicle"]


def test_dry_run_writes_gz(tmp_path):
    assert run.main(["--dry-run", "--out", str(tmp_path)]) == 0
    files = sorted(tmp_path.rglob("*.csv.gz"))
    assert {f.parts[-3] for f in files} == {"tomtom", "here", "bus"}
    with gzip.open(files[0], "rt", encoding="utf-8") as f:
        assert f.readline().startswith("ts_utc,")
