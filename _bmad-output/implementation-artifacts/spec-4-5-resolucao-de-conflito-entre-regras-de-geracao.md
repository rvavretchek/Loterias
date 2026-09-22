---
title: 'Story 4.5 — Resolução de conflito entre Regras de Geração (relaxamento)'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '7d7750f'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Com regras personalizadas impossíveis de satisfazer juntas, hoje a geração falha com aviso; FR-22/AD-12 pedem relaxar a regra que causa o conflito, gerar o jogo e avisar qual foi relaxada.

**Approach:** Em `apps/loterias_core/utils.py`, nova `generate_bet_with_relaxation(game, user)` → `(numbers, clovers, relaxed_rule_name | None)`; `generate_bet` vira wrapper de 2 valores (compatível). Esgotadas as 10000 tentativas com todas as `active_rules`, relaxa **uma** regra em memória — a de maior `updated_at` entre as que o último candidato violou — e tenta mais 10000; se falhar, `(None, None, None)` como hoje. As views (`create`, `regenerate`, API) usam a nova função e, ao relaxar, geram o jogo normalmente e avisam nomeando a regra (rótulo de `RULE_DEFINITIONS`) e o Jogo; a API ganha o campo `regra_relaxada` sem quebrar o contrato.

</frozen-after-approval>

## Implementation Notes

- `utils.py`: `_draw_with_rules` (laço de 10000 tentativas, devolve candidato ou violações do último), `generate_bet_with_relaxation` (relaxa no máximo 1 regra, em memória) e `generate_bet` como wrapper de 2 valores. `views.py`: `create`/`regenerate`/API usam a nova função, aviso `_relaxed_rule_message` nomeando regra e Jogo; API ganha `regra_relaxada`. Suíte: 324 testes OK.
- Testes antigos de "regras impossíveis" agora usam duas regras inatingíveis (`limit_column_count=0` + `limit_row_count=0`), pois uma só passa a ser relaxada.

## Review Triage Log

- Empate em `updated_at` tornava a escolha não determinística: **medium, corrigido** (desempate por `pk`).
- Heurística usa só o último candidato (pode relaxar regra viável): **low, rejeitado** — é o comportamento definido no AD-12/FR-22.
- Custo 2×10000 por chamada dentro do laço de duplicatas: **low, rejeitado** — duplicata é improvável e trabalho é em memória.
- Mensagem sem acentos e `KeyError` hipotético na API: **low, rejeitado** — consistente com as demais mensagens; nomes vêm de `RULE_NAMES_BY_GAME`.
- Testes de relaxamento de `distribution_type` e `regra_relaxada=None` na API: **low, adiado** — cobertos indiretamente.
