# Reconciliação — DESIGN.md/EXPERIENCE.md vs. PRD (prd-Loterias-2026-09-07)

Comparação das duas spines de UX (`DESIGN.md`, `EXPERIENCE.md`) contra o PRD, com foco em §0 (parágrafo do adendo), UJ-1 (passos atualizados), UJ-3, §4.3 (FR-16/FR-17), §4.4 (FR-18–FR-23), §4.5 (FR-24). Objetivo: achar conteúdo/nuance/intenção do PRD que as spines não capturaram, e contradições.

## Gaps

### 1. NFR de FR-22/FR-23 (sem espera perceptível no pior caso de conflito) não tem nenhum padrão de interação correspondente

O PRD, na seção de NFRs de §4.4 (logo após FR-23), é explícito: *"A geração de um jogo com Regras de Geração personalizadas ativas responde na mesma ordem de grandeza de tempo que a geração hoje... percebe como instantânea... o caminho de conflito do FR-22 (múltiplas tentativas) não pode introduzir uma espera perceptível mesmo no pior caso (limite de tentativas atingido)."*

`EXPERIENCE.md` não tem nenhuma menção a estado de carregamento/espera pro botão de gerar jogo — nem pra confirmar que o clique responde instantaneamente (como hoje), nem pra cobrir o caso em que `max_attempts` é atingido e a regra é relaxada. Isso é relevante porque, se a NFR eventualmente não for satisfeita na prática (o pior caso é perceptível), não há um padrão de UI (spinner, disable do botão, etc.) já definido pra esse cenário — a spine assume implicitamente "sempre instantâneo" sem reconhecer que o PRD trata isso como um risco explícito a mitigar.

**Onde caberia:** `EXPERIENCE.md` § Interaction Primitives ou § State Patterns, junto do padrão de "Conflito de regras na geração (FR-22)" já existente.

### 2. "Salvar aplica a partir da próxima geração; gerações anteriores não são recalculadas" (FR-18) não aparece em nenhuma das duas spines

É uma consequência comportamental explícita do FR-18 — potencialmente relevante pro usuário entender (ex.: José pode esperar que jogos já gerados "se atualizem" retroativamente com a nova regra, o que não acontece). Nem `EXPERIENCE.md` § State Patterns nem a UJ-3 (Key Flows) mencionam isso. Não é necessariamente algo que precise de UI nova, mas é uma nuance de intenção do PRD que a spine silenciosamente não carrega — nem como copy, nem como nota de estado.

### 3. FR-23 — "os dois mecanismos não coexistem": a Regra de Sequência adaptativa para de valer inteiramente ao personalizar, não é substituída regra-a-regra

O PRD é enfático: *"Ao editar e salvar a Regra de Geração de um Jogo, a Regra de Sequência adaptativa (baseada nos últimos 5 jogos, §3.1) deixa de se aplicar àquele Jogo para aquele usuário — os dois mecanismos não coexistem."* Isso tem uma implicação de produto não-óbvia: se José salva a tela de Regras de Geração da Mega-Sena com **todos os toggles em NÃO** (nenhuma regra ligada), o resultado não é "mesmo comportamento de hoje" — é **nenhuma restrição de sequência**, porque a regra adaptativa antiga (que hoje sempre limita a no máximo 1 par, ou zero se os últimos 5 jogos tiveram par) deixou de valer assim que ele salvou pela primeira vez.

`EXPERIENCE.md` § State Patterns descreve só o indicador "Usando regras padrão do sistema" / "Personalizado por você", sem qualquer menção a essa mudança de comportamento — um usuário que salva com tudo desligado pode não perceber que está trocando "sequência levemente controlada" por "sem controle nenhum". Isso é candidato a um aviso/copy específico (ex. ao salvar com todos os toggles em NÃO), que a spine não cobre.

### 4. Regras de linha/coluna (FR-19/FR-20) pressupõem um grid do volante que o usuário talvez não reconheça — nenhum padrão de UI trata essa explicação

O PRD marca isso como `[ASSUMPTION]`/questão em aberto de arquitetura (§8.5), então o layout exato do grid não é decisão de produto — mas a **necessidade de comunicar ao usuário o que "linha" e "coluna" significam** (já que pressupõe o volante físico da Caixa, algo que nem todo usuário vai reconhecer de cabeça) é uma questão de UX genuína, e nenhuma das duas spines a menciona. `rule-toggle-row` em ambos os documentos é descrito de forma genérica (label + toggle + valor) igual para todas as regras, sem diferenciar as regras de linha/coluna com algum apoio visual (tooltip, referência ao volante, etc.).

### 5. Contradição interna: UJ-1 passo 5 fala em "os dois filtros" mas lista três critérios

`EXPERIENCE.md` § Key Flows, UJ-1 passo 5: *"abre o Histórico, aplica os dois filtros (Jogo + período + premiado) e vê a lista já restrita"* — mas "Jogo + período + premiado" são três critérios de filtro, não dois, e FR-24 do PRD define exatamente três dimensões cumulativas (Jogo, data/período, "só premiados"). Não é uma contradição vinda do PRD em si, mas um erro de contagem introduzido na própria spine que vale a pena corrigir antes de fechar o documento — a redação sugere que o autor consolidou "Jogo" e "período" como um filtro só, ou esqueceu de contar "premiado".

## Sem contradições de fundo encontradas

Não foi encontrada nenhuma contradição de fato (spine dizendo o oposto do PRD) além do item 5 acima, que é mais um erro de redação/contagem do que uma contradição de intenção. Os mapeamentos de FR-16/17 (layout home/ícones), FR-18–21 (telas de regra por jogo, campos por família), FR-22 (mensagem de conflito) e FR-24 (filtros cumulativos, badge removível, sem paginação) estão consistentes com o texto do PRD.
