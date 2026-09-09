# CLAUDE.md

Este arquivo fornece orientação ao Claude Code (claude.ai/code) ao trabalhar com código neste repositório.

## Visão geral do projeto

Aplicação Django que gera combinações de jogo pra seis loterias brasileiras (Mega-Sena, +Milionária, Lotomania, Lotofácil, Quina, Dupla-Sena). Single-tenant, multiusuário: todo usuário compartilha um único banco SQLite — não há isolamento por organização (uma iteração anterior adicionou multitenancy via SQLite-por-tenant; foi removida em 2026-09-07 por estar arquiteturalmente errada pra esta aplicação e ser a causa raiz de um bug de "não consigo gerar jogos" — ver [docs/diagnostico-projeto.md](docs/diagnostico-projeto.md) pro diagnóstico completo).

**Convenção de nomenclatura:** todo identificador de código — variáveis, constantes, classes, funções, parâmetros, variáveis locais, campos de model, nomes de método de teste — está em inglês, sem exceção (executado por completo em 2026-09-08, Epic 1 da PRD, em `apps/loterias_core` e `apps/accounts`). Strings de UI, `verbose_name`/labels, e o vocabulário de domínio em português (Jogo, Concurso, Acerto, ...) não são afetados e continuam em pt-br, assim como as chaves de dict de contexto de template, atributos `name=` de formulário HTML, e as chaves do payload JSON de `api_create_bet_view` (tratadas como contrato de dado/API, não identificadores). O mapeamento completo antigo→novo está na seção de nomenclatura da PRD ([_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md](_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md) §3.1). Toda a documentação do projeto (este arquivo incluso) é escrita em português do Brasil — código e identificadores de código são a única exceção.

## Comandos

```bash
# Instalar dependências num venv fixado em Python 3.11 (Django 5.0.6 nao suporta 3.13+;
# o Python padrao da maquina costuma ser mais novo -- use `uv venv --python 3.11 .venv` se for o caso)
pip install -r requirements.txt

# Arquivo de ambiente
cp .env.example .env

# Migrar o banco de dados
python manage.py migrate

# Rodar o servidor de desenvolvimento
python manage.py runserver

# Testes (test runner padrao do Django, sem config de pytest no repo)
python manage.py test
python manage.py test apps.loterias_core
python manage.py test apps.loterias_core.tests.SomeTestCase.test_something

# Shell do Django / coleta de estaticos
python manage.py shell
python manage.py collectstatic
```

`apps/__init__.py` precisa existir (vazio) pra `manage.py test` descobrir os testes — sem ele, `apps` vira um pacote de namespace PEP 420 e o test loader do Django trava/não acha nada.

## Arquitetura

### Autenticação

Model de usuário customizado `apps.accounts.models.User` (`AUTH_USER_MODEL`), login só por e-mail (`USERNAME_FIELD = 'email'`, `username = None`), usando django-allauth com verificação de e-mail obrigatória. `apps.accounts.models.UserManager` é obrigatório — o `UserManager.create_user()` padrão do Django exige `username` como argumento posicional independente do `USERNAME_FIELD`, então pular esse manager customizado quebra silenciosamente `createsuperuser`/admin/qualquer criação programática de usuário (isso já aconteceu uma vez; é por isso que o manager existe hoje). O cadastro usa `CustomSignupForm` e `CustomAccountAdapter` ([apps/accounts/forms.py](apps/accounts/forms.py), [apps/accounts/adapter.py](apps/accounts/adapter.py)) — estenda esses em vez dos padrões do allauth ao mudar comportamento de cadastro/login. Nota: o próprio caminho de cadastro do allauth constrói o `User` direto via o adapter e não passa por `UserManager.create_user()`, então não foi afetado por aquele bug — só `createsuperuser`/admin/scripts foram.

Senhas são hasheadas com `apps.accounts.hashers.PepperedArgon2PasswordHasher`, que adiciona `PASSWORD_PEPPER` (variável de ambiente, não guardada no banco) à senha antes de delegar pro hasher Argon2id padrão do Django. É a única entrada em `PASSWORD_HASHERS`; alterar/remover invalida todos os hashes de senha existentes.

### Lógica de domínio das loterias

Quase toda a lógica de negócio vive em [apps/loterias_core/utils.py](apps/loterias_core/utils.py), orientada pelos dicts de configuração por jogo (`GAMES_CONFIG`) no topo de [apps/loterias_core/models.py](apps/loterias_core/models.py):

