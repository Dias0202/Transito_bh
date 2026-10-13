# Auditoria de dados (Fase 0)

Última verificação: **2026-10-13**. Atualize sempre que uma fonte mudar.

## Fontes verificadas

| Fonte | Acesso | Cobertura | Grão | Observações |
|---|---|---|---|---|
| Sinistros com vítima — ocorrências (BHTrans/PBH) | CKAN `relacao-de-ocorrencias-de-acidentes-de-transito-com-vitima` | 2011–2024 | boletim | 184.350 boletins. CSV `;` latin-1 |
| Sinistros — veículos envolvidos | CKAN `relacao-dos-veiculos-envolvidos-...` | 2011–2024 | veículo | 333 mil linhas |
| Sinistros — pessoas envolvidas | CKAN `relacao-das-pessoas-envolvidas-...` | 2011–2024 | pessoa | 405 mil linhas; 2.007 mortes |
| Ônibus tempo real (PBH) | `https://temporeal.pbh.gov.br?param=C` | só o instante atual | veículo | ~2.550 ônibus, ~390 linhas. **Sem histórico** → coletor |
| Contagem volumétrica de radares (BHTrans) | `http://servicosbhtrans.pbh.gov.br/Bhtrans/webservice/` (ZIP mensal) | mar/2021–set/2023 (com buracos) | evento por veículo | 0,2–2,9 GB por mês, ~45 GB total. Campos: equipamento, data/hora, faixa, velocidade aferida e da via, classe (auto/moto/caminhão-ônibus), tamanho, lat/lon, endereço, sentido. Servidor **não aceita Range** (download inteiro) |
| Ponto/estação de ônibus | CKAN `ponto-de-onibus`, `estacao-de-onibus` | mensal até 2026-09 | ponto | infraestrutura |
| GTFS-RT | CKAN `gtfs-rt` | metadado de 2024-01 | — | verificar se ainda responde |
| TomTom Routing / HERE Flow | APIs com chave | a partir da ativação do coletor | snapshot 15–60 min | ver `setup_api_keys.md` |

## Armadilhas encontradas (tratadas no código)

1. **WAF no dados.pbh.gov.br** bloqueia User-Agent não-navegador → `config.HTTP_USER_AGENT`.
2. **Nomes de coluna mudam entre anos** (`numero_boletim`/`no_boletim`/`n_boletim`/`num_boletim`, etc.) → `pbh.COLUMN_ALIASES`.
3. **Coordenadas 2011–2015 em outro layout**: x×100 e y×100 sem o dígito "7" dos milhões. Convertidas em `sinistros.fix_coords`; resíduo de dezenas de metros (< célula H3 res 8).
4. **Geocódigos padrão**: pontos de ~100 m com ≥100 sinistros vindos de ≥5 regionais diferentes (concentrados no Anel Rodoviário; o maior tem ~2.900 sinistros de 8 regionais). 6.618 registros retirados do mapa (`sinistros.flag_placeholders`); seguem nos totais.
5. **14,6 %** dos sinistros sem coordenada válida (após filtros).
6. **Velocidade do GPS de ônibus**: ~64 % reportam < 5 km/h num instante qualquer (pontos, terminais, garagens) — não usar como medida de congestionamento sem filtrar por trecho em operação.
7. Regional "HIPERCENTRO" aparece em poucos registros (655) — tratado como rótulo à parte, fora do ranking de regionais.

## Radares — primeira amostra (ago/2021, processado localmente)

- O ZIP de ago/2021 (157 MB) tem só **10 dias** (1–6, 10, 15, 28 e 31) e um único grupo `0412303`; JSON por hora (~4,4 GB descompactados).
- 12,4 milhões de detecções; **88 pontos** (endereço × sentido). Classes: automóvel 82,0 %, moto 12,5 %, caminhão/ônibus 5,5 %, outros < 0,1 %.
- Coordenadas suspeitas: "Av. Cristiano Machado, nº 673" aparece em -19.930, -43.962 (região oeste, longe da avenida). Validar lat/lon × endereço antes de usar no mapa ou no grafo do GNN.
- Agregação: 15 min × ponto × sentido × classe (contagem, velocidade média/p15/p85, nº acima do limite) — `ingest/radares.py`.

## O que falta auditar

- Radares: consistência de `ID_EQP`/endereço entre meses, meses faltantes (ex.: ago/2021 tem só 0,2 GB), classes de veículo.
- Pesquisa OD RMBH e frota Senatran (download manual).
