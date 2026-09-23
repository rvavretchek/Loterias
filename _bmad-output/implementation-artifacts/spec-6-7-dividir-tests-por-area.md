---
title: 'Story 6.7 — Dividir tests.py por área funcional'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `apps/loterias_core/tests.py` chegou a 4346 linhas, 56 classes em ordem cronológica de story — difícil de navegar pra adicionar cobertura nova por área.

**Approach:** Vira pacote `apps/loterias_core/tests/`, 6 módulos por área funcional (geração/regras, resultados/prêmio, notificações, páginas, admin, integração ponta a ponta) — o `DiscoverRunner` padrão do Django já descobre qualquer `test*.py` dentro de um pacote, sem precisar reexportar nada.

</frozen-after-approval>

## Implementation Notes

- Divisão mecânica (script que extrai cada classe por linha e reagrupa) pra garantir que nenhum teste se perdeu ou duplicou — checagem automática confirmou as 57 unidades (56 classes + o helper `_rule`) atribuídas exatamente uma vez cada.
- Cada módulo novo carrega o MESMO bloco de imports que o `tests.py` original tinha inteiro (import não usado é inofensivo em Python) — trade-off deliberado pra não arriscar faltar um import em algum módulo.
- `_rule()` (helper usado só por `BetSatisfiesRulesTests`) foi junto pra `test_generation.py`, onde é usado.
- `manage.py test apps.loterias_core` sozinho reporta 369 (não 433) — isso é o esperado, é só o sub-total desse app; `manage.py test apps` (loterias_core + accounts, 64 testes) fecha em 433, igual a antes da divisão.
- `CLAUDE.md` atualizado: comando de exemplo corrigido pro caminho novo (`apps.loterias_core.tests.test_generation.SomeTestCase...`) e nova seção descrevendo os 6 módulos e onde encaixar teste novo.
- Suíte: 433 testes OK, `manage.py check` sem problemas, nenhum teste novo nesta story (é reorganização pura).
