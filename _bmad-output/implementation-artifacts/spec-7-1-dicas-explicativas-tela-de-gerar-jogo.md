---
title: 'Story 7.1 — Dicas explicativas na tela de gerar jogo'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A tela de gerar jogo (home) só tem a frase "Selecione um jogo abaixo para começar", que não foi suficiente pra alguém usando o sistema pela primeira vez (feedback real: a esposa do Boss ficou confusa).

**Approach:** Um guia de 3 passos ("Escolha a loteria", "Confira o concurso", "Clique em Gerar jogo") visível no topo da tela pra quem ainda não gerou nenhum jogo; desaparece pra quem já gerou pelo menos 1 (não reexplica pra quem já sabe usar).

</frozen-after-approval>

## Implementation Notes

- `home.html`: guia de 3 passos ("Role até Loteria...", "Confira o número do Concurso...", "Clique em Gerar jogo") em `.lq-card`, mostrado só quando `total_jogos == 0` (já disponível no contexto da view, sem mudança no `views.py`). Some por completo pra quem já gerou pelo menos 1 jogo -- não fica "discreto", desaparece de vez, conforme permitido pelo UX-DR10.
- Testado ao vivo com um usuário novo de verdade (servidor local, recarga automática): o guia aparece; confirmado que o usuário de teste já usado nas sessões anteriores (com jogos salvos) não vê mais nada — comportamento correto pros dois casos.
- Suíte: 435 testes OK (433 + 2 novos).
