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