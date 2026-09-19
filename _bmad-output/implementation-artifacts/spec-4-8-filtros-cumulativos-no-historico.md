---
title: 'Story 4.8 — Filtros cumulativos e exibição legível no histórico'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'a912b3a'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O histórico só filtra por Jogo e mostra números em tabela estreita; FR-24/AD-14 pedem filtros cumulativos (Jogo, período, só premiados) e exibição legível pra Lotomania/Lotofácil (muitos números) e Dupla-Sena (2 sorteios).

**Approach:** `history_view` filtra direto em `GeneratedBet` por querystring (AND): `game`, `created_at` de/até inclusivos no `TIME_ZONE`, `prize__gt=0`; valores inválidos são ignorados. Template em cards (mockup `historico.html`): barra de filtros sempre visível, badges removíveis (links com `aria-label`), mensagem de vazio nomeando os filtros + "Limpar filtros", bolinhas com `flex-wrap`/`role=list`, Dupla-Sena em dois grupos rotulados, foco no heading após filtrar, paginação preservando filtros.

</frozen-after-approval>

## Implementation Notes

- `views.py::history_view` (+ `_parse_date`), `history.html` reescrito, `HistoryFiltersTests`. Suíte: 339 testes OK. Não verificado em navegador.
- Decisão: `GeneratedBet` guarda um único conjunto de números; na Dupla-Sena o mesmo jogo vale pros 2 sorteios, então os dois grupos "1º/2º sorteio" mostram os mesmos números do usuário (sem destaque de acertos por sorteio).
- Badges são `<a>` (link real, focável) e não `<button>` como no mockup.
- Revisão: autorrevisão. Achado: teste de paginação assumia `&amp;` em todo o href — ajustado.
