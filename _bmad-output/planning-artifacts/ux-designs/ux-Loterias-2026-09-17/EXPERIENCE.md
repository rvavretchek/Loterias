---
name: Loterias — Home, Regras de Geração e Histórico (adendo 2026-09-17)
description: "IA/comportamento pras 3 telas do adendo 2026-09-17 do PRD: home autenticada reorganizada, edição de Regras de Geração por usuário+Jogo, histórico com filtros."
status: final
updated: 2026-09-17
sources:
  - "_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md"
  - "_bmad-output/planning-artifacts/brief-layout-e-regras-personalizadas-2026-09-17.md"
---

*DESIGN.md e este documento têm a palavra final sobre qualquer wireframe/mock/import que os contradiga.*

## Foundation

- **Forma:** Web responsivo, desktop-first. Meta de "sem scroll pra gerar um jogo" (PRD FR-16) vale a partir de `≥1280×720`; abaixo disso, scroll é aceitável — não é meta desta rodada.
- **Sistema de UI:** Bootstrap 5.3.2 + Bootstrap Icons 1.11.1, já em uso em todo o app (`templates/base/base.html`). Server-rendered Django — sem SPA/framework JS pesado; JS vanilla pontual só onde já existe (`selectGame()`, sugestão de concurso) ou é estritamente necessário (toggle liga/desliga do campo Valor). Ver DESIGN.md pros tokens visuais herdados.
- **Temas:** claro/escuro já existentes (`data-theme`, preferência salva em `User.preferred_theme`) — todo componente novo desta rodada funciona nos dois sem exceção.

## Information Architecture

Três telas, nenhuma rota nova pra Home/Histórico (já existem), uma família de rotas nova pra Regras de Geração:

- **`/` (Home, `home_view`)** — reorganizada (FR-16/FR-17): sidebar de resumo + área principal com "jogo selecionado" no topo e seletor de jogos logo abaixo. Ponto de entrada pras outras duas telas. Mock: [`mockups/home.html`](mockups/home.html).
- **`/regras/<jogo>/` (nova, FR-18)** — uma página por Jogo, alcançada via ação "editar" no seletor de jogos da Home. Cada Jogo é uma URL própria (ex. `/regras/mega-sena/`), nunca uma aba/JS trocando conteúdo na mesma página — consistente com o padrão de tela-por-rota do resto do app. Formulário pré-carregado com a Regra de Geração atual (default do sistema, ou a personalizada se já existir uma). Um link/botão "‹ Voltar aos jogos" retorna à Home. Mock: [`mockups/regras-geracao.html`](mockups/regras-geracao.html) (Mega-Sena, estado personalizado).
- **`/historico/` (existente, `history_view`)** — ganha uma barra de filtros (Jogo, período, premiado) sempre visível no topo da lista (FR-24), cumulativos entre si. O estado dos filtros vive na querystring (`?jogo=Lotomania&premiado=1`), não em sessão — permite voltar/compartilhar/atualizar a página sem perder o filtro aplicado. Mock: [`mockups/historico.html`](mockups/historico.html) — **nota:** o mock ainda mostra 20 bolinhas pra Lotomania num card de exemplo; o valor correto é 50 (ver `.memlog.md`). O padrão visual (flex-wrap) não muda com a contagem exata — só o dado do mock está desatualizado.

*Mocks gerados como referência visual — em caso de conflito com o que está escrito aqui ou em DESIGN.md, este documento e DESIGN.md têm a palavra final (ver nota no topo).*

## Voice and Tone

Direto e sem jargão técnico, mesmo tom já usado no app (mensagens via `django.contrib.messages`, labels em português claro). Duas mensagens novas desta rodada merecem cuidado específico:

