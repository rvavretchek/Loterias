---
title: 'Story 5.5 — Regras de Geração no Lottiq Design System'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'ab54139'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A tela `/regras/<jogo>/` (Story 4.3) ainda é toda Bootstrap, inclusive os dois modais de confirmação (Restaurar padrão / salvar sem proteção de sequência), que dependem do JS do Bootstrap.

**Approach:** `regras_geracao.html` reescrito com os componentes do DS (`lq-switch`, `lq-input`/`lq-select`, `lq-status`, `lq-card`) preservando toda a lógica (campo Valor nunca some, região `aria-live`, validação server-side, indicador padrão/personalizado). Os dois modais viram `<dialog>` nativo (`showModal()`/`close()`), sem Bootstrap JS — o navegador já trata foco e Esc.

</frozen-after-approval>

## Implementation Notes

- Mantidos: ids/names dos campos (`enabled_<regra>`, `value_<regra>`), `aria-describedby`, mensagens e validações do backend (nada mudou em `views.py`).
- Gatilhos dos modais trocam de `data-bs-toggle`/`data-bs-target` pra `data-open-dialog`; botões de fechar/cancelar usam `data-close-dialog`. Testes que checavam o atributo antigo foram atualizados pro novo.
- `<dialog>` é suportado nos navegadores atuais (Chrome/Edge/Firefox/Safari); não há fallback pra navegadores muito antigos — aceitável, mesmo padrão de "sem polyfill" já usado no projeto.
- Verificado ao vivo (servidor local): a tela renderiza sem nenhuma classe/atributo Bootstrap (`btn btn-*`, `bi-*`, `data-bs-*`, `modal fade` ausentes), com os dois `<dialog>` presentes pro usuário de teste (regras já personalizadas).
- Suíte: 416 testes OK (2 assinaturas de teste do atributo do modal atualizadas).
