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

**Incidente (2026-09-11): pipeline de deploy automatizado nao estava fazendo nada, silenciosamente.** O workflow do GitHub Actions (`.github/workflows/*.yml`, roda em push pra `main`) chama `sudo salt '*' state.apply deploy pillar=...`, que tem 3 states: `diretorio_Loterias` (garante o diretorio), `repo_Loterias` (`git.latest`, funciona certinho -- confirmado buscando o commit novo a cada push) e `subir_Loterias` (`cmd.run` com `docker compose pull --ignore-pull-failures; docker compose up -d --remove-orphans`). Dois problemas achados nesse `subir_Loterias`, so descobertos porque o deploy do Epic 3 (PR #4) e de um fix de cron (PR #5) nao apareceram no app rodando apesar do GitHub Actions reportar sucesso:
1. O state tem um `onlyif` que avalia falso **sempre** -- o log mostra `Comment: onlyif condition is false` em toda execucao, entao `docker compose up` literalmente nunca roda via Salt. Nao consegui localizar/corrigir a definicao do state (fica no Salt master, `ubt-host02`, sem acesso SSH daqui) -- fica registrado como bug conhecido pra quem administra o master consertar.
2. Mesmo que o `onlyif` fosse corrigido, o comando do state nao tem `--build` nem usa um registry (`docker compose pull` sempre reporta "No image to be pulled" -- as imagens sao locais) -- ou seja, mesmo rodando, ele so recria containers com a imagem *ja existente* em cache, nunca reconstroi com o codigo novo. Contornado manualmente em 2026-09-11 com `docker compose build --no-cache && docker compose up -d --remove-orphans` -- mas o mesmo problema vai se repetir no proximo push ate o state ganhar `--build` (ou empurrar pra um registry real).

Ate essas duas coisas serem corrigidas no Salt, **um push pra `main` nao redeploya sozinho** -- e preciso rodar manualmente o bloco de comandos acima (`build --no-cache && up -d`) em `/opt/integrit/apps/Loterias/deploy/lab` depois de cada merge.

Depois de qualquer `docker compose up -d --remove-orphans` que recrie o `loterias-web`, o `nginx-proxy` compartilhado pode continuar apontando pro IP do container antigo (ele resolve o hostname uma vez e cacheia ate o proximo reload) -- se o site responder `502 Bad Gateway` depois de um redeploy, rodar `docker exec nginx-proxy nginx -s reload` no host.

**Cuidado com `--remove-orphans` (incidente de 2026-09-09):** varios projetos deste lab (`loterias-app`, `tupa-app`, `aether-app`, ...) guardam o compose file na mesma convencao de subpasta `deploy/lab/`. Sem um `name:` explicito no compose file, o Docker Compose deriva o nome do projeto do diretorio de trabalho -- e como esse diretorio se chama `lab` em todos eles, todos caem no **mesmo namespace de projeto** por padrao. Rodar `docker compose ... up -d --remove-orphans` a partir de um desses projetos remove os containers dos OUTROS projetos, tratando-os como "orfaos" do mesmo projeto. Este arquivo ja declara `name: loterias` no topo (fixando o namespace, independente do diretorio) -- ao criar um novo projeto neste lab, sempre declarar um `name:` unico no `docker-compose.yml`, nunca depender do nome do diretorio.

O `nginx-proxy` e o CoreDNS possuem configuracao compartilhada em `/opt/infra-lab`. O bloco de proxy aponta para `http://loterias-web:8000`, e os registros DNS de `loterias.internal` e `www.loterias.internal` apontam para `192.168.50.71`.

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