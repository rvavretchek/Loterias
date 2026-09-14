---
title: 'Validação de Jogo em api_create_bet_view'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '2df1462'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Diferente de `create_bet_view`/`save_manual_bet_view`, `api_create_bet_view` não valida
`selected_game not in GAMES_CONFIG` antes de chamar `generate_bet()`. Com um `jogo` inválido no
payload JSON, `generate_bet()` retorna `(None, None)` e a chamada seguinte
(`count_sequential_pairs(nums)`) faz `len(None)`, levantando `TypeError` não tratado (500) em vez de
um erro 400 claro.

**Approach:** Replicar em `api_create_bet_view` a mesma checagem já usada em `create_bet_view`/
`save_manual_bet_view` (`if selected_game not in GAMES_CONFIG`), inserida logo após a checagem de
dados incompletos e antes da normalização de `contest` (mesma ordem de validação das outras 2 views),
devolvendo `JsonResponse({'error': 'Jogo invalido'}, status=400)` -- mesmo texto de mensagem usado
nas outras views (`'Jogo invalido.'`), sem tocar `generate_bet()`/`count_sequential_pairs` nem o
comportamento com um `jogo` válido.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/views.py::api_create_bet_view` -- checagem `not isinstance(selected_game, str)
  or selected_game not in GAMES_CONFIG` inserida logo apos a checagem de dados incompletos, antes de
  `normalize_contest`. Mesma mensagem `'Jogo invalido'` (sem ponto final -- convencao ja usada nas
  outras mensagens de erro JSON desta view, `'Dados incompletos'`/`'Numero de concurso invalido: ...'`,
  diferente das mensagens `messages.error` em HTML que usam ponto final).
- `apps/loterias_core/tests.py::CreateBetViewTests` -- `test_api_create_bet_rejects_invalid_game`
  (jogo string invalida) e `test_api_create_bet_rejects_unhashable_game_type` (jogo tipo lista --
  cobre o caso que quebraria `in GAMES_CONFIG` com `TypeError` sem a checagem de `isinstance`).

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff desde
`2df1462` (~1.5kB, N=2). Um achado convergente real (Blind Hunter + Edge Case Hunter): `jogo` como
lista/dict (tipo não-hasheável) ainda quebraria `in GAMES_CONFIG` com `TypeError` não tratado -- o
mesmo tipo de 500 que esta story existe pra fechar. Corrigido com `isinstance(selected_game, str)`
antes do `in`. Um achado de documentação (spec dizia "mesmo texto... `'Jogo invalido.'`" com ponto,
implementação usa sem ponto) -- resolvido a favor do código: a convenção já estabelecida nesta mesma
função pras mensagens JSON não usa ponto final (`'Dados incompletos'`), diferente das mensagens HTML
via `messages.error`; a menção "mesmo texto" no Intent era sobre a *palavra*, não a pontuação exata.
Um achado pré-existente (parse de JSON/`concurso` não-string ainda pode gerar 500) registrado em
`deferred-work.md`, fora do escopo desta story.

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **297 testes, OK**
  (era 296 antes do patch de revisão), `.venv` pinado (Python 3.11/Django 5.0.6).
