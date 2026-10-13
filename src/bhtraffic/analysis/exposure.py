"""Exposure: crash involvement per vehicle passing, motorcycles vs other vehicles.

At each BHTrans radar location we know how many vehicles of each class passed
(per-vehicle detections, 15-min bins) and, from the crash data, how many injury
crashes happened within RADIUS_M on the same days. Crashes are split by whether a
motorcycle was involved (vehicles table, available up to 2024; radar data covers
2021-2023).

    involvement rate (moto)  = moto-involved crashes   / motorcycle passages
    involvement rate (other) = crashes without a moto  / other-vehicle passages
    rate ratio = moto / other   (bootstrap over locations)

A crash near a radar may involve vehicles that never passed it, so this is an
area-level exposure comparison, not a per-trip risk; it is the honest version of
"12.5% of traffic, 75% of crashes".

    python -m bhtraffic.analysis.exposure   # -> processed/analysis/exposure.json
"""
from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir
from bhtraffic.models.enforcement import _meters

RADIUS_M = 100
REPS = 2000


def radar_locations() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = processed_dir("radares")
    agg = pd.concat([pd.read_parquet(f) for f in glob.glob(str(d / "*.parquet")) if not f.endswith("_radars.parquet")],
                    ignore_index=True)
    dim = pd.concat([pd.read_parquet(f) for f in glob.glob(str(d / "*_radars.parquet"))]).drop_duplicates(["id_endereco", "sentido"])
    # One location = one id_endereco (both directions of a camera pair share it).
    loc = dim.groupby("id_endereco").agg(lat=("lat", "median"), lon=("lon", "median"), endereco=("endereco", "first"),
                                         vel_via=("vel_via", "median")).reset_index()
    agg["date"] = agg["bin"].dt.normalize()
    return agg, loc


def build() -> dict:
    agg, loc = radar_locations()
    s = processed_dir("sinistros")
    occ = pd.read_parquet(s / "ocorrencias.parquet")
    occ = occ[occ["lat"].notna() & ~occ["coord_placeholder"]].copy()
    occ["date"] = occ["dt"].dt.normalize()
    veh = pd.read_parquet(s / "veiculos.parquet")
    moto = set(veh.loc[veh["grupo"] == "motorcycle", "boletim"])
    occ["moto"] = occ["boletim"].isin(moto)

    vol = agg.groupby(["id_endereco", "classe"])["n"].sum().unstack(fill_value=0)
    days = agg.groupby("id_endereco")["date"].apply(lambda x: set(x.unique()))
    loc = loc[loc["id_endereco"].isin(vol.index)].reset_index(drop=True)
    rows = []
    for r in loc.itertuples():
        dset = days.loc[r.id_endereco]
        c = occ[occ["date"].isin(dset)]
        near = _meters(r.lat, r.lon, c["lat"].to_numpy(), c["lon"].to_numpy()) <= RADIUS_M
        cc = c[near]
        v = vol.loc[r.id_endereco]
        rows.append({"id_endereco": r.id_endereco, "endereco": r.endereco, "days": len(dset),
                     "moto_passages": int(v.get("motorcycle", 0)),
                     "other_passages": int(v.sum() - v.get("motorcycle", 0)),
                     "crashes_moto": int(cc["moto"].sum()), "crashes_other": int((~cc["moto"]).sum())})
    t = pd.DataFrame(rows)

    def ratio(ix):
        x = t.iloc[ix]
        return (x["crashes_moto"].sum() / x["moto_passages"].sum()) / (x["crashes_other"].sum() / x["other_passages"].sum())

    rng = np.random.default_rng(0)
    idx = np.arange(len(t))
    boot = [ratio(rng.choice(idx, len(idx))) for _ in range(REPS)]
    tot = t[["moto_passages", "other_passages", "crashes_moto", "crashes_other"]].sum()
    out = {
        "locations": int(len(t)), "location_days": int(t["days"].sum()), "radius_m": RADIUS_M,
        "period": [str(agg["date"].min().date()), str(agg["date"].max().date())],
        "moto_share_of_passages": float(tot["moto_passages"] / (tot["moto_passages"] + tot["other_passages"])),
        "moto_share_of_crashes": float(tot["crashes_moto"] / (tot["crashes_moto"] + tot["crashes_other"])),
        "crashes_per_million_moto": float(tot["crashes_moto"] / tot["moto_passages"] * 1e6),
        "crashes_per_million_other": float(tot["crashes_other"] / tot["other_passages"] * 1e6),
        "rate_ratio": float(ratio(idx)), "ci_low": float(np.percentile(boot, 2.5)), "ci_high": float(np.percentile(boot, 97.5)),
        "totals": {k: int(v) for k, v in tot.items()},
    }
    p = processed_dir("analysis")
    t.to_parquet(p / "exposure_sites.parquet", index=False)
    (p / "exposure.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), "utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=False))
