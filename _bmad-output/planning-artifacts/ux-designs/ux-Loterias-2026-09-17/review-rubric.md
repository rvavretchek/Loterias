# Revisão do par-espinha DESIGN.md + EXPERIENCE.md — ux-Loterias-2026-09-17

**Escopo:** validação como contrato pra consumidores downstream (arquitetura, story-dev humano ou IA) — extração de fonte limpa, toda referência resolvendo, toda decisão estrutural comprometida.

## Veredito Geral

**Adequado, com um achado crítico isolado.** O par de documentos é enxuto, coerente com a disciplina de reuso que o próprio texto prega, e cobre as duas UJs em escopo (UJ-1, UJ-3) com protagonista nomeado, passos numerados e clímax. Os 5 componentes citados em qualquer lugar têm linha correspondente nos dois arquivos, com regras reais (não descrições de uma palavra). O achado crítico é isolado a um ponto: três tokens de cor (`success`/`warning`/`danger`) não têm par claro/escuro, contradizendo a afirmação textual de que "todos os tokens acima são pares claro/escuro". Os demais achados são menores — lacunas de amarração (caminho de falha da UJ-3 não referenciado no próprio Key Flow, um estado de erro de formulário definido só em Voice and Tone sem entrada em State Patterns, uma referência de token em formato abreviado). Nenhum achado bloqueia a extração de fonte hoje, mas o achado crítico de cor deveria ser fechado antes que arquitetura/dev comecem a codificar o tema escuro dos elementos de aviso.

---

## 1. Cobertura de Fluxos (EXPERIENCE.md)

**Veredito: adequado.**

