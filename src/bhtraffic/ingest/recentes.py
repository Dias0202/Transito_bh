"""Recent PBH data: crashes up to the current month, enforcement devices, speed bumps.

- Crashes (`sinistros_mensal`): one monthly snapshot covering 2016 -> last month,
  with date-time, type, regional, fatal flag and point geometry (UTM 23S). It
  matches the yearly dataset exactly for 2016-2024 (counts and boletins) but has
  no vehicles or people, so road-user analyses stay at 2011-2024.
- Enforcement devices (`fiscalizacao`): 51 monthly snapshots since 2022-06. Device
  IDs are not stable across snapshots, so a *site* is defined spatially (devices
  of one family within SITE_M metres) and its presence is tracked month by month.
- Speed bumps (`redutores`): latest snapshot, with installation date.

    python -m bhtraffic.ingest.recentes
    # -> processed/sinistros/ocorrencias_2011_2026.parquet
    #    processed/enforcement/{devices,site_months,sites}.parquet
    #    processed/enforcement/redutores.parquet
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from bhtraffic.config import processed_dir
from bhtraffic.ingest import pbh
from bhtraffic.ingest.sinistros import _h3, _to_latlon, fix_coords, flag_placeholders

SITE_M = 50  # devices of one family closer than this are one site

FAMILY = {
    "Controlador Eletrônico de Velocidade": "speed",
    "Conjugado CEV/DIF": "speed",
    "Conjugado CEV-DIF": "speed",
    "Detector de Avanço de Semáforo": "red_light",
    "Detector de Invasão de Faixa de Exclusiva - MOVE": "bus_lane",
    "Detector de Conversão/Retorno em local Proibido": "turn",
    "Detector de Conversão-Retorno em local Proibido": "turn",
    "Detector de Parada sobre Faixa de Pedestres": "crosswalk",
    "Detector de Trânsito em Local Proibido": "restricted",
}


def _xy(geom: pd.Series) -> tuple[pd.Series, pd.Series]:
    """First coordinate pair of a WKT POINT/LINESTRING (UTM 23S)."""
    m = geom.fillna("").str.extract(r"\(\s*([\d.]+)\s+([\d.]+)")
    return pd.to_numeric(m[0], errors="coerce"), pd.to_numeric(m[1], errors="coerce")


def _latlon(x: pd.Series, y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    lat, lon = _to_latlon(x, y)
    bad = ~(np.isfinite(lat) & np.isfinite(lon))  # pyproj returns inf for NaN input
    return np.where(bad, np.nan, lat), np.where(bad, np.nan, lon)


def _snapshot(path: Path) -> pd.Timestamp:
    return pd.to_datetime(path.name[:8], format="%Y%m%d")


# ---------------------------------------------------------------- crashes
def ocorrencias_mensal(df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pbh.load("sinistros_mensal") if df is None else df
    x, y = fix_coords(*_xy(df["geometria"]))
    lat, lon = _latlon(x, y)
    dt = pd.to_datetime(df["data_hora_boletim"], errors="coerce")
    out = pd.DataFrame({
        "boletim": df["boletim"],
        "dt": dt,
        "tipo": df["descricao_tipo_acidente"],
        "regional": df["descricao_regional"],
        "fatal": df["indicador_fatalidade"].fillna("").str.upper().str.startswith("S"),
        "hora_informada": True,  # times match the yearly dataset exactly; 00:00 is 0.09%
        "lat": lat,
        "lon": lon,
    })
    out["coord_placeholder"] = flag_placeholders(out)
    out["h3"] = _h3(out["lat"].to_numpy(), out["lon"].to_numpy())
    out.loc[out["coord_placeholder"], "h3"] = None
    out["year"], out["month"] = out["dt"].dt.year, out["dt"].dt.month
    out["weekday"], out["hour"] = out["dt"].dt.weekday, out["dt"].dt.hour.astype(float)
    return out.dropna(subset=["dt"]).drop_duplicates("boletim")


def last_complete_month(dt: pd.Series) -> pd.Timestamp:
    """End of the last month whose final day appears in the data."""
    last = dt.max()
    month_end = last + pd.offsets.MonthEnd(0)
    return month_end.normalize() if last.normalize() == month_end.normalize() else last.normalize() - pd.offsets.MonthEnd(1)


def combined(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """2011-2015 from the yearly dataset + 2016 onward from the monthly one, complete months only."""
    cut = last_complete_month(new["dt"])
    keep = ["boletim", "dt", "tipo", "regional", "fatal", "hora_informada", "lat", "lon",
            "coord_placeholder", "h3", "year", "month", "weekday", "hour"]
    a = old.loc[old["year"] < 2016, [c for c in keep if c in old.columns]].assign(source="anual")
    b = new.loc[(new["year"] >= 2016) & (new["dt"] <= cut + pd.Timedelta(days=1)), keep].assign(source="mensal")
    out = pd.concat([a, b], ignore_index=True)
    out.attrs["complete_through"] = str(cut.date())
    return out


# ---------------------------------------------------------------- enforcement
def devices() -> pd.DataFrame:
    """Every device row of every snapshot, with snapshot date, family and lat/lon."""
    frames = []
    for p in pbh.download("fiscalizacao"):
        d = pbh.read_pbh_csv(p)
        d["snapshot"] = _snapshot(p)
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["tipo"] = d["desc_tipo_controlador_transito"].str.strip()
    d["family"] = d["tipo"].map(FAMILY).fillna("other")
    d["x"], d["y"] = _xy(d["geometria"])
    d["lat"], d["lon"] = _latlon(d["x"], d["y"])
    d["speed_limit"] = pd.to_numeric(d["velocidade_regulamentar"], errors="coerce")
    return d[["snapshot", "family", "tipo", "desc_loc_controlador_transito", "speed_limit", "x", "y", "lat", "lon"]] \
        .rename(columns={"desc_loc_controlador_transito": "local"})


def _cluster(x: np.ndarray, y: np.ndarray, r: float) -> np.ndarray:
    """Single-linkage clusters of points closer than r (small n: O(n^2) is fine)."""
    n = len(x)
    parent = np.arange(n)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    d2 = (x[:, None] - x[None, :]) ** 2 + (y[:, None] - y[None, :]) ** 2
    for i, j in zip(*np.nonzero(np.triu(d2 <= r * r, 1))):
        parent[find(i)] = find(j)
    roots = np.array([find(i) for i in range(n)])
    return pd.factorize(roots)[0]


def sites(dev: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sites per family and their month-by-month presence.

    Returns (sites, site_months): sites has centroid, first/last snapshot seen and
    status; site_months has one row per site x snapshot with `present` 0/1.
    """
    dev = dev.dropna(subset=["x", "y"]).copy()
    dev["site"] = ""
    for fam, g in dev.groupby("family"):
        lab = _cluster(g["x"].to_numpy(), g["y"].to_numpy(), SITE_M)
        dev.loc[g.index, "site"] = [f"{fam}_{i:04d}" for i in lab]
    snaps = sorted(dev["snapshot"].unique())
    pres = dev.groupby(["site", "snapshot"]).size().unstack(fill_value=0).reindex(columns=snaps, fill_value=0) > 0
    s = dev.groupby("site").agg(family=("family", "first"), x=("x", "mean"), y=("y", "mean"),
                               lat=("lat", "mean"), lon=("lon", "mean"), local=("local", "first"),
                               speed_limit=("speed_limit", "median"), devices_max=("snapshot", "size"))
    s["first_seen"] = pres.idxmax(axis=1)
    s["last_seen"] = pres.iloc[:, ::-1].idxmax(axis=1)
    s["months_present"] = pres.sum(axis=1)
    s["gaps"] = (pres.astype(int).diff(axis=1) == 1).sum(axis=1)  # re-appearances after an absence
    first, last = snaps[0], snaps[-1]
    s["status"] = np.select(
        [(s["first_seen"] == first) & (s["last_seen"] == last) & (s["gaps"] == 0),
         (s["first_seen"] == first) & (s["last_seen"] < last),
         (s["first_seen"] > first) & (s["last_seen"] == last),
         (s["first_seen"] > first) & (s["last_seen"] < last)],
        ["always", "removed", "installed", "temporary"], default="interrupted")
    sm = pres.stack().rename("present").astype(int).reset_index()
    return s.reset_index(), sm


