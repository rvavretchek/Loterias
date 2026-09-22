# Revisão de acessibilidade — Home / Regras de Geração / Histórico (adendo 2026-09-17)

Alvo: WCAG 2.1 AA. Revisão de `DESIGN.md` + `EXPERIENCE.md` (a seção "Accessibility Floor" de EXPERIENCE.md, linhas 59-64, é o baseline atual — criticada abaixo, não só reafirmada). Contraste calculado com a fórmula de luminância relativa do WCAG a partir dos hex reais no frontmatter `colors` de DESIGN.md (linhas 6-24).

---

- **[CRÍTICO] Contraste do campo Valor desabilitado (1,75:1) anula o próprio motivo de existir do padrão "visível, não escondido"**
  **Local:** DESIGN.md linhas 22-24 (`disabled-bg: #e9ecef`, `disabled-text: #adb5bd`) e 55-61 (`rule-toggle-row.valueFieldWhenOff`, nota "Visível, não escondido — ver EXPERIENCE.md FR-18"); EXPERIENCE.md linha 62 ("o campo Valor desabilitado usa o atributo HTML nativo `disabled`... leitores de tela já anunciam corretamente o estado").
  **Problema:** `#adb5bd` sobre `#e9ecef` dá **1,75:1** de contraste (luminância relativa 0,456 vs 0,835 → (0,835+0,05)/(0,456+0,05) = 1,75). É bem abaixo até do piso de 3:1 pra componente de UI, quanto mais do 4,5:1 de texto. Tecnicamente esse par está isento da SC 1.4.3 (texto de componente inativo), mas isso não resolve o problema real: a decisão de design explícita (linha 61: "nunca usar display:none no campo Valor") existe justamente pra que o usuário continue *vendo* o valor salvo mesmo com o toggle desligado — e com 1,75:1 esse valor fica praticamente ilegível pra qualquer usuário com baixa visão, derrotando o propósito declarado do próprio componente. A isenção do WCAG não é isenção de usabilidade.
  **Correção:** Subir `disabled-text` pra um tom que dê pelo menos ~3:1 sobre `#e9ecef` (ex. algo na faixa de `#6c757d`/`#5c636a`, que já é usado como `text-secondary` no mesmo arquivo — reaproveitar em vez de introduzir um terceiro neutro). Validar o par final com a mesma fórmula antes de fechar.

- **[ALTO] Nenhuma anunciação de status para a troca instantânea de habilitado/desabilitado do campo Valor (WCAG 4.1.3)**
  **Local:** EXPERIENCE.md linha 37 ("Alternar o switch habilita/desabilita o campo Valor **instantaneamente via JS**, sem reload"); Accessibility Floor linha 62.
  **Problema:** A linha 62 afirma que leitores de tela "já anunciam corretamente o estado sem trabalho extra" — isso só é verdade quando o foco *chega* ao campo Valor depois da troca (o atributo `disabled` nativo é lido nesse momento). Não cobre o caso real do fluxo: o usuário ativa o switch e o foco normalmente **permanece no switch** (comportamento correto de teclado) — ninguém navega automaticamente até o campo Valor em seguida. Pra um usuário de leitor de tela que não voltar a tabular até lá, a mudança de estado do campo é muda: não há `aria-live`/`role="status"` anunciando "Campo Valor habilitado" ou "desabilitado". A afirmação do Accessibility Floor é verdadeira só parcialmente e mascara essa lacuna.
  **Correção:** Adicionar uma região `aria-live="polite"` (pode ser visualmente oculta) perto do `rule-toggle-row` que anuncie a transição ("Campo Valor habilitado" / "desabilitado, use o padrão do sistema") no momento do toggle, ou associar o switch ao campo via `aria-controls` + `aria-describedby` no switch informando o efeito.

