---
title: 'Story 5.4 — Home e geração de jogo no Lottiq Design System'
type: 'feature'
created: '2026-09-21'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'b09c2df'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A home autenticada (Gerar jogo, seletor de Jogo, palpite manual, últimos jogos, resumo) ainda é Bootstrap.

**Approach:** `home.html` reescrito com os componentes do DS (tela 05 do design), preservando ids, ordem, `aria-live`, sugestão de concurso e a estrutura das Stories 4.1/4.2: cabeçalho "Gerar jogo", cartão "Jogo selecionado" + campo Concurso (mono) + botão primário, seletor em tiles com radio escondido (`lq-tile-input`), ícones Material Symbols, palpite manual, últimos jogos com `lq-ball`, resumo lateral (≥1280px) ou abaixo.

</frozen-after-approval>

## Implementation Notes

- Fluxo mantido: "Gerar jogo" continua gerando e guardando direto (o design mostra gerar → "Guardar como jogo" em duas etapas; não mudei o comportamento nesta story).
- Ícones por Jogo em Material Symbols: Mega-Sena `emoji_events`, +Milionária `local_florist`, Lotomania `pin`, Lotofácil `bolt`, Quina `star`, Dupla-Sena `filter_2` (mesmos da landing).
- Resumo lateral virou 3 métricas (Jogos guardados, Tipos de jogo, Jogos recentes). O cartão âmbar "Prêmios no ano" do design não entrou: o app não calcula esse total.
- "Verificar/gerado" → vocabulário do DS: "Guardar palpite manual", "Sugestão: concurso N".
- Testes da home atualizados pros novos seletores (`lq-tile-input`, ícones Material, rótulos do resumo). Suíte: 415 OK. Não verificado em navegador (JS do seletor segue sem teste automatizado — item já em deferred-work).