# ---------------------------------------------------------------- speed bumps
def redutores() -> pd.DataFrame:
    d = pbh.load("redutores")
    x, y = _xy(d["geometria"])
    lat, lon = _latlon(x, y)
    return pd.DataFrame({
        "id": d["id_redutor_velocidade"], "endereco": d["endereco_referencia"], "bairro": d["bairro"],
        "installed": pd.to_datetime(d["data_implantacao"], errors="coerce"),
        "x": x, "y": y, "lat": lat, "lon": lon,
    })


def build() -> dict[str, Path]:
    out: dict[str, Path] = {}
    old = pd.read_parquet(processed_dir("sinistros") / "ocorrencias.parquet")
    new = ocorrencias_mensal()
    comb = combined(old, new)
    p = processed_dir("sinistros") / "ocorrencias_2011_2026.parquet"
    comb.to_parquet(p, index=False)
    (processed_dir("sinistros") / "ocorrencias_2011_2026.complete_through.txt").write_text(comb.attrs["complete_through"])
    out["ocorrencias_2011_2026"] = p
    dev = devices()
    s, sm = sites(dev)
    e = processed_dir("enforcement")
    for name, df in (("devices", dev), ("sites", s), ("site_months", sm), ("redutores", redutores())):
        df.to_parquet(e / f"{name}.parquet", index=False)
        out[name] = e / f"{name}.parquet"
    return out


if __name__ == "__main__":
    for k, v in build().items():
        print(k, v)