- **Regra relaxada (FR-22):** nomeia a regra e o Jogo — nunca genérica. Ex.: *"O jogo de Mega-Sena foi gerado relaxando a regra 'Limita quantidade de números em sequência' — não foi possível respeitar todas as regras configuradas."* Nunca: *"Não foi possível aplicar todas as suas preferências."*
- **Histórico sem resultado pro filtro aplicado:** nomeia o que foi filtrado, não um vazio genérico. Ex.: *"Nenhum jogo de Lotomania premiado encontrado nesse período."* com um botão "Limpar filtros" ao lado.
- **Valor fora da faixa aceitável (Regra de Geração):** mensagem inline no próprio campo, nomeando a faixa válida — não um erro genérico de formulário. Ex.: *"O valor pra 'Limita quantidade de números em sequência' precisa estar entre 1 e 3 pra Mega-Sena."* (a faixa exata por regra/Jogo é decisão de arquitetura — PRD §8.6 — mas a mensagem sempre nomeia o limite real, nunca "valor inválido" sozinho).
- **Desligar a última proteção de sequência ao personalizar (FR-23):** se José desliga todos os toggles relacionados a sequência da Mega-Sena, ele fica com MENOS controle de sequência do que o default do sistema tinha antes (a Regra de Sequência adaptativa parava de valer assim que ele personalizou, mesmo antes desse último toggle) — não é óbvio pra quem só está mexendo em um campo por vez. Ao salvar um estado assim, mostra uma confirmação explícita: *"Isso desliga toda a proteção contra sequências pra Mega-Sena — a regra automática que hoje evita repetição não vale mais depois que você personaliza. Confirma?"*

## Component Patterns

- **`game-selector`** (existente, estendido) — cada um dos 6 Jogos ganha um ícone Bootstrap Icons distinto (FR-17): Mega-Sena `bi-trophy`, +Milionária `bi-flower1`, Lotomania `bi-100`, Lotofácil `bi-lightning`, Quina `bi-star`, Dupla-Sena `bi-stack`. Clicar seleciona (como hoje) e agora também atualiza a área "jogo selecionado" no topo — mesma função `selectGame()` já existente em `home.html` (que já reage à troca de jogo pra sugerir o concurso) ganha esse efeito colateral a mais, sem reload de página. Um ícone de lápis/engrenagem no canto do card leva a `/regras/<jogo>/` (ação "editar", FR-18) sem disparar a seleção do jogo — implementado como o padrão `.btn-check` do próprio Bootstrap (radio visualmente escondido + `<label>` só ao redor do conteúdo do card, não envolvendo o ícone de editar), nunca um `<label>` cobrindo um elemento focável aninhado dentro dele (HTML inválido, clique ambíguo). O ícone de editar tem no mínimo 44×44px de área clicável (via padding, mesmo com o glifo visualmente menor) e fica no canto oposto ao de crescimento do hover do card, separado espacialmente do restante da área clicável de seleção.
- **`rule-toggle-row`** (novo, FR-18 a FR-21) — label da regra + switch SIM/NÃO + campo Valor. Alternar o switch habilita/desabilita o campo Valor **instantaneamente via JS**, sem reload (ver DESIGN.md `components.rule-toggle-row`) — o campo nunca desaparece, só fica com `{colors.disabled-bg}`/`{colors.disabled-text}`. Campos exclusivos de Lotofácil/Lotomania (ex. "espaço mínimo entre sequências") só aparecem no formulário do Jogo correspondente — o formulário é montado por família de Jogo (FR-19/FR-20/FR-21), nunca mostra um campo que não se aplica àquele Jogo. As duas regras de "linha"/"coluna" (FR-19/FR-20) ganham um texto de ajuda curto abaixo do campo explicando que a contagem usa o layout do volante oficial daquele Jogo na Caixa (`[NOTE FOR UX]` o texto exato depende do levantamento do grid, PRD §8.5 — ainda não feito; sem esse texto, "linha"/"coluna" não significa nada pro usuário que não conhece o volante físico) — associado ao campo via `aria-describedby`, não só posicionado visualmente abaixo dele, pra quem navega direto até o campo por Tab também ouvir a explicação.
- **`filter-bar`** (novo, FR-24) — `.form-select` pra Jogo, dois inputs de data (`type="date"`) pro período, `.form-check` pra "só premiados". Aplicar dispara um GET normal (recarrega a lista via querystring, sem AJAX). Cada filtro ativo aparece como um badge removível acima da lista (`<button>` real, texto visível "Jogo: Lotomania" + glifo "✕" marcado `aria-hidden="true"`, com `aria-label="Remover filtro Jogo: Lotomania"` no botão — o glifo sozinho não é o nome acessível) — clicar remove só aquele filtro (recarrega via GET), mantendo os demais (cumulativos). Após o reload, o foco vai pro heading da barra de filtros (não pro topo do documento) — importante pra quem remove vários filtros em sequência via teclado.
- **`sidebar-summary`** (novo, FR-16) — só leitura, mesmos 3 `stat-card` de hoje, empilhados verticalmente. Sem interação nova.
- **`number-badge`** (existente, estendido) — a lista de bolinhas quebra linha naturalmente (`flex-wrap`) pra jogos com muitos números (Lotomania: 50; Lotofácil: 15) — sem componente novo. A sequência de bolinhas usa `role="list"`/`role="listitem"` (ou `<ul>/<li>` semânticos) pra que um leitor de tela anuncie quantos números o grupo tem. Pra Dupla-Sena, o card do jogo no histórico mostra duas sub-linhas rotuladas: "1º sorteio:" com suas bolinhas, "2º sorteio:" com as bolinhas dele, empilhadas (nunca lado a lado) — cada grupo envolvido num container `role="group"` com `aria-label` nomeando o sorteio ("1º sorteio", "2º sorteio"), pra não se perder a separação entre os dois conjuntos ao navegar bolinha por bolinha.

