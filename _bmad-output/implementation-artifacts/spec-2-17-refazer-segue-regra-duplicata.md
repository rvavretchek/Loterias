---
title: 'Refazer Segue a Regra de Bloqueio de Duplicata'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'd3b9700'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `regenerate_bet_view` cria um segundo `GeneratedBet` pro mesmo usuário+Jogo+Concurso do
jogo original sem nenhuma checagem, inconsistente com o bloqueio real que a Story 2.14 adicionou em
`create_bet_view`/`save_manual_bet_view` ("não é possível gerar outro pro mesmo Jogo+Concurso").

**Approach:** Decisão do Boss: aplicar a mesma regra. Em vez de `GeneratedBet.objects.create(...)`,
`regenerate_bet_view` substitui `original_bet.numbers`/`clovers`/`sequential_pairs` in-place e salva,
redirecionando pro mesmo `pk`. `_block_if_contest_already_drawn` já roda antes (inalterado) -- como
ele bloqueia sempre que existe `LotteryResult` pro par, e `result_checked=True` só é possível quando
`LotteryResult` já existe (via `check_bet_result_view`), o bet chega nesse ponto sempre com
`result_checked=False`/`hits=0`/`prize=0` -- não há necessidade de resetar esses campos
explicitamente. Teste existente atualizado pra confirmar substituição (1 registro, números
diferentes) em vez de duplicação.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/views.py::regenerate_bet_view` -- substitui `GeneratedBet.objects.create(...)`
  por mutação in-place de `original_bet` (numbers/clovers/sequential_pairs) + reset de
  `manual`/`result_checked`/`hits`/`prize`/`prize_description`, seguido de `.save()`. Docstring
  atualizada.
- `apps/loterias_core/tests.py::RegenerateBetViewTests` -- teste renomeado e reescrito
  (`test_regenerating_bet_replaces_original_in_place`), + 2 novos
  (`test_regenerating_replaces_clovers_for_game_with_clovers`,
  `test_regenerating_resets_manual_and_verification_fields`).

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff
(~3.6kB, N=2; bundlado com os 3 renames triviais já verificados da Story 2.19, que não geraram
achado). Achado convergente real e de maior impacto: `manual=True` sobrevivia à regeneração mesmo o
jogo virando algorítmico -- corrigido resetando `manual`. Achado adicional do Edge Case Hunter que
refutou uma premissa da spec original: a purga manual (Story 2.10) pode apagar o `LotteryResult` de
um par sem `HitNotification` (ex. bet verificado sem prêmio), então `result_checked=True`/`hits`/
`prize` old *podem* sobreviver até este código rodar -- corrigido resetando os 4 campos de
verificação, não só `manual`. Teste de trevos reescrito com mock (`generate_bet`) depois de um
`FAILED` real na primeira tentativa (o pool de trevos da Milionária tem só 15 combinações possíveis,
então comparar por desigualdade sem mock é instável). Dois achados fora do escopo trivial desta
revisão deferidos: `regenerate_bet_view` continua GET sem CSRF/confirmação (pré-existente, mas a
consequência de um disparo acidental fica mais grave agora); condição de corrida check-then-write
sem lock (mesma categoria já deferida nas Stories 2.2/2.6/2.14).

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **307 testes, OK**
  (era 305 antes desta story), `.venv` pinado (Python 3.11/Django 5.0.6).