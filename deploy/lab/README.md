# Deploy no laboratorio

O servico Django e publicado no `ubt-host01` (`192.168.50.71`) como `loterias-web`, usando a rede externa `infra-lab_lab-network`.

## Componentes

- Imagem: `lab-loterias-web`
- Aplicacao: Gunicorn em `loterias-web:8000`
- Proxy: `nginx-proxy` compartilhado
- URL: `http://www.loterias.internal/`
- Persistencia: volumes Docker `loterias_data`, `loterias_tenants` e `loterias_media`

## Operacao

```bash
cd /opt/loterias-app
docker compose --env-file .env -f deploy/lab/docker-compose.yml up -d --build
docker compose --env-file .env -f deploy/lab/docker-compose.yml logs -f loterias-web
```

Os valores `LOTERIAS_SECRET_KEY` e `LOTERIAS_PASSWORD_PEPPER` ficam somente no `.env` do host.

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