## State Patterns

- **Regra de Geração — default vs. personalizada** (FR-18/FR-23): a tela de edição mostra um indicador do estado atual ("Usando regras padrão do sistema" ou "Personalizado por você") no topo do formulário. Quando personalizado, um botão "Restaurar padrão" `[ASSUMPTION]` aparece, apagando a Regra de Geração daquele usuário+Jogo e voltando ao comportamento default (mesmo efeito de nunca ter personalizado). Salvar mostra uma confirmação clara de que a mudança vale só daqui pra frente — jogos já gerados antes não são recalculados nem mudam de números (PRD FR-18).
- **Geração no pior caso do conflito de regras (FR-22):** o limite de tentativas (`max_attempts`, mesmo padrão de `regenerate_bet_view`) roda no servidor antes de responder — não há um estado de "carregando" visível hoje pra gerar um jogo (a resposta já é rápida o bastante pra não precisar). Se o pior caso (todas as tentativas esgotadas antes de relaxar uma regra) se mostrar perceptível ao usuário na prática, um spinner/estado de carregamento no botão "Gerar Jogo" fica como melhoria futura — não bloqueia esta rodada.
- **Home — nenhum jogo selecionado ainda:** a área "jogo selecionado" no topo mostra um prompt leve ("Selecione um jogo abaixo pra começar") em vez de ficar em branco, até o usuário clicar em um jogo no seletor.
- **Campo Concurso sobrevive à reorganização:** o campo de Concurso (editável, aceita concursos especiais/comemorativos fora da sugestão — PRD FR-2/UJ-1) continua existindo dentro da área "jogo selecionado" reposicionada, exatamente como hoje — a reorganização do FR-16 muda POSIÇÃO, nunca remove ou esconde esse campo.
- **Histórico — nenhum resultado pro filtro aplicado:** mensagem nomeando o filtro (ver Voice and Tone) + botão "Limpar filtros", nunca uma tabela vazia sem explicação.
- **Volume total de jogos guardados (sem filtro nenhum aplicado):** os filtros (FR-24) resolvem a legibilidade de UM jogo com muitos números, mas não o volume de MUITOS jogos guardados ao longo do tempo por um usuário ativo — o PRD (§6.2) já adia paginação explícita pra depois, revisitando "se o volume real se mostrar um problema". Esta rodada de UX não resolve esse caso; fica reconhecido aqui pra não ser confundido com o problema já resolvido dos filtros.
- **Conflito de regras na geração (FR-22):** mensagem de aviso (ver Voice and Tone) aparece junto da confirmação de sucesso do jogo gerado — não é um erro, o jogo foi gerado normalmente, só com uma regra relaxada. Cor `{colors.warning}`/`{colors.warning-dark}` (aviso, não erro).
- **Valor fora da faixa aceitável:** o campo Valor entra em estado de erro inline (borda `{colors.danger}`/`{colors.danger-dark}`) com a mensagem nomeando a faixa válida (ver Voice and Tone) — bloqueia o salvamento até corrigido, não deixa salvar um valor fora da faixa silenciosamente.
- **Confirmação ao desligar a última proteção de sequência (FR-23):** um modal Bootstrap (`.modal`, ver Accessibility Floor pro gerenciamento de foco) intercepta o salvamento nesse caso específico — o usuário precisa confirmar explicitamente antes da Regra de Geração ser salva sem nenhuma proteção de sequência ativa.

