"""Do speed cameras and speed bumps change injury crashes nearby?

Design fixed before looking at results:

Cameras (2022-06 -> last complete crash month)
- Unit: enforcement site x month (sites from bhtraffic.ingest.recentes). Presence
  comes from the monthly device snapshots (months without a snapshot inherit the
  previous one). Outcome: injury crashes within RADIUS_M of the site.
- Two-way fixed-effects Poisson: site FE absorbs where the site is; month FE
  absorbs citywide shocks (weather, holidays, trend). The camera coefficient is
  identified only by sites that gained or lost a device. SEs clustered by site.
- Event study around the mass removal of Nov 2025: sites that lost their camera
  then vs sites that kept one, months -12..+8. Leads near zero = no pre-trend.

Speed bumps (installed 2017-2025)
- Stacked before/after: crashes within BUMP_RADIUS_M in the 12 months before vs
  the 12 months after installation (install month excluded), each window scaled
  by the citywide crash count in the same months (ratio of ratios). Bootstrap
  over bumps for the CI.

Caveats stated with the results: cameras are placed where crashes were high
(regression to the mean biases installs towards "works"); the snapshot shows
the registry, not whether a device was physically present or issuing fines.

    python -m bhtraffic.models.enforcement   # -> processed/models/enforcement/*.json
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir

RADIUS_M = 150
BUMP_RADIUS_M = 100
WINDOW = 12
REMOVAL_MONTH = pd.Timestamp("2025-11-01")
EVENT_LEADS, EVENT_LAGS = 12, 8


def _meters(lat1, lon1, lat2, lon2):
    """Equirectangular distance in metres (fine at city scale)."""
    k = 111_320.0
    dx = (lon2 - lon1) * k * np.cos(np.radians((lat1 + lat2) / 2))
    dy = (lat2 - lat1) * k
    return np.hypot(dx, dy)


def load():
    s = processed_dir("sinistros")
    from bhtraffic.ingest.recentes import require_combined

    require_combined()
    c = pd.read_parquet(s / "ocorrencias_2011_2026.parquet")
    through = pd.Timestamp((s / "ocorrencias_2011_2026.complete_through.txt").read_text().strip())
    c = c[c["lat"].notna() & ~c["coord_placeholder"] & (c["dt"] <= through + pd.Timedelta(days=1))].copy()
    c["ym"] = c["dt"].dt.to_period("M").dt.to_timestamp()
    e = processed_dir("enforcement")
    return c, pd.read_parquet(e / "sites.parquet"), pd.read_parquet(e / "site_months.parquet"), \
        pd.read_parquet(e / "redutores.parquet"), through


def counts_near(points: pd.DataFrame, crashes: pd.DataFrame, radius: float, key: str) -> pd.DataFrame:
    """Crash counts per point x month within radius. Chunked to bound memory."""
    out = []
    clat, clon, cym = crashes["lat"].to_numpy(), crashes["lon"].to_numpy(), crashes["ym"].to_numpy()
    for i in range(0, len(points), 200):
        p = points.iloc[i:i + 200]
        d = _meters(p["lat"].to_numpy()[:, None], p["lon"].to_numpy()[:, None], clat[None, :], clon[None, :])
        rows, cols = np.nonzero(d <= radius)
        out.append(pd.DataFrame({key: p[key].to_numpy()[rows], "ym": cym[cols]}))
    df = pd.concat(out, ignore_index=True)
    return df.groupby([key, "ym"]).size().rename("y").reset_index()


def camera_panel(c, sites, sm, through, family="speed"):
    s = sites[sites["family"] == family]
    months = pd.date_range(sm["snapshot"].min().to_period("M").to_timestamp(), through.to_period("M").to_timestamp(), freq="MS")
    pres = (sm[sm["site"].isin(s["site"])]
            .assign(ym=lambda d: d["snapshot"].dt.to_period("M").dt.to_timestamp())
            .groupby(["site", "ym"])["present"].max().unstack())
    pres = pres.reindex(columns=months).ffill(axis=1).fillna(0).astype(int)  # months without snapshot inherit
    pres.columns.name = "ym"
    panel = pres.stack().rename("camera").reset_index()
    y = counts_near(s, c[c["ym"].between(months[0], months[-1])], RADIUS_M, "site")
    panel = panel.merge(y, on=["site", "ym"], how="left").fillna({"y": 0})
    return panel, pres


def fit_twfe(panel: pd.DataFrame, extra: list[str] | None = None):
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    rhs = " + ".join((extra or ["camera"]) + ["C(site)", "C(ym)"])
    # Drop sites with no crash in the whole window: they carry no information in a Poisson FE model.
    keep = panel.groupby("site")["y"].transform("sum") > 0
    d = panel[keep]
    return smf.glm(f"y ~ {rhs}", data=d, family=sm.families.Poisson()).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["site"])[0]})


def _irr(m, term):
    ci = m.conf_int().loc[term]
    return {"irr": float(np.exp(m.params[term])), "ci_low": float(np.exp(ci[0])), "ci_high": float(np.exp(ci[1])),
            "p": float(m.pvalues[term])}


def removal_event_study(panel: pd.DataFrame, pres: pd.DataFrame):
    """Sites with a camera in Oct 2025 that lost it in Nov 2025 vs sites that kept it."""
    before, after = REMOVAL_MONTH - pd.DateOffset(months=1), REMOVAL_MONTH
    if before not in pres.columns or after not in pres.columns:
        return None
    treated = pres.index[(pres[before] == 1) & (pres[after] == 0)]
    control = pres.index[(pres[before] == 1) & (pres[after] == 1)]
    d = panel[panel["site"].isin(treated.union(control))].copy()
    d["treated"] = d["site"].isin(treated).astype(int)
    d["rel"] = ((d["ym"].dt.year - after.year) * 12 + d["ym"].dt.month - after.month)
    d = d[d["rel"].between(-EVENT_LEADS, EVENT_LAGS)]
    terms = []
    for k in range(-EVENT_LEADS, EVENT_LAGS + 1):
        if k == -1:
            continue  # reference month
        name = f"ev_m{abs(k)}" if k < 0 else f"ev_p{k}"
        d[name] = ((d["rel"] == k) & (d["treated"] == 1)).astype(int)
        terms.append(name)
    d["post_treated"] = ((d["rel"] >= 0) & (d["treated"] == 1)).astype(int)
    did = fit_twfe(d, ["post_treated"])
    ev = fit_twfe(d, terms)
    pre_terms = [t for t in terms if t.startswith("ev_m")]
    # Joint Wald test that all leads are zero (pre-trend).
    wald = ev.wald_test(" , ".join(f"{t} = 0" for t in pre_terms), scalar=True)
    return {
        "treated_sites": int(len(treated)), "control_sites": int(len(control)),
        "did_post": _irr(did, "post_treated"),
        "event": [{"rel": (-int(t[4:]) if t.startswith("ev_m") else int(t[4:])), **_irr(ev, t)} for t in terms],
        "pretrend_wald_p": float(wald.pvalue),
        "crashes_treated_pre_month": float(d[(d.treated == 1) & (d.rel < 0)]["y"].mean()),
        "crashes_treated_post_month": float(d[(d.treated == 1) & (d.rel >= 0)]["y"].mean()),
        "crashes_control_pre_month": float(d[(d.treated == 0) & (d.rel < 0)]["y"].mean()),
        "crashes_control_post_month": float(d[(d.treated == 0) & (d.rel >= 0)]["y"].mean()),
    }


GEOCODE_BREAK = pd.Timestamp("2024-01-01")  # PBH stopped using default geocodes; see docs/data_audit.md


def bump_clusters(b: pd.DataFrame, r: float = 200.0) -> np.ndarray:
    """Resampling unit for the bootstrap: the operational project (bumps of one project sit on
    one street and their buffers overlap); bumps without a project are grouped within r metres."""
    from bhtraffic.ingest.recentes import _cluster

    proj = b["projeto"].fillna("").astype(str).str.strip() if "projeto" in b else pd.Series("", index=b.index)
    out = np.empty(len(b), dtype=object)
    has = proj.ne("").to_numpy()
    out[has] = "p_" + proj[has]
    if (~has).any():
        nb = b[~has]
        lab = _cluster(nb["x"].to_numpy(float), nb["y"].to_numpy(float), r)
        out[~has] = [f"s_{i}" for i in lab]
    return out


def bumps_before_after(c: pd.DataFrame, bumps: pd.DataFrame, through: pd.Timestamp, reps: int = 1000,
                       avoid_break: bool = False) -> dict:
    """Ratio of ratios after/before installation, plus a placebo one window earlier.

    Main:    months [+1, +12]  vs [-12, -1]
    Placebo: months [-12, -1]  vs [-24, -13]  (no bump yet: should be ~1 unless bumps
             follow crash spikes, in which case part of the main drop is regression to the mean)
    Main / placebo = drop beyond the pre-installation build-up.
    """
    b = bumps.dropna(subset=["installed", "lat"]).copy()
    b["inst_m"] = b["installed"].dt.to_period("M").dt.to_timestamp()
    first_ok = c["ym"].min() + pd.DateOffset(months=2 * WINDOW)
    last_ok = through.to_period("M").to_timestamp() - pd.DateOffset(months=WINDOW)
    b = b[b["inst_m"].between(first_ok, last_ok)]
    if avoid_break:
        # Keep bumps whose whole window (-24..+12 months) sits on one side of the geocoding change.
        start = b["inst_m"] - pd.DateOffset(months=2 * WINDOW)
        end = b["inst_m"] + pd.DateOffset(months=WINDOW)
        b = b[(end < GEOCODE_BREAK) | (start >= GEOCODE_BREAK)]
    b = b.reset_index(drop=True)
    b["bid"] = b.index
    yy = counts_near(b, c, BUMP_RADIUS_M, "bid").set_index(["bid", "ym"])["y"]
    city = c.groupby("ym").size()
    have = set(yy.index.get_level_values(0))
    win = {"pre2": (-2 * WINDOW, WINDOW), "pre": (-WINDOW, WINDOW), "post": (1, WINDOW)}
    tot = {k: np.zeros(len(b)) for k in win}
    ctot = {k: np.zeros(len(b)) for k in win}
    for r in b.itertuples():
        loc = yy.loc[r.bid] if r.bid in have else pd.Series(dtype=float)
        for k, (start, n) in win.items():
            ms = pd.date_range(r.inst_m + pd.DateOffset(months=start), periods=n, freq="MS")
            tot[k][r.Index] = loc.reindex(ms, fill_value=0).sum()
            ctot[k][r.Index] = city.reindex(ms, fill_value=0).sum()

    def rr(ix, a, b_):
        return (tot[a][ix].sum() / ctot[a][ix].sum()) / (tot[b_][ix].sum() / ctot[b_][ix].sum())

    rng = np.random.default_rng(0)
    idx = np.arange(len(b))
    # Cluster bootstrap: resample whole projects / street clusters, not single bumps.
    cl = bump_clusters(b)
    groups = pd.Series(idx).groupby(cl).apply(lambda s: s.to_numpy()).to_list()
    boots = [np.concatenate([groups[g] for g in rng.integers(0, len(groups), len(groups))]) for _ in range(reps)]
    out = {"bumps": int(len(b)), "clusters": int(len(groups)), "avoid_geocode_break": avoid_break,
           "years": [int(b["inst_m"].dt.year.min()), int(b["inst_m"].dt.year.max())],
           "crashes": {k: int(v.sum()) for k, v in tot.items()}}
    for name, (a, b_) in {"main": ("post", "pre"), "placebo": ("pre", "pre2")}.items():
        bt = [rr(ix, a, b_) for ix in boots]
        out[name] = {"ratio": float(rr(idx, a, b_)), "ci_low": float(np.percentile(bt, 2.5)), "ci_high": float(np.percentile(bt, 97.5))}
    bt = [rr(ix, "post", "pre") / rr(ix, "pre", "pre2") for ix in boots]
    out["main_over_placebo"] = {"ratio": out["main"]["ratio"] / out["placebo"]["ratio"],
                                "ci_low": float(np.percentile(bt, 2.5)), "ci_high": float(np.percentile(bt, 97.5))}
    return out


def main() -> None:
    c, sites, sm, bumps, through = load()
    out = processed_dir("models", "enforcement")
    res: dict = {"radius_m": RADIUS_M, "through": str(through.date())}
    for fam in ("speed", "red_light"):
        panel, pres = camera_panel(c, sites, sm, through, fam)
        switchers = int((pres.nunique(axis=1) > 1).sum())
        m = fit_twfe(panel)
        post = panel[panel["ym"] >= GEOCODE_BREAK]
        m_post = fit_twfe(post) if post.groupby("site")["camera"].nunique().gt(1).any() else None
        res[fam] = {"sites": int(pres.shape[0]), "switching_sites": switchers, "months": int(pres.shape[1]),
                    "twfe_camera": _irr(m, "camera"),
                    "twfe_camera_since_2024": _irr(m_post, "camera") if m_post is not None else None,
                    "removal_nov2025": removal_event_study(panel, pres)}
        panel.to_parquet(out / f"panel_{fam}.parquet", index=False)
    res["bumps"] = bumps_before_after(c, bumps, through)
    res["bumps_same_side_of_2024"] = bumps_before_after(c, bumps, through, avoid_break=True)
    (out / "effects.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