- `generate_bet()` — gera um jogo válido aleatório. Jogos em `GAMES_WITH_SEQUENCE_RULE` (Mega-Sena, +Milionária, Quina, Dupla-Sena) seguem uma regra de números sequenciais: se os últimos `MIN_SEQUENCE_INTERVAL` (5) jogos daquele tipo tiveram algum par sequencial, o próximo jogo gerado precisa evitar pares sequenciais por completo; caso contrário, no máximo um par é permitido. `count_sequential_pairs()` implementa a contagem de pares.
- `fetch_cef_result()` — busca o resultado oficial via a **API oficial da Caixa** (`https://servicebus2.caixa.gov.br/portaldeloterias/api/<jogo>/<concurso>`, JSON, consulta por concurso exato — trocado do scraping de HTML frágil na Story 2.1, 2026-09-08). Verifica que o campo `numero` da resposta bate com o `concurso` pedido antes de aceitar o resultado — nunca grava dado de um concurso errado sob o nome de outro. Falha soft (retorna `None`) em vez de levantar exceção. Chamado sob demanda (usuário clica em "verificar") e, desde a Story 2.1, também por uma rotina diária de cron (`apps/loterias_core/jobs.py::fetch_daily_results`, agendada via `django-crontab`/`CRONJOBS`) que varre todo par Jogo/Concurso em aberto (presente em algum `GeneratedBet` mas sem `LotteryResult` ainda). Notificação de acerto (site ou e-mail) ainda não está implementada — ver Epic 2 da PRD.
- `calculate_bet_prize()` / `check_user_results()` — comparam um `GeneratedBet` salvo contra um `LotteryResult` pra calcular acertos e valor do prêmio.

Models: `GeneratedBet` (um jogo gerado pelo usuário, FK pro `AUTH_USER_MODEL`), `LotteryResult` (resultado oficial do sorteio, único por `game`+`contest`), `GameStatistics` (estatísticas agregadas por usuário/jogo, único por `user`+`game`).

### Settings

`loterias/settings/__init__.py` só reexporta `base.py` — hoje não há separação dev/prod de settings; o comportamento por ambiente é todo controlado por variáveis de ambiente (via `python-dotenv` lendo `.env`), ex.: `DEBUG`, `EMAIL_BACKEND`/vars SMTP do Brevo, `SECRET_KEY`, `PASSWORD_PEPPER`. `requirements.txt` fixa Django 5.0.6/django-allauth 0.63.3; sempre confira se as versões instaladas no interpretador ativo realmente batem antes de debugar comportamento estranho de auth — um desalinhamento de ambiente anterior (Django 6.0.5/allauth 65.19.2 instalados contra código escrito pra 5.0.6/0.63.3) causou warnings de settings depreciados e foi um suspeito na investigação do bug de multitenancy. `django-crontab` (adicionado na Story 2.1, 2026-09-08) agenda `CRONJOBS` — hoje só a rotina diária `fetch_daily_results` (3h, horário de Brasília); note que o comando `python manage.py crontab` depende do módulo `fcntl` (POSIX-only) e não roda no Windows, só dentro do container Linux.

### Deploy

A imagem Docker é construída a partir do [Dockerfile](Dockerfile) (Python 3.12-slim, gunicorn, mais `cron`/`tzdata` desde a Story 2.1 pro container de cron). As especificidades do deploy do lab (host, rede, nginx-proxy, DNS) estão documentadas em [deploy/lab/README.md](deploy/lab/README.md) — deploy via `docker compose -f deploy/lab/docker-compose.yml`, com dois serviços (`loterias-web`, rodando só gunicorn, e `loterias-cron`, sidecar rodando `cron -f` pras rotinas agendadas, ambos compartilhando o volume `loterias_data`), e `LOTERIAS_SECRET_KEY`/`LOTERIAS_PASSWORD_PEPPER` fornecidas só via o `.env` do host, nunca commitadas. O lab é hoje um ambiente de teste (sem dados reais de usuário) até o Boss declarar produção explicitamente — ver runbook de backup/validação de migration no próprio `deploy/lab/README.md`.

### Diretórios que não fazem parte da aplicação Django

- `Laboratório/` — notas de documentação/reconstrução de uma infraestrutura de laboratório interna não relacionada (`infra-lab`: DNS, proxy reverso, Keycloak, OpenBao, etc.), não é a infraestrutura desta aplicação.
- `_bmad/`, `_bmad-output/`, `.claude/`, `.agent/`, `.agents/`, `.cline/`, `.opencode/`, `.qwen/` — configuração de ferramentas/framework de agentes de IA, não relacionado ao código de runtime da aplicação.
