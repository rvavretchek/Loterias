---
title: 'Story 6.6 — Fluxo ponta a ponta de uma aposta, manual e automática'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Nenhum teste cobre o ciclo completo (registro → captura → prêmio → notificação) numa única passagem; em particular, `save_manual_bet_view`/`check_bet_result_view` calculam e aplicam o prêmio na hora, mas NUNCA criam `HitNotification` diretamente — isso só acontece na próxima varredura de `_notify_covered_bets` (AD-4) — e essa costura entre "prêmio já visível" e "notificação só depois" nunca foi provada com teste.

**Approach:** 2 testes de integração — automático (`create_bet_view` → `fetch_daily_results` → `HitNotification`) e manual (`save_manual_bet_view` com resultado já disponível → prêmio visível na hora → `fetch_daily_results` roda depois → `HitNotification` só aparece nesse momento, não antes).

</frozen-after-approval>

## Implementation Notes

- `EndToEndBetLifecycleTests`: 2 testes de integração. Automático -- `create_bet_view` (HTTP) sem resultado ainda → `fetch_daily_results()` (cron) → `LotteryResult`, `bet.hits/prize`, `HitNotification` e o `bet_detail_view` mostrando `premio_info` correto, tudo numa passagem. Manual -- `save_manual_bet_view` com resultado JÁ disponível na hora (`apply_prize_to_bet` roda direto na view) → prêmio já visível em `bet_detail_view` → mas `HitNotification` ainda NÃO existe → só aparece depois que `fetch_daily_results()` roda (a varredura por estado do AD-4, não o caminho de escrita do resultado).
- Confirmado (não era garantido antes de existir teste): a costura entre "prêmio aplicado na hora pela view" e "notificação só na próxima varredura" funciona -- `_notify_covered_bets` não pula um bet só porque `result_checked` já está `True`, ele filtra por `notification__isnull=True`.
- Suíte: 433 testes OK (431 + 2 novos).
