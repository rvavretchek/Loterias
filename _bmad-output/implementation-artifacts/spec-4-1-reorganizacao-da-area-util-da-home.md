---
title: 'Story 4.1 — Reorganização da área útil da home'
type: 'feature'
created: '2026-09-18'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A home autenticada abre com os 3 cards de resumo ocupando o topo da área útil, então gerar um jogo exige rolar a tela (FR-16, UX-DR2).

**Approach:** Só template/CSS em `templates/loterias_core/home.html` (sem model/view/URL novos): área "jogo selecionado" (concurso + Gerar Jogo) no topo da coluna central, seletor de jogos logo abaixo, resumo (mesmos 3 `stat-card`, mesmo conteúdo) numa sidebar fixa à direita em viewports ≥1280px (empilha abaixo disso); prompt leve enquanto nenhum jogo estiver selecionado. Ícone por Jogo, `aria-live` e check de seleção ficam pra Story 4.2; edição de regras pra 4.3.

</frozen-after-approval>

## Implementation Notes

- Arquivos: `templates/loterias_core/home.html` (reestruturação), `apps/loterias_core/tests.py` (`HomeViewTests`, +5 testes; suíte completa 328/328 OK).
- Layout: `.home-layout` (flex; coluna abaixo de 1280px, linha ≥1280px) com `.home-main` (form único: área `#jogo-selecionado` com concurso + Gerar Jogo, depois `#seletor-de-jogos`; depois Guardar Jogo Manual e Últimos Jogos) e `<aside id="resumo-lateral">` (sticky, `top: 5.5rem` por causa da navbar `sticky-top`) com os mesmos 3 `stat-card` e as mesmas variáveis de contexto.
- Decisão: o hero ("Gerador de Loterias" + texto) some para usuário autenticado (só visitante) — sem isso o formulário não cabe em 1280×720 sem rolar. Container `py-4` autenticado.
- Grid de cards de jogo: `col-6 col-md-4 col-xxl-2` (não `col-xl-2`) — com sidebar de 300px a coluna principal só tem ~816px entre 1280 e 1399px, 6 cards por linha estreitariam demais os nomes.
- `selectGame()` só esconde o prompt "Selecione um jogo abaixo"; nome do jogo, ícones, `aria-live` e check de seleção ficam pra Story 4.2.
- Não verificado em navegador real (só testes de renderização/ordem no HTML) — validar visualmente em 1280×720 antes de fechar o Epic.
- Sprint-status: `sprint-status.yaml` ainda não tem chaves do Epic 4, então nenhuma transição de status foi feita.

## Review Triage Log

- Grid `col-xl-2` estreito demais com sidebar: **medium, corrigido** (`col-xxl-2`).
- Sidebar sticky colide com navbar `sticky-top`: **medium, corrigido** (`top: 5.5rem`).
- Sem teste de que concurso/radios/submit ficam no mesmo `<form>`: **medium, corrigido** (novo teste).
- Testes frágeis (`assertIn` em CSS/atributo literal): **low, corrigido** (regex tolerante a espaços).
- Sem teste de hero ausente pra autenticado: **low, corrigido** (novo teste).
- Cards do seletor inacessíveis por teclado / submit sem seleção falha em silêncio: **medium, adiado** (pré-existente; Story 4.2/`.btn-check`), entrada em `deferred-work.md`.
- Área "jogo selecionado" não mostra o jogo escolhido: **false** — fora do escopo da 4.1; é a Story 4.2 (UX-DR4).
- Prompt não volta após bfcache/re-render: **low, rejeitado** — POST falho redireciona (página nova, radios limpos); caso bfcache raro e corrigir adicionaria lógica.
- Sidebar no fim da página em telas estreitas: **false** — comportamento especificado (AC: empilha abaixo, scroll aceitável).
- Dois `{% if user.is_authenticated %}` seguidos / textos sem acento: **low, rejeitado** — legibilidade/consistência com o arquivo, sem impacto.
