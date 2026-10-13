"""When do crashes spike? Calendar and weather effects on citywide hourly crashes.

Unit: one row per clock hour, 2011-2024, BRT. Outcome: injury crashes that hour
(all crashes with a reported time, with or without coordinates).

Effects are estimated with a Poisson GLM (statsmodels, standard errors clustered by
day, robust to overdispersion) that controls for
weekday x hour (168 levels), month, year and the pandemic period, so each
event coefficient is an incidence-rate ratio (IRR): IRR 1.20 = +20% crashes in
that hour versus a comparable hour without the event.

Events
- holiday (public), optional day (ponto facultativo), Carnaval, eve / day after
- BH Série A match window: kickoff -2h .. +3h (any stadium), clássico flag
- rain: mm in the hour; "first rain" after >=72 dry hours (oil film effect)

The stadium analysis repeats the GLM on crashes within RADIUS_KM of each stadium.

    python -m bhtraffic.models.temporal   # -> processed/models/temporal/*.json|parquet
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir

MATCH_BEFORE_H, MATCH_AFTER_H = 2, 3
RADIUS_KM = 1.5
DRY_HOURS = 72
# Mobility restrictions in BH: first closure 2020-03-18; broad reopening mid-2021.
PANDEMIC = ("2020-03-18", "2021-06-30")
YEARS = (2011, 2024)


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_inputs():
    """Crashes 2011 -> last complete month (yearly + monthly datasets, see ingest.recentes)."""
    s = processed_dir("sinistros")
    from bhtraffic.ingest.recentes import require_combined

    require_combined()
    o = pd.read_parquet(s / "ocorrencias_2011_2026.parquet")
    through = pd.Timestamp((s / "ocorrencias_2011_2026.complete_through.txt").read_text().strip())
    o = o[o["hora_informada"] & o["hour"].notna() & (o["dt"] < through + pd.Timedelta(days=1))].copy()
    o.attrs["through"] = through
    o["ts"] = o["dt"].dt.floor("h")
    cal = processed_dir("calendar")
    hol = pd.read_parquet(cal / "holidays.parquet")
    mat = pd.read_parquet(cal / "matches.parquet")
    w = processed_dir("weather") / "inmet_A521.parquet"
    weather = pd.read_parquet(w) if w.exists() else None
    return o, hol, mat, weather


def hourly_frame(hol: pd.DataFrame, mat: pd.DataFrame, weather: pd.DataFrame | None,
                 years=YEARS, end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Hour grid with calendar/weather covariates (no outcome). `end` overrides years[1]."""
    last = end + pd.Timedelta(hours=23) if end is not None else pd.Timestamp(f"{years[1]}-12-31 23:00")
    ts = pd.date_range(f"{years[0]}-01-01", last, freq="h")
    f = pd.DataFrame({"ts": ts})
    f["date"] = f["ts"].dt.normalize()
    f["hour"], f["weekday"] = f["ts"].dt.hour, f["ts"].dt.weekday
    f["month"], f["year"] = f["ts"].dt.month, f["ts"].dt.year

    pub = set(hol.loc[hol["kind"] == "public", "date"])
    opt = set(hol.loc[hol["kind"] == "optional", "date"]) - pub
    carn = set(hol.loc[hol["carnaval"], "date"])
    off = pub | opt
    f["holiday"] = f["date"].isin(pub).astype(int)
    f["optional_day"] = f["date"].isin(opt - carn).astype(int)
    f["carnaval"] = f["date"].isin(carn).astype(int)
    f["holiday_eve"] = ((f["date"] + pd.Timedelta(days=1)).isin(off) & ~f["date"].isin(off)).astype(int)
    f["day_after_holiday"] = ((f["date"] - pd.Timedelta(days=1)).isin(off) & ~f["date"].isin(off)).astype(int)
    f["pandemic"] = f["ts"].between(*PANDEMIC).astype(int)

    # Match windows: hours overlapping [kickoff - 2h, kickoff + 3h].
    f["match"], f["classico"] = 0, 0
    for k, c in zip(mat["kickoff"], mat["classico"]):
        win = f["ts"].between(k.floor("h") - pd.Timedelta(hours=MATCH_BEFORE_H), k.floor("h") + pd.Timedelta(hours=MATCH_AFTER_H))
        f.loc[win, "match"] = 1
        if c:
            f.loc[win, "classico"] = 1

    if weather is not None:
        # INMET hourly precipitation is the total of the hour ENDING at the timestamp,
        # so the value stamped h+1 is the rain that fell during crash hour [h, h+1).
        w = (weather.assign(ts=weather["ts"].dt.floor("h") - pd.Timedelta(hours=1))
             .groupby("ts")["rain_mm"].sum(min_count=1))
        f["rain_mm"] = f["ts"].map(w)
        f["rain_missing"] = f["rain_mm"].isna().astype(int)
        r = f["rain_mm"].fillna(0)
        f["rain_any"] = (r > 0.2).astype(int)
        f["rain_heavy"] = (r >= 5).astype(int)
        dry = r.shift(1).rolling(DRY_HOURS, min_periods=DRY_HOURS).sum().fillna(1) <= 0.2
        f["first_rain"] = (f["rain_any"].astype(bool) & dry).astype(int)
    return f


