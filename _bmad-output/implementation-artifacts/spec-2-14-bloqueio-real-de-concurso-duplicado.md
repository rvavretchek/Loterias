---
title: 'Bloqueio Real de Concurso Duplicado'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '4651fa7'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `create_bet_view`/`save_manual_bet_view` mostram `messages.warning()` sobre concurso
duplicado (mesmo usuário, mesmo Jogo+Concurso) mas criam o registro duplicado mesmo assim -- falta
`return`/interrupção após o aviso.

**Approach:** Decisão do Boss: opção (a), bloquear totalmente a duplicata. Trocar `messages.warning`
por `messages.error` com mensagem clara ("Você já tem um jogo de {game} para o concurso {contest}.
Não é possível gerar outro pro mesmo Jogo+Concurso.") e `return redirect('home')` logo em seguida, nas
2 views (`create_bet_view` e `save_manual_bet_view`), mesmo padrão já usado por
`_block_if_contest_already_drawn`. Nenhuma mudança em `api_create_bet_view` (não persiste
`GeneratedBet`, já coberto pela Story 2.11/2.13 anteriores) nem em `check_duplicate_bet` (que
verifica duplicata de *números sorteados*, não de Jogo+Concurso -- checagem diferente, já existente,
fora do escopo desta story).

</frozen-after-approval>

## Code Map

- `apps/loterias_core/views.py::_block_if_duplicate_bet` -- novo helper, mesmo padrao de
  `_block_if_contest_already_drawn`: checa `GeneratedBet.objects.filter(user=, game=, contest=)`,
  `messages.error` + redirect se existir.
- `apps/loterias_core/views.py::create_bet_view`/`save_manual_bet_view` -- chamada de
  `GeneratedBet.objects.filter(...).exists()` + `messages.warning` (sem return) substituida por
  `_block_if_duplicate_bet(...)`.
- `_bmad-output/planning-artifacts/epics.md` -- decisao do Boss registrada inline na Story 2.14
  (opcao a, bloquear totalmente), conforme a propria AC pedia.
- `apps/loterias_core/tests.py` -- `test_leading_zero_spelling_counts_as_duplicate_bet` (jah existia,
  Story 2.12) atualizado pra esperar bloqueio; novo `test_blocks_duplicate_contest_for_same_user` em
  `SaveManualBetViewTests`.

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff desde
`4651fa7` (~3.7kB, N=2). Aplicados 3 patches: extraído `_block_if_duplicate_bet` (evita duplicação do
bloco de 3 linhas repetido nas 2 views, mesmo padrão de `_block_if_contest_already_drawn`); mensagem
ajustada de "pro" pra "para o" (registro mais neutro, consistente com as demais mensagens da view);
decisão do Boss registrada inline em `epics.md` (a própria AC da story pedia isso antes da
implementação). Dois achados reais mas fora do escopo desta story deferidos: condição de corrida
check-then-create (mesma categoria já deferida nas Stories 2.2/2.6, corrigir exigiria
`UniqueConstraint`+migration) e `regenerate_bet_view` continuando a criar duplicata sem checagem
(fora do Given/When/Then literal da AC, que só cita `create_bet_view`/`save_manual_bet_view` --
decisão de produto pendente sobre se "refazer" deveria seguir a mesma regra).

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **298 testes, OK**,
  `.venv` pinado (Python 3.11/Django 5.0.6).