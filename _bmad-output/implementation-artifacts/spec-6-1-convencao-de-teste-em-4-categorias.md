---
title: 'Story 6.1 — Convenção de teste em 4 categorias'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Não existe convenção documentada de cobertura de teste; cada story redecide o que testar, sem padrão.

**Approach:** Nova seção no `CLAUDE.md` documentando a convenção de 4 categorias (caminho feliz, entrada inválida, entrada vazia/ausente, fronteira/concorrência) pra cobertura NOVA (não retroativa), com um exemplo real do próprio código.

</frozen-after-approval>

## Implementation Notes

- Seção "Convenção de testes" adicionada ao CLAUDE.md, entre "Comandos" e "Arquitetura" (é prática transversal, não amarrada a uma subseção de arquitetura). Exemplos usam `normalize_contest` e `bet_satisfies_rules`/`save_official_result`, que são os alvos concretos das Stories 6.2/6.5/6.4 seguintes.
- Decisão registrada explicitamente: ao cobrir uma função que ainda não tem as 4 categorias, completar na mesma story -- evita a "story de completar teste" separada que ninguém prioriza depois.
- Suíte: 424 testes OK (sem mudança de código, só doc).
