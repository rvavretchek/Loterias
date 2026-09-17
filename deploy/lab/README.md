# Deploy no laboratorio

O servico Django e publicado no `ubt-host01` (`192.168.50.71`) como `loterias-web`, usando a rede externa `infra-lab_lab-network`.

## Componentes

- Imagem: `lab-loterias-web`
- Aplicacao: Gunicorn em `loterias-web:8000`
- Proxy: `nginx-proxy` compartilhado
- URL: `http://www.loterias.internal/`
- Persistencia: volumes Docker `loterias_data` e `loterias_media`

## Operacao

**Checkout real (gerenciado pelo Salt via CI, ver secao abaixo):** `/opt/integrit/apps/Loterias` no `ubt-host01`. Existe tambem um checkout legado em `/opt/loterias-app` (mesma maquina) que **nao e mais o que esta rodando** desde 2026-09-11 -- foi usado pra subir os containers manualmente antes da automacao via Salt existir, ficou parado no commit de 2026-09-09 (Story 2.1) por dias sem ninguem perceber (ver incidente abaixo), e deve ser tratado como morto. Nao usar `/opt/loterias-app` pra nada daqui pra frente; se sobrar, e so um artefato historico.

```bash
cd /opt/integrit/apps/Loterias/deploy/lab
docker compose up -d --build
docker compose logs -f loterias-web
```

Os valores `LOTERIAS_SECRET_KEY` e `LOTERIAS_PASSWORD_PEPPER` ficam somente no `.env` do host, em `/opt/integrit/apps/Loterias/deploy/lab/.env` (root:root, `chmod 600`, **nunca commitado**) -- e o `docker-compose.yml` desta pasta que consome esse arquivo (Compose le `.env` automaticamente do mesmo diretorio do compose file quando nao ha `-f` apontando pra outro lugar). Chaves esperadas nesse arquivo, com nomes batendo em `docker-compose.yml`: `LOTERIAS_SECRET_KEY`, `LOTERIAS_PASSWORD_PEPPER`, `BREVO_SMTP_HOST`, `BREVO_SMTP_PORT`, `BREVO_SMTP_USE_TLS`, `BREVO_SMTP_USER`, `BREVO_SMTP_KEY`, `BREVO_FROM_EMAIL`, `OPERATOR_ALERT_EMAIL`.