- **[ALTO] Atualização ao vivo da área "jogo selecionado" não tem região `aria-live` especificada**
  **Local:** EXPERIENCE.md linha 36 ("a mesma função `selectGame()`... ganha esse efeito colateral a mais, sem reload de página") e linha 75 (UJ-1 passo 2: "a área 'jogo selecionado' no topo atualiza na hora"); Accessibility Floor (linhas 59-64) não menciona esse comportamento em nenhum ponto, apesar de ser um dos dois únicos comportamentos explicitamente "JS-driven" desta rodada (o outro é o toggle do Valor, já coberto acima).
  **Problema:** Um usuário de leitor de tela que ativa um card do `game-selector` (por teclado ou toque) não recebe nenhum sinal de que uma área *fora* do elemento ativado (`aria-live`-less, no topo da página) acabou de mudar de conteúdo — nome do jogo, sugestão de concurso, etc. Sem um leitor de tela reprocessar aquela área manualmente (o que a maioria dos usuários não faz proativamente), a mudança passa despercebida, e o fluxo "clique no jogo → concurso já sugerido → gera" do UJ-1 (linhas 74-78) simplesmente não existe pra esse usuário — ele preencheria/geraria olhando pro estado antigo.
  **Correção:** Marcar o container "jogo selecionado" com `aria-live="polite"` (ou `aria-atomic="true"` se o conteúdo trocado for extenso), documentado explicitamente na seção Accessibility Floor junto com o padrão de anúncio (nome do jogo + indicação de que o concurso foi pré-preenchido).

- **[MÉDIO-ALTO] Estado "selecionado" do `game-selector` depende só de cor (WCAG 1.4.1, uso de cor)**
  **Local:** DESIGN.md linhas 43-48 (`components.game-selector`: `border`, `borderActive: accent-primary`, `backgroundActive: rgba(13, 110, 253, 0.1)`, `hoverTransform`); EXPERIENCE.md linha 54 (seleção via "radio nativo por trás").
  **Problema:** Os únicos dois tokens que diferenciam visualmente um card selecionado de um não-selecionado são cor de borda e um tingimento de fundo a 10% de opacidade — nenhum ícone de check, mudança de peso/espessura de borda, ou marca não-cromática é definido. Pra usuários com deficiência de percepção de cor (deuteranopia/protanopia, que têm dificuldade específica com tons de azul-vs-cinza em fundos claros), um azul a 10% de opacidade sobre `bg-card`/`bg-primary` quase brancos é uma pista fraca demais pra carregar sozinha o significado "este é o jogo selecionado". A semântica nativa do radio ajuda quem usa leitor de tela (que não depende de cor), mas não resolve pra quem enxerga a tela e depende só da cor.
  **Correção:** Adicionar um segundo indicador não-cromático ao estado ativo — largura de borda maior (não só cor), um ícone de check no canto do card, ou negrito no nome do jogo — em vez de reformular a paleta.

- **[MÉDIO] Elemento interativo aninhado dentro de outro elemento interativo no `game-selector`**
  **Local:** EXPERIENCE.md linha 36 ("Um ícone de lápis/engrenagem pequeno no canto do card leva a `/regras/<jogo>/`... sem disparar a seleção do jogo") + linha 54 ("radio nativo por trás").
  **Problema:** Se a seleção do jogo é implementada como de praxe em formulários Bootstrap — um `<label>` clicável envolvendo o card, associado a um `<input type="radio">` — colocar um segundo elemento focável (`<a>`/`<button>` do ícone de editar) *dentro* desse `<label>` é um padrão de HTML inválido (conteúdo interativo dentro de `<label>` não é permitido pelo content model) e o comportamento de clique/toque nesse caso é inconsistente entre navegadores — o clique no ícone pode acabar também disparando o radio por baixo, ou o link pode não ser alcançável isoladamente por teclado/leitor de tela. O texto "sem disparar a seleção do jogo" descreve a intenção, não como ela é garantida.
  **Correção:** Sair do padrão `<label>` envolvendo tudo — usar o card como um `<div>` não-focável com o radio nativo visualmente escondido mas presente (ex. `.btn-check` do próprio Bootstrap, que já resolve isso) e o ícone de editar como um elemento irmão posicionado por CSS, não aninhado.

- **[MÉDIO] Dois pares de cor não validados ficam abaixo de 4,5:1 pra uso como texto, contradizendo a alegação do Accessibility Floor**
  **Local:** DESIGN.md linhas 17-18 (`accent-primary: #0d6efd`, `accent-primary-dark: #3b82f6`); EXPERIENCE.md linha 63 ("Contraste de cor: herdado dos tokens de DESIGN.md, já validados nos dois temas pelo uso atual do app").
  **Problema:** Fazendo a conta pra os dois temas:
  - Claro: `#0d6efd` sobre `#ffffff` (bg-card) = **4,50:1** — exatamente no limiar da AA pra texto normal, sem margem nenhuma; qualquer variação de renderização/antialiasing pode empurrar pra baixo do corte.
  - Escuro: `#3b82f6` sobre `#1e293b` (bg-card-dark) = **3,98:1** — abaixo de 4,5:1, falha pra uso como texto/ícone informativo (passa só no piso de 3:1 de componente de UI/borda).
  A frase "já validados... nenhuma cor nova introduzida" (linha 63) é verdadeira só em parte: nenhuma cor é nova, mas a validação de contraste em si não é demonstrada em nenhum dos dois documentos, e pelo menos o par escuro falha se usado como texto/ícone (ex. o ✕ dos badges de filtro, o texto de um link ativo, o texto "Personalizado por você" se usar a cor de destaque).
  **Correção:** Restringir `accent-primary`/`accent-primary-dark` a uso em bordas/fundos (onde 3:1 basta) e nunca como cor de texto/ícone informativo sozinho nesta rodada; ou trocar por um tom mais escuro/saturado só pro uso textual.

