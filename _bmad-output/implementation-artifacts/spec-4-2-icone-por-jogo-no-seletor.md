---
title: 'Story 4.2 — Ícone por Jogo no seletor'
type: 'feature'
created: '2026-09-18'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Todos os Jogos usam o mesmo ícone genérico (`bi-dice-5`) no seletor; a área "jogo selecionado" não reflete a escolha; o estado selecionado depende só de cor; e os cards são `div onclick` com radio `d-none required` (sem teclado, submit sem seleção falha em silêncio — item adiado da Story 4.1). (FR-17, UX-DR1, UX-DR4, UX-DR7)

**Approach:** Só template/CSS/JS em `templates/loterias_core/home.html`. Seletor no padrão `.btn-check` (radio visualmente escondido + `<label>` como card, focável por teclado) com ícone Bootstrap Icons distinto por Jogo (`bi-trophy`, `bi-flower1`, `bi-123`, `bi-lightning`, `bi-star`, `bi-stack`, todos `aria-hidden`) e indicador de check (`bi-check-circle-fill`) no card selecionado além da cor. Ao escolher um jogo, a área "jogo selecionado" mostra ícone/nome/resumo do Jogo numa região `aria-live="polite" aria-atomic="true"`, além de esconder o prompt e sugerir o concurso (comportamento existente). Sem ícone de editar (Story 4.3); sem model/view/URL novos.

</frozen-after-approval>

## Implementation Notes

_(preenchido durante a implementação)_

- Arquivos: `templates/loterias_core/home.html` (seletor `.btn-check` + `<label>`, ícones, check, área "jogo selecionado" como região `aria-live`, JS `selectGame(radio)`), `apps/loterias_core/tests.py` (+3 testes; suíte 333/333 OK).
- **Correção fora do previsto:** `bi-100` (Lotomania, sugerido no UX e aprovado) **não existe** no Bootstrap Icons 1.11.1 (verificado no CSS do CDN; só existe `bi-123`). Trocado por `bi-123` em código, `EXPERIENCE.md`, `epics.md`, `epic-4-context.md` e no memlog do UX. Como o bloco `<frozen-after-approval>` desta spec citava `bi-100`, ele também foi ajustado — mudança factual, não de escopo; o Boss deve confirmar.
- A área "jogo selecionado" é uma única região `aria-live` sem alternar `display` (troca só texto/classe do ícone e do nome; estado inicial mostra o prompt com ícone de seta) — anúncio confiável em leitores de tela.
- Item adiado da 4.1 resolvido: seletor agora é radio `.btn-check` + label (foco por teclado, `required` mostra a mensagem nativa do navegador ao enviar sem jogo).

## Review Triage Log

- `<label>` com `div`/`h5` (HTML inválido): **medium, corrigido** (spans + `.h5`).
- Região aria-live com filho alternando `hidden` (anúncio não confiável): **medium, corrigido** (sem alternar display).
- `bi-100` inexistente (achado ao verificar o mapa de ícones): **high, corrigido** (`bi-123`).
- JS sem teste automatizado: **medium, adiado** (`deferred-work.md`; sem infra de frontend no projeto).
- Sem null-check em `iconEl`: **low, corrigido** junto da reescrita do JS.
- Anúncio no carregamento via restauração bfcache: **low, rejeitado** (sem custo-benefício).
- Testes com regex frágeis a reordenação de atributos: **low, rejeitado**.
- Mapa de ícones hard-coded no template: **false** — o teste compara com `GAMES_CONFIG`, então um jogo novo quebra o teste; mover pra `models.py` fugiria do escopo "sem model".
- `rgba(13,110,253,.1)`/`calc(1rem - 1px)` hard-coded: **false** — mesmo padrão de `base.html` (`.game-selector.active`); o cálculo mantém o tamanho do card (borda 3px vs 2px).
- Redação/acentos de `data-resumo`: **low, rejeitado** (consistente com o arquivo).
