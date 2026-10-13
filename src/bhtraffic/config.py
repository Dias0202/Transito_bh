"""Paths and constants shared across the package.

Data never lives in git. Resolution order for the data root:
1. ``BHTRAFFIC_DATA_ROOT`` env var
2. Google Drive mount on Colab (``/content/drive/MyDrive/transito_bh``)
3. ``<repo>/data`` locally
"""
from __future__ import annotations

import os
from datetime import timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COLAB_DRIVE_ROOT = Path("/content/drive/MyDrive/transito_bh")

# Brasília time, no DST since 2019.
BRT = timezone(timedelta(hours=-3), name="BRT")

# PBH crash coordinates are UTM zone 23S. SIRGAS 2000 is the official datum.
CRS_UTM_BH = "EPSG:31983"
CRS_WGS84 = "EPSG:4326"

H3_RES = 8

# dados.pbh.gov.br sits behind a WAF that blocks non-browser user agents.
HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 transito-bh-research"
)


def data_root() -> Path:
    env = os.environ.get("BHTRAFFIC_DATA_ROOT")
    if env:
        return Path(env)
    if COLAB_DRIVE_ROOT.parent.exists():
        return COLAB_DRIVE_ROOT
    return REPO_ROOT / "data"


def raw_dir(*parts: str) -> Path:
    p = data_root().joinpath("raw", *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def processed_dir(*parts: str) -> Path:
    p = data_root().joinpath("processed", *parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def corridors_file() -> Path:
    return REPO_ROOT / "data" / "corridors.toml"


def figures_dir() -> Path:
    p = REPO_ROOT / "paper" / "figures"
    p.mkdir(parents=True, exist_ok=True)
    return p
