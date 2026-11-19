# Arandu — Design System

Arandu é um **sistema multitenant de pré-vendas para empresas de serviços de TI**: recebe oportunidades comerciais (normalmente do CRM de cada cliente), qualifica com Go/No-Go, dimensiona por serviço, precifica em cenários, e aprova com rastreabilidade completa. Tem também suporte a leilão reverso / licitação pública (DFP), desenvolvido pela **Integrit Soluções Empresariais** — Integrit aparece só como fornecedor (rodapé, login), nunca co-assinando o header do produto.

O que o design precisa comunicar, nesta ordem: **confiabilidade, segurança, capacidade de adaptação e qualidade técnica**.

## Setup — sem provider

Nenhum componente lê contexto/provider — não precisa envolver nada em `<ThemeProvider>` ou similar. Só linke `styles.css` (a única entrada — ela já resolve tokens + estilos dos componentes) e importe os componentes direto de `window.AranduDesignSystem_ddacb7.*` (ou do bundle importável, conforme o runtime).

```jsx
const { Card, StatCard, Button, StatusBadge, Icon } = ADS; // window.AranduDesignSystem_ddacb7

function OportunidadeResumo() {
  return (
    <Card>
      <div style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'center' }}>
        <StatCard label="Valor do cenário" value="R$ 2.800.000" trend="up" />
        <StatusBadge status="Em aprovação" />
      </div>
      <Button variant="primary" icon="add">Criar Oportunidade</Button>
    </Card>
  );
}
```

## Estilo — sempre pelos componentes + tokens, nunca `.ar-*` na mão

Os componentes React já renderizam as classes `.ar-*` internamente (fonte: `components/components.css`, compilada em `styles.css`). **Nunca escreva `.ar-*` à mão** — use os componentes e suas props. Para layout/glue ao redor dos componentes (grids, espaçamento entre cards, contêineres de tela), use as **custom properties** abaixo — nunca valores soltos:

- Cor: `--brand-teal` `#2D9FA3` (ação — um botão teal por tela), `--brand-ink` `#1F2F32` (texto/inverso), `--brand-amber` `#F2A12C` (acento/2º nível, nunca "sucesso"); escalas completas `--teal-50…900`, `--amber-50…700`, `--neutral-0…950`. Semântico: `--success/warning/danger/info-{bg,border,fg,solid}`.
- Superfície: `--surface-page` `#F6F7F8`, `--surface-card` `#FFF`, `--surface-sunken`, `--surface-brand-soft` (teal 10%, nav ativo/tiles/badges).
- Sombra: `--shadow-xs/sm/md/lg/xl`, `--shadow-brand` (teal 22%, **só** botão primário).
- Espaçamento: grade de 4px. Shell: header 64px, side nav 256px, coluna 1280px, padding main 32px (24px mobile), padding card 24px, gap de grade 24px. Controles 32/40/48/56 (40 é o padrão).
- Raio: 4px chips · 6px tags · 8px botões/inputs/nav · 12px cards/tabelas · 16px modais · `full` pills/avatares.
- Tipografia: Manrope 400–800 (títulos 800, `letter-spacing:-.02em`); corpo 14px app / 16px site; rótulos 12px 700 uppercase `tracking .04em`. **Números financeiros sempre `IBM Plex Mono` tabular** (classe `.num`) — DRE/forecast/FTE precisam alinhar coluna a coluna. Escala 11/12/13/14/16/18/20/24/30/36/44.
- Animação: 150ms cor/hover/foco, 200ms abrir/fechar, 300ms elevação; easing `cubic-bezier(.2,.6,.2,1)`. Sem bounce/spring/entrada animada de página.
- Foco: `box-shadow 0 0 0 3px rgba(45,159,163,.28)` + borda teal — nunca outline do browser.

## Onde está a verdade

- `styles.css` — único arquivo que um consumidor precisa linkar (resolve tudo via `@import`).
- `tokens/*.css` — fonts, colors, typography, spacing, shape, elevation, motion, status, base.
- `components/components.css` — classes `.ar-*` reais (leia antes de estilizar algo fora do padrão).
- Cada `components/<grupo>/<Nome>/<Nome>.prompt.md` — API e exemplos por componente.
- `guidelines/cards/` — 25 cartões de especificação visual (cor, tipo, espaçamento, forma, marca).

## Conteúdo e copy (pt-BR sempre)

**Idioma.** Português do Brasil sempre. Números pt-BR: `R$ 3.548.261`, `20,0%`, datas `25/04/2026`, negativos `-R$ 60.000`.

**Tom.** Direto, técnico, coloquial-profissional — pré-vendas experiente falando com outro, sem jargão de marketing nem superlativo vazio. Contrações e oralidade brasileira ("pra", "não vingou", "achismo de corredor"). Frases curtas com travessão que corta o exagero: "Do Go/No-Go à proposta, num lugar só." / "Cada aprovação vira registro — quem decidiu, quando e por quê."

**Pessoa.** "Você" para o tenant; "Arandu" em 3ª pessoa ("Arandu dimensiona, precifica e aprova"). Nunca "nós oferecemos".

**Promessas de segurança são sempre construção, nunca declaração**: "isolados por construção — não por configuração que alguém possa esquecer de ativar".

