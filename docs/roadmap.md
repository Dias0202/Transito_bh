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
| F4 | Previsão de velocidade 15–60 min (Graph WaveNet / STGCN) — GPU Colab | F2, F2b | ⏳ |
| F5 | SUMO: pilotos Hipercentro/Contorno, Antônio Carlos × Pampulha, Anel BR-040 ↔ Cristiano Machado; calibração com radares + TomTom | F2 | ⏳ |
| F6 | RL semafórico (sumo-rl, PPO/MAPPO) vs tempo fixo | F5 | ⏳ |
| F7 | Camada macro BH (cenários de política: faixa exclusiva, restrição de carga no Anel) | F5, OD RMBH | ⏳ |
| F8 | Paper v1.0 PT/EN + site com cenas de resultados | todas | ⏳ |

## Pesquisa Origem-Destino RMBH

Fonte: Agência RMBH (Pesquisa OD 2012 e atualizações). Download manual pelo site da Agência —
registrar em `docs/data_audit.md` a versão usada. Necessária para a demanda da camada macro (F7).

## Frota

Frota por município/tipo: Senatran (Ministério dos Transportes), publicação mensal em planilha.
Não está no CKAN da PBH; baixar manualmente para `raw/frota/` e registrar versão.
