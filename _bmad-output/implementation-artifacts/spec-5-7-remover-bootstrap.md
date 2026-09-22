---
title: 'Story 5.7 — Remover o Bootstrap e fechar a migração'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '2e6587f'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Todas as telas já usam o Lottiq Design System (5.1–5.6); falta remover o Bootstrap/Bootstrap Icons/crispy-forms e documentar o Lottiq no README/CLAUDE.md.

**Approach:** Varredura de todo `templates/` por classes/atributos Bootstrap (`btn`, `card`, `bi-*`, `data-bs-*`, `form-control` etc., distinguindo de falsos positivos como `lq-card`/`lq-container`); remoção dos 3 últimos usos reais (`d-inline` em 3 forms, `d-flex`/`flex-grow-1` no `base.html`); remoção dos links CDN do Bootstrap/Bootstrap Icons e do script Bootstrap JS; remoção de `crispy_forms`/`crispy_bootstrap5` de `INSTALLED_APPS`, `CRISPY_*` settings e `requirements.txt`. README e CLAUDE.md atualizados pro Lottiq e o Design System.

</frozen-after-approval>

## Implementation Notes

- Varredura automatizada (tokenização das classes de cada `class="..."`, ignorando prefixos `lq-`/`is-`) achou só 4 usos reais restantes: `d-inline` (3 forms em `bet_detail.html`/`history.html`/`notificacoes.html` — removidos, os forms já estão dentro de containers flex, layout inalterado) e `d-flex flex-column min-vh-100` no `<body>` do `base.html` (substituído por `.lq-body`/`.lq-main`, novas classes em `lottiq.css` que reproduzem o layout de rodapé fixo). `class="btn-delete"` foi preservado — não é Bootstrap, é o seletor do `confirm()` compartilhado em `base.html`.
- `base.html`: removidos os `<link>` do Bootstrap CSS/Bootstrap Icons e o `<script>` do Bootstrap JS bundle; removido também o auto-dismiss de `.alert` (Bootstrap) do script inline, já que nenhum template usa mais essa classe — só o `.lq-banner` (próprio) continua.
- `crispy_forms`/`crispy_bootstrap5` removidos de `INSTALLED_APPS` e `CRISPY_ALLOWED_TEMPLATE_PACKS`/`CRISPY_TEMPLATE_PACK` de `loterias/settings/base.py`, e das duas linhas em `requirements.txt`. Nenhum template carrega `crispy_forms_tags` (trocado por `{% lq_form %}` desde a Story 5.3).
- README reescrito: nome Lottiq, descrição atual (sem multitenancy, sem tema claro/escuro na UI), stack (Lottiq Design System no lugar de "Bootstrap 5 + Crispy Forms"), passo `createcachetable` no setup.
- CLAUDE.md: nova seção "Interface (Lottiq Design System)" em Arquitetura, descrevendo os arquivos CSS, `{% lq_form %}`, os modais `<dialog>` nativos e o aviso de que Bootstrap/crispy foram removidos por completo — não reintroduzir.
- Verificado ao vivo (servidor local, usuário de teste): todas as telas tocadas no Epic 5 renderizam 200 sem nenhuma referência a `bootstrap`/`bi-`/`data-bs-`/`crispy` no HTML.
- Suíte: 416 testes OK, `manage.py check` sem problemas.