**Casing.** Sentence case em títulos/botões/rótulos (exceção herdada: "Criar Nova Oportunidade" em Title Case). Uppercase só em micro-rótulos (12px), eyebrows, tags.

**Vocabulário de domínio — use exatamente estes termos**: Oportunidade, Qualificação Go/No-Go, Cenário (START/TARGET/ÓTIMO/STOP/STOP-PJ/HIGH-RISK), Dimensionamento, MOD, Insumos, DRE, Forecast, Cash Flow, NCG, Break-even, FTE, Vigência, Transição, Guarda de margem, Custódia/custodiante/quórum, Tenant, Leilão reverso, Certame, Parâmetros, Encargos, Faixas, Cargos e Salários.

**Statuses (nunca traduza nem invente)**: oportunidade — Em desenvolvimento, Reprovada, Ganha, Perdida, Cancelada, Entregue; cenário/aprovação — Rascunho, Em aprovação, Aprovado, Aprovado com ressalvas.

**Emoji: nunca**, em nenhuma superfície.

## Ícones

**Material Symbols Outlined** é o único sistema — webfont do Google Fonts (já em `tokens/fonts.css`), sem sprite/SVG/PNG próprios. Padrão `FILL 0, wght 400, GRAD 0, opsz 24`, 24px (20px em botões, 18px em ações densas de tabela). Preenchido (`FILL 1, wght 500` / `<Icon filled />`) **só** no item de nav ativo. Nunca emoji ou unicode como ícone (exceções: `→` em "Saiba mais →" e `·` como separador). Glifos canônicos: `dashboard` Início · `lightbulb` Oportunidades · `business_center` Empresa · `settings` Parâmetros · `fact_check` Qualificação · `calculate` Dimensionamento · `layers` Cenários · `verified` Aprovação · `lock` Segurança/custódia · `engineering` Arquitetura · `badge` Cargos · `description` Resumo executivo.

## Cobertura

Inventário = o que os mockups do Arandu realmente definem — nada além disso foi inventado, exceto 3 adições intencionais: `IBM Plex Mono` para números (alinhamento de DRE/forecast/FTE), `Field` (wrapper rótulo/hint/erro) e `Icon` (wrapper fino sobre Material Symbols). Telas fora do recorte dos UI kits (calculadoras de dimensionamento por serviço, leilão reverso, hub de Parâmetros, Ficha da Empresa, Usuários, Cargos e Salários, Gestão de Demanda, etc.) usam o mesmo shell e os mesmos componentes — componha a partir de `components/`.

# AranduDesignSystem (arandu-design-system@0.1.0)

This design system is the published arandu-design-system React library, bundled as a single
browser global. All 29 components are the real upstream code.

## Where things are

- `_ds_bundle.js` — the whole-DS bundle at the project root; loads every component to `window.AranduDesignSystem`. First line is a `/* @ds-bundle: … */` metadata header.
- `styles.css` — the single stylesheet entry: it `@import`s the tokens, fonts, and component styles (`_ds_bundle.css`). Link this one file.
- `components/<group>/<Name>/<Name>.prompt.md` (example JSX + variants), `<Name>.d.ts` (types), `<Name>.html` (variant grid).
- `tokens/*.css` — CSS custom properties, names verbatim from upstream.
- `fonts/` — `@font-face` files + `fonts.css` (when the package ships fonts).

For a specific component, `read_file("components/<group>/<Name>/<Name>.prompt.md")`.

## Loading

Add these two lines to your page once (React must be on the page first):

```html
<link rel="stylesheet" href="styles.css">
<script src="_ds_bundle.js"></script>
```

Components are then available at `window.AranduDesignSystem.*`. Mount into a dedicated child node (e.g. `<div id="ds-root">`), not the host page's own React root, so the two trees don't collide:

```jsx
const { Accordion } = window.AranduDesignSystem;
ReactDOM.createRoot(document.getElementById('ds-root')).render(<Accordion />);
```

## Tokens

223 CSS custom properties from arandu-design-system. Names are
preserved verbatim from upstream. They are declared inside `_ds_bundle.css` (this DS ships one compiled stylesheet rather than separate token files).

- **color** (35): `--text-strong`, `--text-body`, `--text-muted`, …
- **spacing** (27): `--space-0`, `--space-1`, `--space-2`, …
- **typography** (14): `--font-sans`, `--font-display`, `--font-mono`, …
- **radius** (6): `--radius-xs`, `--radius-sm`, `--radius-md`, …
- **shadow** (7): `--shadow-none`, `--shadow-xs`, `--shadow-sm`, …
- **other** (134): `--brand-teal`, `--brand-ink`, `--brand-amber`, …

## Components

### data
- `Accordion`
- `DataTable`
- `NavCard`
- `Pagination`
- `StatCard`

### navigation
- `AppFooter`
- `AppHeader`
- `Breadcrumbs`
- `NavItem`
- `PageHeading`
- `SideNav`
- `Tabs`

### core
- `Badge`
- `Button`
- `Card`
- `Icon`
- `IconButton`
- `StatusBadge`
- `Tag`

### feedback
- `Banner`
- `Modal`
- `Toast`

### forms
- `Checkbox`
- `Field`
- `Input`
- `Radio`
- `Select`
- `Textarea`
- `ToggleGroup`