## Interaction Primitives

- Seleção de jogo: clique/tap num card do `game-selector` (radio nativo por trás, acessível via teclado).
- Alternância de regra: switch nativo (`<input type="checkbox">` estilizado como `.form-switch`), navegável e ativável via teclado/Enter/Espaço.
- Filtros: `<select>`/`<input type="date">`/`<input type="checkbox">` nativos, sem componente custom de data.
- Navegação entre telas: link/botão HTML padrão, sempre com `href` real (nunca só `onclick` em JS) — preserva "abrir em nova aba"/voltar do navegador.

## Accessibility Floor

- Todo ícone de Jogo (`game-selector`) é decorativo (`aria-hidden="true"`) — o nome do Jogo já aparece como texto ao lado (`<h5>{{ config.name }}</h5>`), nunca ícone sozinho carregando significado.
- O campo Valor desabilitado (`rule-toggle-row`) usa o atributo HTML nativo `disabled` (não CSS puro) — leitores de tela já anunciam corretamente o estado quando o foco chega até o campo. Isso não cobre o momento da troca em si: quando o switch é ativado/desativado, o foco normalmente continua no switch (comportamento correto de navegação), então uma região `aria-live="polite"` (visualmente oculta) perto do `rule-toggle-row` anuncia a transição ("Campo Valor habilitado"/"desabilitado, use o padrão do sistema") no momento do toggle, sem depender de o usuário tabular até lá.
- A área "jogo selecionado" (atualizada via JS ao trocar de jogo no `game-selector`, ver Component Patterns) é uma região `aria-live="polite"` (com `aria-atomic="true"`, já que o conteúdo trocado é grande — nome do jogo + campo de concurso pré-preenchido) — sem isso, um usuário de leitor de tela que seleciona um jogo não recebe nenhum sinal de que uma área fora do elemento ativado mudou de conteúdo.
- O diálogo de confirmação ao desligar a última proteção de sequência (FR-23, ver Voice and Tone) é um modal Bootstrap (`.modal`, consistente com o padrão visual do resto do app, não um `window.confirm()` nativo) — segue as 4 regras básicas de foco de modal: foco move pro modal ao abrir, fica preso dentro dele (focus trap), volta pro elemento de origem (o botão "Salvar") ao fechar, e fecha via Esc. O componente `.modal` do próprio Bootstrap já implementa essas 4 regras nativamente — não é um modal customizado do zero.
- Contraste de cor: `disabled-text`/`disabled-text-dark` reaproveitam `text-secondary`/`text-secondary-dark` (ver DESIGN.md Colors) especificamente pra corrigir um par insuficiente (1,75:1) do rascunho anterior. `accent-primary`/`accent-primary-dark` ficam restritos a borda/fundo (nunca texto/ícone sozinho) por ficarem abaixo ou no limiar de 4,5:1 em pelo menos um tema — ver DESIGN.md Do's and Don'ts.
- Estado "selecionado" do `game-selector` nunca depende só de cor — o `selectedIndicator` (ícone de check, DESIGN.md `components.game-selector`) é o segundo sinal não-cromático, além de borda/fundo.
- Badges de filtro removíveis (`filter-bar`) são `<button>` reais, não `<span onclick>` — focáveis, ativáveis via teclado, com `aria-label` nomeando a ação (ver Component Patterns).
- Todo elemento navegável por teclado nesta rodada (cards do `game-selector`, switches do `rule-toggle-row`, badges do `filter-bar`) mantém o contorno de foco padrão do Bootstrap (`:focus-visible`) sem removê-lo — nenhum CSS novo desta rodada usa `outline: none`.
- Nenhum elemento interativo fica aninhado dentro de outro (ex. o ícone de editar do `game-selector` nunca dentro do `<label>` do radio de seleção) — ver Component Patterns pro padrão `.btn-check` que evita isso.
- O texto de ajuda das regras de "linha"/"coluna" é associado ao campo via `aria-describedby`, não só posicionamento visual — ver Component Patterns.
- A sequência de `number-badge` usa `role="list"`/`role="listitem"`, e os dois sorteios da Dupla-Sena ficam em containers `role="group"` com `aria-label` próprio — ver Component Patterns.

