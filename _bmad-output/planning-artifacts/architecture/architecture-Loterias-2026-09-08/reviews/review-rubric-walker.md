# Review: ARCHITECTURE-SPINE.md (Loterias, 2026-09-08)

**Reviewer:** rubric-walker (good-spine checklist)
**Target:** `_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md`
**Driving spec:** `_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md` (FR-1..FR-14, §3.1 rename)
**Also checked against:** `CLAUDE.md`, `docs/diagnostico-projeto.md`, and the actual code (`apps/loterias_core/models.py`, `utils.py`, `views.py`, `apps/accounts/{models,forms,adapter,views,urls}.py`, `loterias/settings/base.py`, `Dockerfile`, `deploy/lab/docker-compose.yml`, `requirements.txt`).

## Verdict

**Not ready as-is.** The spine is well-formed and mostly ratifies the brownfield code correctly (naming/rename mapping, current write-paths for `ResultadoLoteria`, current Dockerfile/compose shape are all described accurately), and the cron/notification half (FR-1–FR-9) is architected with real, checkable rules (AD-5/6/7). But it has two areas where a Rule is either unenforceable as written or entirely absent for the PRD's most novel/risky capability, plus one un-modeled data need and one environmental gap. These are exactly the kind of divergence points a spine review exists to catch — recommend a revision pass before this is used to drive epics/stories.

---

## Findings

### 1. [HIGH] AD-7's sidecar rule doesn't actually run `cron` — it reuses an image that has no cron binary

AD-7's own diagnosis is correct: "a imagem atual (`python:3.12-slim`) não tem daemon de cron instalado." Verified against `Dockerfile`: it does `pip install -r requirements.txt` and nothing else — zero `apt-get`/system package steps, so there is no `cron` executable in the image today.

But AD-7's *Rule* says the new `loterias-cron` service uses "mesma imagem/Dockerfile do `loterias-web`" with `CMD` changed to `manage.py crontab add && cron -f`. If the Dockerfile is genuinely unchanged, `cron -f` has nothing to exec — the sidecar container will crash-loop or no-op, and (per AD-7's own stated purpose) "a rotina simplesmente nunca dispara em produção," which is precisely the failure mode the AD claims to prevent.

This fails the checklist item "Every AD's Rule is enforceable and actually prevents its stated divergence" — it's enforceable (a builder can absolutely stand up a second compose service with that CMD) but it does not prevent the divergence/failure it names, because the missing ingredient (`apt-get install -y cron`, or a separate `Dockerfile.cron` / build stage) is never stated as part of the rule.

**Fix:** AD-7's Rule needs an explicit line that the Dockerfile (or a cron-specific variant/stage) installs the `cron` package, otherwise two builders will hit this in two different ways (one patches the shared Dockerfile, one forks a second Dockerfile, one discovers it in prod).

### 2. [HIGH] FR-10–FR-13 (passwordless-first signup) has no architecture — dismissed as "just extend the existing form," but the existing form and settings do the opposite of what's needed

The Capability Map row for FR-10–FR-13 says: *"apps/accounts (views/forms existentes, estendidas) | convenção já fixada em CLAUDE.md (estender `CustomSignupForm`/`CustomAccountAdapter`)."* That treats this as routine, already-covered ground.

Checked against the actual code and settings, and this is not routine:

- `loterias/settings/base.py`: `ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']` — password is required at signup **today**. FR-10 requires the signup screen to ask for **only** email.
- `ACCOUNT_CONFIRM_EMAIL_ON_GET = True` + `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` — today, clicking the confirmation link confirms and **logs the user in immediately**. FR-12 requires the link to land on a password-creation screen instead, and FR-10 requires "conta pendente não permite login antes da senha ser definida" — i.e., login must be blocked until a step that, in the current settings, is skipped entirely (password already exists) and gated by a flag (auto-login) that must not fire yet.
- `apps/accounts/forms.py` `CustomSignupForm` currently requires `first_name`/`last_name` at signup and inherits allauth's password fields — none of that matches "e-mail only" (FR-10) or "name/surname only at first login" (FR-14).
- `apps/accounts/models.py` has no notion of a "pending" account (no usable-password flag, no state field) that a builder could use to gate login.

This is not a narrow gap — it's the single most novel mechanism in the whole PRD (deliberately inverting allauth's built-in signup/confirm/login sequence), yet it gets zero AD, no decision on which adapter/view hooks change, no decision on how "pending, no password yet" is represented, and no reconciliation with the `ACCOUNT_*` settings that currently contradict it.

Tellingly, the spine's own cited source, `docs/diagnostico-projeto.md` §5.3, already flagged this explicitly: *"precisa de uma view de 'definir senha' customizada acionada pelo link de confirmação, e um passo obrigatório de completar perfil no primeiro acesso autenticado."* The spine cites this document as a source but doesn't carry its own diagnosis forward into an AD — it regresses to treating the work as a template-level `forms.py` edit.

**Risk if unaddressed:** two builders will independently invent incompatible solutions — e.g. one adds a `has_usable_password()` check + custom `ACCOUNT_ADAPTER.login()` override, another adds a new boolean field to `User`, a third builds a bespoke non-allauth view outside `SignupView` entirely — each with different implications for `EmailConfirmationHMAC` reuse (FR-11/13 depend on the same token mechanism), for the `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` setting, and for whether `CustomSignupForm` still exists as today's class or is replaced.

### 3. [MEDIUM-HIGH] AD-6's exact cron times assume a timezone the container isn't shown to have

