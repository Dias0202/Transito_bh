"""Safety "what if" scenarios built only on effects measured in this project.

Every scenario says where its effect comes from (`source`): a model fitted here
(with its CI) or an external assumption (with citation). Uncertainty is
propagated by Monte Carlo: effect drawn from a log-normal matching the 95% CI,
baseline counts drawn as Poisson around the observed recent rate.

Baseline: crashes in the last 24 complete months (consistent geocoding since
2024, see docs/data_audit.md), annualised.

Scenarios
1. Speed bumps at the N highest-crash places *within the conditions where the
   effect was measured*: >= 90% of the crashes within 100 m on local streets
   (residential/tertiary; measured bumps: median share 100%), and a crash rate no
   higher than the 99th percentile around measured bumps (extrapolating to busier
   places is outside the evidence). Not within 100 m of an existing bump; sites
   >= 200 m apart so no crash is counted twice.
2. Speed cameras back at the sites removed in Nov 2025.
3. First rain after a dry spell: crashes attributable to it per year; a policy
   that removes a share p of that excess avoids p x excess (p is the lever).
4. Lower mean speed on the avenues with BHTrans radars: baseline speeds measured
   (radar detections); the crash response is the Power Model (Nilsson 2004:
   injury crashes ~ (v1/v0)^2), an external assumption, with the exponent drawn
   uniformly in [1.5, 2.5] for sensitivity; the speed reduction is the lever.

    python -m bhtraffic.sim.whatif   # -> processed/sim/whatif.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir
from bhtraffic.models.enforcement import _meters

DRAWS = 5000
BUMP_N = [10, 25, 50, 100, 150, 200, 300, 400, 500]
LOCAL = {"residential", "tertiary"}
MIN_LOCAL_SHARE = 0.9
rng = np.random.default_rng(0)


def lognormal_from_ci(point: float, lo: float, hi: float, n: int = DRAWS) -> np.ndarray:
    sd = (np.log(hi) - np.log(lo)) / (2 * 1.96)
    return np.exp(rng.normal(np.log(point), sd, n))


def summarize(x: np.ndarray) -> dict:
    return {"median": float(np.median(x)), "lo": float(np.percentile(x, 5)), "hi": float(np.percentile(x, 95))}


def recent_crashes(months: int = 24):
    from bhtraffic.models.enforcement import load

    c_all, sites, sm, bumps, through = load()
    c_all["road"] = crash_roads(c_all)
    end = through.to_period("M").to_timestamp()
    start = end - pd.DateOffset(months=months - 1)
    return c_all[c_all["ym"].between(start, end)].copy(), c_all, sites, sm, bumps, through, months


def _road_class(x: np.ndarray, y: np.ndarray) -> list[str]:
    from bhtraffic.geo import osm

    ox = osm._setup()
    G = ox.project_graph(ox.graph_from_place(osm.PLACE, network_type="drive", simplify=True), to_crs="EPSG:31983")
    e = ox.distance.nearest_edges(G, x, y)
    return [osm._cls(G.edges[u, v, k].get("highway")) for u, v, k in e]


def crash_roads(c: pd.DataFrame) -> pd.Series:
    """Road class of each crash's nearest OSM edge (cached)."""
    f = processed_dir("sim") / "crash_road_class.parquet"
    if f.exists():
        r = pd.read_parquet(f).set_index("boletim")["road"]
        if c["boletim"].isin(r.index).all():
            return c["boletim"].map(r)
    from pyproj import Transformer

    t = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
    x, y = t.transform(c["lon"].to_numpy(), c["lat"].to_numpy())
    road = pd.Series(_road_class(np.asarray(x), np.asarray(y)), index=c.index)
    pd.DataFrame({"boletim": c["boletim"], "road": road}).to_parquet(f, index=False)
    return road


def _within(points: pd.DataFrame, c: pd.DataFrame, radius: float, mask: np.ndarray | None = None) -> np.ndarray:
    clat, clon = c["lat"].to_numpy(), c["lon"].to_numpy()
    out = np.zeros(len(points))
    for i in range(0, len(points), 300):
        p = points.iloc[i:i + 300]
        d = _meters(p["lat"].to_numpy()[:, None], p["lon"].to_numpy()[:, None], clat[None, :], clon[None, :]) <= radius
        out[i:i + 300] = (d & mask[None, :]).sum(1) if mask is not None else d.sum(1)
    return out


def measured_support(c_all: pd.DataFrame, bumps: pd.DataFrame, local: np.ndarray) -> dict:
    """Crash rate and local share around the bumps whose effect was measured."""
    b = bumps.dropna(subset=["lat"])
    yrs = (c_all["ym"].max() - c_all["ym"].min()).days / 365.25
    n = _within(b, c_all, 100)
    return {"rate_p50": float(np.percentile(n / yrs, 50)), "rate_p99": float(np.percentile(n / yrs, 99))}