- **[MÉDIO] Token `disabled-text` não tem par `-dark`, quebrando o padrão do resto da paleta**
  **Local:** DESIGN.md linhas 6-24 — todo outro token tem par claro/escuro explícito (`bg-primary`/`bg-primary-dark`, `text-primary`/`text-primary-dark`, etc.) exceto `disabled-text` (linha 24), que só tem um valor.
  **Problema:** Fica ambíguo se o tema escuro reaproveita `#adb5bd` pro texto do campo Valor desabilitado. Se reaproveitar (o cenário mais provável dado que não há outro candidato definido), o contraste desse texto vira **~4,99:1** contra `disabled-bg-dark` (`#334155`) — quase 3× melhor que o par do tema claro (1,75:1, ver primeiro finding). Ou seja, o mesmo componente fica drasticamente mais legível no escuro que no claro, uma inconsistência não intencional que a ausência do token esconde em vez de expor.
  **Correção:** Adicionar `disabled-text-dark` explicitamente ao frontmatter, e resolver esse token junto da correção do finding crítico acima (idealmente os dois pares — claro e escuro — ficando na mesma faixa de contraste, ~3:1+).

- **[MÉDIO] Botão de remover badge de filtro depende do glifo "✕" como único nome acessível**
  **Local:** EXPERIENCE.md linha 38 (exemplo: `"Jogo: Lotomania ✕"`) e linha 64 ("são `<button>` reais, não `<span onclick>` — focáveis e ativáveis via teclado").
  **Problema:** Ser um `<button>` real resolve foco/ativação por teclado, mas não resolve o nome acessível: se o texto do botão for literalmente "Jogo: Lotomania ✕", um leitor de tela pode anunciar o caractere Unicode `✕` como "multiplicação" ou "x", não como "remover" — o usuário ouve "Jogo: Lotomania, multiplicação, botão" sem entender a ação. Nenhum dos dois documentos especifica um `aria-label` diferente do texto visível.
  **Correção:** `aria-label="Remover filtro Jogo: Lotomania"` no `<button>`, com o "✕" marcado `aria-hidden="true"` dentro dele (mesmo padrão já adotado pros ícones de jogo, linha 61 de EXPERIENCE.md).

- **[MÉDIO] Restauração de foco após remoção de filtro (reload GET completo) não especificada**
  **Local:** EXPERIENCE.md linha 38 ("Aplicar dispara um GET normal (recarrega a lista via querystring, sem AJAX)").
  **Problema:** Cada clique num "✕" de badge recarrega a página inteira. Sem gerenciamento explícito de foco pós-carregamento, o comportamento padrão do navegador é resetar o foco pro topo do documento — um usuário de teclado que remove dois ou três filtros em sequência (cenário plausível: "só Lotomania, premiados, deste mês" → tira um por um) precisa tabular do zero pela página inteira a cada remoção, em vez de continuar de onde parou na barra de filtros.
  **Correção:** Documentar destino de foco pós-reload (ex. mover foco pro heading da barra de filtros ou pro primeiro badge restante) — via `autofocus` no elemento certo do template renderizado, já que não há JS/AJAX nesse fluxo.

