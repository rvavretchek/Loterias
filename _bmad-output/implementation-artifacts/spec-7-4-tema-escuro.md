---
title: 'Story 7.4 — Tema escuro'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O tema escuro nunca foi ligado à UI. A infraestrutura de suporte (campo `preferred_theme` no `User`, view `toggle_theme`, context processor `theme_context` expondo `theme`/`is_dark`) sobreviveu à migração pro Lottiq Design System (Epic 5), mas sem uso visual -- os tokens `--dark-*` existem só na fonte do design system (Claude Design), nunca foram importados pro CSS do app, e o alternador foi removido do cabeçalho de propósito, deixado pra esta rodada.

**Approach:** Importar os tokens `--dark-*` da fonte pra `lottiq-tokens.css`, sob um seletor `:root[data-theme="dark"]` que redefine os tokens semânticos (`--surface-*`, `--text-*`, `--border-*`, `--action-*`) pros equivalentes escuros. `base.html` aplica `data-theme="{{ theme }}"` na tag `<html>` (o `theme_context` já calcula isso). Um alternador reaparece no cabeçalho (`.lq-header-right`), reusando a rota/`toggle_theme` já existente.

</frozen-after-approval>

## Implementation Notes

- Tokens escuros trazidos da fonte (projeto "Lottiq Design System" no Claude Design, `tokens/colors.css`) pra `lottiq-tokens.css`, sob `:root[data-theme="dark"]`: redefine os semânticos (`--surface-page/card/sunken`, `--text-heading/body-color/muted/faint`, `--border-default/strong`, `--action-primary/-hover/-ink`, `--status-waiting/win/empty/error-*`) com os valores `--dark-*` (bg, surface, surface-2, border, border-soft, action, action-ink, text, text-muted, teal-soft-bg/fg, celebration-bg/border/fg/muted). Marca (`--lq-navy`/`--lq-teal`/`--lq-amber`) e tipografia/espaçamento/raio permanecem iguais -- só a paleta de cor semântica muda.
- `templates/base/base.html`: `<html lang="pt-BR" data-theme="{{ theme }}">` -- `theme_context` (já registrado em `TEMPLATE_CONTEXT_PROCESSORS`) fornece `theme` ('light'/'dark') tanto pra usuário autenticado (`user.preferred_theme`) quanto anônimo (sessão). Alternador restaurado em `.lq-header-right`, à esquerda do sino/menu, visível pra autenticado e anônimo (`toggle_theme` já suporta os dois), ícone sol/lua conforme o tema atual, link simples pra `{% url 'toggle_theme' %}` (a view já lê `HTTP_REFERER` e redireciona de volta).
- Sem JS novo -- a troca é 100% CSS via atributo `data-theme` renderizado no server, sem flash de tema errado (FOUC) porque o atributo já vem certo no HTML inicial.
- Suíte: cobre (a) alternador presente e aponta pra `toggle_theme` com ícone condizente ao tema atual, (b) `data-theme` no `<html>` reflete `theme_context` pra usuário autenticado com `preferred_theme='dark'` e pra anônimo com sessão, (c) alternância persiste entre requisições (reusa os testes já existentes de `toggle_theme` em `apps/accounts/tests.py`, sem duplicar).
- Achado durante a implementação: boa parte dos componentes migrados no Epic 5 tinham cor fixada direto (`background: #fff`, `color: var(--lq-navy)`) em vez do token semântico (`--surface-card`, `--text-heading`) -- funcionava por coincidência no tema claro (onde os dois valores batem), mas quebraria legibilidade no escuro (texto navy sobre fundo escuro, cartão branco sobre página escura). Corrigido em `lottiq.css` e em todo template migrado no Epic 5 (`home`, `history`, `bet_detail`, `statistics`, `regras_geracao`, `notificacoes`, `preferencias_notificacao`, `profile`, `landing`) trocando pro token semântico -- preserva o visual claro pixel a pixel (mesmo valor resolvido) e corrige o escuro. O cartão-mockup da landing (`.lp-sample`, simulando um "print" do produto) foi deixado com cor fixa de propósito -- é uma peça de design autocontida, não a página em si.
- `body` ganhou `background: var(--surface-page)` (antes dependia do branco padrão do navegador).
- Suíte completa: 440 testes OK (437 + 3 novos). Verificado ao vivo via curl contra o servidor de desenvolvimento local: `data-theme="light"` por padrão, alternador aponta pra `/contas/.../toggle/` com ícone `dark_mode`; forçando `preferred_theme='dark'` no usuário de teste, `data-theme="dark"` aparece no `<html>` renderizado.
