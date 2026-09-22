# Reconciliação — DESIGN.md/EXPERIENCE.md vs. Brief (brief-layout-e-regras-personalizadas-2026-09-17.md)

Comparação das duas spines de UX contra o brief original (captura fiel do pedido do Boss, ainda não processado por `bmad-prd`/`bmad-create-epics-and-stories`). Foco: conteúdo/nuance/intenção do brief que nem o PRD nem as spines de UX carregaram adiante — em especial as "Perguntas em aberto" que o brief levanta e que uma estrutura de FR/token pode ter descartado silenciosamente.

## Gaps

### 1. Pergunta em aberto do brief sobre faixa de valor e valor inatingível não vira nenhum padrão de UI nas spines

Brief, Frente 3: *"'Valor' de cada regra — faixa válida, e o que a regra faz exatamente quando o valor não é atingível (ex. pedir 0 sequências num jogo que estruturalmente sempre tem pelo menos 1 par, dependendo da faixa numérica)?"* — isso é uma pergunta sobre **validação de entrada** (o que acontece quando o usuário digita um Valor fora da faixa, no momento em que digita/salva), distinta do FR-22 (que trata de conflito *entre regras* na hora de gerar, não de um valor individual fora da faixa aceitável).

Nem `DESIGN.md` nem `EXPERIENCE.md` têm um estado de erro/validação pro campo Valor do `rule-toggle-row` (ex.: mensagem inline se o número digitado for inválido pra aquele Jogo). A spine cobre o "conflito entre regras ao gerar" (FR-22) mas não "valor individual sem sentido pro Jogo", que é uma pergunta distinta e ainda em aberto no brief.

### 2. Pressuposto de grid (linha/coluna) — o brief já sinalizava isso como algo a confirmar "antes de implementar", e a spine trata a regra de linha/coluna como se já fosse trivial de apresentar

Brief, Frente 3: *"'Linha'/'coluna' pressupõe um layout em grade pro volante de cada jogo (como o volante físico da Caixa) — precisa confirmar o grid exato por jogo (quantas colunas, numeração) antes de implementar as regras de linha/coluna."* O brief já antecipa que isso é um bloqueio de implementação, não só um detalhe cosmético. As spines (`rule-toggle-row` em ambos os documentos) tratam a regra de linha/coluna com o mesmo padrão genérico das demais regras (label + toggle + valor), sem reconhecer que essa regra em particular depende de uma informação ainda não levantada — nem um placeholder, nem uma nota indicando que a apresentação dessa regra específica pode mudar quando o grid for confirmado.

### 3. Preocupação do brief sobre volume da lista de histórico é mais ampla do que "bolinhas por jogo" — cobre o total de jogos guardados de um usuário ativo, não só números por jogo individual

Brief, Frente 4: *"o layout atual de 'bolinhas em linha' ... pode não escalar bem pra 20 números por jogo × **todos os jogos guardados de um usuário ativo**."* Ou seja, a preocupação original tem duas dimensões: (a) muitos números dentro de um jogo (Lotomania/Lotofácil/Dupla-Sena) e (b) muitos jogos na lista de histórico de um usuário que já gerou centenas de apostas ao longo do tempo.

As spines resolvem bem a dimensão (a) — `flex-wrap` nas bolinhas, sub-linhas pra Dupla-Sena. A dimensão (b) fica sem resposta: `EXPERIENCE.md` não tem nenhum estado ou nota pra "usuário com centenas de jogos no histórico, mesmo com filtros aplicados" — a mitigação implícita é só "os filtros reduzem o volume exibido", sem paginação (isso é consistente com o PRD, que marca paginação como fora do MVP em §6.2). Mas isso é uma decisão que existe no PRD e não nas spines — quem lê só `DESIGN.md`/`EXPERIENCE.md` não sabe que a ausência de paginação foi uma decisão deliberada (vs. um esquecimento). Vale ao menos uma nota de estado reconhecendo o limite (ex.: "sem paginação nesta rodada, filtros são a única forma de reduzir a lista").

### 4. Concursos especiais/comemorativos (comportamento hoje existente, mas parte do UJ-1 atualizado) — não fica claro se a edição do campo Concurso continua possível na nova área "jogo selecionado" do topo

O PRD (UJ-1, passo 1) preserva explicitamente a possibilidade de o usuário sobrescrever a sugestão de concurso pra cobrir concursos especiais (ex. "Lotomania da Independência"). Isso não é um pedido novo do brief nem do adendo — é comportamento já existente (FR-2) que a home redesenhada (FR-16/FR-17) precisa continuar suportando. `EXPERIENCE.md` § Key Flows UJ-1 passo 2 só diz que "o campo de concurso já vem com a sugestão preenchida", sem confirmar que o campo continua editável na nova área "jogo selecionado" do topo. Provavelmente é uma omissão por ser óbvio (o campo já existe e não está sendo removido), mas como o brief e o PRD tratam isso como parte do fluxo essencial de UJ-1, vale confirmar explicitamente que a reorganização de FR-16 não acidentalmente torna esse campo somente-leitura ou o esconde.

### 5. "Decisão de layout, não de produto" (brief) sobre o comportamento da sidebar — resolvido, mas vale registrar que a spine decidiu por uma opção específica sem marcar `[ASSUMPTION]`

Brief, Frente 2, pergunta em aberto: *"'Resumo pode ficar de lado' — sidebar fixa, colapsável, ou só menor mas ainda no fluxo vertical?"* — pergunta explicitamente deixada em aberto pro planejamento. `DESIGN.md`/`EXPERIENCE.md` resolvem isso (sidebar de largura fixa, não colapsável, empilha abaixo de 1280px) mas não marcam a decisão como `[ASSUMPTION]` do jeito que outras decisões similares no mesmo documento são marcadas (ex. "Restaurar padrão" tem `[ASSUMPTION]` explícito). Não é um gap de conteúdo, mas uma inconsistência de tratamento — uma pergunta em aberto do brief foi respondida silenciosamente como fato consumado, enquanto outra decisão de mesmo peso foi sinalizada como suposição.

## Sem contradições encontradas

Nenhuma contradição direta entre as spines e o brief. Os itens acima são gaps de nuance/pergunta-em-aberto não carregada, não casos em que a spine afirma o oposto do brief.
