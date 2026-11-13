# Trânsito BH — onde, quando e com quem o trânsito fere em Belo Horizonte

[English](README.md) · **Site:** <https://dias0202.github.io/transito-bh/>

Diagnóstico do trânsito de Belo Horizonte e da RMBH com dados abertos, e modelos estatísticos e de aprendizado de
máquina avaliados contra linhas de base honestas. Entregas: paper bilíngue (Quarto, `paper/`), site *scrollytelling*
(`site/`, publicado a partir de [`Dias0202/transito-bh`](https://github.com/Dias0202/transito-bh)) e pacote Python
reprodutível (`src/bhtraffic`).

> Estado: rascunho de trabalho (paper v0.1, 16/10/2026). Sinistros até agosto de 2026. Seções do paper marcadas como
> *planejadas* descrevem métodos, não resultados. Ver [docs/roadmap.md](docs/roadmap.md).

## Achados

Números de `paper/pt/index.qmd`, gerados por `bhtraffic.export.site` e `bhtraffic.viz.figures`.

- **38 sinistros com vítima por dia** em 2025 (13.887), o maior número desde 2014; 148 sinistros com morte.
- **75%** dos sinistros com vítima envolvem uma moto; motociclistas e pedestres são **80%** das mortes (2020–2024).
  Nos pontos com radar, motos são 13,2% das passagens e estão em 76,6% dos sinistros próximos: **razão de taxas de 21**
  por passagem (IC 95% 18–25, bootstrap por ponto; exposição por área, não risco por viagem).
- Picos às **7h e 18h** nos dias úteis; pior hora da semana: **quarta, 18h**.
- Chuva: **+13,6%** de sinistros por hora com chuva (RR 1,136; IC 95% 1,10–1,17); a **primeira chuva após 72 h secas**
  soma mais **+19%** (RR 1,19; 1,09–1,30). Feriados −31% (sobretudo menos tráfego). Jogos de futebol: sem efeito detectável.
- **Redutores de velocidade: ~21% menos sinistros com vítima** a até 100 m, líquido de uma janela placebo
  (×0,79; IC 95% 0,72–0,87). **Radares de velocidade:** sem efeito detectável a 150 m (×1,00; 0,92–1,10).

## Métodos

| Pergunta | Desenho | Resultado |
|---|---|---|
| Risco por célula H3 × dia da semana × hora (72.072 células-hora) | LightGBM com perda Poisson, só histórico (v0) e + 14 variáveis viárias do OpenStreetMap fixadas antes de olhar o ano de teste (v1). Variáveis só de anos anteriores ao alvo: treino com alvo 2024 (histórico 2019–2023), **teste com alvo 2025** (histórico 2020–2024). Linhas de base: média de 3 anos da célula-hora; taxa da célula × perfil horário da cidade. Bootstrap por blocos de células (500 réplicas). | Risco concentrado: 5% das células-hora concentram 23% dos sinistros. O LightGBM ajusta melhor na deviance (Δ IC 95% [−0,020; −0,011], mas **empata com a linha de base transparente na métrica de priorização** (captura top 5% Δ [−0,2; +0,9] p.p.); em 2024 empatou nas duas. OSM não acrescenta nada. Reportado assim. |
| Feriados, jogos, chuva | GLM Poisson horário (137.328 horas, 2011–ago/2026) com efeitos fixos de dia × hora, mês, ano e pandemia; erros-padrão clusterizados por dia | Razões de taxas com IC 95% (acima) |
| Radares e avanço de sinal | Painel Poisson ponto × mês com efeitos fixos de ponto e mês, EP clusterizado por ponto; estudo de evento da retirada em massa de nov/2025 | Sem efeito detectável. O estudo de evento rejeita tendências paralelas (p = 0,005) e é rotulado como frágil |
| Redutores (2.627, 2013–2025) | 12 meses depois × 12 antes, relativos ao total da cidade (razão de razões), com janela placebo um ano antes para medir regressão à média; bootstrap por projeto operacional | ×0,82 bruto, placebo ×1,04 [0,99–1,09], **líquido ×0,79 [0,72–0,87]** |
| Cenários "e se" | Efeitos medidos acima, ou premissas explicitamente rotuladas (p. ex. o *Power Model* para velocidade), propagados por Monte Carlo (5.000 sorteios; intervalos de 90%) | p. ex. 100 redutores nas ruas locais elegíveis de maior risco: 118 (81–153) sinistros evitados por ano |
| Microssimulação | Piloto SUMO da Av. Antônio Carlos, demanda ajustada às contagens dos radares | **Ainda não calibrado** (melhor GEH 41, meta < 5); nenhum resultado de cenário é publicado |

As escolhas de desenho foram fixadas antes de olhar os resultados, efeito nulo é reportado como resultado, e todo
cenário diz se o efeito foi medido aqui ou é premissa.

## Rodar

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[geo,viz,ml,dev]"
pytest
python -m bhtraffic.collect.run --dry-run                  # coletor sobre fixtures, sem rede
```

A CI instala o ambiente de teste fixado em `requirements/ci.txt` (compilado de `requirements/ci.in` com
`uv pip compile --universal --python-version 3.11`) e roda `pytest`. A ordem do pipeline, o site e o paper estão
descritos no [README em inglês](README.md#run).

## Coletor e custo zero

Um cron do GitHub Actions coleta GPS dos ônibus (a cada 15 min nos picos dos dias úteis, de hora em hora no resto) e
tempos de viagem do TomTom Routing (a cada 30 min nos picos). Precisa dos segredos `TOMTOM_API_KEY` e `RCLONE_CONF`
([docs/setup_api_keys.md](docs/setup_api_keys.md), [docs/setup_rclone.md](docs/setup_rclone.md)) e só roda agendado com
a variável de repositório `COLLECTOR_ENABLED=true`.

O projeto não pode gerar nenhuma cobrança: todo serviço fica abaixo de 75% da cota grátis
(`src/bhtraffic/collect/budget.py`), provedores que exigem cartão sem teto de gastos ficam bloqueados (HERE), e
`tests/test_budget.py` expande os crons em calendários reais e falha se o pior mês estourar alguma cota.

## Dados

Dados brutos e processados ficam no Google Drive, nunca no git. Só agregados são publicados, mais um retrato de
posições de ônibus sem identificação de veículo ou linha (`site/public/data/bus.json`). Particularidades e correções:
[docs/data_audit.md](docs/data_audit.md).

## Licença

Código: [MIT](LICENSE). Dados: licenças originais de cada fonte (dados abertos PBH/BHTrans, OpenStreetMap ODbL,
termos do TomTom).
