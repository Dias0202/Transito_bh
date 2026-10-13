"""Export aggregated, real data for the scrollytelling site (site/public/data).

Only aggregates leave the package: no raw rows, no personal data.

    python -m bhtraffic.export.site            # writes site/public/data/*.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bhtraffic.config import BRT, REPO_ROOT, processed_dir

OUT = REPO_ROOT / "site" / "public" / "data"

# Window for "current picture" metrics: last 5 complete years published.
RECENT_YEARS = 5


def _load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    d = processed_dir("sinistros")
    paths = [d / f"{n}.parquet" for n in ("ocorrencias", "veiculos", "pessoas")]
    if not all(p.exists() for p in paths):
        from bhtraffic.ingest import sinistros

        t = sinistros.build()
        return t["ocorrencias"], t["veiculos"], t["pessoas"]
    return tuple(pd.read_parquet(p) for p in paths)  # type: ignore[return-value]


def _dump(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.json"
    # allow_nan=False: NaN is not valid JSON and breaks the browser parser.
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    return p


def summary(o, v, p) -> dict:
    last = int(o["year"].max())
    recent = o[o["year"] > last - RECENT_YEARS]
    moto_bol = set(v.loc[v["grupo"] == "motorcycle", "boletim"])
    fatal_p = p[p["fatal"]]
    fatal_recent = fatal_p[fatal_p["boletim"].isin(recent["boletim"])]
    return {
        "first_year": int(o["year"].min()),
        "last_year": last,
        "recent_window": [last - RECENT_YEARS + 1, last],
        "crashes_total": int(len(o)),
        "crashes_last_year": int((o["year"] == last).sum()),
        "crashes_per_day_last_year": round(float((o["year"] == last).sum()) / (366 if last % 4 == 0 else 365), 1),
        "deaths_total": int(len(fatal_p)),
        "deaths_recent": int(len(fatal_recent)),
        "share_crashes_with_motorcycle_recent": round(recent["boletim"].isin(moto_bol).mean(), 3),
        "share_deaths_motorcycle_recent": round((fatal_recent["grupo_veiculo"] == "motorcycle").mean(), 3),
        "share_deaths_pedestrian_recent": round(fatal_recent["pedestre"].fillna(False).astype(bool).mean(), 3),
        "geocode_placeholders_removed": int(o["coord_placeholder"].sum()),
        "share_without_coords": round(float(o["lat"].isna().mean()), 3),
        "share_hour_informed": round(float(o["hour"].notna().mean()), 3),
    }


def yearly(o, p) -> list[dict]:
    deaths = p[p["fatal"]].merge(o[["boletim", "year"]], on="boletim").groupby("year").size()
    crashes = o.groupby("year").size()
    return [
        {"year": int(y), "crashes": int(crashes[y]), "deaths": int(deaths.get(y, 0))}
        for y in crashes.index
    ]


def clock(o) -> dict:
    """Crash counts by weekday x hour over the recent window (hour informed only)."""
    last = int(o["year"].max())
    r = o[(o["year"] > last - RECENT_YEARS) & o["hour"].notna()]
    m = r.groupby(["weekday", "hour"]).size().unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0)
    return {"weekday_hour": m.astype(int).values.tolist(), "n": int(len(r))}


def hexes(o) -> dict:
    """GeoJSON of H3 res-8 cells with crash counts in the recent window."""
    import h3

    last = int(o["year"].max())
    r = o[(o["year"] > last - RECENT_YEARS) & o["h3"].notna()]
    g = r.groupby("h3").agg(n=("boletim", "size"), fatal=("fatal", "sum"), regional=("regional", lambda s: s.mode().iat[0] if s.notna().any() else None))
    feats = []
    for cell, row in g.iterrows():
        ring = [[round(lon, 5), round(lat, 5)] for lat, lon in h3.cell_to_boundary(cell)]
        ring.append(ring[0])
        feats.append(
            {
                "type": "Feature",
                "properties": {"h3": cell, "n": int(row.n), "fatal": int(row.fatal), "regional": row.regional if isinstance(row.regional, str) else None},
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def regionals(o) -> list[dict]:
    """Per-regional stats + its worst cell centre, for the map camera path."""
    import h3

    last = int(o["year"].max())
    r = o[(o["year"] > last - RECENT_YEARS) & o["regional"].notna() & (o["regional"] != "HIPERCENTRO")]
    out = []
    for name, d in r.groupby("regional"):
        top = d["h3"].dropna().value_counts()
        lat, lon = h3.cell_to_latlng(top.index[0])
        out.append(
            {
                "regional": name,
                "crashes": int(len(d)),
                "fatal_crashes": int(d["fatal"].sum()),
                "top_cell": top.index[0],
                "top_cell_crashes": int(top.iat[0]),
                "center": [round(lon, 5), round(lat, 5)],
            }
        )
    return sorted(out, key=lambda x: -x["crashes"])


def vehicles(o, v, p) -> dict:
    last = int(o["year"].max())
    recent = set(o.loc[o["year"] > last - RECENT_YEARS, "boletim"])
    vr = v[v["boletim"].isin(recent)]
    pr = p[p["boletim"].isin(recent)]
    dead = pr[pr["fatal"]]
    # Pedestrians have no vehicle species; label them explicitly.
    dead_group = dead["grupo_veiculo"].where(~dead["pedestre"].fillna(False).astype(bool), "pedestrian")
    return {
        "involved": vr["grupo"].value_counts().astype(int).to_dict(),
        "deaths_by_road_user": dead_group.value_counts().astype(int).to_dict(),
        "deaths_pedestrians": int(dead["pedestre"].fillna(False).astype(bool).sum()),
        "moto_by_year": (
            v[v["grupo"] == "motorcycle"].merge(o[["boletim", "year"]], on="boletim")
            .groupby("year").size().astype(int).rename(index=int).to_dict()
        ),
    }


def bus_snapshot() -> dict | None:
    """Live PBH bus positions at export time (aggregated speed stats + points)."""
    from bhtraffic.collect import bus

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows, errors = bus.collect(ts)
    if not rows:
        print("bus snapshot failed:", errors, file=sys.stderr)
        return None
    df = pd.DataFrame(rows).dropna(subset=["lat", "lon"])
    df = df[df["lat"].between(-20.2, -19.6) & df["lon"].between(-44.3, -43.7)]
    return {
        "ts_utc": ts,
        "ts_brt": datetime.fromisoformat(ts).astimezone(BRT).strftime("%Y-%m-%d %H:%M"),
        "vehicles": int(df["vehicle"].nunique()),
        "lines": int(df["line"].nunique()),
        "median_speed_kmh": float(df["speed_kmh"].median()),
        "share_reporting_under_5kmh": round(float((df["speed_kmh"] < 5).mean()), 3),
        "median_speed_moving_kmh": float(df.loc[df["speed_kmh"] >= 5, "speed_kmh"].median()),
        "points": df[["lon", "lat", "speed_kmh"]].round({"lon": 5, "lat": 5, "speed_kmh": 0}).values.tolist(),
    }


def main() -> int:
    o, v, p = _load()
    written = [
        _dump("summary", summary(o, v, p)),
        _dump("yearly", yearly(o, p)),
        _dump("clock", clock(o)),
        _dump("hexes", hexes(o)),
        _dump("regionals", regionals(o)),
        _dump("vehicles", vehicles(o, v, p)),
    ]
    snap = bus_snapshot()
    if snap:
        written.append(_dump("bus", snap))
    for w in written:
        print(f"{w.relative_to(REPO_ROOT)}  {w.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
