# Chaves de API — TomTom e HERE

O coletor (`.github/workflows/collector.yml`) lê duas chaves dos *secrets* do repositório.
Sem elas ele roda mesmo assim, coletando só as posições dos ônibus (que não exigem chave).

## TomTom (Routing API)

1. Crie conta em <https://developer.tomtom.com/> (não pede cartão no plano gratuito).
2. Em **Dashboard → Keys**, use a chave padrão ou crie uma nova com o produto **Routing API** habilitado.
3. Limite gratuito (confirme na página de preços, muda com o tempo): ~2.500 requisições/dia.
   O coletor usa 18 corredores × 2 sentidos = **36 req/execução**, ~48 execuções por dia útil ≈ **1.730 req/dia**.

## HERE (Traffic API v7)

1. Crie conta em <https://platform.here.com/> → **Access Manager → Apps → Register new app**.
2. Gere uma **API Key** para o app.
3. Verifique na hora do cadastro se o plano gratuito exige cartão de crédito e qual é a cota mensal.
   O coletor faz **4 req/execução** (uma por *bounding box*), ~1.250 execuções/mês.

## Cadastrar no GitHub

Repositório → **Settings → Secrets and variables → Actions → New repository secret**:

| Nome | Valor |
|---|---|
| `TOMTOM_API_KEY` | chave TomTom |
| `HERE_API_KEY` | chave HERE |
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