AD-6 pins the retry schedule to three concrete wall-clock times: 3h00, 3h15, 3h30 "horário de Brasília." `django-crontab`'s `CRONJOBS` writes ordinary crontab lines, which the OS `cron` daemon interprets in the **container's system time**, not Django's `TIME_ZONE` setting (`America/Sao_Paulo`, confirmed in `loterias/settings/base.py`) — `TIME_ZONE`/`USE_TZ` only affect how Django itself renders/stores datetimes, not what wall-clock cron fires on.

Neither the `Dockerfile` nor `deploy/lab/docker-compose.yml` sets `TZ` or installs `tzdata`. Docker's `python:3.12-slim` defaults to UTC. As specified, "3h00" in the container's crontab is 3h00 UTC = 00h00 Brasília — a 3-hour drift that could run the routine *before* the nightly Caixa draws finish, directly undermining the stated rationale in FR-1 ("janela segura após os sorteios noturnos da Caixa terminarem") and AD-6 itself.

**Fix:** AD-7 (or AD-6) needs an explicit line: set `TZ=America/Sao_Paulo` (and install `tzdata`) in the cron container/image, or express the `CRONJOBS` entries with that constraint made explicit, so a builder doesn't ship a routine that silently fires at the wrong time.

### 4. [MEDIUM] FR-8's "tabela de valores de premiação vigentes" is a new data need that's never modeled anywhere in the spine

FR-8 states `update_monthly_prize_values` "atualiza a tabela de valores de premiação vigentes usada por `calculate_bet_prize`." That's a persistent structure distinct from anything in the current schema — today, `calcular_premiacao_jogo`/`calculate_bet_prize` reads prize values embedded in the specific `resultado_oficial`/`LotteryResult.premiacoes` for that draw (confirmed in `apps/loterias_core/utils.py`), not from any separate "current tier values" table.

The spine's Models list (Design Paradigm + Structural Seed) only adds `HitNotification` and `NotificationPreference` (AD-3). Nowhere is a model, field, or even a settings constant named for the "tabela vigente" FR-8 needs. This also sits in tension with the FR-9 NFR the spine itself echoes in Consistency Conventions — that a displayed prize must always trace to a concrete `LotteryResult.prizes` and never be estimated — without the spine resolving whether FR-8's "current" table is a fallback/estimate source (which the NFR forbids using for display) or something else entirely.

This is a real capability (FR-8, explicitly bound in the frontmatter and mapped in the Capability table) with no architecture behind its data, which is exactly the kind of gap that lets two builders pick incompatible schemas (a new model vs. a field bolted onto `LotteryResult` vs. a settings/constants dict).

### 5. [LOW] Stack table materially understates how stale `django-crontab` is

The version pin itself checks out: PyPI's `django-crontab` latest release is indeed `0.7.1` — this is genuinely the current/only available version, not a hallucinated one. But the risk note ("não recebe release há mais de 12 meses") is a significant understatement: `0.7.1` shipped **March 2016** — over a decade unmaintained, not "12+ months." The "risco baixo" conclusion may still be right (it's a small package that only shells out to `python-crontab`), but the evidence quoted to support it undersells the actual staleness, which matters for a portfolio document meant to demonstrate the PM's diagnostic rigor (per PRD §2.1's "Jobs To Be Done" bullet about the project demonstrating that rigor).

### 6. [LOW] Two smaller gaps, noted for completeness

- **FR-2's capability-map row** ("bloqueio de concurso já sorteado") glosses over that it's a behavior change to code that already ships: today `gerar_jogo`/`salvar_jogo_manual` only *warn* (not block) on a duplicate `jogo`+`concurso` for the *same user* (see `apps/loterias_core/views.py` lines ~60–61 and ~192–193); FR-2 requires a hard block keyed on whether *any* `LotteryResult` exists for that `jogo`+`concurso`, which is a different check entirely. Not an architecture-breaking omission (it's confined to two view functions), but a one-line Consistency Convention entry would remove ambiguity about "block, don't warn" and "check `LotteryResult`, not sibling `GeneratedBet` rows."
- **No restart policy stated for `loterias-cron`.** The existing `loterias-web` service has `restart: unless-stopped`; AD-7's rule for the new sidecar doesn't say whether it inherits the same policy. If the cron container dies silently, FR-1/FR-8 simply stop running with no operational signal — a small operational-envelope gap worth one line in AD-7.

---

## What the spine gets right (for balance)

- Paradigm (Shared-Database integration between web and cron processes, never in-process calls) is a genuinely useful invariant and is enforced consistently through AD-5/6/7.
- AD-1/AD-2 (rename convention + rename-epic-first sequencing, using `RenameModel`/`RenameField` with a pre-migration backup step) directly and correctly answers PRD Open Question §8.4.
- The rename mapping table cross-checked cleanly against the actual `apps/loterias_core/models.py`/`utils.py`/`views.py` symbol names — no stale or invented legacy names found.
- AD-3/AD-4's "no second source of truth" rule (cache fields on `GeneratedBet` stay authoritative, `HitNotification` never substitutes them) is a real, enforceable rule that would catch a common bug class.
- The Consistency Conventions table correctly reuses django-allauth's existing `EmailConfirmation` history for FR-11's cooldown/rate-limit instead of inventing a new model — good minimalism, and it's an accurate read of what allauth already tracks.
- `requirements.txt`/`Dockerfile`/`docker-compose.yml` claims about current state (celery/redis present but unused, no cron service today, single `gunicorn` process, no `django-crontab` in requirements) all checked out exactly as described.
