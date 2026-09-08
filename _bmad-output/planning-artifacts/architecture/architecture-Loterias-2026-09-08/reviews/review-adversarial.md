---
name: 'Adversarial Review — ARCHITECTURE-SPINE.md'
type: architecture-review
target: '_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md'
verdict: 'not-safe-to-split — 7 real divergence gaps, 2 of them build-breaking on day one'
created: '2026-09-08'
---

# Adversarial Review — Loterias ARCHITECTURE-SPINE.md

**Method:** for each AD, construct two units that each obey the AD's literal text, built by developers/agents who cannot see each other's code, and check whether the result composes. Only reporting gaps that produce actual divergence (data-shape clash, dual ownership, race, dead-end route) — not style nitpicks.

**Verdict:** the spine is **not yet safe to split** across independent builders. Two gaps (G1, G2) are severe enough that a literal, good-faith implementation of the stated ADs breaks the product on day one (silent cross-user notification loss; admin/existing-user lockout). Five more (G3–G7) are real incompatibility risks that will surface later, under load or on rename day.

---

## G1 — [CRITICAL] Notification generation is coupled to "who wrote the LotteryResult row," not to actual outstanding work

**ADs involved:** AD-4, FR-1, FR-3, the Consistency Conventions row on `LotteryResult`/`HitNotification`.

**The trap:** the spine says `LotteryResult` is written via `update_or_create(game=, contest=)` by **two independent paths** — the existing on-demand path (`check_bet_result_view`, `save_manual_bet_view`) and the new `fetch_daily_results` job — "então não há conflito" (Consistency Conventions table). Separately, FR-3/AD-4 say a `HitNotification` is created **only** inside `fetch_daily_results`, and only "ao gravar um `LotteryResult` novo." FR-1 further scopes the job to only process "Jogo com concursos em aberto (**sem** `LotteryResult` registrado)."

Chain those three sentences together and you get: if *any* user's on-demand click (`check_bet_result_view`) or a manual-bet save (`salvar_jogo_manual`, which already calls `fetch_cef_result`/`capturar_resultado_cef` synchronously today — see `apps/loterias_core/views.py` lines 206–218) writes the `LotteryResult` for a Jogo+Concurso *before* the nightly job gets to it, that Jogo+Concurso is no longer "aberto." The nightly job will never again see it as a "LotteryResult novo" event — so it will **never** create `HitNotification` rows for any *other* user who holds a `GeneratedBet` on that same Jogo+Concurso. `LotteryResult` is global (unique per Jogo+Concurso, not per user), but the notification-creation trigger is a one-shot event on the row's creation, owned by whichever code path got there first.

The same coupling also means: if `fetch_daily_results` itself dies mid-loop (killed, OOM, exception) after `update_or_create`-ing the `LotteryResult` row but before finishing the per-`GeneratedBet` notification/email loop for that concurso, the 3h15/3h30 re-runs (AD-6) will skip it too — it's not "aberto" anymore — and the unfinished users are silently never notified. There is no "ensure every `GeneratedBet` for every existing `LotteryResult` has a `HitNotification`" reconciliation pass anywhere in the spine; notification creation is purely event-driven off the write, never state-driven off the read.

