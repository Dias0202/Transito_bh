"""Congestion diagnosis from BHTrans radar counts (2021-2023).

For each radar location x direction:
- free-flow speed = median of the 15-min car mean speed between 00:00 and 04:59
  (nights, all days): what the road delivers when it is empty;
- speed index = car mean speed / free-flow speed, per day type (weekday,
  Saturday, Sunday/holiday) x hour; 1.0 = free flow, <0.7 = congested
  (same cut-off as common "travel time index" practice, ~1.4x travel time);
- volume = vehicles per hour, all classes.

Radar sites are point measurements: they show *where along the corridor the
camera is*, not the whole corridor. Read together with TomTom corridor delays.

    python -m bhtraffic.analysis.congestion   # -> processed/analysis/congestion_*.parquet
"""
from __future__ import annotations

import glob

import pandas as pd

from bhtraffic.config import processed_dir

CONGESTED = 0.7
MIN_NIGHT_BINS = 20


def load_radar() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = processed_dir("radares")
    aggs = [pd.read_parquet(f) for f in sorted(glob.glob(str(d / "*.parquet"))) if not f.endswith("_radars.parquet")]
    dims = [pd.read_parquet(f) for f in sorted(glob.glob(str(d / "*_radars.parquet")))]
    dim = pd.concat(dims).drop_duplicates(["id_endereco", "sentido"], keep="last")
    return pd.concat(aggs, ignore_index=True), dim


def day_type(ts: pd.Series, holidays: set) -> pd.Series:
    d = ts.dt.normalize()
    wd = ts.dt.weekday
    out = pd.Series("weekday", index=ts.index)
    out[wd == 5] = "saturday"
    out[(wd == 6) | d.isin(holidays)] = "sunday_holiday"
    return out


def profiles(agg: pd.DataFrame, holidays: set) -> pd.DataFrame:
    """Speed index and volume per site x direction x day type x hour."""
    key = ["id_endereco", "sentido"]
    car = agg[agg["classe"] == "car"].copy()
    night = car[car["bin"].dt.hour < 5]
    ff = night.groupby(key).agg(free_flow=("vel_mean", "median"), night_bins=("vel_mean", "size"))
    ff = ff[ff["night_bins"] >= MIN_NIGHT_BINS]

    car["day_type"] = day_type(car["bin"], holidays)
    car["hour"] = car["bin"].dt.hour
    sp = car.groupby(key + ["day_type", "hour"]).agg(speed=("vel_mean", "median"), days=("bin", lambda s: s.dt.date.nunique()))

    allv = agg.assign(day_type=day_type(agg["bin"], holidays), hour=agg["bin"].dt.hour, date=agg["bin"].dt.date)
    vol = (allv.groupby(key + ["day_type", "hour", "date"])["n"].sum()
           .groupby(level=key + ["day_type", "hour"]).mean().rename("veh_per_hour"))
    moto = (allv[allv["classe"] == "motorcycle"].groupby(key + ["day_type", "hour", "date"])["n"].sum()
            .groupby(level=key + ["day_type", "hour"]).mean().rename("moto_per_hour"))

    p = sp.join(vol).join(moto).reset_index().merge(ff.reset_index(), on=key)
    p["speed_index"] = p["speed"] / p["free_flow"]
    p["moto_share"] = p["moto_per_hour"] / p["veh_per_hour"]
    return p


def ranking(p: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """Weekday ranking of sites by worst hour and hours below the congestion cut-off."""
    w = p[p["day_type"] == "weekday"]
    g = w.groupby(["id_endereco", "sentido"])
    r = pd.DataFrame({
        "worst_index": g["speed_index"].min(),
        "worst_hour": w.loc[g["speed_index"].idxmin(), ["id_endereco", "sentido", "hour"]].set_index(["id_endereco", "sentido"])["hour"],
        "congested_hours": g["speed_index"].apply(lambda s: int((s < CONGESTED).sum())),
        "free_flow": g["free_flow"].first(),
        "peak_veh_per_hour": g["veh_per_hour"].max(),
    }).reset_index()
    return r.merge(dim[["id_endereco", "sentido", "endereco", "lat", "lon", "vel_via"]], on=["id_endereco", "sentido"], how="left") \
            .sort_values(["congested_hours", "worst_index"], ascending=[False, True])


def main() -> None:
    agg, dim = load_radar()
    cal = processed_dir("calendar") / "holidays.parquet"
    hol = set(pd.read_parquet(cal).query("kind == 'public'")["date"]) if cal.exists() else set()
    p = profiles(agg, hol)
    r = ranking(p, dim)
    out = processed_dir("analysis")
    p.to_parquet(out / "congestion_profiles.parquet", index=False)
    r.to_parquet(out / "congestion_ranking.parquet", index=False)
    span = (agg["bin"].min(), agg["bin"].max(), agg["bin"].dt.date.nunique())
    print(f"radar data: {span[0]} .. {span[1]} ({span[2]} days), {len(r)} sites")
    print(r.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
