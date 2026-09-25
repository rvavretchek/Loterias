---
title: 'Story 6.2 — Cobertura de normalize_contest'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `normalize_contest` já tem boa cobertura unitária, mas faltam as 4 categorias em pontos de entrada reais: `save_manual_bet_view` não tem teste de concurso vazio, o `clean_contest` do admin (Story 2.16) nunca foi exercitado por teste nenhum, e não há teste de entrada anormalmente grande (o `int()` interno tem limite do próprio Python pra dígitos, mas isso nunca foi travado por teste).

**Approach:** Completar as 4 categorias nos pontos de entrada que ainda faltam: vazio em `save_manual_bet_view`, inválido/válido no formulário do admin (`_NormalizedContestFormMixin`), e fronteira com string de dígitos muito grande.

</frozen-after-approval>

## Implementation Notes

- 4 testes novos em `ContestCoverageStory62Tests`: concurso vazio em `save_manual_bet_view` (categoria vazia); string de 5000 dígitos rejeitada em `create_bet_view` (categoria fronteira -- o próprio `int()` do Python 3.11+ recusa strings de dígito gigante, `normalize_contest` só repassa o `ValueError`, sem checagem própria de tamanho); formulário do admin (`LotteryResultAdminForm`/`_NormalizedContestFormMixin`, Story 2.16) rejeitando concurso inválido com mensagem inline (nunca tinha teste) e normalizando `03500`→`3500` no caminho válido.
- Suíte: 428 testes OK (424 + 4 novos).
