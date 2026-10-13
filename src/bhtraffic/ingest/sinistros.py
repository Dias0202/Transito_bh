"""Tidy the PBH/BHTrans crash datasets (accidents with victims, 2011+).

Three linked tables keyed by ``boletim`` (police report id):
ocorrencias (one row per crash), veiculos (per vehicle), pessoas (per person).

Coordinate quirk found in the raw files: 2011-2015 store UTM in a different
fixed-point layout (x * 100, and y * 100 with the leading "7" millions digit
dropped). ``fix_coords`` maps them onto the 2016+ convention so both line up
on the same UTM 23S grid. Residual offsets of a few tens of metres remain, well
below H3 res-8 cell size (~0.7 km2), so spatial aggregation is unaffected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bhtraffic.config import CRS_UTM_BH, CRS_WGS84, H3_RES
from bhtraffic.ingest import pbh

VEHICLE_GROUPS = {
    "AUTOMOVEL": "car",
    "CAMIONETA": "car",
    "CAMINHONETE": "car",
    "UTILITARIO": "car",
    "MOTOCICLETA": "motorcycle",
    "MOTONETA": "motorcycle",
    "CICLOMOTOR": "motorcycle",
    "ONIBUS": "bus",
    "MICROONIBUS": "bus",
    "CAMINHAO": "truck",
    "CAMINHAO-TRATOR": "truck",
    "REBOQUE E SEMI-REBOQUE": "truck",
    "BICICLETA": "bicycle",
}

# BH municipal bounds in UTM 23S, padded. Anything outside is a bad geocode.
_X_RANGE = (595_000, 622_000)
_Y_RANGE = (7_780_000, 7_816_000)


def fix_coords(x: pd.Series, y: pd.Series) -> tuple[pd.Series, pd.Series]:
    x = pd.to_numeric(x, errors="coerce")
    y = pd.to_numeric(y, errors="coerce")
    legacy = x > 10_000_000
    x = x.where(~legacy, x / 100)
    y = y.where(~legacy, y / 100 + 7_000_000)
    ok = x.between(*_X_RANGE) & y.between(*_Y_RANGE)
    return x.where(ok), y.where(ok)


def _to_latlon(x: pd.Series, y: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    from pyproj import Transformer

    t = Transformer.from_crs(CRS_UTM_BH, CRS_WGS84, always_xy=True)
    lon, lat = t.transform(x.to_numpy(), y.to_numpy())
    return lat, lon


def flag_placeholders(df: pd.DataFrame, min_n: int = 100, min_regionals: int = 5) -> pd.Series:
    """Flag default geocodes: one ~100 m spot holding many crashes that were
    reported in many different regionals (a real place belongs to one or two).
    In 2011-2024 these cluster on the Anel Rodoviario, e.g. -19.906,-43.989
    with ~2,900 crashes from 8 regionals."""
    key = [df["lat"].round(3), df["lon"].round(3)]
    g = df.groupby(key)["regional"].agg(["size", "nunique"])
    bad = g[(g["size"] >= min_n) & (g["nunique"] >= min_regionals)].index
    return pd.Series(pd.MultiIndex.from_arrays(key).isin(bad), index=df.index)


def _h3(lat: np.ndarray, lon: np.ndarray, res: int = H3_RES) -> list[str | None]:
    import h3

    return [
        h3.latlng_to_cell(a, b, res) if np.isfinite(a) and np.isfinite(b) else None
        for a, b in zip(lat, lon)
    ]


def ocorrencias(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pbh.load("sinistros_ocorrencias") if raw is None else raw.copy()
    out = pd.DataFrame(
        {
            "boletim": df["boletim"],
            "dt": pd.to_datetime(df["data_hora_boletim"], format="%d/%m/%Y %H:%M", errors="coerce"),
            "tipo": df["desc_tipo_acidente"],
            "regional": df["desc_regional"],
            "tempo": df["desc_tempo"],
            "pavimento": df["pavimento"],
            "velocidade_permitida": pd.to_numeric(df["velocidade_permitida"], errors="coerce").replace(0, np.nan),
            "fatal": df["indicador_fatalidade"].str.upper().str.startswith("S"),
            "hora_informada": df["hora_informada"].str.upper().str.startswith("S"),
        }
    )
    x, y = fix_coords(df["coordenada_x"], df["coordenada_y"])
    lat, lon = _to_latlon(x, y)
    out["lat"], out["lon"] = lat, lon
    out["coord_placeholder"] = flag_placeholders(out)
    out.loc[out["coord_placeholder"], ["lat", "lon"]] = np.nan
    out["h3"] = _h3(out["lat"].to_numpy(), out["lon"].to_numpy())
    out["year"] = out["dt"].dt.year
    out["month"] = out["dt"].dt.month
    out["weekday"] = out["dt"].dt.weekday  # 0 = Monday
    # Hour is only meaningful when the report says the time was informed.
    out["hour"] = out["dt"].dt.hour.where(out["hora_informada"])
    return out.drop_duplicates("boletim")


def veiculos(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pbh.load("sinistros_veiculos") if raw is None else raw.copy()
    especie = df["descricao_especie"].str.upper()
    return pd.DataFrame(
        {
            "boletim": df["boletim"],
            "especie": especie,
            "grupo": especie.map(VEHICLE_GROUPS).fillna("other"),
            "categoria": df["descricao_categoria"],
            "situacao": df["desc_situacao"],
        }
    )


def pessoas(raw: pd.DataFrame | None = None) -> pd.DataFrame:
    df = pbh.load("sinistros_pessoas") if raw is None else raw.copy()
    especie = df["especie_veiculo"].str.upper()
    return pd.DataFrame(
        {
            "boletim": df["boletim"],
            "severidade": df["desc_severidade"],
            "fatal": df["desc_severidade"].str.upper().eq("FATAL"),
            "condutor": df["condutor"].str.upper().str.startswith("S"),
            "pedestre": df.get("pedestre", pd.Series(index=df.index, dtype=object)).str.upper().str.startswith("S"),
            "sexo": df["sexo"],
            "idade": pd.to_numeric(df["idade"], errors="coerce").where(lambda s: s.between(0, 110)),
            "especie_veiculo": especie,
            "grupo_veiculo": especie.map(VEHICLE_GROUPS).fillna("other"),
        }
    )


def build() -> dict[str, pd.DataFrame]:
    """Tidy all three tables and persist them to processed/sinistros/*.parquet."""
    from bhtraffic.config import processed_dir

    tables = {"ocorrencias": ocorrencias(), "veiculos": veiculos(), "pessoas": pessoas()}
    for name, df in tables.items():
        df.to_parquet(processed_dir("sinistros") / f"{name}.parquet", index=False)
    return tables
