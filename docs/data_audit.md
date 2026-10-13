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
| TomTom Routing (HERE bloqueado: custo zero) | API com chave | a partir de 2026-10-13 | pico dia útil, 30 min | ver `setup_api_keys.md` |

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

## Dados até 2026 (adicionados em 2026-10-13)

| Fonte (CKAN PBH) | Cobertura | Observações |
|---|---|---|
| `ocorrencia-sinistro-transito-com-vitima` | 2016 → mês corrente (retrato mensal; usamos o mais recente) | Bate **exatamente** com a base anual em 2016–2024 (contagem por ano e 100 % dos boletins). Sem pessoas/veículos. Indicador de fatalidade revisado: 2019 tem 98 sinistros fatais aqui vs 83 na base anual. Último mês costuma vir parcial → usar só meses completos (`last_complete_month`). 7,9 % sem coordenada. |
| `fiscalizacao-eletronica` | 51 retratos mensais, jun/2022 → set/2026 | **IDs não são estáveis** entre retratos → ponto definido espacialmente (mesma família a < 50 m). Alguns retratos de 2022–23 usam **vírgula** como separador e têm BOM; campos de endereço com quebra de linha entre aspas. **Quebra de cadastro entre out/2025 (669 equipamentos) e nov/2025 (163)**, recomposição ao longo de 2026, muitas vezes em outros locais. Cadastro ≠ operação. |
| `redutor-de-velocidade` | retrato mensal; datas de implantação 2006–2025 | Geometria LINESTRING (usamos o 1º vértice). Algumas linhas sem data de implantação (só manutenção) → fora do antes/depois. |
| INMET 2025–2026 | horária até ago/2026 | 2026.zip é atualizado ao longo do ano. |

### Quebra de geocodificação em 2024

Até 2023 a PBH atribuía centenas de sinistros por ano a geocódigos padrão (ex.: −19,906; −43,989 no Anel: 305 em
2019, 406 em 2023; também −19,918; −43,997 e −19,991; −43,962). A partir de 2024 esses pontos desaparecem (maior ponto
exato: 24 em 2024, 48 em 2025) e a fração sem coordenada cai de ~10 % para ~3 %. Não há sinal de *novos* pontos
padrão. Consequência: descontinuidade espacial em 2024. Os estudos antes/depois (`models/enforcement.py`) trazem
checagens de robustez restritas a um lado da quebra (`twfe_camera_since_2024`, `bumps_same_side_of_2024`).
