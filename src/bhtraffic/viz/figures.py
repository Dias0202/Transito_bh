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
        "capture_title": "Concentração do risco, {y}: % dos sinistros nos k% célula-horários de maior risco previsto",
        "capture_x": "Célula-horários priorizados (% do total)",
        "series": {"model": "LightGBM (Poisson)", "cellxprofile": "Taxa da célula × perfil horário", "baseline": "Média 3 anos do mesmo célula-horário", "random": "Aleatório"},
        "shap_title": "O que o modelo usa: |SHAP| médio por variável",
        "irr_title": "Efeito sobre sinistros por hora (razão de taxas, IC 95%), BH 2011–2024",
        "irr_x": "Razão de taxas (1 = sem efeito)",
        "events": {"holiday": "Feriado", "optional_day": "Ponto facultativo", "carnaval": "Carnaval", "holiday_eve": "Véspera de feriado", "day_after_holiday": "Dia após feriado", "match": "Jogo Série A em BH (−2h a +3h)", "classico": "Clássico (adicional)", "rain_any": "Chuva na hora", "rain_heavy": "Chuva forte ≥5 mm (adicional)", "first_rain": "Primeira chuva após 72h seco (adicional)"},
        "features": {"cell_total": "Sinistros/ano na célula", "city_slot_share": "Perfil horário da cidade", "cell_last": "Sinistros na célula, ano anterior", "hour": "Hora", "cell_hour_share": "Perfil horário da célula", "cell_moto_share": "% com moto na célula", "lon": "Longitude", "slot_mean5": "Média 5 anos do célula-horário", "weekday": "Dia da semana", "regional": "Regional", "cell_speed_limit": "Velocidade máxima (mediana)", "cell_weekday_share": "Perfil semanal da célula", "slot_mean3": "Média 3 anos do célula-horário", "ring1_total": "Sinistros nas 6 células vizinhas", "lat": "Latitude", "cell_fatal_share": "% fatais na célula", "slot_last": "Célula-horário, ano anterior"},
    },
    "en": {
        "crashes": "Injury crashes",
        "deaths": "Deaths",
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "hour": "Hour",
        "road_users": {"motorcycle": "Motorcyclists", "pedestrian": "Pedestrians", "car": "Car occupants", "bicycle": "Cyclists", "truck": "Truck occupants", "bus": "Bus occupants"},
        "deaths_by_user": "Deaths by road user",
        "regional": "Injury crashes by district",
        "capture_title": "Risk concentration, {y}: % of crashes in the top-k% cell-hours by predicted risk",
        "capture_x": "Cell-hours prioritised (% of all)",
        "series": {"model": "LightGBM (Poisson)", "cellxprofile": "Cell rate × hourly profile", "baseline": "3-year mean of same cell-hour", "random": "Random"},
        "shap_title": "What the model uses: mean |SHAP| per feature",
        "irr_title": "Effect on hourly crashes (rate ratio, 95% CI), BH 2011–2024",
        "irr_x": "Rate ratio (1 = no effect)",
        "events": {"holiday": "Public holiday", "optional_day": "Optional day off", "carnaval": "Carnaval", "holiday_eve": "Holiday eve", "day_after_holiday": "Day after holiday", "match": "Série A match in BH (−2h to +3h)", "classico": "Derby (additional)", "rain_any": "Rain in the hour", "rain_heavy": "Heavy rain ≥5 mm (additional)", "first_rain": "First rain after 72h dry (additional)"},
        "features": {"cell_total": "Crashes/year in cell", "city_slot_share": "Citywide hourly profile", "cell_last": "Crashes in cell, previous year", "hour": "Hour", "cell_hour_share": "Cell hourly profile", "cell_moto_share": "% involving motorcycle in cell", "lon": "Longitude", "slot_mean5": "5-year mean of cell-hour", "weekday": "Weekday", "regional": "District", "cell_speed_limit": "Speed limit (median)", "cell_weekday_share": "Cell weekly profile", "slot_mean3": "3-year mean of cell-hour", "ring1_total": "Crashes in 6 neighbour cells", "lat": "Latitude", "cell_fatal_share": "% fatal in cell", "slot_last": "Cell-hour, previous year"},
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


def risk_capture(pred: pd.DataFrame, year: int, lang: str = "pt") -> Path:
    """Cumulative share of crashes captured when prioritising cell-hours by each predictor."""
    y = pred["y"].to_numpy()
    ks = np.linspace(0, 0.30, 61)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    _style(ax)
    styles = {"model": (AMBER, "-", 2.2), "cellxprofile": (TEXT, "--", 1.4), "baseline": ("#A79F94", "-", 1.4)}
    rng = np.random.default_rng(0)
    for name, (color, ls, lw) in styles.items():
        order = np.lexsort((rng.random(len(y)), -pred[f"pred_{name}"].to_numpy()))
        cum = np.concatenate([[0], np.cumsum(y[order])]) / y.sum()
        ax.plot(ks * 100, cum[(ks * len(y)).astype(int)] * 100, color=color, ls=ls, lw=lw, label=L[lang]["series"][name])
    ax.plot([0, 30], [0, 30], color=RULE, lw=1, label=L[lang]["series"]["random"])
    ax.set_xlabel(L[lang]["capture_x"], color=MUTED, fontsize=9)
    ax.set_ylabel("%", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.set_title(L[lang]["capture_title"].format(y=year), loc="left", fontsize=10, color=TEXT)
    return _save(fig, "risk_capture", lang)


def risk_shap(shap_mean_abs: dict, lang: str = "pt", top: int = 10) -> Path:
    s = pd.Series(shap_mean_abs).sort_values().tail(top)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    _style(ax)
    ax.barh([L[lang]["features"].get(k, k) for k in s.index], s.values, color=["#A79F94"] * (len(s) - 2) + [AMBER] * 2)
    ax.set_title(L[lang]["shap_title"], loc="left", fontsize=10, color=TEXT)
    return _save(fig, "risk_shap", lang)


def effects(irr: list[dict], lang: str = "pt") -> Path:
    """Forest plot of incidence-rate ratios from bhtraffic.models.temporal."""
    d = pd.DataFrame(irr)
    d = d[d["event"].isin(L[lang]["events"])].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    _style(ax)
    y = np.arange(len(d))
    sig = (d["ci_low"] > 1) | (d["ci_high"] < 1)
    colors = np.where(sig & (d["irr"] > 1), AMBER, np.where(sig, TEXT, "#A79F94"))
    ax.hlines(y, d["ci_low"], d["ci_high"], color=colors, lw=2)
    ax.scatter(d["irr"], y, color=colors, zorder=3)
    ax.axvline(1, color=RULE, lw=1)
    ax.set_yticks(y, [L[lang]["events"][e] for e in d["event"]])
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.7, 1, 1.4], ["0.5", "0.7", "1", "1.4"])
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xlabel(L[lang]["irr_x"], color=MUTED, fontsize=9)
    ax.set_title(L[lang]["irr_title"], loc="left", fontsize=10, color=TEXT)
    return _save(fig, "effects", lang)


def all_figures(o: pd.DataFrame, p: pd.DataFrame, recent: tuple[int, int]) -> list[Path]:
    out = []
    for lang in ("pt", "en"):
        out += [yearly(o, p, lang), clock(o, recent, lang), road_users(o, p, recent, lang), regionals(o, recent, lang)]
    return out
