import numpy as np
import pandas as pd

from bhtraffic.ingest import recentes
from bhtraffic.models import enforcement


def test_xy_parses_point_and_linestring():
    x, y = recentes._xy(pd.Series(["POINT (604936.7 7792129.51)", "LINESTRING (615725.70 7798182.97, 615732.00 7798184.34)", None]))
    assert x.iloc[0] == 604936.7 and y.iloc[1] == 7798182.97
    assert np.isnan(x.iloc[2])


def test_last_complete_month():
    full = pd.Series(pd.to_datetime(["2026-06-30 23:00", "2026-07-31 10:00"]))
    partial = pd.Series(pd.to_datetime(["2026-07-31 10:00", "2026-08-22 12:10"]))
    assert recentes.last_complete_month(full) == pd.Timestamp("2026-07-31")
    assert recentes.last_complete_month(partial) == pd.Timestamp("2026-07-31")


def test_cluster_links_close_points_only():
    x = np.array([0.0, 30.0, 60.0, 500.0])
    lab = recentes._cluster(x, np.zeros(4), 50)
    assert lab[0] == lab[1] == lab[2] and lab[3] != lab[0]  # chain within 50 m, far point alone


def test_site_status_from_snapshots():
    snaps = pd.to_datetime(["2025-09-01", "2025-10-01", "2025-11-01", "2025-12-01"])
    rows = []
    for s in snaps:
        rows.append({"snapshot": s, "family": "speed", "x": 1000.0, "y": 1000.0})            # always
        if s <= snaps[1]:
            rows.append({"snapshot": s, "family": "speed", "x": 5000.0, "y": 1000.0})        # removed
        if s >= snaps[2]:
            rows.append({"snapshot": s, "family": "speed", "x": 9000.0, "y": 1000.0})        # installed
    dev = pd.DataFrame(rows).assign(lat=0.0, lon=0.0, local="x", speed_limit=60, tipo="t")
    s, sm = recentes.sites(dev)
    assert sorted(s["status"]) == ["always", "installed", "removed"]
    assert sm.groupby("site")["present"].sum().sort_values().tolist() == [2, 2, 4]


def test_counts_near_radius():
    pts = pd.DataFrame({"site": ["a"], "lat": [-19.92], "lon": [-43.94]})
    cr = pd.DataFrame({"lat": [-19.92, -19.9209, -19.93], "lon": [-43.94, -43.94, -43.94],
                       "ym": pd.to_datetime(["2025-01-01"] * 3)})
    y = enforcement.counts_near(pts, cr, 150, "site")
    assert y["y"].sum() == 2  # 0 m and ~100 m inside, ~1.1 km outside
