# rclone → Google Drive (coletor)

O GitHub Actions envia cada coleta para `gdrive:transito_bh/raw/collector/` usando **rclone com o seu
token OAuth pessoal**. Service account não serve: ela não tem cota no "Meu Drive" e o upload falha com
`storageQuotaExceeded` (só funcionaria em Shared Drive do Workspace).

## 1. Instalar rclone localmente

Windows: `winget install Rclone.Rclone` (ou baixe em <https://rclone.org/downloads/>).

## 2. (Recomendado) Criar seu próprio OAuth client

> **Estado atual (2026-10-13):** o remote foi criado com o client **compartilhado** do rclone
> (`rclone config create gdrive drive scope=drive.file`) e o coletor já grava no Drive.
> O rclone avisa que esse client "is being retired and will stop working during 2026" —
> quando o upload começar a falhar, faça este passo 2 e recrie o remote com seu client.

O client padrão do rclone é compartilhado e sofre *rate limit*. Siga
<https://rclone.org/drive/#making-your-own-client-id>:

1. Google Cloud Console → crie um projeto → habilite **Google Drive API**.
2. **OAuth consent screen**: tipo *External*, adicione seu e-mail como usuário.
3. **⚠️ Publique o app (Publishing status → In production).**
   Em modo *Testing* o *refresh token* **expira em 7 dias** e o coletor para de gravar sem aviso
   (o job falha e o GitHub manda e-mail, mas os dados daquele período se perdem).
   Em produção aparece o aviso "app não verificado" no login — normal para uso pessoal, clique em *Avançado → continuar*.
4. **Credentials → Create credentials → OAuth client ID → Desktop app**. Guarde *client id* e *secret*.

## 3. Configurar o remote

```bash
rclone config
# n (new remote) → name: gdrive → storage: drive
# client_id / client_secret: os do passo 2
# scope: 1 (drive)  — ou 3 (drive.file) para acesso só ao que o rclone criar
# service_account_file: (vazio) → auto config: y → faça login no navegador
```

Teste: `rclone mkdir gdrive:transito_bh/raw/collector && rclone lsd gdrive:transito_bh`

## 4. Virar secret

```bash
rclone config file      # mostra o caminho do rclone.conf
```

Copie **o conteúdo inteiro** do arquivo para o secret `RCLONE_CONF` do repositório.
O nome do remote precisa ser `gdrive` (o workflow usa `gdrive:transito_bh/...`).

## 5. Validar

GitHub → **Actions → collector → Run workflow**. Confira:
- arquivos novos em `Meu Drive/transito_bh/raw/collector/<fonte>/date=AAAA-MM-DD/`;
- **duração cobrada do job** (aba *Usage*/resumo do run). Precisa ficar ≤ 60 s para caber em 2.000 min/mês.
  Se passar, reduza a cadência para 30 min ou mova o coletor para um repositório público separado.

## 6. Ligar o cron

O agendamento fica **desligado** até existir a variável do repositório `COLLECTOR_ENABLED`.
Depois que um *Run workflow* manual gravar no Drive e durar ≤ 60 s:
**Settings → Secrets and variables → Actions → Variables → New repository variable** →
`COLLECTOR_ENABLED` = `true`. Para pausar, mude para `false`.

> Ordem recomendada: **rclone primeiro**. O GPS dos ônibus não precisa de chave e a PBH não guarda histórico —
> cada dia sem Drive configurado é dado perdido. Chaves TomTom/HERE podem vir depois (o coletor pula o que não tiver chave).

## Manutenção

- Se o job começar a falhar em "Upload to Google Drive", gere o token de novo (`rclone config reconnect gdrive:`) e atualize o secret.
- No Colab, o mesmo diretório aparece em `/content/drive/MyDrive/transito_bh` após `drive.mount`.