def bump_candidates(c: pd.DataFrame, bumps: pd.DataFrame, years: float, support: dict) -> pd.DataFrame:
    """Greedy, non-overlapping candidate sites ranked by crashes within 100 m, inside the measured support."""
    import h3

    from pyproj import Transformer

    c = c.copy()
    local = c["road"].isin(LOCAL).to_numpy()
    c["cell"] = [h3.latlng_to_cell(a, b, 10) for a, b in zip(c["lat"], c["lon"])]
    cand = c[local].groupby("cell").agg(lat=("lat", "mean"), lon=("lon", "mean"), n_cell=("boletim", "size")).reset_index()
    cand["n100"] = _within(cand, c, 100)
    cand["n100_local"] = _within(cand, c, 100, local)
    cand["per_year"] = cand["n100"] / years
    cand["local_share"] = cand["n100_local"] / cand["n100"].clip(lower=1)
    cand = cand[(cand["local_share"] >= MIN_LOCAL_SHARE) & (cand["per_year"] <= support["rate_p99"])]
    b = bumps.dropna(subset=["lat"])
    near = _within(cand, b.assign(ym=0), 100) > 0
    cand = cand[~near].sort_values("n100", ascending=False).reset_index(drop=True)
    t = Transformer.from_crs("EPSG:4326", "EPSG:31983", always_xy=True)
    cand["x"], cand["y"] = t.transform(cand["lon"].to_numpy(), cand["lat"].to_numpy())
    chosen = []
    for r in cand.itertuples():
        if all(np.hypot(r.x - q.x, r.y - q.y) >= 200 for q in chosen):
            chosen.append(r)
        if len(chosen) >= max(BUMP_N):
            break
    return pd.DataFrame(chosen)[["lat", "lon", "n100", "per_year", "local_share"]]


def scenario_bumps(c, c_all, bumps, months, effect) -> dict:
    years = months / 12
    support = measured_support(c_all, bumps, None)
    cand = bump_candidates(c, bumps, years, support)
    theta = lognormal_from_ci(effect["ratio"], effect["ci_low"], effect["ci_high"])
    curve = []
    for n in BUMP_N:
        if n > len(cand):
            break
        rate = cand["per_year"].head(n).to_numpy()
        base = rng.poisson(rate[None, :].repeat(DRAWS, 0)).sum(1)
        avoided = base * (1 - theta)
        curve.append({"n": n, "baseline_per_year": float(rate.sum()), "avoided": summarize(avoided)})
    return {"source": "measured (models.enforcement bumps main_over_placebo, cluster bootstrap)",
            "effect": effect, "support": support, "min_local_share": MIN_LOCAL_SHARE,
            "candidates_available": int(len(cand)), "curve": curve,
            "top_sites": cand.head(20)[["lat", "lon", "per_year", "local_share"]].round(5).to_dict("records")}


def scenario_cameras(c, sites, sm, months, effects: dict) -> dict:
    """Cameras back at the sites that lost them in Nov 2025."""
    from bhtraffic.models.enforcement import REMOVAL_MONTH

    s = sites[sites["family"] == "speed"].set_index("site")
    pres = sm[sm["site"].isin(s.index)].pivot_table(index="site", columns="snapshot", values="present", aggfunc="max").fillna(0)
    cols = sorted(pres.columns)
    before = max(x for x in cols if x < REMOVAL_MONTH)
    after = min(x for x in cols if x >= REMOVAL_MONTH)
    lost = pres.index[(pres[before] == 1) & (pres[after] == 0)]
    still_off = [i for i in lost if pres.loc[i, cols[-1]] == 0]  # not reinstalled at the last snapshot
    p = s.loc[still_off]
    d = _meters(p["lat"].to_numpy()[:, None], p["lon"].to_numpy()[:, None], c["lat"].to_numpy()[None, :], c["lon"].to_numpy()[None, :])
    near = (d <= 150).any(axis=0)  # a crash near two sites counts once
    base_rate = near.sum() / (months / 12)
    out = {"source": "measured (models.enforcement twfe_camera); effect not distinguishable from 1",
           "sites": int(len(still_off)), "baseline_per_year": float(base_rate), "variants": {}}
    for name, e in effects.items():
        theta = lognormal_from_ci(e["irr"], e["ci_low"], e["ci_high"])
        base = rng.poisson(base_rate, DRAWS)
        out["variants"][name] = {"effect": e, "avoided": summarize(base * (1 - theta))}
    return out