**Incidente (2026-09-11): pipeline de deploy automatizado nao estava fazendo nada, silenciosamente.** O workflow do GitHub Actions (`.github/workflows/deploy.yml`, roda em push pra `main`) chama `sudo salt '*' state.apply deploy pillar=...`, que tem 3 states: `diretorio_Loterias` (garante o diretorio), `repo_Loterias` (`git.latest`, funciona certinho -- confirmado buscando o commit novo a cada push) e `subir_Loterias` (`cmd.run` com `docker compose pull --ignore-pull-failures; docker compose up -d --remove-orphans`). Dois problemas achados nesse `subir_Loterias`, so descobertos porque o deploy do Epic 3 (PR #4) e de um fix de cron (PR #5) nao apareceram no app rodando apesar do GitHub Actions reportar sucesso:
1. O state generico `subir_{{project}}` (definido em `/srv/salt/deploy/init.sls` no master `ubt-host02`) checa a existencia do compose file com um `onlyif` que olha a **raiz do checkout** (`{{ deploy_path }}`, ex. `/opt/integrit/apps/Loterias/docker-compose.yml`) -- mas o compose do Loterias mora em `deploy/lab/docker-compose.yml`, entao o `onlyif` avaliava falso **sempre** (`Comment: onlyif condition is false` em todo log) e `docker compose up` literalmente nunca rodava via Salt.
2. Mesmo que o `onlyif` fosse corrigido, o comando do state nao tinha `--build` nem usava um registry (`docker compose pull` sempre reporta "No image to be pulled" -- as imagens sao locais) -- ou seja, mesmo rodando, so recriava containers com a imagem *ja existente* em cache, nunca reconstruia com o codigo novo.

**Corrigido definitivamente 2026-09-16**, direto no state compartilhado do master (`/srv/salt/deploy/init.sls` em `ubt-host02`, backup do original salvo como `init.sls.bak-2026-09-16` no mesmo diretorio): o state agora aceita um pillar opcional `compose_dir` (default = `deploy_path`, preservando o comportamento pros outros projetos do lab que tem o compose na raiz) usado tanto no `onlyif` quanto no `cwd`/comando, e o comando ganhou `--build`. `.github/workflows/deploy.yml` agora passa `compose_dir: /opt/integrit/apps/<repo>/deploy/lab` no pillar do `state.apply` -- o step de contorno ad hoc (`sudo salt 'ubt-host01' cmd.run '... build --no-cache ...'`, adicionado 2026-09-14) foi removido, ficando so um step leve de `nginx -s reload` depois (ver item abaixo sobre IP cacheado). Acesso SSH ao master documentado: `ubt-host02` = `192.168.50.72` na rede do lab (o DNS publico `ubt-host02.integrit.net` nao e alcancavel daqui), usuario `operador01` (mesma chave do host01), com `sudo -l` liberando `NOPASSWD: /usr/bin/salt` -- da pra administrar o Salt inteiro (states, `cmd.run` como root em qualquer minion aceito, incluindo o proprio `ubt-host02`) sem precisar da senha de sudo geral.

Depois de qualquer `docker compose up -d --remove-orphans` que recrie o `loterias-web`, o `nginx-proxy` compartilhado pode continuar apontando pro IP do container antigo (ele resolve o hostname uma vez e cacheia ate o proximo reload) -- se o site responder `502 Bad Gateway` depois de um redeploy, rodar `docker exec nginx-proxy nginx -s reload` no host.

**Cuidado com `--remove-orphans` (incidente de 2026-09-09):** varios projetos deste lab (`loterias-app`, `tupa-app`, `aether-app`, ...) guardam o compose file na mesma convencao de subpasta `deploy/lab/`. Sem um `name:` explicito no compose file, o Docker Compose deriva o nome do projeto do diretorio de trabalho -- e como esse diretorio se chama `lab` em todos eles, todos caem no **mesmo namespace de projeto** por padrao. Rodar `docker compose ... up -d --remove-orphans` a partir de um desses projetos remove os containers dos OUTROS projetos, tratando-os como "orfaos" do mesmo projeto. Este arquivo ja declara `name: loterias` no topo (fixando o namespace, independente do diretorio) -- ao criar um novo projeto neste lab, sempre declarar um `name:` unico no `docker-compose.yml`, nunca depender do nome do diretorio.

O `nginx-proxy` e o CoreDNS possuem configuracao compartilhada em `/opt/infra-lab`. O bloco de proxy aponta para `http://loterias-web:8000`, e os registros DNS de `loterias.internal` e `www.loterias.internal` apontam para `192.168.50.71`.

## Runbook: backfill inicial de notificacoes (Story 2.15)

**Rodar UMA VEZ, logo depois de confirmar que o primeiro ciclo real e nao assistido do cron
(`loterias-cron`, 3h/3h15/3h30) terminou de verdade** -- nao antes, e evitando rodar durante essa
mesma janela (3h-3h30 horario de Brasilia): `loterias-cron` pode estar criando `HitNotification` novas
nesse intervalo, e o numero visto no dry-run pode nao bater mais com o que o `--apply` de fato marca
se rodado durante a janela. Todo `GeneratedBet` historico com acerto ja verificado via checagem sob
demanda (antes do cron rodar de verdade), mas sem `HitNotification` ainda, ganha uma `HitNotification`
nova na primeira varredura por estado real -- o usuario veria "notificacao nova" de um acerto que ja
conhecia. Isso ja aconteceu no lab em 2026-09-14 (4 `HitNotification` geradas assim).

```bash
cd /opt/integrit/apps/Loterias/deploy/lab
# 1. Dry-run primeiro -- so mostra quantas seriam marcadas, nao grava nada
docker compose exec loterias-web python manage.py mark_initial_notifications_read

# 2. Se o numero impresso for compativel com o volume esperado de acerto historico ja conhecido,
#    aplica de verdade
docker compose exec loterias-web python manage.py mark_initial_notifications_read --apply
```

**Nota:** este comando so ajusta o badge/lista de notificacao no site (`is_read=True`) -- se algum
usuario ja tinha `NotificationPreference.email_enabled=True` antes do primeiro ciclo real do cron, o
e-mail de acerto premiado (Story 2.7) pode ja ter sido disparado pra um acerto que o usuario ja
conhecia, e este comando nao desfaz isso (e-mail ja enviado nao pode ser "despublicado"). Fora do
escopo desta story (AC pede so ajuste do estado de leitura) -- registrado em `deferred-work.md`.

**Claramente distinguivel de uma purga de dados:** o comando nunca apaga
`HitNotification`/`GeneratedBet`/`LotteryResult` -- so ajusta `HitNotification.is_read` das linhas
que ja existem no momento da chamada. Por ser uma acao manual pontual (nunca chamada pelo cron), uma
notificacao genuina criada depois do backfill nunca e afetada.

## Validacao

```bash
docker ps --filter name=loterias-web
curl -I -H 'Host: www.loterias.internal' http://127.0.0.1/
dig +short @192.168.50.71 www.loterias.internal
```

## Backup e validacao de migration antes de aplicar em producao

**Nota (2026-09-08):** enquanto este ambiente for um lab/staging de teste (sem dados reais de usuario), este procedimento nao precisa ser seguido — o volume `loterias_data` pode ser recriado livremente. Ele passa a ser obrigatorio **a partir do dia em que o Boss declarar este ambiente como producao**.

Antes de aplicar qualquer `migrate` que altere schema (rename de model/campo, etc.) num ambiente de producao:

```bash
# 1. Copiar o volume real antes de qualquer migrate
docker run --rm -v loterias_data:/data -v /opt/loterias-backups:/backup \
  alpine cp /data/db.sqlite3 /backup/db.sqlite3.$(date +%Y%m%d-%H%M%S)

# 2. Validar a migration contra uma COPIA do backup (nunca contra o arquivo real em uso)
cp /opt/loterias-backups/db.sqlite3.<timestamp> /tmp/db-validacao.sqlite3
sqlite3 /tmp/db-validacao.sqlite3 "SELECT COUNT(*) FROM loterias_core_generatedbet;"   # contagem ANTES
DATABASE_NAME=/tmp/db-validacao.sqlite3 docker compose -f /opt/integrit/apps/Loterias/deploy/lab/docker-compose.yml run --rm loterias-web python manage.py migrate
sqlite3 /tmp/db-validacao.sqlite3 "SELECT COUNT(*) FROM loterias_core_generatedbet;"   # contagem DEPOIS -- deve bater
sqlite3 /tmp/db-validacao.sqlite3 "SELECT * FROM loterias_core_generatedbet LIMIT 5;"  # amostra manual

# 3. Só depois de validar na copia, aplicar o migrate no volume real
docker compose -f /opt/integrit/apps/Loterias/deploy/lab/docker-compose.yml exec loterias-web python manage.py migrate
```

`DATABASE_NAME` e a variavel de ambiente que `loterias/settings/base.py` le pra `DATABASES['default']['NAME']` -- apontando ela pra copia temporaria, o passo 2 nunca escreve no arquivo de producao real.