# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Django web app that generates bet combinations for six Brazilian lotteries (Mega-Sena, +Milionária, Lotomania, Lotofácil, Quina, Dupla-Sena). Single-tenant, multi-user: every user shares one SQLite database — there is no per-organization isolation (an earlier iteration added SQLite-per-tenant multitenancy; it was removed on 2026-09-07 because it was architecturally wrong for this app and was the root cause of a "can't generate games" bug — see [docs/diagnostico-projeto.md](docs/diagnostico-projeto.md) for the full diagnosis). Codebase, model fields, and UI strings are in Portuguese (pt-br) — match that convention when adding code, not English.

## Commands

```bash
# Install deps into a venv pinned to Python 3.11 (Django 5.0.6 predates 3.13 support;
# the machine's default Python is often newer — use `uv venv --python 3.11 .venv` if so)
pip install -r requirements.txt

# Env file
cp .env.example .env

# Migrate the database
python manage.py migrate

# Run dev server
python manage.py runserver

# Tests (standard Django test runner, no pytest config in repo)
python manage.py test
python manage.py test apps.loterias_core
python manage.py test apps.loterias_core.tests.SomeTestCase.test_something

# Django shell / static collection
python manage.py shell
python manage.py collectstatic
```

`apps/__init__.py` must exist (empty) for `manage.py test` to discover tests at all — without it, `apps` is a PEP 420 namespace package and Django's test loader crashes/finds nothing.

## Architecture

### Auth

Custom user model `apps.accounts.models.User` (`AUTH_USER_MODEL`), email-only login (`USERNAME_FIELD = 'email'`, `username = None`), backed by django-allauth with mandatory email verification. `apps.accounts.models.UserManager` is required — Django's default `UserManager.create_user()` demands `username` as a positional arg regardless of `USERNAME_FIELD`, so skipping this custom manager silently breaks `createsuperuser`/admin/any programmatic user creation (this happened once already; it's why the manager exists now). Signup uses `CustomSignupForm` and `CustomAccountAdapter` ([apps/accounts/forms.py](apps/accounts/forms.py), [apps/accounts/adapter.py](apps/accounts/adapter.py)) — extend these rather than allauth's defaults when changing signup/login behavior. Note: allauth's own signup path builds the `User` directly via the adapter and does not go through `UserManager.create_user()`, so it was unaffected by that bug — only `createsuperuser`/admin/scripts were.

Passwords are hashed with `apps.accounts.hashers.PepperedArgon2PasswordHasher`, which appends `PASSWORD_PEPPER` (env var, not stored in the DB) to the password before delegating to Django's stock Argon2id hasher. This is the only entry in `PASSWORD_HASHERS`; changing/removing it invalidates all existing password hashes.

### Lottery domain logic

Almost all business logic lives in [apps/loterias_core/utils.py](apps/loterias_core/utils.py), driven by the per-game config dicts (`JOGOS_CONFIG`) at the top of [apps/loterias_core/models.py](apps/loterias_core/models.py):

- `gerar_aposta()` — generates a random valid bet. Games in `JOGOS_COM_REGRA_SEQUENCIA` (Mega-Sena, +Milionária, Quina, Dupla-Sena) are subject to a sequential-numbers rule: if the user's last `INTERVALO_MIN_SEQUENCIA` (5) games of that type had a sequential pair, the next generated game must avoid sequential pairs entirely; otherwise at most one sequential pair is allowed. `contar_pares_sequenciais()` implements the pairing count.
- `capturar_resultado_cef()` — scrapes `loterias.caixa.gov.br` HTML directly (regex-based, no official API) to fetch official draw results. This is inherently fragile against site markup changes; it fails soft (returns `None`) rather than raising. Called on-demand today (user clicks "verificar"); there is no scheduled/automatic result polling yet, and no win notification (site or email) — both are planned but unimplemented. `Celery`/`redis` are already in requirements.txt for this purpose but have no tasks defined yet.
- `calcular_premiacao_jogo()` / `verificar_resultados_usuarios()` — compare a saved `JogoGerado` against a `ResultadoLoteria` to compute hits and prize value.

Models: `JogoGerado` (a user's generated bet, FK to `AUTH_USER_MODEL`), `ResultadoLoteria` (official draw result, unique per `jogo`+`concurso`), `EstatisticaJogo` (per-user/per-game aggregate stats, unique per `usuario`+`jogo`).

### Settings

`loterias/settings/__init__.py` just re-exports `base.py` — there's currently no separate dev/prod settings split; environment-specific behavior is driven entirely by env vars (via `python-dotenv` loading `.env`), e.g. `DEBUG`, `EMAIL_BACKEND`/Brevo SMTP vars, `SECRET_KEY`, `PASSWORD_PEPPER`. `requirements.txt` pins Django 5.0.6/django-allauth 0.63.3; always verify the active interpreter's installed versions actually match before debugging odd auth behavior — a prior environment drift (Django 6.0.5/allauth 65.19.2 installed against code written for 5.0.6/0.63.3) caused deprecated-settings warnings and was a contributing suspect in the multitenancy bug investigation.

### Deployment

Docker image builds from [Dockerfile](Dockerfile) (Python 3.12-slim, gunicorn). Lab deployment specifics (host, network, nginx-proxy, DNS) are documented in [deploy/lab/README.md](deploy/lab/README.md) — deploys via `docker compose -f deploy/lab/docker-compose.yml`, with `LOTERIAS_SECRET_KEY`/`LOTERIAS_PASSWORD_PEPPER` supplied only via the host's `.env`, never committed.

### Directories that are not part of the Django app

- `Laboratório/` — documentation/reconstruction notes for an unrelated internal lab infrastructure (`infra-lab`: DNS, reverse proxy, Keycloak, OpenBao, etc.), not this application's infrastructure.
- `_bmad/`, `_bmad-output/`, `.claude/`, `.agent/`, `.agents/`, `.cline/`, `.opencode/`, `.qwen/` — AI tooling/agent framework config, unrelated to app runtime code.
