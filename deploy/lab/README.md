# Deploy no laboratorio

O servico Django e publicado no `ubt-host01` (`192.168.50.71`) como `loterias-web`, usando a rede externa `infra-lab_lab-network`.

## Componentes

- Imagem: `lab-loterias-web`
- Aplicacao: Gunicorn em `loterias-web:8000`
- Proxy: `nginx-proxy` compartilhado
- URL: `http://www.loterias.internal/`
- Persistencia: volumes Docker `loterias_data` e `loterias_media`

## Operacao

```bash
cd /opt/loterias-app
docker compose --env-file .env -f deploy/lab/docker-compose.yml up -d --build
docker compose --env-file .env -f deploy/lab/docker-compose.yml logs -f loterias-web
```

Os valores `LOTERIAS_SECRET_KEY` e `LOTERIAS_PASSWORD_PEPPER` ficam somente no `.env` do host.

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
DATABASE_NAME=/tmp/db-validacao.sqlite3 docker compose --env-file .env -f deploy/lab/docker-compose.yml run --rm loterias-web python manage.py migrate
sqlite3 /tmp/db-validacao.sqlite3 "SELECT COUNT(*) FROM loterias_core_generatedbet;"   # contagem DEPOIS -- deve bater
sqlite3 /tmp/db-validacao.sqlite3 "SELECT * FROM loterias_core_generatedbet LIMIT 5;"  # amostra manual

# 3. Só depois de validar na copia, aplicar o migrate no volume real
docker compose --env-file .env -f deploy/lab/docker-compose.yml exec loterias-web python manage.py migrate
```

`DATABASE_NAME` e a variavel de ambiente que `loterias/settings/base.py` le pra `DATABASES['default']['NAME']` -- apontando ela pra copia temporaria, o passo 2 nunca escreve no arquivo de producao real.