- UJ-1 e UJ-3 são as únicas UJs no PRD relevantes a este ciclo de UX (`_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md` linhas 45, 70). UJ-2 (cadastro da Sônia) é fluxo não relacionado, fora de escopo por design deste adendo — corretamente ausente, não é uma lacuna.
- **UJ-1** (EXPERIENCE.md linhas 72-78): protagonista nomeado (Dulce), 5 passos numerados, clímax explícito em negrito ("**Clímax (sem scroll):**", linha 77). Nomes verbatim do PRD (ver achado #7).
- **UJ-3** (EXPERIENCE.md linhas 80-86): protagonista nomeado (José), 5 passos numerados, clímax explícito em negrito (linha 85).
- **Achado (maior) — caminho de falha da UJ-3 não está no próprio Key Flow.** O PRD nomeia explicitamente o conflito de Regras de Geração impossíveis de satisfazer como o "Caso de borda" da UJ-3 (PRD linha ~89, seção UJ-3). O Key Flow da UJ-3 em EXPERIENCE.md (linhas 80-86) não menciona esse caso nem aponta para onde ele está tratado — quem lê só a seção Key Flows (como os exemplos de referência fazem, com uma linha `Failure:` ao final de cada fluxo) sai sem saber que esse caminho existe pra UJ-3. O conteúdo em si existe (Voice and Tone linha 29, State Patterns linha 50), só não está amarrado ao fluxo que o PRD atribui a ele.
- **Achado (menor) — caminho de falha da UJ-1 também não usa o padrão `Failure:` dos exemplos.** O passo 3 do Key Flow da UJ-1 (linha 76) menciona de passagem o aviso de regra relaxada, e o passo 5 (linha 78) cobre a resolução via histórico/filtros — mas nenhuma linha final tipo `Falha:` amarra o caso "filtro sem resultado" (State Patterns linha 48) nem o "rotina diária falha" (fora de escopo desta rodada, ok não estar aqui) ao fluxo. Diferença de forma em relação aos exemplos (`design-example-mobile.md`/`shadcn`), que fecham cada Key Flow com uma linha `Failure:` dedicada.

## 2. Completude de Tokens (DESIGN.md)

**Veredito: thin — um achado crítico isolado, resto completo.**

- Todos os tokens do frontmatter (`colors`, `typography`, `rounded`, `spacing`, `components`) e todas as referências `{path.to.token}` em ambos os arquivos foram extraídos e checadas (`grep` de `\{[a-zA-Z][a-zA-Z0-9_.\-]*\}` nos dois arquivos). Toda referência interna do frontmatter (`{colors.border}`, `{colors.accent-primary}`, `{rounded.full}`, `{colors.disabled-bg}`, `{colors.disabled-bg-dark}`, `{colors.disabled-text}`, `{colors.bg-card}`, `{spacing.card-padding}`) resolve pra um token definido. As referências em prosa (`{rounded.DEFAULT}`, `{rounded.full}` em DESIGN.md linha 94; `{components.rule-toggle-row.valueFieldWhenOff}` em DESIGN.md linha 100) também resolvem.
- **Achado (crítico) — `success`/`warning`/`danger` sem par claro/escuro.** DESIGN.md linhas 19-21 define `success: '#198754'`, `warning: '#ffc107'`, `danger: '#dc3545'` sem os equivalentes `-dark` que todo outro token de cor da lista tem (`bg-primary`/`bg-primary-dark`, `text-primary`/`text-primary-dark`, `text-secondary`/`text-secondary-dark`, `border`/`border-dark`, `accent-primary`/`accent-primary-dark`, `disabled-bg`/`disabled-bg-dark`). A seção "Colors" (linha 78) afirma textualmente: *"Todos os tokens acima são pares claro/escuro do que já existe em `templates/base/base.html`"* — uma afirmação falsa para esses três tokens especificamente. Nenhum dos dois arquivos referencia `success`/`warning`/`danger` em nenhum componente ou trecho de prosa (checado via grep) — então além de faltar o par escuro, são tokens não amarrados a nenhuma regra de uso nesta rodada (mensagem de erro de validação, aviso de conflito FR-22, badge de "premiado" no histórico são todos candidatos óbvios de uso e nenhum aponta pra esses tokens por nome). Um consumidor downstream que precisar estilizar essas mensagens no tema escuro não tem de onde tirar o valor — e pode legitimamente presumir, pela afirmação da linha 78, que um par exista.
- **Achado (menor) — referência de token em formato abreviado.** EXPERIENCE.md linha 37 usa `{disabled-bg}`/`{disabled-text}` (sem o prefixo `colors.`) em vez de `{colors.disabled-bg}`/`{colors.disabled-text}` como o resto do documento faz. Resolve sem ambiguidade (só existe um token com esse nome no sistema todo), mas quebra a convenção de path completo usada em todo o restante do par de documentos.
- **Nota (bloat, ver também §6) — `spacing.gutter` nunca referenciado.** Definido no frontmatter (DESIGN.md linha 41) mas não aparece em nenhuma referência `{spacing.gutter}` nem é citado por nome em nenhuma prosa. Impacto baixo — spacing não carrega o mesmo risco de "faltou o par escuro" que cor carrega — mas é um token morto.

## 3. Cobertura de Componentes (ambas as espinhas)

**Veredito: strong.**

- Componentes citados em qualquer lugar dos dois arquivos: `game-selector`, `number-badge`, `rule-toggle-row`, `sidebar-summary`, `filter-bar` — exatamente 5, e os 5 têm entrada tanto em DESIGN.md § Components (linhas 98-102) quanto em EXPERIENCE.md § Component Patterns (linhas 36-40), com nomes idênticos byte-a-byte (checado via grep) e regras reais e específicas por componente (ex.: `rule-toggle-row` especifica que o campo Valor usa `disabled` nativo, nunca `display:none`; `filter-bar` especifica GET normal sem AJAX, badges removíveis por filtro individual) — não são descrições de uma palavra.
- Componentes pré-existentes reaproveitados sem alteração (`.card`, `.form-control`, `.form-select`, `.stat-card`, `.numero-bola`/`.trevo-bola`) são citados como herdados-como-estão no Do's/Don'ts de DESIGN.md (linha 106) em vez de ganharem linha própria — padrão equivalente ao usado no exemplo Drift (`design-example-shadcn.md` linha 93, componentes shadcn citados como "used as-is") pra componentes que este ciclo não modifica. Não é uma lacuna.

## 4. Cobertura de Estados (EXPERIENCE.md)

**Veredito: adequado.**

Percorridas as 3 telas da IA (home, regras de geração, histórico) contra os estados aplicáveis (vazio, cold-load, foco, erro, desabilitado):

- **Home:** "nenhum jogo selecionado ainda" coberto (State Patterns linha 46). Conteúdo da sidebar de resumo é herdado sem mudança (FR-16 só reposiciona), então não precisa de novo estado de cold-load.
- **Regras de Geração:** estado default-vs-personalizado coberto (linha 44) com indicador textual e botão condicional "Restaurar padrão". Estado desabilitado do campo Valor coberto com detalhe (nunca `display:none`, sempre `disabled` nativo — DESIGN.md linha 100, Accessibility Floor linha 62).
  - **Achado (menor) — erro de validação do campo Valor não tem entrada em State Patterns.** A mensagem existe em Voice and Tone (linha 31: *"O valor pra '...' precisa estar entre 1 e 3 pra Mega-Sena"*), mas o gatilho/tratamento do estado (validação em tempo real vs. no submit? bloqueia salvar? mensagem some ao corrigir?) não aparece em State Patterns, ao contrário dos demais estados de erro do documento (ex. "Histórico — nenhum resultado", linha 48, que está em State Patterns E é referenciado em Voice and Tone). Um consumidor que só ler State Patterns não sabe que esse estado existe.
  - **Achado (menor) — confirmação de "desligar última proteção" (FR-23) também só em Voice and Tone (linha 32), sem entrada em State Patterns** — mesma observação: mensagem bem especificada, mas o estado/gatilho não amarrado à tabela de estados.
- **Histórico:** "nenhum resultado pro filtro aplicado" coberto (linha 48) com mensagem nomeando o filtro + botão "Limpar filtros". Volume grande sem filtro é explicitamente reconhecido como fora de escopo (linha 49), não confundido com o problema de filtros.
- **Achado (menor) — nenhum estado de foco (`:focus-visible`) documentado**, apesar de Interaction Primitives (linhas 54-57) declarar múltiplos elementos novos navegáveis por teclado (switch de regra, badges de filtro removíveis). Os exemplos de referência (`experience-example-shadcn.md` linha 92: *"Focus rings inherit shadcn's ring token"*) fecham esse ponto explicitamente; aqui não há uma linha equivalente nem em Accessibility Floor nem em DESIGN.md.

## 5. Cobertura de Referências Visuais

**Veredito: n/a — nada pra revisar, sem defeito.**

`.working/` existe mas está vazio (0 arquivos). `imports/` existe e está vazio. Não há diretórios `mockups/` nem `wireframes/`. Conforme a instrução da tarefa, isso é esperado (a produção dos 3 mocks HTML pode estar rodando em paralelo) e não é tratado como defeito.

## 6. Bloat e Overespecificação

**Veredito: strong.**

O documento é enxuto de propósito — a seção Brand & Style e o Do's/Don'ts de DESIGN.md (linhas 106-109) proíbem explicitamente inventar componente/paleta/tipografia nova pra esta rodada, e o restante do texto segue essa disciplina (5 componentes novos/estendidos, nada além disso). Único ponto de bloat real: os tokens `spacing.gutter` (§2) e, em menor medida, `success`/`warning`/`danger` (§2, já contados como crítico ali) definidos sem uso amarrado em nenhum componente ou prosa desta rodada.

## 7. Disciplina de Herança

**Veredito: strong, com uma lacuna de sintaxe menor.**

- **Frontmatter `sources` resolve:** os dois arquivos-fonte existem e são legíveis — `_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md` (67.307 bytes) e `_bmad-output/planning-artifacts/brief-layout-e-regras-personalizadas-2026-09-17.md` (7.353 bytes), ambos confirmados via leitura de diretório. DESIGN.md cita só o PRD como fonte; EXPERIENCE.md cita PRD + brief — assimetria defensável (DESIGN.md é puramente visual/herdado da UI existente; o brief carrega decisão comportamental, não visual) e não um erro de referência quebrada.
- **Nomes de UJ verbatim do PRD:** confirmado — "UJ-1. Dulce gera jogos e é avisada de um acerto." e "UJ-3. José personaliza como a Mega-Sena é gerada pra ele." batem literalmente com os cabeçalhos em negrito do PRD (linhas 45 e 70).
- **Nomes de componente idênticos entre as seções:** confirmado nos 5 componentes (ver §3).
- **Referências de token da EXPERIENCE.md resolvendo em DESIGN.md por nome:** resolvem, com a única exceção de forma já registrada em §2 (`{disabled-bg}`/`{disabled-text}` sem o prefixo `colors.`).

## 8. Adequação de Forma

**Veredito: strong.**

- **DESIGN.md** segue a ordem canônica presente: Brand & Style → Colors → Typography → Layout & Spacing → Shapes → Components → Do's and Don'ts. Omite Elevation & Depth — defensável: o app já usa a elevação padrão do Bootstrap (`.card`) sem nenhuma decisão nova de profundidade nesta rodada, e a seção Brand & Style já declara "mínimo de invenção necessária" como princípio geral, então não haveria conteúdo genuíno pra essa seção.
- **EXPERIENCE.md** tem as 8 seções obrigatórias: Foundation, Information Architecture, Voice and Tone, Component Patterns, State Patterns, Interaction Primitives, Accessibility Floor, Key Flows — todas presentes, na ordem correta, mais a seção condicional "Responsive & Platform" (linhas 66-68), corretamente disparada pelo comportamento de breakpoint descrito em Foundation/FR-16. Omite "Inspiration & Anti-patterns" (opcional, não faz falta pra um projeto que reaproveita 100% de um sistema visual já existente — não há "inspiração externa" a documentar).

---

## Notas Mecânicas

- Arquivos-fonte verificados como existentes e legíveis: `prd-Loterias-2026-09-07/prd.md`, `brief-layout-e-regras-personalizadas-2026-09-17.md`.
- Tokens extraídos do frontmatter de DESIGN.md: 18 cores, 3 papéis de tipografia, 2 valores de `rounded`, 2 de `spacing`, 5 objetos de `components` — todos definidos, nenhuma referência quebrada.
- Componentes extraídos (união das duas espinhas): `game-selector`, `number-badge`, `rule-toggle-row`, `sidebar-summary`, `filter-bar` — 5, todos com linha nos dois arquivos.
- UJs em escopo: UJ-1, UJ-3 (PRD). UJ-2 fora de escopo por design, não é lacuna.
- Diretórios de referência visual checados: `.working/` (vazio), `imports/` (vazio), `mockups/`/`wireframes/` (inexistentes) — nenhum arquivo pra revisar nesta passada.

### Achados por severidade

- **Crítico (1):** `success`/`warning`/`danger` sem par claro/escuro, contradizendo a afirmação de "todos os tokens são pares claro/escuro" (DESIGN.md linhas 19-21, 78).
- **Maior (1):** caminho de falha da UJ-3 (conflito de Regras de Geração, FR-22) não referenciado dentro do próprio Key Flow da UJ-3, apesar de o PRD atribuir esse caso de borda especificamente a ela (EXPERIENCE.md linhas 80-86).
- **Menor (5):** caminho de falha da UJ-1 sem linha `Failure:`/referência cruzada explícita no Key Flow (EXPERIENCE.md linhas 72-78); referência de token em formato abreviado `{disabled-bg}`/`{disabled-text}` (EXPERIENCE.md linha 37); erro de validação do campo Valor sem entrada em State Patterns (só em Voice and Tone linha 31); confirmação de "desligar última proteção" (FR-23) sem entrada em State Patterns (só em Voice and Tone linha 32); ausência de tratamento de estado de foco (`:focus-visible`) em Accessibility Floor apesar de múltiplos elementos novos navegáveis por teclado.
- **Nota/bloat (1):** `spacing.gutter` definido e nunca referenciado.
