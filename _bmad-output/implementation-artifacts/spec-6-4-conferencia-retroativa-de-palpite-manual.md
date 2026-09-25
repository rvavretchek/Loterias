---
title: 'Story 6.4 — Conferência retroativa de palpite manual salvo antes da captura'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Um palpite manual salvo antes da captura do resultado (`LotteryResult` ainda não existe) é estruturalmente coberto pela varredura por estado de `fetch_daily_results`/`_notify_covered_bets` (jobs.py) — mas isso nunca foi testado com um bet `manual=True` especificamente, nem o caso "não bate" (sem falso positivo).

**Approach:** Teste de ponta a ponta em `FetchDailyResultsJobTests`: palpite manual sem `LotteryResult` → `fetch_daily_results()` roda → bet conferido corretamente (premiado e não premiado), `HitNotification` criada só quando cabe.

</frozen-after-approval>

## Implementation Notes

- 2 testes novos em `FetchDailyResultsJobTests`: palpite manual (`manual=True`) sem `LotteryResult` ainda, capturado depois via `fetch_daily_results()` -- caso "bate" (hits/prize corretos, `HitNotification(won=True)` criada) e caso "não bate" (result_checked=True, hits=0, sem `HitNotification` -- sem falso positivo).
- `check_bet_result_view` (verificação manual) não ganhou teste equivalente por não ter nenhuma ramificação de código que dependa de `bet.manual` -- já é exercitado genericamente por `CheckBetResultViewTests`/`BetDetailViewTests`; duplicar só trocando esse campo não agregaria.
- Suíte: 430 testes OK (428 + 2 novos).
