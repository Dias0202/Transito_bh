# Roadmap

Projeto hobby contínuo: cada fase entrega algo publicável (figura, seção do paper ou cena do site).

| Fase | Entrega | Depende de | Status |
|---|---|---|---|
| F1 | Fundação: pacote, coletor, ingestão PBH, EDA de sinistros, site scrollytelling, esqueleto do paper | — | ✅ |
| F1.5 | Chaves TomTom/HERE + rclone; coletor rodando no cron | ações do usuário | ✅ desde 2026-10-13 (run manual: 36 rotas TomTom, 4.442 segmentos HERE, 2.168 ônibus; job 48 s). HERE bloqueado por custo zero; TomTom só pico 30 min |
| F2 | Radares BHTrans (contagens por veículo, mar/2021–set/2023): volume, velocidade, mix veicular por corredor × hora — no Colab | Drive (só agregados; ZIP apagado após processar) | 🟡 módulo pronto, ago/2021 processado |
| F2b | Diagnóstico de congestionamento com 4+ semanas do coletor (índice de atraso por corredor × hora, RMBH) | F1.5 | ⏳ |
| F2c | Ônibus: velocidade comercial e *bunching* por linha com séries do GPS coletado + GTFS | F1.5 | ⏳ |
| F3 | Risco de sinistro H3 × dia × hora (LightGBM Poisson + SHAP), treino→2023, teste 2024 | F1 | 🟡 v0 e v1 (OSM) empatam com taxa×perfil (bootstrap); top 5% = 23% dos sinistros. Próximo: exposição (radares) |
| F3b | Efeitos temporais: feriados, jogos (Série A), chuva INMET — GLM quase-Poisson (`models/temporal.py`) | F1 | ✅ chuva +13,6%, 1ª chuva após 72h seco +20% adicional, feriado −31%, jogos sem efeito (310 jogos Série A) |
| F2d | Congestionamento por radar (índice de velocidade vs fluxo livre noturno) — `analysis/congestion.py` | F2 | 🟡 rodado na amostra ago/2021; refazer com 31 meses após notebook 04 |
| F2e | Dados até jul/2026: sinistros mensais (2016→), histórico de fiscalização eletrônica (51 retratos, jun/2022→), redutores com data de implantação — `ingest/recentes.py` | — | ✅ |
| F3c | Efeito de radares e redutores (`models/enforcement.py`): FE Poisson ponto × mês, estudo de evento da retirada de nov/2025, antes/depois de redutores com placebo | F2e | ✅ radar sem efeito detectável (×0,99 [0,90–1,09]); retirada nov/2025 ×1,00 [0,80–1,24] (pré-tendência rejeitada: frágil); redutor ×0,79 [0,72–0,86] líquido do placebo |
| F9 | **Simulador "e se" de segurança** (`sim/whatif.py`): cenários com efeitos medidos + premissas externas explícitas, incerteza por Monte Carlo sobre os ICs. Cenários: redutores nos N pontos de maior risco; radares de volta; velocidade máxima 60→50 nas arteriais (Nilsson, velocidades reais dos radares); resposta à primeira chuva | F3, F3b, F3c, F2 | ⏳ |
| F9b | **Simulador interativo no site**: controles (nº de redutores, regionais, % de redução de velocidade) recalculando a partir de agregados por célula; sempre com faixa de incerteza e rótulo medido/premissa | F9 | ✅ cena "E se" no site (3 cenários) |
| F4 | Previsão de velocidade 15–60 min (Graph WaveNet / STGCN) — GPU Colab | F2, F2b | ⏳ |
| F5 | SUMO: pilotos Hipercentro/Contorno, Antônio Carlos × Pampulha, Anel BR-040 ↔ Cristiano Machado; calibração com radares + TomTom | F2 | ⏳ |
| F6 | RL semafórico (sumo-rl, PPO/MAPPO) vs tempo fixo | F5 | ⏳ |
| F7 | Camada macro BH — "e se" de tráfego: faixa exclusiva, semáforo adaptativo, restrição de carga no Anel, obras/fechamentos; tempo de viagem e atraso por cenário | F5, OD RMBH | ⏳ |
| F10 | **"E se" de infraestrutura (SUMO, micro + meso)** — catálogo abaixo; cada cenário rodado contra a linha de base calibrada, métricas: tempo de viagem por corredor, atraso, filas, velocidade, emissões (HBEFA do SUMO) e conflitos (SSM do SUMO, *proxy* de risco) | F5, F7 | 📝 registrado |
| F8 | Paper v1.0 PT/EN + site com cenas de resultados | todas | ⏳ |

## Regras dos cenários "e se"

- **Medido × premissa:** cada número de cenário diz de onde vem o efeito — estimado aqui (com IC) ou parâmetro de literatura (com citação). Premissa nunca aparece como resultado.
- **Incerteza sempre visível:** Monte Carlo sobre os ICs; o site mostra faixa, não ponto.
- **Efeito nulo é resultado:** se o efeito medido inclui zero (ex.: radares), o cenário mostra uma faixa que inclui zero.
- **Custo zero:** SUMO e simulações rodam local ou em CPU no Colab (sem unidades extras).

## Catálogo de cenários de infraestrutura (F10) — registrado, ainda não modelado

| Cenário | Onde (piloto) | O que muda na rede SUMO |
|---|---|---|
| Sem redução de faixas nos viadutos (*lane drop*) | Anel Rodoviário (ex.: viadutos entre BR-040 e Cristiano Machado) | mantém o nº de faixas da pista nos viadutos/pontes, eliminando o estrangulamento |
| Mais viadutos (separação em nível) | cruzamentos semaforizados críticos dos corredores (Antônio Carlos, Cristiano Machado, Amazonas) | substitui interseção em nível por passagem em desnível; remove semáforo do fluxo principal |
| Mais trevos / alças | acessos do Anel e das BRs | novas alças de entrada/saída, faixas de aceleração/desaceleração |
| Proibir caminhões (total ou por horário) | Anel Rodoviário, Hipercentro | restrição por classe veicular e janela horária; demanda de carga realocada para rotas alternativas ou fora do pico |
| Faixa exclusiva de ônibus / BRT | corredores sem MOVE | faixa dedicada; prioridade semafórica |
| Semáforo adaptativo (RL) | Hipercentro / Contorno | controlador PPO/MAPPO vs plano de tempo fixo (F6) |
| Obras e fechamentos | qualquer piloto | remoção temporária de arestas; redistribuição de rotas |

**Premissas a explicitar por cenário:** demanda fixa vs. demanda induzida (mais capacidade atrai mais tráfego — reportar as duas), parâmetros de geometria (raios, comprimento de faixas de aceleração), e para caminhões a origem/destino da carga (Pesquisa OD + contagens de radar por classe).
**Validação da linha de base antes de qualquer cenário:** tempos de viagem TomTom por corredor e volumes/velocidades dos radares BHTrans por hora.

## Pesquisa Origem-Destino RMBH

Fonte: Agência RMBH (Pesquisa OD 2012 e atualizações). Download manual pelo site da Agência —
registrar em `docs/data_audit.md` a versão usada. Necessária para a demanda da camada macro (F7).

## Frota

Frota por município/tipo: Senatran (Ministério dos Transportes), publicação mensal em planilha.
Não está no CKAN da PBH; baixar manualmente para `raw/frota/` e registrar versão.