**Two compliant-but-incompatible units:**
- **Unit A** (implements FR-3/AD-4 literally): `fetch_daily_results` checks `created=True` from its own `update_or_create` call and only then loops `GeneratedBet` → `HitNotification`. Fully spec-compliant.
- **Unit B** (keeps `check_bet_result_view`/`save_manual_bet_view` "unchanged," as the PRD's own `[NOTE FOR PM]` under FR-9 explicitly says is fine — "continua funcionando em paralelo... não há conflito"): on-demand `update_or_create` on the *same* `LotteryResult` row, zero awareness of `HitNotification`.

Both are individually correct per their own AD. Composed: any single user who clicks "verificar" before 3am (or whose manual-bet save auto-checks) permanently and silently suppresses SM-1 ("Todo Acerto Premiado gerado pela rotina diária resulta em uma Notificação visível") for every other user sharing that Jogo+Concurso — a real prize, with a real `LotteryResult`, that never produces a notification for anyone else. This is exactly the kind of "two different owners writing the same entity" clash the review was asked to hunt for.

**Fix direction:** decouple notification creation from "did I just write this row." Either (a) make notification generation a state-derived pass — for every `LotteryResult` (new or pre-existing) missing `HitNotification` coverage across matching `GeneratedBet` rows, regardless of which path created it — run inside `fetch_daily_results` (and/or on-demand path too, gated so it never sends duplicate email — see G4), or (b) retire the on-demand `LotteryResult`-writing side effect now that the daily job exists, and have `check_bet_result_view` only *read* an existing result rather than fetch/write one. AD-4 needs to pick one and say so explicitly; right now it lets both paths write and assumes that's harmless, which it is only for the single row itself, not for the notification fan-out keyed off it.

---

## G2 — [CRITICAL] AD-8's allowlist has no `/admin/` or staff exemption, and no grandfather clause for pre-existing users

**AD involved:** AD-8.

**The trap:** AD-8's rule is "redireciona **qualquer** request autenticado com `first_name`/`last_name` vazio... exceto a própria tela de captura, assets estáticos e logout." This is a blanket rule with a three-item allowlist. Two things it doesn't account for:

1. **Every account that exists today** (this is a live, already-deployed app — see `deploy/lab/docker-compose.yml`, commit `39b4b50 Deploy`) has `first_name`/`last_name` blank, because nothing before this PRD ever asked for them. `AbstractUser.first_name`/`last_name` default to `blank=True`, and `apps/accounts/models.py`'s own `create_user`/`create_superuser` never populate them. FR-14's UJ-2 describes this as a **new-signup** gate ("no primeiro login... obrigatório"), but AD-8's Rule text says "qualquer request autenticado" with no cutover/grandfather condition — nothing distinguishes "first login after the new FR-10–14 flow" from "any pre-existing session."
2. **`/admin/`** is not in the allowlist. `django.contrib.admin` is installed (`INSTALLED_APPS` in `loterias/settings/base.py`) and is how Ricardo (the Boss/operator) manages the site today.

**Two compliant-but-incompatible units:**
- **Unit A** implements the middleware literally: blanket check, allowlist = {capture screen, static, logout}. On deploy, this immediately redirect-locks every existing user — including Ricardo's own admin/staff login, since `/admin/login/` accepts the session but the *next* admin page request gets redirected to the capture screen (which itself isn't part of the admin site and offers no path back into `/admin/`).
- **Unit B**, building the same middleware from the "obviously this is for new signups" reading, adds an unstated exemption — e.g. `if user.is_staff: return None` or `if user.date_joined < CUTOVER_DATE: return None` — neither of which appears anywhere in the spine, so a reviewer checking Unit B "against the AD" would flag it as scope creep, and a different agent building the companion FR-14 view story has no way to know which exemption (if any) Unit A assumed.

**Fix direction:** AD-8 needs an explicit statement on (a) whether `/admin/` (or `is_staff`/`is_superuser`) is exempt, and (b) how pre-existing accounts are handled — a data migration that backfills a sentinel/marks them "grandfathered," or an explicit `date_joined`/flag cutover, or a one-time management command. Silence here isn't a detail two builders will independently converge on; it's a coin flip between "gate everyone, including yourself, out of admin" and "gate only new users," decided differently by whoever writes the middleware vs. whoever runs the first production deploy.

---

## G3 — [HIGH] AD-8's allowlist doesn't include FR-12's password-creation screen, and the two "the user is authenticated but incomplete" gates fight over the same request

