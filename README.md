# Trânsito BH

**PT** · Diagnóstico do trânsito de Belo Horizonte e da RMBH com dados abertos — onde, quando e com quem o
trânsito fere — e soluções de aprendizado de máquina validadas com dados reais e simulação.
Entregas: paper bilíngue (Quarto), site *scrollytelling* e pacote Python reprodutível.

**EN** · A diagnosis of traffic in Belo Horizonte (Brazil) and its metro region from open data — where, when and
whom traffic hurts — plus machine-learning solutions validated on real data and in simulation.
Deliverables: bilingual paper (Quarto), a scrollytelling site and a reproducible Python package.

> Status: fase 1 (fundação + EDA de sinistros). Ver [docs/roadmap.md](docs/roadmap.md).

## Primeiros números · First findings (2020–2024, BHTrans)

- **36 sinistros com vítima por dia** em 2024 (13.266); **159 mortes**, maior número desde 2014.
- **75 %** dos sinistros com vítima envolvem uma moto; motociclistas + pedestres = **80 %** das mortes.
- Picos às **7h e 18h** nos dias úteis; pior hora: **quarta, 18h**.
- Pampulha tem mais sinistros fatais que qualquer outra regional; hexágono mais crítico sobre a Av. Antônio Carlos.

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
  models/temporal.py   holiday / match / rain effects on hourly crashes (quasi-Poisson GLM)
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
pip install -e ".[geo,viz,dev]"
pytest                                                    # 9 tests
python -m bhtraffic.collect.run --dry-run                 # collector on fixtures, no network
python -c "from bhtraffic.ingest import sinistros; sinistros.build()"   # ~185k crashes -> data/processed
python -m bhtraffic.export.site                           # site/public/data/*.json
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
