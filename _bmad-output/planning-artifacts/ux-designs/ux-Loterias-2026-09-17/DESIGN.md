---
name: Loterias — UI existente (Bootstrap 5)
description: "Sistema visual herdado do app autenticado (Home, Regras de Geração, Histórico) — Bootstrap 5 + Bootstrap Icons já em uso; não é o design system novo que o Boss vai construir separadamente pra landing page."
status: final
updated: 2026-09-17
sources:
  - "_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md"
colors:
  bg-primary: '#f8f9fa'
  bg-primary-dark: '#0f172a'
  bg-card: '#ffffff'
  bg-card-dark: '#1e293b'
  text-primary: '#212529'
  text-primary-dark: '#f1f5f9'
  text-secondary: '#6c757d'
  text-secondary-dark: '#94a3b8'
  border: '#dee2e6'
  border-dark: '#334155'
  accent-primary: '#0d6efd'
  accent-primary-dark: '#3b82f6'
  success: '#198754'
  success-dark: '#22c55e'
  warning: '#ffc107'
  warning-dark: '#f59e0b'
  danger: '#dc3545'
  danger-dark: '#ef4444'
  disabled-bg: '#e9ecef'
  disabled-bg-dark: '#334155'
  disabled-text: '#6c757d'
  disabled-text-dark: '#94a3b8'
typography:
  body:
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: '1rem'
    fontWeight: 400
  stat-value:
    fontSize: '1.75rem'
    fontWeight: 700
  stat-label:
    fontSize: '0.875rem'
    fontWeight: 400
rounded:
  DEFAULT: '12px'
  full: '50%'
spacing:
  card-padding: '1.5rem'
  gutter: '1rem'
components:
  game-selector:
    border: '{colors.border}'
    borderActive: '{colors.accent-primary}'
    borderWidthActive: '3px'
    backgroundActive: 'rgba(13, 110, 253, 0.1)'
    selectedIndicator: 'bi-check-circle-fill, canto superior direito do card — indicador não-cromático além da cor de borda/fundo, ver EXPERIENCE.md Accessibility Floor'
    icon: 'ver mapeamento por Jogo em EXPERIENCE.md § Component Patterns'
    hoverTransform: 'translateY(-2px)'
  number-badge:
    shape: '{rounded.full}'
    size: '42px'
    background: 'linear-gradient({colors.accent-primary}, #0056b3)'
    backgroundClover: 'linear-gradient(#f59e0b, #d97706)'
    fontWeight: 700
  rule-toggle-row:
    valueFieldWhenOff:
      background: '{colors.disabled-bg}'
      backgroundDark: '{colors.disabled-bg-dark}'
      textColor: '{colors.disabled-text}'
      opacity: 1
      note: "Nunca display:none — ver Components/Do's and Don'ts abaixo."
  sidebar-summary:
    background: '{colors.bg-card}'
    border: '{colors.border}'
    padding: '{spacing.card-padding}'
  filter-bar:
    background: '{colors.bg-card}'
    border: '{colors.border}'
    position: 'sempre visível, topo da lista (não colapsável)'
---

## Brand & Style

Não é uma identidade de marca nova — é a extensão visual do que já existe no app autenticado, com o mínimo de invenção necessária pras 3 telas do adendo 2026-09-17 (home, edição de Regras de Geração, histórico). O tom é utilitário e denso em dados (o usuário está gerando/consultando jogos, não sendo vendido algo), consistente com a Feature 4.1 já em produção. **A landing page pra visitante não autenticado está deliberadamente fora deste documento** — o Boss vai construir um design system próprio pra ela; nada aqui deve ser tratado como referência quando esse trabalho começar.

## Colors

O app já roda em dois temas (`[data-theme="light"|"dark"]`, alternância via `theme-toggle` no cabeçalho — `apps/accounts` guarda a preferência em `User.preferred_theme`). Todos os tokens acima têm par claro/escuro do que já existe em `templates/base/base.html` (`success`/`warning`/`danger` incluídos — usados no indicador "Personalizado por você" (`success`), no aviso de regra relaxada FR-22 e na confirmação de FR-23 (`warning`), e na validação inline de Valor fora da faixa (`danger`), ver EXPERIENCE.md State Patterns). `disabled-text`/`disabled-text-dark` reaproveitam o mesmo valor de `text-secondary`/`text-secondary-dark` (não um terceiro neutro) — contraste calculado contra `disabled-bg`/`disabled-bg-dark` fica na mesma faixa nos dois temas (~4,5:1+), corrigindo um problema real do rascunho anterior (`#adb5bd` sobre `#e9ecef` dava só 1,75:1, ilegível na prática apesar de "visível, não escondido" ser a intenção declarada).