## Responsive & Platform

Breakpoint da sidebar: ver DESIGN.md Layout & Spacing. A barra de filtros do histórico e o formulário de Regras de Geração usam o grid responsivo padrão do Bootstrap (campos empilham em telas estreitas) — nenhum layout específico de mobile foi pedido nesta rodada além de "não quebrar".

## Key Flows

Só os fluxos alterados ou novos desta rodada — UJ-2 (cadastro) e os demais já documentados no PRD seguem como estão, sem mudança.

### UJ-1. Dulce gera jogos e é avisada de um acerto. *(atualizado 2026-09-17 — passos 1-2, ver PRD)*

1. Dulce entra na Home. A sidebar de resumo está à direita; a área "jogo selecionado" no topo mostra o prompt de seleção (ainda sem jogo escolhido).
2. Clica em Mega-Sena no seletor abaixo (ícone `bi-trophy`) — a área "jogo selecionado" no topo atualiza na hora, e o campo de concurso já vem com a sugestão preenchida.
3. Gera o jogo. Se a Regra de Geração dela pra Mega-Sena estiver personalizada e um conflito acontecer, vê o aviso nomeando qual regra foi relaxada (FR-22) junto da confirmação — o jogo foi gerado normalmente.
4. **Clímax (sem scroll):** todo esse processo, do clique no jogo até a confirmação, acontece sem precisar rolar a tela — a área útil inicial já contém tudo.
5. Mais tarde, quer conferir só os jogos de Lotomania premiados do mês — abre o Histórico, aplica os filtros que interessam (Jogo + período + premiado, cumulativos) e vê a lista já restrita, sem precisar procurar manualmente.
- **Caminho de falha:** se tentar gerar pra um Concurso que já tem resultado, vê o bloqueio de sempre (FR-2), sem sair da área "jogo selecionado" — não perde a seleção de jogo nem precisa reabrir o seletor.

### UJ-3. José personaliza como a Mega-Sena é gerada pra ele. *(nova, 2026-09-17, ver PRD)*

1. Na Home, José clica no ícone de editar no card da Mega-Sena (sem selecionar o jogo pra gerar) — vai pra `/regras/mega-sena/`.
2. A tela mostra "Usando regras padrão do sistema" e o formulário com os 5 campos da família Mega-Sena/Dupla-Sena/Quina/+Milionária, todos com o switch em NÃO e os campos Valor visíveis-porém-desabilitados.
3. Liga "Limita quantidade de números em sequência", digita o valor, muda "Tipo de distribuição" pra "Totalmente Aleatória", salva.
4. **Clímax:** o indicador do topo muda pra "Personalizado por você"; a próxima Mega-Sena que ele gerar na Home usa essas regras, não mais o default.
5. Se quiser desistir da personalização, o botão "Restaurar padrão" volta ao comportamento de antes, sem precisar zerar cada campo manualmente.
- **Caso de borda (PRD, "conflito de regras"):** numa geração futura de Mega-Sena, se as regras que José configurou forem impossíveis de satisfazer juntas, ele vê o aviso nomeando qual regra foi relaxada (ver Voice and Tone, "Regra relaxada") junto da confirmação de que o jogo foi gerado normalmente — nunca uma falha silenciosa nem uma tela travada sem gerar nada (FR-22).
