"""Static figures for the paper (PNG + SVG in paper/figures/).

Same palette as the site (site/DESIGN.md): warm neutrals, one amber accent.
Labels come in PT and EN so each paper language gets its own file.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from bhtraffic.config import figures_dir

PAPER = "#F6F3EE"
TEXT = "#1A1714"
MUTED = "#5E574E"
RULE = "#CFC7BB"
AMBER = "#C46A00"
RAMP = LinearSegmentedColormap.from_list("bh", ["#E4DED4", AMBER])

L = {
    "pt": {
        "crashes": "Sinistros com vítima",
        "deaths": "Mortes",
        "weekdays": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        "hour": "Hora",
        "road_users": {"motorcycle": "Motociclistas", "pedestrian": "Pedestres", "car": "Automóveis", "bicycle": "Ciclistas", "truck": "Caminhões", "bus": "Ônibus"},
        "deaths_by_user": "Mortes por tipo de usuário",
        "regional": "Sinistros com vítima por regional",
    },
    "en": {
        "crashes": "Injury crashes",
        "deaths": "Deaths",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "hour": "Hour",
        "road_users": {"motorcycle": "Motorcyclists", "pedestrian": "Pedestrians", "car": "Car occupants", "bicycle": "Cyclists", "truck": "Truck occupants", "bus": "Bus occupants"},
        "deaths_by_user": "Deaths by road user",
        "regional": "Injury crashes by district",
    },
}


def _style(ax):
    ax.set_facecolor(PAPER)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(RULE)
    ax.tick_params(colors=MUTED, labelsize=9)


def _save(fig, name: str, lang: str) -> Path:
    out = figures_dir() / f"{name}_{lang}.png"
    fig.patch.set_facecolor(PAPER)
    fig.savefig(out, dpi=200, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    return out


def yearly(o: pd.DataFrame, p: pd.DataFrame, lang: str = "pt") -> Path:
    deaths = p[p["fatal"]].merge(o[["boletim", "year"]], on="boletim").groupby("year").size()
    crashes = o.groupby("year").size()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 4.6), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for ax, s, color, label in ((a1, crashes, TEXT, L[lang]["crashes"]), (a2, deaths, AMBER, L[lang]["deaths"])):
        _style(ax)
        ax.plot(s.index, s.values, color=color, lw=2)
        ax.scatter([s.index[-1]], [s.values[-1]], color=color, zorder=3)
        ax.set_title(label, loc="left", fontsize=10, color=color, fontweight="bold")
    a2.set_xticks(crashes.index[::2])
    return _save(fig, "yearly", lang)


def clock(o: pd.DataFrame, years: tuple[int, int], lang: str = "pt") -> Path:
    r = o[o["year"].between(*years) & o["hour"].notna()]
    m = r.groupby(["weekday", "hour"]).size().unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.imshow(m.values, cmap=RAMP, aspect="auto")
    ax.set_yticks(range(7), L[lang]["weekdays"])
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel(L[lang]["hour"], color=MUTED, fontsize=9)
    _style(ax)
    for s in ax.spines.values():
        s.set_visible(False)
    w, h = np.unravel_index(m.values.argmax(), m.shape)
    ax.add_patch(plt.Rectangle((h - 0.5, w - 0.5), 1, 1, fill=False, ec=TEXT, lw=1.5))
    return _save(fig, "clock", lang)


def road_users(o: pd.DataFrame, p: pd.DataFrame, years: tuple[int, int], lang: str = "pt") -> Path:
    recent = set(o.loc[o["year"].between(*years), "boletim"])
    dead = p[p["fatal"] & p["boletim"].isin(recent)]
    grp = dead["grupo_veiculo"].where(~dead["pedestre"].fillna(False).astype(bool), "pedestrian")
    s = grp[grp != "other"].value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(6, 3))
    _style(ax)
    colors = [AMBER if k == "motorcycle" else "#A79F94" for k in s.index]
    ax.barh([L[lang]["road_users"].get(k, k) for k in s.index], s.values, color=colors)
    for i, v in enumerate(s.values):
        ax.text(v, i, f" {v}", va="center", fontsize=9, color=TEXT)
    ax.set_title(f"{L[lang]['deaths_by_user']}, {years[0]}–{years[1]}", loc="left", fontsize=10, color=TEXT)
    return _save(fig, "road_users", lang)


def regionals(o: pd.DataFrame, years: tuple[int, int], lang: str = "pt") -> Path:
    r = o[o["year"].between(*years) & o["regional"].notna() & (o["regional"] != "HIPERCENTRO")]
    s = r["regional"].str.title().value_counts().sort_values()
    fig, ax = plt.subplots(figsize=(6, 3.4))
    _style(ax)
    ax.barh(s.index, s.values, color=["#A79F94"] * (len(s) - 1) + [AMBER])
    ax.set_title(f"{L[lang]['regional']}, {years[0]}–{years[1]}", loc="left", fontsize=10, color=TEXT)
    return _save(fig, "regionals", lang)


def all_figures(o: pd.DataFrame, p: pd.DataFrame, recent: tuple[int, int]) -> list[Path]:
    out = []
    for lang in ("pt", "en"):
        out += [yearly(o, p, lang), clock(o, recent, lang), road_users(o, p, recent, lang), regionals(o, recent, lang)]
    return out