**Contraste de `accent-primary`:** `#0d6efd` sobre branco é 4,50:1 (limiar exato de AA texto, sem margem) e `#3b82f6` sobre `bg-card-dark` é 3,98:1 (abaixo de 4,5:1). Por isso `accent-primary`/`accent-primary-dark` só são usados nesta rodada como cor de **borda/fundo** (onde 3:1 já basta) — nunca como cor de texto ou ícone informativo sozinho (ver Do's and Don'ts).

## Typography

Herdado sem alteração — `Inter` via Google Fonts, já carregado. `stat-value`/`stat-label` são os únicos papéis nomeados aqui porque migram de posição (resumo vira sidebar, FR-16) sem mudar de tamanho.

## Layout & Spacing

**Home (FR-16):** duas colunas na área útil (`≥1280px`, ver EXPERIENCE.md Foundation): sidebar de resumo à direita (largura fixa, ~3 colunas Bootstrap de 12) + coluna principal à esquerda (jogo selecionado no topo, seletor de jogos logo abaixo). Abaixo de `1280px`, a sidebar empilha abaixo do conteúdo principal (`col-lg-*`/`col-12` padrão Bootstrap) — scroll é aceitável nessa faixa, não é meta do FR-16.

**Tela de Regras de Geração:** página cheia (não modal), mesmo padrão de `.container.py-5` das demais telas do app.

**Histórico:** barra de filtros ocupa a largura total, fixa no topo da lista de resultados (não colapsável, ver EXPERIENCE.md FR-24).

## Shapes

`{rounded.DEFAULT}` (12px) em cards e no card da sidebar de resumo — mesmo raio já usado em `.card`. `{rounded.full}` nas bolinhas de número/trevo (`.numero-bola`/`.trevo-bola`, já existentes) e nos ícones do seletor de jogos.

## Components

- **`game-selector`** (existente, `.game-selector` em `home.html`) — ganha um ícone por Jogo (ver EXPERIENCE.md § Component Patterns pro mapeamento exato) no lugar do `bi-dice-5` genérico repetido hoje. Estado ativo/hover inalterados.
- **`number-badge`** (existente, `.numero-bola`/`.trevo-bola`) — reaproveitado sem mudança visual pro histórico com muitos números (FR-24): a lista de bolinhas simplesmente quebra linha (`flex-wrap`) quando não cabe mais numa linha só — sem novo componente, sem agrupamento por dezena.
- **`rule-toggle-row`** (novo, FR-18 a FR-21) — uma linha por regra: label + toggle SIM/NÃO (`.form-check.form-switch` do Bootstrap) + campo Valor (`.form-control` numérico) ao lado. Quando o toggle está NÃO, o campo Valor usa `disabled` do HTML nativo (fica com `{components.rule-toggle-row.valueFieldWhenOff}`) — nunca é removido do DOM/escondido.
- **`sidebar-summary`** (novo, FR-16) — os 3 `stat-card` existentes (Jogos Gerados/Tipos/Recentes), empilhados verticalmente dentro de uma coluna lateral em vez de 3 colunas lado a lado no topo. Mesmo `stat-card` visual, só o container pai muda de `row` horizontal pra `col` vertical.
- **`filter-bar`** (novo, FR-24) — grupo horizontal de controles Bootstrap padrão (`.form-select` pra Jogo, inputs de data pro período, `.form-check` pra "só premiados"), sempre visível acima da lista/tabela de resultados.

## Do's and Don'ts

- **Do** reaproveitar `.card`, `.form-control`, `.form-select`, `.numero-bola`/`.trevo-bola`, `.stat-card`, `.game-selector` como já existem — nada nesta rodada justifica um componente visual do zero.
- **Do** manter os dois temas (claro/escuro) funcionando em qualquer elemento novo — usar sempre as variáveis CSS já definidas (`var(--bg-card)`, `var(--text-secondary)`, etc.), nunca um hex literal novo.
- **Don't** inventar uma paleta ou tipografia nova pras 3 telas do adendo — isso é trabalho do design system futuro do Boss, fora de escopo aqui (ver PRD §5).
- **Don't** esconder (`display:none`) o campo Valor de uma Regra de Geração desligada — sempre visível e desabilitado (ver `rule-toggle-row`).
- **Don't** usar `accent-primary`/`accent-primary-dark` como cor de texto/ícone sozinho — contraste insuficiente em pelo menos um dos dois temas (ver Colors). Só borda/fundo.
- **Don't** usar só cor pra indicar o jogo selecionado no `game-selector` — sempre acompanhado do `selectedIndicator` não-cromático.