**ADs involved:** AD-8, FR-12, FR-10, existing allauth settings (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True`, `ACCOUNT_CONFIRM_EMAIL_ON_GET = True` in `loterias/settings/base.py`).

**The trap:** today, clicking the email-confirmation link both confirms the email **and logs the user in** (that's what `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` does), then redirects to `LOGIN_REDIRECT_URL` ('/'). FR-10/FR-12 layer a new "pending account, no usable password yet" state on top of that same mechanism — the user is expected to land on a password-creation screen next. But at the moment they're logged in via the confirmation link, `first_name`/`last_name` are empty (FR-14 hasn't happened yet) — so AD-8's `RequireProfileCompletionMiddleware`, whose allowlist is only "a própria tela de captura, assets estáticos e logout," will intercept that very first authenticated request and redirect to the name-capture screen *before the password-creation screen (FR-12) is ever reached*. The password is never set; the user "completes" the name-capture form and is now sitting inside the app fully authenticated with no password ever having been chosen — silently breaking FR-12's contract.

**Two compliant-but-incompatible units:**
- **Unit A** (AD-8 middleware, built to the letter): allowlist = {capture screen, static, logout}. Doesn't know FR-12's screen needs to run first.
- **Unit B** (FR-10–13 signup flow, built to the letter): assumes the standard allauth "confirm → authenticated → land on my custom password-set view" flow works as it does today, unaware a colleague's middleware will intercept that redirect first.

Neither AD says which screen has precedence when both conditions are true (empty password *and* empty name), or that FR-12's URL must be added to AD-8's allowlist.

**Fix direction:** AD-8's allowlist must explicitly include the password-creation view's URL name, and the spine should state the ordering invariant directly: "password-incomplete gates password-complete gates name-complete" (or fold both gates into one middleware with an explicit precedence list), not leave two independently-built gates to race for the same redirect.

---

## G4 — [HIGH] No mandated uniqueness/atomicity for `HitNotification`, combined with AD-6's independent cron triggers and AD-7's dual-writer container, opens a duplicate-email race

**ADs involved:** AD-3, AD-4, AD-6, AD-7.

**The trap:** AD-6 puts three independent `CRONJOBS` entries (3h00/3h15/3h30) on the same idempotent job, relying on `LotteryResult`'s `update_or_create` + "no longer open" filtering to make re-runs safe. That's sound *for the `LotteryResult` row itself*. But nothing in AD-3/AD-4/the Consistency Conventions table requires a DB-level uniqueness constraint (e.g. `unique_together`/`UniqueConstraint` on `(bet, result)`) on `HitNotification`, nor mandates `get_or_create`/`update_or_create` as its write pattern — FR-3's "no máximo uma vez... idempotente" is stated only as a testable consequence, not as an enforced invariant. `django-crontab` (per the Stack section) doesn't itself guarantee non-overlapping runs; if a 3h00 invocation is still scraping (network stalls against `loterias.caixa.gov.br` are the documented normal failure mode) when 3h15 fires, you can get two OS processes — potentially split across the same `loterias-cron` container or, worse, no barrier at all if `loterias-web` also happens to run `check_bet_result_view` concurrently — evaluating "does this `GeneratedBet`+`LotteryResult` pair already have a `HitNotification`" at the same instant, both getting "no," and both creating a row. FR-7 fires an email per premiada notification created — so this is a duplicate-email bug in exactly the case the PRD calls out as a non-negotiable contra-metric (SM-C1: "nunca reenviado por reexecução da rotina").

**Two compliant-but-incompatible units:**
- **Unit A**'s model for `HitNotification` has no unique constraint (spine doesn't require one); job logic does a plain `.exists()` check then `.create()` — correct under sequential execution, racy under overlap.
- **Unit B** independently adds `unique_together = ('bet', 'result')` as a defensive modeling choice (also not prohibited) and writes via `.create()` inside a `try/except IntegrityError` — different failure mode (constraint violation swallowed) than Unit A (silent duplicate row + duplicate email).

Both "obey" AD-3/AD-4's text; the actual behavior under a real overlap is different depending purely on which developer happened to add the constraint.

**Fix direction:** AD-3 or AD-4 should mandate a DB-level `UniqueConstraint`/`unique_together` on `(bet, result)` for `HitNotification` (matching the ER diagram's own "gera no máximo 1" cardinality, which is currently only a diagram annotation, not an enforced rule) and mandate `get_or_create`/`update_or_create` as the write path — turning a possible race into a guaranteed-idempotent no-op instead of leaving the outcome to whichever builder happened to think of it.

---

## G5 — [MEDIUM-HIGH] Nothing specifies how `fetch_daily_results()` knows it's the "3h30 = final attempt" run that should email the operator

**ADs involved:** AD-5, AD-6, FR-9.

**The trap:** AD-5 mandates jobs as pure functions with a management command that "só chama a função," and `CRONJOBS` pointing at `call_command` with the command name — "nunca a função direta." AD-6 then requires that **only** the 3h30 invocation emails the operator alert (FR-9), and only for Jogo/Concurso still without a `LotteryResult` after all three tries. But `fetch_daily_results()` is specified as a single, parameterless-sounding pure function, invoked identically by all three `CRONJOBS` entries — nothing says how the function (or its management-command wrapper) distinguishes "I am the 3rd invocation of the day" from "I am the 1st."

**Two compliant-but-incompatible units:**
- **Unit A** (jobs.py author) implements clock introspection inside the function: `if timezone.localtime().minute >= 30: send_alerts()`. Fragile (a cron fired a minute late from container CPU contention silently skips the alert, or double-fires it if the previous run overran past :30), but matches "the function needs no external signal."
- **Unit B** (settings/CRONJOBS author) assumes the natural Django idiom instead: three `CRONJOBS` entries calling the *same* management command with a different `--attempt=1/2/3` argument, which the command threads into `fetch_daily_results(attempt=N)`.

If Unit A ships `fetch_daily_results()` with no `attempt` parameter and Unit B's `CRONJOBS`/command wrapper passes one, that's a `TypeError` at every single nightly run. If Unit A ships clock-based detection and Unit B never wires an argument, it "works" by accident but is exactly the kind of implicit coupling a spine should have foreclosed.

**Fix direction:** AD-6 (or AD-5) should fix the actual interface: either the management command accepts an explicit `--attempt`/`--final` flag and the spine states that in the Structural Seed, or the spine states clock-based detection is the intended mechanism and specifies the exact boundary (e.g., "invocation is final iff `>= 03:25` local time," with a rationale for why that's robust to a few minutes of scheduler jitter).

---

## G6 — [MEDIUM] AD-2's rename mapping (PRD §3.1) is silent on identifiers shared *across* the three renamed models, inviting divergent translations mid-rename

**ADs involved:** AD-2, AD-1, PRD §3.1.

**The trap:** the mapping table (PRD §3.1) is thorough for field names and function names, but misses at least two symbols that are referenced *across* class boundaries in `apps/loterias_core/models.py` today:
- `related_name='jogos'` (on `JogoGerado.usuario`) and `related_name='estatisticas'` (on `EstatisticaJogo.usuario`) — these are code identifiers under AD-1's own rule ("todo identificador de código... é em inglês"), used as `user.jogos`/`user.estatisticas` reverse accessors, but they don't appear anywhere in the §3.1 table.
- `ResultadoLoteria.JOGOS_CHOICES = JogoGerado.JOGOS_CHOICES` and `EstatisticaJogo.jogo = models.CharField(..., choices=JogoGerado.JOGOS_CHOICES, ...)` — `LotteryResult` and `GameStatistics` reference `GeneratedBet`'s class attribute `JOGOS_CHOICES` directly, but that attribute name is also absent from the §3.1 table (only the module-level `JOGOS_CONFIG`/`JOGOS_COM_REGRA_SEQUENCIA`/`INTERVALO_MIN_SEQUENCIA` constants are listed).

**Two compliant-but-incompatible units:** AD-2 says the rename is "um epic isolado," not necessarily one atomic PR — nothing prevents it being split model-by-model between two developers/agents (e.g., one doing `GeneratedBet`, another doing `LotteryResult`/`GameStatistics`, both "renaming per §3.1"). If the `GeneratedBet` renamer picks `GAME_CHOICES` for the old `JOGOS_CHOICES` (a reasonable English name, not contradicted by §3.1) while the `LotteryResult`/`GameStatistics` renamer — working from the same table, seeing no entry for it — independently writes `GamesChoices` or keeps referencing `GeneratedBet.JOGOS_CHOICES` (not yet renamed on their branch), the file fails to import. Same risk for `related_name`: one picks `generated_bets`, the unrelated admin/template code (or a test) expecting the old `jogos` accessor breaks with no compile-time signal — only a runtime `AttributeError`, easy to miss if AD-2's "passa 100% na suite de testes" gate doesn't happen to cover every reverse-accessor usage (the current `tests.py` does not exercise `user.jogos`/`user.estatisticas` directly).

**Fix direction:** either extend the PRD §3.1 table (owned by the PRD, but the spine's AD-2 is the thing that should flag this as a completeness requirement before the rename epic is considered "done") to include `related_name` values and cross-referenced class attributes, or have AD-2 state a stronger rule: "the rename epic is a single PR/commit across all three models, reviewed as one unit, specifically because cross-model references (shared `choices=`, `related_name`) can't be safely split across independent renamers."

---

## G7 — [MEDIUM] AD-7 puts two containers on one SQLite file with no mandated concurrency setting

**ADs involved:** AD-7, Stack section.

**The trap:** before this spine, `loterias-web` was the only writer to `db.sqlite3`. AD-7 adds `loterias-cron` as a second, routinely-writing process against the same file via the shared `loterias_data` volume — explicitly by design ("os dois containers só se comunicam através do arquivo SQLite... nunca por HTTP"). Django's sqlite3 backend defaults to no `timeout` in `DATABASES[...]['OPTIONS']` (i.e., `sqlite3`'s own default, effectively immediate failure on lock contention) and the repo's `loterias/settings/base.py` sets no `OPTIONS` at all. Nothing in the Stack table or AD-7 mandates WAL journal mode or a busy-timeout, even though AD-7 is precisely the change that makes sustained concurrent writers (a nightly job doing potentially dozens of `update_or_create`/`create` calls across many Jogos over multiple minutes, per FR-1/FR-3) newly routine, at the same time real users are generating/checking bets during business hours (less likely at 3am specifically, but the job's retries under AD-6 can span 3h00–3h30+, and nothing constrains `update_monthly_prize_values` — FR-8 — to a specific off-peak hour at all).

**Two compliant-but-incompatible units:** the developer wiring `loterias-cron` (AD-7) and the developer touching `loterias/settings/base.py` for an unrelated reason (e.g. FR-6/FR-14 changes) both leave `DATABASES[...]['OPTIONS']` untouched — neither AD requires either of them to add it, so it's equally likely nobody does, and equally possible one dev "fixes" it locally in a way the other doesn't know about (e.g. adding `'timeout': 20` only when debugging a `database is locked` error they hit personally, without it being recorded as a project-wide convention).

**Fix direction:** AD-7 (or a new small AD) should mandate `DATABASES['default']['OPTIONS'] = {'timeout': N}` (and/or WAL mode via a startup `PRAGMA`) as part of introducing the second writer, stated once in the spine so it isn't left to whichever developer happens to hit the lock error first in production.

---

## Lower-confidence / worth a look but not written up in full

- **NotificationPreference default-row ownership (AD-3):** "`NotificationPreference` só é escrita pela própria tela de preferências" reads as forbidding any other write path, but FR-7's email-gating check in `fetch_daily_results` needs *some* answer for users who never visited the preferences screen (no row exists yet). A read-side default-fallback (`site_enabled=True, email_enabled=False` when no row) is consistent with the AD; a `get_or_create` call from the job is a plausible, idiomatic implementation that technically violates the AD's literal wording. Worth AD-3 stating explicitly which one is intended, and whether `user` is enforced unique (`OneToOneField`) since that isn't stated either.
- **Middleware allowlist granularity vs. same-page ancillary endpoints:** the profile-completion screen almost certainly renders the site's shared template chrome (theme toggle, etc.); `accounts/theme/toggle/` isn't in AD-8's stated allowlist ("captura, estáticos, logout"), so a legitimate in-page action from the capture screen itself gets redirected back to the same screen instead of executing. Minor (no infinite loop, just a silently-broken toggle), but it's the same root cause as G2/G3 — the allowlist is enumerated by guessing at what an authenticated-incomplete user might click, not derived from an actual list of exempt URL names fixed in the spine.

---

## Summary Table

| ID | Severity | AD(s) to tighten | One-line gap |
|----|----------|-------------------|---------------|
| G1 | Critical | AD-4 (FR-3 trigger) | Notification creation fires on "I wrote this row," not "this row needs coverage" — on-demand writes silently starve other users' notifications |
| G2 | Critical | AD-8 | Allowlist has no `/admin/`/staff exemption and no grandfather clause — blanket rule locks out every pre-existing account, including the operator, on deploy |
| G3 | High | AD-8 (+ FR-12) | Password-creation screen not in the allowlist — profile-completion gate wins the race and password is never set |
| G4 | High | AD-3 / AD-4 | No mandated uniqueness constraint on `HitNotification` — overlapping cron runs (AD-6) can double-create notifications and duplicate emails (violates SM-C1) |
| G5 | Medium-High | AD-5 / AD-6 | No specified mechanism for `fetch_daily_results()` to know it's the "final" (3h30) invocation that should alert the operator |
| G6 | Medium | AD-2 / PRD §3.1 | Rename mapping omits cross-model identifiers (`related_name`, shared `JOGOS_CHOICES`) — splitting the rename by model risks import-breaking divergence |
| G7 | Medium | AD-7 | Two containers now write one SQLite file with no mandated timeout/WAL setting |
