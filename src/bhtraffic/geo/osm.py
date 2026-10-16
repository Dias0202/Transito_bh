"""OpenStreetMap road features per H3 cell (free; Overpass via osmnx, cached).

Snapshot is current OSM (2026), applied to 2011-2024 crashes: road changes in
between (new BRT lanes, roundabouts) are not reflected. Stated as a limitation.

    python -m bhtraffic.geo.osm   # -> processed/osm/h3_features.parquet
"""
from __future__ import annotations

import h3
import numpy as np
import pandas as pd

from bhtraffic.config import CRS_UTM_BH, H3_RES, processed_dir, raw_dir

PLACE = "Belo Horizonte, Minas Gerais, Brazil"
ROAD_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential"]
POINT_TAGS = {"highway": ["traffic_signals", "crossing", "bus_stop", "stop", "give_way", "speed_camera"],
              "junction": ["roundabout"]}


def _setup():
    import osmnx as ox

    ox.settings.use_cache = True
    ox.settings.cache_folder = str(raw_dir("osm", "cache"))
    ox.settings.requests_timeout = 300
    return ox


def _cls(v) -> str:
    v = v[0] if isinstance(v, list) else v
    v = str(v).replace("_link", "")
    return v if v in ROAD_CLASSES else "other"


def _num(v):
    v = v[0] if isinstance(v, list) else v
    try:
        return float(str(v).split()[0].split(";")[0])
    except (ValueError, TypeError):
        return np.nan


def build() -> pd.DataFrame:
    ox = _setup()
    G = ox.graph_from_place(PLACE, network_type="drive", simplify=True)
    nodes, edges = ox.graph_to_gdfs(G)

    # Edges: length by class, lanes and maxspeed, assigned to the cell of their midpoint.
    mid = edges.geometry.to_crs(CRS_UTM_BH).interpolate(0.5, normalized=True).to_crs("EPSG:4326")
    e = pd.DataFrame({
        "h3": [h3.latlng_to_cell(p.y, p.x, H3_RES) for p in mid],
        "cls": edges["highway"].map(_cls),
        "len_km": edges["length"].to_numpy() / 1000,
        "lanes": edges["lanes"].map(_num) if "lanes" in edges else np.nan,
        "maxspeed": edges["maxspeed"].map(_num) if "maxspeed" in edges else np.nan,
        "oneway": edges["oneway"].astype(bool).to_numpy() if "oneway" in edges else False,
    })
    by_cls = e.pivot_table(index="h3", columns="cls", values="len_km", aggfunc="sum", fill_value=0)
    by_cls.columns = [f"km_{c}" for c in by_cls.columns]
    agg = e.groupby("h3").agg(km_total=("len_km", "sum"), lanes_mean=("lanes", "mean"),
                              maxspeed_max=("maxspeed", "max"), maxspeed_mean=("maxspeed", "mean"),
                              oneway_share=("oneway", "mean"))

    # Nodes: intersections (3+ streets) per cell.
    n = pd.DataFrame({"h3": [h3.latlng_to_cell(y, x, H3_RES) for y, x in zip(nodes["y"], nodes["x"])],
                      "street_count": nodes["street_count"].to_numpy()})
    inter = n[n["street_count"] >= 3].groupby("h3").size().rename("intersections")

    # Point features.
    # osmnx 2 repeats the full city polygon once per tag in the Overpass query, which
    # gets a 413; query a simplified envelope and clip back to the exact boundary.
    city = ox.geocode_to_gdf(PLACE).geometry.iloc[0]
    pts = ox.features_from_polygon(city.buffer(0.005).simplify(0.002), POINT_TAGS)
    pts = pts[pts.geometry.notna() & pts.geometry.intersects(city)]
    c = pts.geometry.representative_point()
    hw = pts["highway"].astype("string") if "highway" in pts else pd.Series(pd.NA, index=pts.index, dtype="string")
    kind = hw.where(hw.isin(POINT_TAGS["highway"]).fillna(False).astype(bool), pd.NA)
    if "junction" in pts:
        kind = kind.mask((pts["junction"].astype("string") == "roundabout").fillna(False).astype(bool), "roundabout")
    keep = kind.notna().to_numpy()
    pts, c, kind = pts[keep], c[keep], kind[keep]
    p = pd.DataFrame({"h3": [h3.latlng_to_cell(g.y, g.x, H3_RES) for g in c], "kind": kind.astype(str).to_numpy()})
    pc = p.pivot_table(index="h3", columns="kind", aggfunc="size", fill_value=0)
    pc.columns = [f"n_{k}" for k in pc.columns]

    out = pd.concat([by_cls, agg, inter, pc], axis=1).fillna({"intersections": 0})
    out = out.fillna({c: 0 for c in out.columns if c.startswith(("km_", "n_"))})
    out.index.name = "h3"
    path = processed_dir("osm") / "h3_features.parquet"
    out.reset_index().to_parquet(path, index=False)
    return out.reset_index()


if __name__ == "__main__":
    df = build()
    print(df.shape)
    print(df.describe().T.round(2).to_string())
