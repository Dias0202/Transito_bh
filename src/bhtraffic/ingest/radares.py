"""BHTrans radar volumetric counts (one event per detected vehicle).

Source: http://servicosbhtrans.pbh.gov.br/Bhtrans/webservice/ — one ZIP per month
(mar/2021-set/2023, 0.2-2.9 GB each, no HTTP Range support). Inside:
    DADOS_ABERTOS_<MES>_<ANO>/<group>/<YYYY>/<MM>/<YYYYMMDD>/<YYYYMMDD>_<HH>.json
Each JSON is a list of events with keys like "ID EQP", "DATA HORA", "FAIXA",
"VELOCIDADE AFERIDA", "CLASSIFICAÇÃO", "LATITUDE", "ENDEREÇO", "SENTIDO".

Raw months are far too big to keep, so ``build_month`` downloads one ZIP,
aggregates it to 15-minute bins and deletes the ZIP. Run it on Colab with the
output on Drive (see notebooks/04_radares_colab.ipynb).
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from bhtraffic.config import HTTP_USER_AGENT, processed_dir

BASE = "http://servicosbhtrans.pbh.gov.br/Bhtrans/webservice/"
BIN = "15min"

COLS = {
    "ID EQP": "id_eqp",
    "DATA HORA": "ts",
    "FAIXA": "faixa",
    "ID DE ENDEREÇO": "id_endereco",
    "VELOCIDADE DA VIA": "vel_via",
    "VELOCIDADE AFERIDA": "vel",
    "CLASSIFICAÇÃO": "classe",
    "TAMANHO": "tamanho",
    "LATITUDE": "lat",
    "LONGITUDE": "lon",
    "ENDEREÇO": "endereco",
    "SENTIDO": "sentido",
}

CLASSES = {"AUTOMÓVEL": "car", "AUTOMOVEL": "car", "MOTO": "motorcycle", "CAMINHÃO / ÔNIBUS": "truck_bus", "CAMINHAO / ONIBUS": "truck_bus"}


def list_archives() -> list[str]:
    html = requests.get(BASE, headers={"User-Agent": HTTP_USER_AGENT}, timeout=30).text
    return sorted(set(re.findall(r'HREF="/Bhtrans/webservice/([^"]+\.zip)"', html)))


def download(name: str, dest_dir: Path) -> Path:
    dest = dest_dir / name.replace("%20", "")
    if dest.exists():
        return dest
    tmp = dest.with_suffix(".part")
    with requests.get(BASE + name, headers={"User-Agent": HTTP_USER_AGENT}, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    tmp.rename(dest)
    return dest


def parse_events(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records).rename(columns=COLS)
    df = df[[c for c in COLS.values() if c in df.columns]]
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    for c in ("vel", "vel_via", "tamanho", "lat", "lon"):
        df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")
    df["classe"] = df["classe"].astype(str).str.strip().str.upper().map(CLASSES).fillna("other")
    df["sentido"] = df["sentido"].astype(str).str.strip()
    return df.dropna(subset=["ts"])


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Counts and speed stats per radar location x direction x class x 15 min."""
    df = df.assign(bin=df["ts"].dt.floor(BIN), over=(df["vel"] > df["vel_via"]))
    g = df.groupby(["id_endereco", "sentido", "classe", "bin"], observed=True)
    out = g.agg(
        n=("vel", "size"),
        vel_mean=("vel", "mean"),
        vel_p15=("vel", lambda s: np.nanpercentile(s, 15) if s.notna().any() else np.nan),
        vel_p85=("vel", lambda s: np.nanpercentile(s, 85) if s.notna().any() else np.nan),
        n_over_limit=("over", "sum"),
    ).reset_index()
    return out


def radars(df: pd.DataFrame) -> pd.DataFrame:
    """Dimension table: one row per radar location x direction."""
    return (
        df.groupby(["id_endereco", "sentido"], observed=True)
        .agg(id_eqp=("id_eqp", "first"), endereco=("endereco", "first"), lat=("lat", "median"),
             lon=("lon", "median"), vel_via=("vel_via", "median"), faixas=("faixa", "nunique"))
        .reset_index()
    )


def aggregate_zip(path: Path, limit_files: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    aggs, dims = [], []
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.infolist() if m.filename.endswith(".json")]
        for m in members[:limit_files]:
            try:
                records = json.loads(z.read(m).decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue  # truncated file in the archive; skip, logged by caller via coverage
            if not records:
                continue
            ev = parse_events(records)
            aggs.append(aggregate(ev))
            dims.append(radars(ev))
    agg = pd.concat(aggs, ignore_index=True) if aggs else pd.DataFrame()
    dim = pd.concat(dims, ignore_index=True).drop_duplicates(["id_endereco", "sentido"]) if dims else pd.DataFrame()
    return agg, dim


def build_month(name: str, work_dir: Path, keep_zip: bool = False) -> Path:
    """Download one month, aggregate to processed/radares/<MES_ANO>.parquet, delete the ZIP."""
    work_dir.mkdir(parents=True, exist_ok=True)
    zpath = download(name, work_dir)
    agg, dim = aggregate_zip(zpath)
    stem = Path(name.replace("%20", "")).stem
    out = processed_dir("radares") / f"{stem}.parquet"
    agg.to_parquet(out, index=False)
    dim.to_parquet(processed_dir("radares") / f"{stem}_radars.parquet", index=False)
    if not keep_zip:
        zpath.unlink(missing_ok=True)
    return out
