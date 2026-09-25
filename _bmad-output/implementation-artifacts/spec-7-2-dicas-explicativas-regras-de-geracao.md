---
title: 'Story 7.2 — Dicas explicativas na tela de Regras de Geração'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A tela de Regras de Geração só mostra o rótulo curto de cada regra (ex. "Limita quantidade de números em sequência"); só 2 das 7 regras (linha/coluna do volante) têm texto de ajuda hoje.

**Approach:** `RULE_DEFINITIONS` ganha uma `explanation` (linguagem comum) por regra; `_build_rule_rows` combina explicação + detalhe do volante (quando aplicável) no mesmo `help` já renderizado via `aria-describedby`.

</frozen-after-approval>

## Implementation Notes

- `RULE_DEFINITIONS` (models.py) ganhou `explanation` pra cada uma das 7 regras, em linguagem comum. `_build_rule_rows` (views.py) combina `explanation` + o detalhe do volante (`_GRID_HELP`, só linha/coluna) no mesmo `help` que já era renderizado via `aria-describedby` -- nenhuma mudança de template necessária, o `regras_geracao.html` já suportava `row.help` genérico desde a Story 4.3.
- Achado durante o teste: texto com aspas retas (`"Homogênea"`) quebrava `assertContains` por causa do autoescape do Django (`&quot;`) -- reescrito sem aspas, é conteúdo real exibido ao usuário, não só um detalhe de teste.
- Suíte: 436 testes OK (435 + 1 novo, cobrindo as 7 explicações via Lotofácil).
