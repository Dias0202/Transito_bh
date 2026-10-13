# Trânsito BH

**PT** · Diagnóstico do trânsito de Belo Horizonte e da RMBH com dados abertos — onde, quando e com quem o
trânsito fere — e soluções de aprendizado de máquina validadas com dados reais e simulação.
Entregas: paper bilíngue (Quarto), site *scrollytelling* e pacote Python reprodutível.

**EN** · A diagnosis of traffic in Belo Horizonte (Brazil) and its metro region from open data — where, when and
whom traffic hurts — plus machine-learning solutions validated on real data and in simulation.
Deliverables: bilingual paper (Quarto), a scrollytelling site and a reproducible Python package.

> Status: diagnóstico até jul/2026, primeiros modelos (risco, chuva/feriados, radares e redutores). Ver [docs/roadmap.md](docs/roadmap.md).

## Primeiros números · First findings (BHTrans/PBH, até jul/2026)

- **38 sinistros com vítima por dia** em 2025 (13.887), o maior número desde 2014; 148 sinistros com morte.
- **75 %** dos sinistros com vítima envolvem uma moto; motociclistas + pedestres = **80 %** das mortes (2020–2024).
- Picos às **7h e 18h** nos dias úteis; pior hora: **quarta, 18h**. Chuva: **+14 %**; primeira chuva após 3 dias secos: **+19 %** a mais.
- Pampulha lidera em sinistros e em sinistros fatais (2021–2025); hexágono mais crítico sobre a Av. Antônio Carlos.
- **Redutores de velocidade: ~21 % menos sinistros** a até 100 m. Radares: sem efeito detectável a 150 m.

## Estrutura · Layout

```
src/bhtraffic/
  config.py            paths (local vs Colab/Drive), CRS, constants
  collect/             stdlib-only collector: TomTom Routing, PBH bus GPS (HERE blocked: zero-cost)
  ingest/pbh.py        CKAN download (dados.pbh.gov.br, behind a WAF)
  ingest/sinistros.py  crash tables: column aliases, coordinate fix, placeholder geocodes, H3
  ingest/radares.py    BHTrans radar counts: monthly ZIP -> 15-min aggregates
  ingest/collector.py  collector csv.gz -> parquet, coverage
  geo/corridors.py     corridors + bboxes from data/corridors.toml
  viz/figures.py       paper figures (PT/EN)
  export/site.py       aggregated JSON for the site
  models/risk.py       crash-risk model (H3 × weekday × hour), baselines, bootstrap, SHAP
  models/temporal.py   holiday / match / rain effects on hourly crashes (Poisson GLM, day-clustered SEs)
  models/enforcement.py  speed cameras (site x month FE Poisson, Nov 2025 removal) and speed bumps (before/after + placebo)
  ingest/recentes.py   monthly crash dataset 2016 -> current, enforcement-device history, speed bumps
  analysis/congestion.py  radar speed index vs night free-flow
  ingest/calendar.py, ingest/inmet.py, geo/osm.py   covariates (all free sources)
data/corridors.toml    18 corridors (BH + RMBH), 4 HERE bboxes
notebooks/             00 Colab setup · 01 ingest · 02 EDA crashes · 03 vehicle mix · 04 radars (Colab) · 05 collector
paper/                 Quarto: pt/ and en/, shared figures/
site/                  Vite + TypeScript + GSAP + MapLibre scrollytelling ("Quiet Precision", see site/DESIGN.md)
.github/workflows/     collector cron (GitHub Actions -> rclone -> Google Drive)
docs/                  setup_api_keys, setup_rclone, data_audit, roadmap
tests/                 parsers, corridors schema, crash-data fixes
```

## Rodar · Run

```bash
python -m venv .venv && .venv/Scripts/activate          # Windows (source .venv/bin/activate on Linux/macOS)
pip install -e ".[geo,viz,ml,dev]"
pytest
python -m bhtraffic.collect.run --dry-run                 # collector on fixtures, no network
```

Pipeline, nesta ordem · in this order (all sources free; outputs in `data/processed`, or Drive on Colab):

```bash
python -c "from bhtraffic.ingest import sinistros; sinistros.build()"   # 1. yearly crash tables 2011-2024 (+ vehicles, people)
python -m bhtraffic.ingest.recentes                       # 2. monthly crashes 2016 -> now, enforcement history, speed bumps
python -m bhtraffic.ingest.calendar                       # 3. holidays + Série A matches
python -m bhtraffic.ingest.inmet 2011 2026                #    hourly rain (INMET A521)
python -m bhtraffic.geo.osm                               #    OSM road features per H3 cell
python -m bhtraffic.models.risk                           # 4. models
python -m bhtraffic.models.temporal
python -m bhtraffic.models.enforcement
python -m bhtraffic.export.site                           # 5. site/public/data/*.json
```

Site:

```bash
cd site && npm install && npm run dev      # http://localhost:5173
npm run build                              # static output in site/dist (relative paths)
```

Paper (needs [Quarto](https://quarto.org) ≥ 1.4; PDF via Typst, no LaTeX):

```bash
cd paper && quarto render                  # _output/pt/index.html|pdf, _output/en/...
```

Colab (GPU): open `notebooks/00_colab_setup.ipynb` from GitHub, add the `GH_TOKEN` Colab Secret, run. The setup cell clones the repo to `/content/Transito_bh` and installs it in editable mode (the package resolves `data/`, `paper/` and `site/` from the repo root).

## Coletor · Collector

GitHub Actions cron: bus GPS every 15 min at BRT weekday peaks (06–10h, 16–20h) and hourly otherwise;
TomTom Routing every 30 min at weekday peaks only. Job is stdlib-only so it fits the 2,000 free minutes.
Needs secrets `TOMTOM_API_KEY`, `RCLONE_CONF` —
see [docs/setup_api_keys.md](docs/setup_api_keys.md) and [docs/setup_rclone.md](docs/setup_rclone.md).

### Custo zero (mandatório) · Zero cost (mandatory)

Este projeto **não pode gerar nenhuma cobrança**. Todo serviço fica abaixo de 75% da cota grátis,
provedores que exigem cartão sem teto de gastos ficam bloqueados (HERE), e `tests/test_budget.py`
falha se a agenda do coletor estourar alguma cota no pior mês. Regras completas: [CLAUDE.md](CLAUDE.md).

This project **must never incur a charge**: every service stays under 75% of its free tier, providers that
need a card without a hard spending cap are blocked (HERE), and `tests/test_budget.py` fails if the
collector schedule would exceed any free tier in the worst-case month.

## Dados · Data

Raw and processed data live on Google Drive (`MyDrive/transito_bh`), never in git. Only aggregates are published, plus one bus-position snapshot without vehicle or line IDs (`site/public/data/bus.json`).
Quirks and fixes: [docs/data_audit.md](docs/data_audit.md).

## Licença · License

Code: MIT. Data: original licences of each source (PBH/BHTrans open data, OpenStreetMap ODbL, provider terms for TomTom/HERE).