def scenario_first_rain(temporal: dict) -> dict:
    h = pd.read_parquet(processed_dir("models", "temporal") / "hourly.parquet")
    end = h["ts"].max()
    recent = h[h["ts"] > end - pd.DateOffset(months=24)]
    ev = {e["event"]: e for e in temporal["city"]}
    fr = recent[recent["first_rain"] == 1]
    years = 2.0
    obs = fr["y"].sum() / years
    irr = lognormal_from_ci(ev["first_rain"]["irr"], ev["first_rain"]["ci_low"], ev["first_rain"]["ci_high"])
    excess = rng.poisson(obs, DRAWS) * (1 - 1 / irr)  # crashes in first-rain hours above what rain alone gives
    rain = recent[recent["rain_any"] == 1]
    irr_r = lognormal_from_ci(ev["rain_any"]["irr"], ev["rain_any"]["ci_low"], ev["rain_any"]["ci_high"])
    rain_excess = rng.poisson(rain["y"].sum() / years, DRAWS) * (1 - 1 / irr_r)
    return {"source": "measured (models.temporal first_rain, rain_any); the policy share p is an assumption",
            "first_rain_hours_per_year": float(len(fr) / years), "crashes_in_first_rain_hours_per_year": float(obs),
            "excess_first_rain_per_year": summarize(excess),
            "rain_hours_per_year": float(len(rain) / years), "excess_rain_per_year": summarize(rain_excess)}


SPEED_DELTAS = [1, 2, 3, 5, 7, 10]  # km/h reduction of mean car speed


def scenario_speed(c: pd.DataFrame, months: int) -> dict | None:
    import glob

    d = processed_dir("radares")
    files = [f for f in glob.glob(str(d / "*.parquet")) if not f.endswith("_radars.parquet")]
    if not files:
        return None
    agg = pd.concat([pd.read_parquet(f, columns=["id_endereco", "classe", "n", "vel_mean"]) for f in files])
    car = agg[(agg["classe"] == "car") & agg["vel_mean"].notna()]
    v0 = (car["vel_mean"] * car["n"]).groupby(car["id_endereco"]).sum() / car.groupby("id_endereco")["n"].sum()
    dim = pd.concat([pd.read_parquet(f) for f in glob.glob(str(d / "*_radars.parquet"))]).groupby("id_endereco").agg(lat=("lat", "median"), lon=("lon", "median"))
    loc = dim.join(v0.rename("v0"), how="inner").dropna()
    dist = _meters(loc["lat"].to_numpy()[:, None], loc["lon"].to_numpy()[:, None], c["lat"].to_numpy()[None, :], c["lon"].to_numpy()[None, :])
    # assign each crash to its nearest radar location within 100 m (no double counting)
    nearest = np.where(dist.min(0) <= 100, dist.argmin(0), -1)
    base = np.bincount(nearest[nearest >= 0], minlength=len(loc)) / (months / 12)
    expo = rng.uniform(1.5, 2.5, DRAWS)
    curve = []
    for dv in SPEED_DELTAS:
        ratio = ((loc["v0"].to_numpy()[None, :] - dv) / loc["v0"].to_numpy()[None, :]) ** expo[:, None]
        counts = rng.poisson(np.repeat(base[None, :], DRAWS, 0))
        avoided = (counts * (1 - ratio)).sum(1)
        curve.append({"dv": dv, "avoided": summarize(avoided)})
    return {"source": "speeds measured (BHTrans radars); crash response = Power Model (Nilsson 2004), assumption; reduction = lever",
            "locations": int(len(loc)), "mean_speed": float(np.average(loc["v0"], weights=base + 1e-9)),
            "baseline_per_year": float(base.sum()), "exponent_range": [1.5, 2.5], "curve": curve}


def main() -> None:
    c, c_all, sites, sm, bumps, through, months = recent_crashes()
    enf = json.loads((processed_dir("models", "enforcement") / "effects.json").read_text("utf-8"))
    tmp = json.loads((processed_dir("models", "temporal") / "effects.json").read_text("utf-8"))
    res = {
        "baseline_window": f"{(through.to_period('M').to_timestamp() - pd.DateOffset(months=months - 1)).date()}..{through.date()}",
        "draws": DRAWS,
        "bumps": scenario_bumps(c, c_all, bumps, months, enf["bumps"]["main_over_placebo"]),
        "cameras": scenario_cameras(c, sites, sm, months, {
            "all_period": enf["speed"]["twfe_camera"],
            "since_2024": enf["speed"]["twfe_camera_since_2024"],
        }),
        "first_rain": scenario_first_rain(tmp),
        "speed": scenario_speed(c, months),
    }
    out = processed_dir("sim")
    (out / "whatif.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "bumps"} | {"bumps_curve": res["bumps"]["curve"], "bump_candidates": res["bumps"]["candidates_available"]}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
