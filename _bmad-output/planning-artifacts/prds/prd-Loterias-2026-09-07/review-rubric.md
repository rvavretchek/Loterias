# PRD Quality Review — Loterias: Verificação de Resultados e Novo Fluxo de Cadastro

## Overall verdict

This is an unusually earned PRD for its scale: every FR carries testable consequences, the Não-Objetivos/§6.2 sections de-scope honestly instead of by omission, and the brownfield references (`capturar_resultado_cef`, `calcular_premiacao_jogo`, `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) check out against the actual codebase. The main soft spots are a handful of unquantified numbers inside otherwise-testable FRs (FR-1's "ex.: 3h", FR-9's "2–3 tentativas... com espaçamento") and a bundling of two only loosely-related feature areas under one Vision without naming a single MVP scope kind. Nothing here blocks moving to architecture/stories; the findings below are tightening, not rescue work.

## Decision-readiness — strong

The PRD states decisions as decisions rather than hedged considerations. §5 rejects Celery+Redis explicitly with a stated reason ("desproporcional a duas tarefas periódicas simples neste porte de projeto") rather than presenting it as an open option. FR-9 names a real trade-off and its cost in plain language: failure is silent to the end user ("não é um alerta ao usuário final... O usuário final simplesmente não vê Notificação") while alerting only the operator — the PRD doesn't dress this up as acceptable-to-everyone. §6.2 explicitly defers an admin panel for failure history to v2 rather than pretending FR-9's operator email is a complete solution. The three Open Questions in §8 are genuinely open (env var name, ToS legal text, where operator sees alert history) — none is a rhetorical question answered in the next sentence.

### Findings
- **low** Working title unresolved (title line, "*Working title — confirmar.*") — a cosmetic loose end but it is a decision left dangling in the one place a reader looks first. *Fix:* resolve before this PRD is treated as final, or move the note to §8.

## Substance over theater — strong

No findings. Only two UJs, both load-bearing (UJ-1 drives FR-1–FR-9, UJ-2 drives FR-10–FR-14) — no persona padding. The NFRs under §4.1 and §4.2 are product-specific, not boilerplate: "o sistema nunca estima ou arredonda um valor de prêmio na ausência de dado oficial confirmado" and "as rotinas agendadas respeitam uma cadência deliberadamente baixa... para não sobrecarregar nem ser bloqueado pelo site da Caixa" both name a concrete failure mode being guarded against, not a generic "must be reliable." The Vision (§1) is grounded in the actual current UX gap ("precisa lembrar de voltar ao site e clicar manualmente em 'verificar resultado', jogo por jogo") rather than a swappable statement.

## Strategic coherence — adequate

§1's thesis — the system should answer "e se eu tiver ganhado?" without being asked — genuinely drives Feature 4.1 end to end: FR ordering (capture → cross-check → notify → detail → preference → email → failure handling) follows the thesis, not ease of implementation. Success Metrics reinforce it rather than measuring activity: SM-1 is about notification reliability, not engagement volume, and SM-C1 is a real counter-metric ("não otimizar" — bounds email volume against SM-1's own incentive to over-notify).

Feature 4.2 (cadastro) is not united with this thesis, and the PRD does not pretend otherwise — §1 justifies it separately as matching "como o Ricardo quer que a primeira impressão do produto aconteça," and §0 frames the document itself as serving two purposes (working spec + portfolio piece) rather than one product thesis. The honesty is good; the coherence gap is still real for a reader trying to extract "what is this PRD betting on" as a single sentence.

### Findings
- **medium** Two feature areas, no single thesis (§1, §0) — the Vision paragraph argues for 4.1 from the notification thesis and then bolts on 4.2 via a different justification ("corresponde a como o Ricardo quer que a primeira impressão... aconteça"). A reader building a slide from this PRD would need two sentences, not one. *Fix:* either split into two PRDs, or add one sentence in §1 naming the umbrella logic (e.g., "this release fixes the two moments — first impression, first win — where the product currently requires the user to do the system's job").
- **low** MVP scope kind not named — §6 doesn't state whether this MVP is problem-solving, experience, platform, or revenue-shaped (rubric §3). It's inferable (4.1 reads as problem-solving, 4.2 as experience) but left implicit.

## Done-ness clarity — strong

This is the PRD's best dimension. Every FR (FR-1 through FR-14) carries a "Consequências (testáveis)" block with verifiable conditions — e.g. FR-2's "retorna erro claro, sem gravar o registro" is paired with a concrete negative case ("Concurso fora da sequência normal... é aceito normalmente"), and FR-11 gives hard numbers ("desabilitado por 60 segundos," "Limite de 5 reenvios por conta por dia") instead of adjectives. FR-4's UX placement is explicitly deferred ("local exato definido por UX") rather than left ambiguous by omission — that's a legitimate deferral, not a done-ness gap.

### Findings
- **medium** FR-9's retry policy is underspecified for something the FR itself calls testable — "tenta novamente 2–3 vezes (com espaçamento entre tentativas)" doesn't say whether it's 2 or 3, and "espaçamento" has no duration. The consequence "Esgotadas as 2–3 tentativas do dia, exatamente um e-mail..." can't be tested without picking one. *Fix:* commit to a number and a spacing value (or explicitly mark both `[ASSUMPTION]` deferred to implementation, matching how FR-9's operator-email address is already tagged).
- **low** FR-1's schedule is illustrative, not committed — "de madrugada (ex.: 3h, horário de Brasília)" — the "ex.:" signals this is an example, so an engineer doesn't know if 3h is the requirement or a placeholder. *Fix:* either commit to a time or mark it `[ASSUMPTION]` like FR-9's email variable is.
- **low** FR-8's monthly cadence has no day/time specified (unlike FR-1's "ex.: 3h" at least gestures at one) — "Mensalmente, o sistema atualiza..." doesn't say which day of the month. Low severity since the FR's own testable consequence doesn't depend on the exact day.

## Scope honesty — strong

§5 (Não-Objetivos) and §6.2 (Fora de Escopo do MVP) both do real work rather than gesturing — §6.2 names four concrete omissions, one flagged `[NOTE FOR PM]` for pre-launch revisit (ToS text) and one explicitly deferred to v2 with the reason why it's safe to defer (FR-9 "registra o problema, mas não define onde/como o operador vê isso"). Open-items density (3 Open Questions, 1 inline `[ASSUMPTION]`, 2 `[NOTE FOR PM]`) is appropriately light for a solo-dev/portfolio-stakes PRD — the rubric's guidance that high counts are fine at low stakes cuts the other way too: this count is proportionate, not thin.

### Findings
- **low** Assumptions Index roundtrip is incomplete — §9's second entry ("§4.2, FR-12 — texto dos termos de serviço é o placeholder...") has no matching inline `[ASSUMPTION]` tag at FR-12 itself (§4.2, FR-12 only says "texto placeholder no Anexo A" with no bracket marker), unlike the first entry, whose inline tag is present at FR-9's consequências. See also Mechanical notes.

## Downstream usability — strong

Glossário (§3) is genuinely load-bearing — ten terms defined once and used identically everywhere checked (e.g. "Notificação de Acerto" appears consistently across UJ-1, FR-3–FR-7 with the same capitalization). §0 explicitly instructs downstream readers to treat the Glossário as canonical. FR IDs (FR-1–FR-14), UJ IDs (UJ-1, UJ-2), and SM IDs (SM-1–SM-3, SM-C1) are contiguous with no gaps or duplicates. UJs each have a named, contextualized protagonist (Dulce, Sônia) rather than floating scenario text.

### Findings
- **low** Inconsistent "Realiza UJ-X" tagging — FR-2, FR-3, FR-5, FR-9, FR-10, FR-12, FR-13, FR-14 each state which UJ step they realize; FR-1, FR-6, FR-7, FR-8, FR-11 don't. This is defensible (those five are supporting/cross-cutting FRs not tied to one UJ step) but it's not stated as a convention, so a downstream reader can't tell "omitted because cross-cutting" from "omitted by oversight." *Fix:* one line in §4's intro clarifying the convention.

## Shape fit — strong

The PRD sits between two shapes and names the tension itself: §0 states it serves as both a working spec and a portfolio artifact ("a documentação em si é parte do valor demonstrado"), which explains and justifies rigor well beyond what a pure hobby/solo project would need (rubric: "Hobby/solo → rigor light, substance bar still applies"). Because the elevated rigor is a stated goal rather than an accident, it isn't over-formalization. UJs with named protagonists are appropriately load-bearing given this is a real consumer-facing flow (Dulce, Sônia), not an internal single-operator tool. Brownfield references were spot-checked against the actual repo and are accurate: `capturar_resultado_cef`, `calcular_premiacao_jogo`, and `verificar_resultado_jogo` all exist in `apps/loterias_core` (views.py/utils.py/models.py), `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` exists in `loterias/settings/base.py`, and `celery`/`redis` are indeed still present in `requirements.txt`, confirming §5's claim that they need removal.

No findings.

## Mechanical notes

- **Assumptions Index roundtrip — one entry unmatched.** §9's first entry (FR-9 operator email) has a corresponding inline `` `[ASSUMPTION]` `` tag at §4.1 FR-9. §9's second entry (FR-12 ToS placeholder) has no matching inline tag at §4.2 FR-12 — the FR text just says "texto placeholder no Anexo A" without the bracket marker. Minor, but breaks the stated roundtrip convention.
- **Glossary consistency** — spot-checked terms ("Jogo," "Concurso," "JogoGerado," "ResultadoLoteria," "Acerto," "Notificação de Acerto") are used with consistent capitalization and singular/plural form across FRs and UJs. No drift found.
- **ID continuity** — FR-1 through FR-14 contiguous; UJ-1/UJ-2 contiguous; SM-1/SM-2/SM-3 plus SM-C1 counter-metric, no gaps or duplicates. Cross-references (e.g. "Realiza UJ-1, passos 1–3," "Ver FR-9") all resolve to existing sections.
- **UJ protagonist naming** — both UJs carry a named protagonist with contextual detail (Dulce's games and impatience; Sônia's first-time signup), satisfying the rubric's requirement directly.