- **[BAIXO-MÉDIO] Alvos de toque pequenos e aninhados: ícone de editar do `game-selector` e "✕" dos badges de filtro**
  **Local:** EXPERIENCE.md linha 36 ("ícone de lápis/engrenagem **pequeno** no canto do card") e linha 38 (badges de filtro, sem tamanho especificado).
  **Problema:** O ícone de editar é descrito explicitamente como "pequeno" e fica no canto de um card que, na maior parte da sua área, já é um alvo de toque grande e concorrente (seleção do jogo) — combinado com o problema de aninhamento de elemento interativo (finding acima), o risco de toque acidental (selecionar o jogo em vez de editar a regra, ou vice-versa) é real, especialmente em telas de toque. O target-size mínimo de 24×24px é AA só a partir do WCAG 2.2 (é AAA na 2.1, que é o baseline pedido aqui), mas mesmo fora do critério formal isso é um risco de usabilidade motora concreto que vale registrar dado que o próprio texto já assume o risco de conflito de clique ("sem disparar a seleção do jogo") sem definir como ele é evitado no espaço físico do ícone.
  **Correção:** Especificar um tamanho mínimo de área clicável pro ícone de editar (ex. 44×44px de hit-area mesmo com ícone visual menor, via padding), separado espacialmente do restante do card (ex. sempre no canto oposto à direção de hover/crescimento do card).

- **[BAIXO] Lista de bolinhas de número sem semântica de lista/agrupamento, mais crítico no caso Dupla-Sena**
  **Local:** EXPERIENCE.md linha 40 (Lotomania: 20 bolinhas; Lotofácil: 15; Dupla-Sena com duas sub-linhas rotuladas "1º sorteio:"/"2º sorteio:").
  **Problema:** Nenhum dos documentos especifica que a sequência de `number-badge` usa marcação de lista (`<ul>/<li>` ou `role="list"`) — pra 20 elementos (Lotomania) sem esse agrupamento, um usuário de leitor de tela não tem como saber quantos números faltam navegar nem que está dentro de um grupo coeso. No caso da Dupla-Sena isso piora: os rótulos "1º sorteio:"/"2º sorteio:" (texto solto antes de cada grupo, aparentemente) não são confirmados como programaticamente associados às bolinhas correspondentes (ex. via `role="group" aria-label="1º sorteio"`) — um usuário navegando pelas 6+6 bolinhas em sequência pode perder a noção de qual sorteio está ouvindo depois das primeiras.
  **Correção:** Envolver cada grupo de bolinhas num container com `role="group"` e `aria-label` nomeando o sorteio/jogo, e usar `<ul>/<li>` (ou `role="list"`/`role="listitem"`) pra a sequência de números em geral.

- **[BAIXO] Texto de ajuda de "linha"/"coluna" (FR-19/FR-20) sem associação `aria-describedby` confirmada**
  **Local:** EXPERIENCE.md linha 37 ("ganham um texto de ajuda curto abaixo do campo... `[NOTE FOR UX]` o texto exato depende do levantamento do grid, PRD §8.5 — ainda não feito").
  **Problema:** O texto em si está marcado como pendente (`[NOTE FOR UX]`), mas a lacuna de acessibilidade é separada do conteúdo: nada garante que, quando esse texto for escrito, ele seja associado ao campo via `aria-describedby` em vez de só posicionado visualmente abaixo dele. Sem essa associação, um usuário de leitor de tela que navega direto até o campo Valor por Tab nunca ouve a explicação de "linha"/"coluna" — só um sighted user rolando visualmente a vê.
  **Correção:** Quando o texto de PRD §8.5 for definido, especificar explicitamente `aria-describedby` ligando o `<input>` ao elemento de ajuda, não só posicionamento CSS.

- **[BAIXO] Mecanismo do diálogo de confirmação (FR-23) não especificado — risco de foco preso/perdido se for modal customizado**
  **Local:** EXPERIENCE.md linha 32 (mensagem de confirmação ao desligar a última proteção de sequência) e linha 44 (mesma ideia, "Salvar mostra uma confirmação clara").
  **Problema:** Nenhum dos dois documentos diz se essa confirmação é um `window.confirm()` nativo (acessível por padrão, foco gerenciado pelo navegador) ou um modal Bootstrap customizado. Se for modal customizado, faltam requisitos básicos de foco (foco movido pro modal ao abrir, preso dentro dele, devolvido ao elemento de origem ao fechar, fechável por Escape) que hoje não aparecem em nenhuma seção do documento — nem Interaction Primitives, nem Accessibility Floor.
  **Correção:** Se optar por modal customizado (mais provável, dado o padrão visual do resto do app), adicionar essas quatro regras de foco explicitamente à seção Accessibility Floor; se for `confirm()` nativo, declarar isso explicitamente pra fechar a ambiguidade.

---

## Resumo por severidade

- Crítico: 1
- Alto: 2
- Médio-Alto: 1
- Médio: 6
- Baixo-Médio: 1
- Baixo: 3

**Total: 14 achados.**
