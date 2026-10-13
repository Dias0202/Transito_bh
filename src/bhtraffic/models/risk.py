"""Crash-risk model: expected crashes per H3 cell x weekday x hour (F3).

Unit of analysis is a cell-slot (H3 res 8 cell, weekday 0-6, hour 0-23). For a
target year Y the features use only years < Y (no leakage); the label is the
number of injury crashes in that cell-slot during Y.

    train: target 2024, history 2019-2023
    test:  target 2025, history 2020-2024

Model: LightGBM with Poisson objective. Baselines: (a) mean count of the same
cell-slot over the previous 3 years; (b) the cell's yearly mean x the citywide
weekday-hour profile (a strong, classic rate x profile model). Ranking metric: share of the target
year's crashes that fall in the top-k% cell-slots ranked by each predictor
(what an enforcement/engineering budget would actually use).

Runs on a laptop CPU in seconds; no paid compute.

    python -m bhtraffic.models.risk          # writes processed/models/risk/*
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import h3
import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir

HISTORY = 5
SHRINK = 30
TEST_YEAR = 2025
TOP_K = (0.01, 0.05, 0.10)
CATEGORICAL = ["regional"]


def load_crashes() -> pd.DataFrame:
    """Crashes 2011 -> last complete month. Vehicle mix and speed limit exist only up to
    2024 (yearly dataset); they are used as *history* features, so a 2025 target is fine."""
    base = processed_dir() / "sinistros"
    o = pd.read_parquet(base / "ocorrencias_2011_2026.parquet")
    old = pd.read_parquet(base / "ocorrencias.parquet", columns=["boletim", "velocidade_permitida"])
    o = o.merge(old, on="boletim", how="left")
    v = pd.read_parquet(base / "veiculos.parquet")
    o = o[o["h3"].notna() & ~o["coord_placeholder"] & o["hora_informada"] & o["hour"].notna()].copy()
    o["hour"] = o["hour"].astype(int)
    moto = v.loc[v["grupo"] == "motorcycle", "boletim"].unique()
    o["moto"] = o["boletim"].isin(moto)
    return o[["boletim", "h3", "regional", "year", "weekday", "hour", "fatal", "moto", "velocidade_permitida"]]


def _slot_counts(df: pd.DataFrame) -> pd.Series:
    return df.groupby(["h3", "weekday", "hour"]).size()


def build_panel(crashes: pd.DataFrame, target_year: int, cells: list[str]) -> pd.DataFrame:
    """One row per (cell, weekday, hour) with history features and the target-year label."""
    hist = crashes[(crashes["year"] >= target_year - HISTORY) & (crashes["year"] < target_year)]
    last = crashes[crashes["year"] == target_year - 1]
    last3 = hist[hist["year"] >= target_year - 3]
    tgt = crashes[crashes["year"] == target_year]

    idx = pd.MultiIndex.from_product([cells, range(7), range(24)], names=["h3", "weekday", "hour"])
    p = pd.DataFrame(index=idx)
    p["y"] = _slot_counts(tgt).reindex(idx, fill_value=0)
    p["slot_last"] = _slot_counts(last).reindex(idx, fill_value=0)
    p["slot_mean3"] = _slot_counts(last3).reindex(idx, fill_value=0) / 3
    p["slot_mean5"] = _slot_counts(hist).reindex(idx, fill_value=0) / HISTORY
    p = p.reset_index()

    cell = hist.groupby("h3").agg(
        cell_total=("boletim", "size"),
        cell_fatal_share=("fatal", "mean"),
        cell_moto_share=("moto", "mean"),
        cell_speed_limit=("velocidade_permitida", "median"),
        regional=("regional", lambda s: s.mode().iat[0] if s.notna().any() else None),
    ).reindex(cells)
    cell["cell_total"] = cell["cell_total"].fillna(0) / HISTORY
    cell["cell_last"] = last.groupby("h3").size().reindex(cells, fill_value=0)
    # Spatial spillover: crashes in the 6 neighbouring cells.
    totals = cell["cell_total"].to_dict()
    cell["ring1_total"] = [sum(totals.get(n, 0.0) for n in h3.grid_ring(c, 1)) for c in cells]
    cell["lat"], cell["lon"] = zip(*(h3.cell_to_latlng(c) for c in cells))

    # Citywide temporal profile: share of all crashes in this weekday-hour.
    prof = hist.groupby(["weekday", "hour"]).size()
    prof = (prof / prof.sum()).rename("city_slot_share").reset_index()

    p = p.merge(cell, left_on="h3", right_index=True).merge(prof, on=["weekday", "hour"], how="left")
    p["city_slot_share"] = p["city_slot_share"].fillna(0)

    # Each cell's own hour and weekday profile, shrunk toward the city profile
    # (empirical Bayes, prior weight SHRINK crashes) so sparse cells stay stable.
    for col, n_levels in (("hour", 24), ("weekday", 7)):
        city = hist.groupby(col).size()
        city = city / city.sum()
        own = hist.groupby(["h3", col]).size().rename("n").reset_index()
        own = own.merge(hist.groupby("h3").size().rename("tot"), left_on="h3", right_index=True)
        own[f"cell_{col}_share"] = (own["n"] + SHRINK * own[col].map(city)) / (own["tot"] + SHRINK)
        p = p.merge(own[["h3", col, f"cell_{col}_share"]], on=["h3", col], how="left")
        cell_tot = p["h3"].map(hist.groupby("h3").size()).fillna(0)
        p[f"cell_{col}_share"] = p[f"cell_{col}_share"].fillna(SHRINK * p[col].map(city) / (cell_tot + SHRINK))
    p["regional"] = p["regional"].astype("category")
    return p


FEATURES = [
    "weekday", "hour", "slot_last", "slot_mean3", "slot_mean5",
    "cell_total", "cell_last", "cell_fatal_share", "cell_moto_share", "cell_speed_limit",
    "ring1_total", "lat", "lon", "city_slot_share", "cell_hour_share", "cell_weekday_share", "regional",
]


# v1: road features from OpenStreetMap (bhtraffic.geo.osm), fixed before looking at
# 2024 results. Speed cameras are excluded on purpose: they are placed *because*
# of crash history, so they would leak the outcome.
OSM_FEATURES = [
    "km_total", "km_motorway", "km_trunk", "km_primary", "km_secondary", "km_tertiary",
    "intersections", "n_traffic_signals", "n_crossing", "n_bus_stop", "n_roundabout",
    "lanes_mean", "maxspeed_max", "oneway_share",
]


def add_osm(panel: pd.DataFrame) -> pd.DataFrame:
    osm = pd.read_parquet(processed_dir("osm") / "h3_features.parquet")[["h3", *OSM_FEATURES]]
    out = panel.merge(osm, on="h3", how="left")
    fill0 = [c for c in OSM_FEATURES if c.startswith(("km_", "n_")) or c == "intersections"]
    out[fill0] = out[fill0].fillna(0)
    return out


def capture(y: np.ndarray, score: np.ndarray, k: float) -> float:
    """Share of crashes inside the top-k fraction of slots ranked by score (ties broken randomly)."""
    rng = np.random.default_rng(0)
    order = np.lexsort((rng.random(len(score)), -score))
    n = max(1, int(round(k * len(score))))
    return float(y[order[:n]].sum() / y.sum())


def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    mu = np.clip(mu, 1e-9, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(y > 0, y * np.log(y / mu), 0.0)
    return float(2 * np.mean(t - (y - mu)))


@dataclass
class Result:
    model: object
    train: pd.DataFrame
    test: pd.DataFrame
    metrics: dict
    features: list


def _lgbm():
    import lightgbm as lgb

    return lgb.LGBMRegressor(
        objective="poisson", n_estimators=600, learning_rate=0.03, num_leaves=31,
        min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
        reg_lambda=1.0, random_state=0, verbose=-1,
    )


def fit_eval(crashes: pd.DataFrame | None = None, test_year: int = TEST_YEAR, osm: bool | None = None) -> Result:
    """osm=None uses OSM features when processed/osm/h3_features.parquet exists (build it with
    `python -m bhtraffic.geo.osm`), otherwise falls back to v0 and says so in metrics."""
    if osm is None:
        osm = (processed_dir("osm") / "h3_features.parquet").exists()
    crashes = load_crashes() if crashes is None else crashes
    cells = sorted(crashes["h3"].unique())
    train = build_panel(crashes, test_year - 1, cells)
    test = build_panel(crashes, test_year, cells)
    test["regional"] = pd.Categorical(test["regional"], categories=train["regional"].cat.categories)

    # v0: history-only features. Kept as a fixed reference for every later version.
    v0 = _lgbm().fit(train[FEATURES], train["y"], categorical_feature=CATEGORICAL)
    test["pred_v0"] = v0.predict(test[FEATURES])
    model, feats = v0, FEATURES
    if osm:
        train, test = add_osm(train), add_osm(test)
        feats = FEATURES + OSM_FEATURES
        model = _lgbm().fit(train[feats], train["y"], categorical_feature=CATEGORICAL)
    test["pred_model"] = model.predict(test[feats])
    test["pred_baseline"] = test["slot_mean3"]
    test["pred_cellxprofile"] = test["cell_total"] * test["city_slot_share"]

    y = test["y"].to_numpy()
    metrics: dict = {"test_year": test_year, "cells": len(cells), "slots": len(test), "crashes_test": int(y.sum()),
                     "model_version": "v1_osm" if osm else "v0", "features": feats}
    for name in ("model", "v0", "baseline", "cellxprofile"):
        mu = test[f"pred_{name}"].to_numpy()
        m = {
            "poisson_deviance": poisson_deviance(y, mu),
            "mae": float(np.mean(np.abs(y - mu))),
            "spearman": float(pd.Series(mu).corr(pd.Series(y), method="spearman")),
        }
        for k in TOP_K:
            m[f"capture_top{int(k * 100)}pct"] = capture(y, mu, k)
        metrics[name] = m
    return Result(model, train, test, metrics, feats)


def bootstrap_diff(test: pd.DataFrame, a: str, b: str, reps: int = 500, k: float = 0.05) -> dict:
    """Cell-block bootstrap of (a - b) for Poisson deviance and top-k capture: 95% intervals.

    Resampling whole cells keeps each cell's 168 slots together (they are correlated).
    """
    rng = np.random.default_rng(0)
    groups = {c: g.index.to_numpy() for c, g in test.groupby("h3")}
    cells = np.array(list(groups))
    y, pa, pb = (test[c].to_numpy() for c in ("y", f"pred_{a}", f"pred_{b}"))
    dev, cap = [], []
    for _ in range(reps):
        idx = np.concatenate([groups[c] for c in rng.choice(cells, len(cells))])
        dev.append(poisson_deviance(y[idx], pa[idx]) - poisson_deviance(y[idx], pb[idx]))
        cap.append(capture(y[idx], pa[idx], k) - capture(y[idx], pb[idx], k))
    q = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    return {"deviance_diff_ci95": q(dev), f"capture_top{int(k * 100)}pct_diff_ci95": q(cap)}


def explain(res: Result, n: int = 5000):
    """Mean |SHAP| per feature on a random sample of test slots."""
    import shap

    sample = res.test.sample(min(n, len(res.test)), random_state=0)
    sv = shap.TreeExplainer(res.model).shap_values(sample[res.features])
    imp = pd.Series(np.abs(sv).mean(axis=0), index=res.features).sort_values(ascending=False)
    return imp, sv, sample


def main() -> None:
    out = processed_dir() / "models" / "risk"
    out.mkdir(parents=True, exist_ok=True)
    res = fit_eval()
    imp, _, _ = explain(res)
    res.metrics["shap_mean_abs"] = imp.round(5).to_dict()
    res.metrics["model_minus_cellxprofile"] = bootstrap_diff(res.test, "model", "cellxprofile")
    res.metrics["model_minus_v0"] = bootstrap_diff(res.test, "model", "v0")
    (out / "metrics.json").write_text(json.dumps(res.metrics, indent=2, ensure_ascii=False), "utf-8")
    cols = ["h3", "weekday", "hour", "regional", "lat", "lon", "y", "pred_model", "pred_v0", "pred_baseline", "pred_cellxprofile"]
    res.test[cols].to_parquet(out / f"predictions_{res.metrics['test_year']}.parquet", index=False)
    print(json.dumps(res.metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
