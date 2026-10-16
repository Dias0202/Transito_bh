"""Download open data from dados.pbh.gov.br (CKAN) and convert to parquet.

The portal sits behind a WAF that rejects non-browser user agents, so every
request sends ``config.HTTP_USER_AGENT``.

    from bhtraffic.ingest import pbh
    pbh.download("sinistros_ocorrencias")          # raw CSVs (cached)
    df = pbh.load("sinistros_ocorrencias")          # tidy DataFrame, all years
    pbh.build_all()                                 # every dataset -> processed/pbh/*.parquet
"""
from __future__ import annotations

import io
import re
import ssl
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from bhtraffic.config import HTTP_USER_AGENT, processed_dir, raw_dir

CKAN = "https://dados.pbh.gov.br/api/3/action"

# key -> CKAN dataset id
DATASETS = {
    "sinistros_ocorrencias": "relacao-de-ocorrencias-de-acidentes-de-transito-com-vitima",
    "sinistros_veiculos": "relacao-dos-veiculos-envolvidos-nos-acidentes-de-transito-com-vitima",
    "sinistros_pessoas": "relacao-das-pessoas-envolvidas-nos-acidentes-de-transito-com-vitima",
    "sinistros_logradouros": "relacao-dos-logradouros-dos-locais-de-acidentes-de-transito-com-vitima",
    "ponto_onibus": "ponto-de-onibus",
    # Monthly snapshots, 2016 -> current month (point geometry, no vehicles/people).
    "sinistros_mensal": "ocorrencia-sinistro-transito-com-vitima",
    # Monthly snapshots of enforcement devices since 2022-06: every snapshot is kept,
    # because the history (installs/removals) is the point.
    "fiscalizacao": "fiscalizacao-eletronica",
    "redutores": "redutor-de-velocidade",
}

# Datasets published as one snapshot per month: only the latest is needed.
LATEST_ONLY = {"ponto_onibus", "sinistros_mensal", "redutores"}


class _DefaultTLSAdapter(HTTPAdapter):
    # The WAF also fingerprints TLS: urllib3 >= 2 offers a trimmed cipher list
    # that gets a 403, while the stdlib default context (same as urllib/curl) passes.
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl.create_default_context()
        return super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.headers["User-Agent"] = HTTP_USER_AGENT
_session.mount("https://", _DefaultTLSAdapter())


def package(dataset_key: str) -> dict:
    r = _session.get(f"{CKAN}/package_show", params={"id": DATASETS[dataset_key]}, timeout=30)
    r.raise_for_status()
    return r.json()["result"]


def _year(name: str) -> int | None:
    m = re.search(r"(19|20)\d{2}", name)
    return int(m.group(0)) if m else None


def csv_resources(dataset_key: str) -> list[dict]:
    res = [
        r for r in package(dataset_key)["resources"]
        if r["url"].lower().endswith(".csv") and "dicion" not in r["name"].lower()
    ]
    if dataset_key in LATEST_ONLY:
        # File names start with the snapshot date (YYYYMMDD_...); resource titles are inconsistent.
        res = sorted(res, key=lambda r: Path(r["url"]).name)[-1:]
    return res


def download(dataset_key: str, force: bool = False) -> list[Path]:
    out = raw_dir("pbh", dataset_key)
    paths = []
    for r in csv_resources(dataset_key):
        dest = out / Path(r["url"]).name
        if force or not dest.exists():
            resp = _session.get(r["url"], timeout=120)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
        paths.append(dest)
    return paths


# Column names drift across yearly files (e.g. numero_boletim / no_boletim /
# n_boletim). Map every variant seen in 2011-2024 to one canonical name.
COLUMN_ALIASES = {
    "numero_boletim": "boletim",
    "num_boletim": "boletim",
    "no_boletim": "boletim",
    "n_boletim": "boletim",
    "sequencial_veiculo": "seq_veic",
    "codigo_categoria": "cod_categ",
    "codigo_especie": "cod_especie",
    "codigo_situacao": "cod_situacao",
    "descricao_situacao": "desc_situacao",
    "descricao_tipo_socorro": "desc_tipo_socorro",
    "numero_envolvido": "no_envolvido",
    "codigo_severidade": "cod_severidade",
    "indicador_pedestre": "pedestre",
    "indicador_passageiro": "passageiro",
}


def _norm_col(c: str) -> str:
    c = unicodedata.normalize("NFKD", c.strip()).encode("ascii", "ignore").decode()
    c = re.sub(r"[^0-9a-zA-Z]+", "_", c).strip("_").lower()
    return COLUMN_ALIASES.get(c, c)


def read_pbh_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    text = text.lstrip("\ufeff")
    # Most files use ';', but some monthly snapshots (fiscalizacao 2022-23) use ','.
    header = text.split("\n", 1)[0]
    sep = ";" if header.count(";") >= header.count(",") else ","
    df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    df.columns = [_norm_col(c) for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c]]  # trailing ';' creates an empty column
    for c in df.columns:
        df[c] = df[c].str.strip()
    df = df.replace({"": None})
    return df


def load(dataset_key: str) -> pd.DataFrame:
    frames = []
    for p in download(dataset_key):
        df = read_pbh_csv(p)
        df["source_file"] = p.name
        df["source_year"] = _year(p.name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build_all() -> dict[str, Path]:
    out = {}
    for key in DATASETS:
        df = load(key)
        dest = processed_dir("pbh") / f"{key}.parquet"
        df.to_parquet(dest, index=False)
        out[key] = dest
    return out