def add_outcome(f: pd.DataFrame, crashes: pd.DataFrame) -> pd.DataFrame:
    return f.assign(y=f["ts"].map(crashes.groupby("ts").size()).fillna(0).astype(int))


EVENTS = ["holiday", "optional_day", "carnaval", "holiday_eve", "day_after_holiday", "match", "classico"]
WEATHER = ["rain_any", "rain_heavy", "first_rain", "rain_missing"]


def fit_glm(df: pd.DataFrame, events: list[str]):
    import statsmodels.api as sm
    import statsmodels.formula.api as smf

    formula = "y ~ " + " + ".join(events + ["pandemic", "C(weekday):C(hour)", "C(month)", "C(year)"])
    # Quasi-Poisson: dispersion from Pearson chi2 so CIs account for overdispersion.
    # Standard errors clustered by calendar day: hours within a day share weather and
    # traffic conditions, so treating them as independent would overstate precision.
    groups = pd.factorize(df["date"])[0]
    return smf.glm(formula, data=df, family=sm.families.Poisson()).fit(
        cov_type="cluster", cov_kwds={"groups": groups})


def irr_table(model, events: list[str]) -> pd.DataFrame:
    ci = model.conf_int()
    rows = []
    for e in events:
        if e in model.params:
            rows.append({"event": e, "irr": float(np.exp(model.params[e])),
                         "ci_low": float(np.exp(ci.loc[e, 0])), "ci_high": float(np.exp(ci.loc[e, 1])),
                         "p": float(model.pvalues[e])})
    return pd.DataFrame(rows)


def stadium_frame(f: pd.DataFrame, crashes: pd.DataFrame, mat: pd.DataFrame, stadium: str) -> pd.DataFrame:
    """Hourly crashes within RADIUS_KM of one stadium, with that stadium's own match windows."""
    m = mat[mat["stadium"] == stadium]
    lat, lon = m["lat"].iat[0], m["lon"].iat[0]
    c = crashes[crashes["lat"].notna() & ~crashes["coord_placeholder"]]
    near = c[_haversine_km(c["lat"], c["lon"], lat, lon) <= RADIUS_KM]
    g = add_outcome(f.drop(columns=["match", "classico"]), near)
    g["match"] = 0
    for k in m["kickoff"]:
        g.loc[g["ts"].between(k.floor("h") - pd.Timedelta(hours=MATCH_BEFORE_H), k.floor("h") + pd.Timedelta(hours=MATCH_AFTER_H)), "match"] = 1
    first = m["kickoff"].min().normalize() - pd.Timedelta(days=365)
    return g[g["ts"] >= first]  # only years the stadium was in use


MATCH_DATA_END = pd.Timestamp("2024-12-31 23:00")  # Brasileirão dataset ends with the 2024 season


def main() -> None:
    crashes, hol, mat, weather = load_inputs()
    through = crashes.attrs["through"]
    f = hourly_frame(hol, mat, weather, end=through)
    df = add_outcome(f, crashes)
    wx = WEATHER if weather is not None else []
    # Holidays and rain: the whole period. Matches: only hours the match data covers,
    # otherwise 2025-26 games would be counted as "no match" hours.
    calendar_ev = [e for e in EVENTS if e not in ("match", "classico")] + wx
    city = fit_glm(df, calendar_ev)
    dm = df[df["ts"] <= MATCH_DATA_END]
    match_fit = fit_glm(dm, EVENTS + wx)
    rows = irr_table(city, calendar_ev).assign(period=f"{df.ts.min().year}-{through.date()}").to_dict("records")
    rows += irr_table(match_fit, ["match", "classico"]).assign(period=f"{dm.ts.min().year}-2024").to_dict("records")
    in_frame = mat["kickoff"].between(dm["ts"].min(), dm["ts"].max())
    res = {"city": rows, "n_hours": len(df), "crashes": int(df["y"].sum()), "through": str(through.date()),
           "matches_in_frame": int(in_frame.sum()), "classicos_in_frame": int(mat.loc[in_frame, "classico"].sum()),
           "pearson_dispersion": float(city.pearson_chi2 / city.df_resid)}
    res["stadiums"] = {}
    for st in sorted(mat["stadium"].unique()):
        g = stadium_frame(f[f["ts"] <= MATCH_DATA_END], crashes, mat, st)
        ev = ["holiday", "carnaval", "match"] + (["rain_any"] if weather is not None else [])
        try:
            m = fit_glm(g, ev)
            res["stadiums"][st] = {"irr": irr_table(m, ev).to_dict("records"), "crashes": int(g["y"].sum()),
                                   "match_hours": int(g["match"].sum()), "crashes_in_match_hours": int(g.loc[g["match"] == 1, "y"].sum())}
        except Exception as e:  # sparse stadium series can fail to converge; report, don't hide
            res["stadiums"][st] = {"error": repr(e)}
    out = processed_dir("models", "temporal")
    (out / "effects.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), "utf-8")
    df.to_parquet(out / "hourly.parquet", index=False)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
