# Chaves de API — TomTom (HERE bloqueado)

> **Custo zero é mandatório** (`src/bhtraffic/collect/budget.py`, `tests/test_budget.py`). Nada aqui pode gerar cobrança.

O coletor (`.github/workflows/collector.yml`) lê a chave TomTom dos *secrets* do repositório.
Sem ela ele roda mesmo assim, coletando só as posições dos ônibus (que não exigem chave).

## TomTom (Routing API)

1. Crie conta em <https://developer.tomtom.com/> (não pede cartão no plano gratuito).
2. Em **Dashboard → Keys**, use a chave padrão ou crie uma nova com o produto **Routing API** habilitado.
3. Limite gratuito (docs.tomtom.com/pricing, lido em 2026-10-13): **Routing API 20 mil req/mês**, sem cartão.
   Sem cartão/crédito pré-pago a TomTom não tem como cobrar. **Nunca cadastre cartão nem compre crédito.**
   O coletor usa 18 corredores × 2 sentidos = **36 req/execução**, só no cron `7,37 9-12,19-22 * * 1-5`
   (pico de dia útil, a cada 30 min) → pior mês 23 × 16 × 36 = **13.248 req** (66% da cota). `tests/test_budget.py` garante.

## HERE — BLOQUEADO

A conta HERE exige cartão de crédito e não oferece teto rígido de gastos: qualquer excesso vira cobrança.
Por isso o HERE está **bloqueado no código** (`bhtraffic.collect.budget.BLOCKED`) e o workflow não recebe
a chave. Recomendado: apagar o secret `HERE_API_KEY`, apagar a API key no HERE e remover o cartão / encerrar
a conta HERE. Os dados de trânsito vêm do TomTom (tempo de viagem por corredor) e do GPS dos ônibus.

## Cadastrar no GitHub

Repositório → **Settings → Secrets and variables → Actions → New repository secret**:

| Nome | Valor |
|---|---|
| `TOMTOM_API_KEY` | chave TomTom |
| `RCLONE_CONF` | conteúdo do `rclone.conf` (ver [setup_rclone.md](setup_rclone.md)) |

Localmente, defina as variáveis no shell antes de rodar (o código lê só variáveis de ambiente;
`.env.example` lista os nomes — se usar um `.env`, carregue-o com seu shell/IDE, ele nunca é versionado).

## Termos de uso — leia antes de publicar

- Confira nos termos do plano gratuito de cada provedor se é permitido **armazenar** respostas e por quanto tempo.
- O paper e o site publicam **apenas agregados** (medianas por corredor × hora, índices), nunca respostas brutas das APIs.
- Teste rápido:

```bash
# PowerShell: $env:TOMTOM_API_KEY="..." ; bash: export TOMTOM_API_KEY=...
PYTHONPATH=src python -m bhtraffic.collect.run --sources tomtom --out out/
```
