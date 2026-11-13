"""Calendar events for Belo Horizonte: holidays and football matches.

Holidays: the `holidays` package (Brazil, Minas Gerais; public + optional such as
Carnaval and Ash Wednesday) plus BH municipal holidays (Assunção 15/08,
Imaculada Conceição 08/12; Corpus Christi is promoted from optional to public).

Matches: Brasileirão Série A 2003-2024 (github.com/adaoduque/Brasileirao_Dataset,
CC BY 4.0) filtered to the three BH stadiums. Coverage gap, stated in the paper:
Campeonato Mineiro, Copa do Brasil, Libertadores/Sul-Americana and Série B
(Cruzeiro 2020-2022, América in several years) are NOT included, so "no match"
days may still have had a game.

    python -m bhtraffic.ingest.calendar   # -> processed/calendar/{holidays,matches}.parquet
"""
from __future__ import annotations

import io
import tomllib
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from bhtraffic.config import REPO_ROOT, processed_dir

MATCHES_URL = "https://raw.githubusercontent.com/adaoduque/Brasileirao_Dataset/master/campeonato-brasileiro-full.csv"
STADIUMS_FILE = REPO_ROOT / "data" / "stadiums.toml"
BH_CLUBS = {"Cruzeiro", "Atletico-MG", "America-MG"}
MUNICIPAL = {(8, 15): "Assunção de Nossa Senhora (BH)", (12, 8): "Imaculada Conceição (BH)"}


def holidays_table(years: range) -> pd.DataFrame:
    import holidays

    # Names are matched below ("Carnaval", "Corpus Christi"), so the language is pinned:
    # without it the package localizes by LANG and returns "Carnival" on English locales.
    lang = "pt_BR"
    rows = []
    for y in years:
        public = holidays.country_holidays("BR", subdiv="MG", years=y, language=lang)
        optional = holidays.country_holidays(
            "BR", subdiv="MG", years=y, categories=("optional",), language=lang
        )
        for d, name in public.items():
            rows.append({"date": d, "name": name, "kind": "public"})
        for d, name in optional.items():
            if d not in public:
                rows.append({"date": d, "name": name, "kind": "optional"})
        for (m, dd), name in MUNICIPAL.items():
            if date(y, m, dd) not in public:
                rows.append({"date": date(y, m, dd), "name": name, "kind": "public"})
    df = pd.DataFrame(rows)
    # Corpus Christi is a municipal holiday in BH (the package lists it as optional).
    df.loc[df["name"].str.contains("Corpus Christi"), "kind"] = "public"
    df["date"] = pd.to_datetime(df["date"])
    df["carnaval"] = df["name"].str.contains("Carnaval", case=False)
    return df.sort_values("date").reset_index(drop=True)


def stadiums() -> dict[str, dict]:
    return tomllib.loads(STADIUMS_FILE.read_text("utf-8"))


def matches_table(raw_csv: str | None = None) -> pd.DataFrame:
    """Série A matches played in BH stadiums, with kickoff in local time."""
    if raw_csv is None:
        raw_csv = requests.get(MATCHES_URL, timeout=60).text
    df = pd.read_csv(io.StringIO(raw_csv), dtype=str)
    alias = {a.strip().casefold(): key for key, s in stadiums().items() for a in s["aliases"]}
    df["stadium"] = df["arena"].fillna("").str.strip().str.casefold().map(alias)
    df = df[df["stadium"].notna()].copy()
    df["kickoff"] = pd.to_datetime(df["data"] + " " + df["hora"], format="%d/%m/%Y %H:%M", errors="coerce")
    df = df.dropna(subset=["kickoff"])
    st = stadiums()
    df["lat"] = df["stadium"].map(lambda k: st[k]["lat"])
    df["lon"] = df["stadium"].map(lambda k: st[k]["lon"])
    df["classico"] = df["mandante"].isin(BH_CLUBS) & df["visitante"].isin(BH_CLUBS)
    return (
        df.rename(columns={"mandante": "home", "visitante": "away"})
        [["kickoff", "stadium", "home", "away", "classico", "lat", "lon"]]
        .sort_values("kickoff").reset_index(drop=True)
    )


def build(years: range = range(2010, 2028)) -> list[Path]:
    out = processed_dir("calendar")
    h, m = holidays_table(years), matches_table()
    h.to_parquet(out / "holidays.parquet", index=False)
    m.to_parquet(out / "matches.parquet", index=False)
    return [out / "holidays.parquet", out / "matches.parquet"]


if __name__ == "__main__":
    for p in build():
        print(p)
