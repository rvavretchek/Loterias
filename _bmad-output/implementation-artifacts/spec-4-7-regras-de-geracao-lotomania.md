---
title: 'Story 4.7 — Regras de Geração da Lotomania'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '09a17b1'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A Lotomania precisa das 3 regras reduzidas (sequência, espaço mínimo entre sequências, mínimo de sequências), sem linha/coluna/distribuição (FR-21, AD-11).

**Approach:** Nenhum código novo de regra: `RULE_NAMES_BY_GAME['Lotomania']` (Story 4.3) já lista só essas 3 e `bet_satisfies_rules` (4.4/4.6) as avalia. A story fecha a lacuna com teste de geração ponta a ponta na Lotomania.

</frozen-after-approval>

## Implementation Notes

- Verificado: tela `/regras/lotomania/` mostra só as 3 regras (teste existente) e `RULE_NAMES_BY_GAME` não tem linha/coluna/distribuição. Adicionado `test_lotomania_generation_respects_its_three_rules`. Suíte: 330 OK.
- Viabilidade medida: sorteio uniforme 50/100 satisfaz rápido (ms) combinações como sequência ≤3 + gap 0, ≤6 + gap 3; combinações muito apertadas (ex. sequência ≤3 + mín. 4 sequências + gap 2) caem no relaxamento da 4.5.
