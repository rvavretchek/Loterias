---
title: 'Suporte ao 2º Sorteio da Dupla-Sena'
type: 'feature'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '7273fa0'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A Dupla-Sena tem 2 sorteios por concurso (confirmado ao vivo contra a API oficial:
`listaDezenas` + `listaDezenasSegundoSorteio`), mas `fetch_cef_result`/`LotteryResult` só capturam e
conferem o 1º -- um acerto real só no 2º sorteio nunca vira notificação.

**Approach:** Decisão do Boss: vale o esforço. 2 campos novos em `LotteryResult`
(`numbers_second_draw`, `prizes_second_draw`, ambos `JSONField` com default vazio, migration nova).
`fetch_cef_result` captura `listaDezenasSegundoSorteio` e extrai a 2ª metade de
`listaRateioPremio` (faixas do 2º sorteio -- a 1ª metade já era extraída sozinha por
`_extract_prize_tiers` via dedup, comportamento inalterado) só pra Dupla-Sena; os 2 campos ficam
sempre presentes no dict devolvido (vazios pra qualquer outro jogo), pra chamador nunca precisar
checar o jogo antes de ler. `calculate_bet_prize` extrai seu núcleo de cálculo por-sorteio
(`_calculate_prize_for_draw`) e, só pra Dupla-Sena com `numbers_second_draw` presente, chama esse
núcleo 2x (1 por sorteio) e fica com o de maior prêmio -- nunca soma os 2, nunca ignora o 2º. Os 3
pontos que persistem `LotteryResult` (`jobs.py`, `save_manual_bet_view`, `check_bet_result_view`) e
o que lê pra `bet_detail_view` são atualizados pra propagar os 2 campos novos.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py::LotteryResult` -- `numbers_second_draw`/`prizes_second_draw`
  (`JSONField`, defaults vazios) + migration `0006_lotteryresult_numbers_second_draw_and_more.py`.
- `apps/loterias_core/utils.py::fetch_cef_result` -- captura `listaDezenasSegundoSorteio` e a 2a
  metade de `listaRateioPremio` pra Dupla-Sena (guarda contra lista de tamanho impar).
  `_extract_prize_tiers` docstring corrigida (nao "resolve" mais, resolveu).
- `apps/loterias_core/utils.py::calculate_bet_prize`/`_calculate_prize_for_draw` -- nucleo
  extraido, chamado 2x pra Dupla-Sena com `numbers_second_draw`, fica com o de maior valor
  (`>` estrito -- empate fica com o 1o).
- `apps/loterias_core/jobs.py::fetch_daily_results` -- `existing_results` exclui Dupla-Sena sem
  `numbers_second_draw` ainda, pra continuar revisitando ate os 2 sorteios estarem completos.
  `_notify_covered_bets` propaga os 2 campos novos no dict `official_result`.
  `update_monthly_prize_values` NAO promove `prizes_second_draw` (achado deferido).
- `apps/loterias_core/views.py` -- `save_manual_bet_view`, `check_bet_result_view`,
  `bet_detail_view` propagam os 2 campos novos (persistencia e leitura).
- `templates/loterias_core/bet_detail.html` -- mostra os 2 sorteios separadamente quando
  `numbers_second_draw` existe (achado da revisão -- sem isso, um acerto do 2º sorteio não seria
  visualmente reconciliável com os números mostrados).
- `_bmad-output/implementation-artifacts/deferred-work.md` -- entrada original da Story 2.1 (Dupla-
  Sena 2º sorteio) removida, resolvida por esta story.
- `apps/loterias_core/tests.py` -- 13 casos novos: `FetchCefResultTests` (3), `CalculateBetPrizeTests`
  (5), `FetchDailyResultsJobTests` (2), `HitNotificationGenerationTests` (1, ponta a ponta).

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff
(~16.3kB, N=5). Achados reais corrigidos: guarda contra split assimétrico de `listaRateioPremio`
(lista de tamanho ímpar); `fetch_daily_results` revisitando pra sempre uma captura de Dupla-Sena sem
2º sorteio ainda (achado de maior impacto -- sem isso, o par nunca mais seria revisitado); template
não mostrava os números do 2º sorteio (confiança do usuário no resultado exibido); teste de ponta a
ponta através de `fetch_daily_results`/`_notify_covered_bets` (achado de maior valor do Verification
Gap Reviewer -- os testes originais só cobriam `calculate_bet_prize`/`fetch_cef_result` isolados,
nunca a fiação real que alimenta esses 2 pontos); teste de desempate (`>` estrito, nunca `>=`).
Um achado fora do escopo trivial desta revisão deferido: `update_monthly_prize_values` não promove
`prizes_second_draw` pro `PrizeTier` (impacto baixo -- só afeta o caminho de fallback).

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` -- nenhuma mudança de
  model pendente.
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **325 testes, OK**
  (era 307 antes desta story), `.venv` pinado (Python 3.11/Django 5.0.6).