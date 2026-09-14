---
title: 'Renomear Arquivos de Template pra Inglês'
type: 'chore'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'd3b9700'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `historico.html`, `detalhes_jogo.html`, `estatisticas.html` continuam em português
enquanto views/rotas já estão em inglês desde o Epic 1 (fora do mapeamento oficial da Story 1.3
porque nome de arquivo não é identificador de código Python).

**Approach:** `git mv` pros 3 arquivos (`history.html`, `bet_detail.html`, `statistics.html`) +
atualizar as 3 chamadas `render()` correspondentes em `apps/loterias_core/views.py`. Decisão do Boss:
sim, renomear. Nenhuma mudança de conteúdo/comportamento das telas.

</frozen-after-approval>

## Implementation Notes

Rename mecânico puro, sem revisão em 3 camadas (risco desprezível, confirmado por grep: zero
referência solta a `historico.html`/`detalhes_jogo.html`/`estatisticas.html` em `apps/`/`templates/`
depois do rename, nenhum outro template usa `{% extends %}`/`{% include %}` pra esses 3 arquivos).

## Verificação

**Comandos executados:**
- `grep -rn "historico\.html\|detalhes_jogo\.html\|estatisticas\.html" apps/ templates/` -- nenhum
  resultado, confirma que nenhuma referência ficou pra trás.
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **305 testes, OK**,
  `.venv` pinado (Python 3.11/Django 5.0.6).
