---
title: 'Story 5.6 — Histórico, detalhe, avisos, estatísticas e preferências no Lottiq Design System'
type: 'feature'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '6ea6fbe'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `history.html`, `bet_detail.html`, `notificacoes.html`, `statistics.html` e `preferencias_notificacao.html` ainda são Bootstrap.

**Approach:** As 5 telas reescritas com os componentes do DS (`lq-card`, `lq-ball`, `lq-status`, `lq-balls`, novos `lq-chip`/`lq-pagination`/`lq-progress` adicionados a `lottiq.css`), mantendo filtros, paginação, semântica de acessibilidade (grupos de sorteio da Dupla-Sena, `role=list`) e todo o comportamento das Stories 2.x/4.8. `preferencias_notificacao.html` usa o `{% lq_form %}` da Story 5.3 (sem crispy). Vocabulário do DS: "Verificar" → "Conferir resultado da Caixa" no detalhe do jogo.

</frozen-after-approval>

## Implementation Notes

- Componentes novos em `lottiq.css`: `.lq-chip` (badge de filtro removível), `.lq-pagination`, `.lq-progress`/`.lq-progress-bar`, `.lq-input:disabled`/`.lq-select:disabled`.
- `class="btn-delete"` preservada nos botões de excluir (histórico e detalhe) — é o seletor do `confirm()` em `base.html`, não depende de Bootstrap.
- Números batidos nas notificações usam `lq-ball-hit` (âmbar, só em contexto de acerto — a regra do DS). Trevos usam `lq-ball-clover`.
- Renomeação de vocabulário (só nesta story, dentro do texto já tocado): "Verificar Resultado da CEF" → "Conferir resultado da Caixa" no detalhe do jogo; a URL (`/jogo/<pk>/verificar/`) e o nome da view continuam iguais (identificadores, não texto de UI).
- Testes atualizados pra refletir classes novas (não mudança de comportamento): `lq-ball-hit`/`lq-ball-clover` no lugar de `numero-bola`/`trevo-bola`; `lq-status-win` no lugar de `bi-trophy-fill`; texto do botão no lugar de `bi-check2`; `Concurso 100`/`Concurso 200` no lugar de `>100<`/`>200<` (o concurso agora vem com rótulo); `Sem prêmio`/acento corrigido; `lq-balls` no lugar do utilitário `flex-wrap` do Bootstrap.
- Verificado ao vivo (servidor local, usuário de teste): histórico, detalhe de jogo, avisos, estatísticas e preferências renderizam 200, sem `btn btn-*`/`bi-*` remanescentes.
- Suíte: 416 testes OK.
