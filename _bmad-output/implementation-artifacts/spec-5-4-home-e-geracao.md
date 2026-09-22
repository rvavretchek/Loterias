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

## Correção pós-entrega (2026-09-22)

- **Bug reportado pelo Boss:** navegando só por teclado, não dava pra selecionar um jogo -- o Tab ia parar no botão "editar regras" no lugar do próximo jogo, e o link de editar parecia não funcionar.
- **Causa raiz:** cada tile tinha seu próprio `<a>` "editar regras" intercalado entre os radios do mesmo grupo (`name="jogo"`). Radios não marcados de um grupo saem inteiramente da sequência de Tab (só ficam alcançáveis pelas setas) -- então, ao focar o 1º radio, o próximo Tab pulava direto pro link de editar daquele tile, nunca pro 2º jogo. Isso valia pra qualquer lugar que o link ficasse (intercalado ou em bloco), porque a exclusão dos outros radios da sequência de Tab independe de onde o link está.
- **Correção:** um único link "Editar regras de geração" depois de todo o grupo de radios (nunca entre eles), com o texto/`href` atualizados por `selectGame()` pro jogo escolhido (via novo `data-regras-url` em cada radio). Antes de qualquer seleção, o link mostra "Editar regras de geração" e aponta pro primeiro Jogo -- funciona sem JS (link real, `href` de servidor), e o JS só refina texto/destino. Tab: `[grupo de radios, setas escolhem] → [link de editar, agora único] → resto da página`.
- Teste novo: `test_only_one_edit_rules_link_and_it_comes_after_the_whole_radio_group`. Suíte: 416 OK.
