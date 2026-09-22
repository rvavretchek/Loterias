---
name: 'Revisão adversarial — Architecture Spine (adendo 2026-09-17)'
type: review
altitude: epic
target: '_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md'
method: 'construção de pares de builders hipotéticos que obedecem cada AD à letra e ainda assim divergem'
created: '2026-09-17'
---

# Revisão adversarial — Architecture Spine (adendo 2026-09-17)

## Método

Para cada AD do spine, construí dois "builders" hipotéticos (duas stories/duas leituras do mesmo texto, já que o dev é solo mas as stories são lidas isoladamente e sequencialmente, às vezes por uma sessão de agente sem memória da anterior) que seguem a letra da Rule e ainda assim produzem formatos de dado, caminhos de escrita ou comportamento de fallback incompatíveis. Cada achado é uma lacuna que o texto atual do AD não fecha — não uma crítica de estilo.

## Veredito geral

O spine é sólido no paradigma geral (nenhuma segunda forma de execução, escrita única por `GenerationRule`, sem FK nova) mas tem **duas contradições internas exploráveis dentro do próprio AD-12** (a mais grave torna o mecanismo de relax literalmente não-implementável como especificado) e **duas inconsistências reais entre a Capability Map e o resto do documento** sobre qual `rule_name` vale para qual Jogo. Nenhuma é hipotética de baixo risco — todas as quatro produzem, na prática, dois builders que passam em "cumpri a Rule ao pé da letra" e ainda assim entregam código que não interopera (ou pior, reintroduz o próprio bug que o AD dizia prevenir).

## Contagem por severidade

- **Crítico:** 3 (F1, F2, F3)
- **Alto:** 2 (F4, F5)
- **Médio:** 2 (F6, F7)
- **Baixo:** 1 (F8)

## Achados

### F1 (Crítico) — AD-12: o algoritmo de relax é inconsistente com a própria assinatura que o AD define

A Rule do AD-12 descreve o relax em duas frases que não podem ambas ser verdadeiras dada a assinatura declarada:

> "identifica **quais regras** o último candidato violou, escolhe **a de maior `updated_at` entre essas**" — implica um conjunto de violações do candidato.

> assinatura: `bet_satisfies_rules(...) -> tuple[bool, str | None]` — um único nome de regra violada, não uma lista.

Se o candidato viola 2+ regras ao mesmo tempo (cenário normal quando várias `GenerationRule` estão ativas), uma função pura que retorna `str | None` só pode reportar uma — tipicamente a primeira checada (short-circuit), não necessariamente a de maior `updated_at`. A frase "escolhe a de maior `updated_at` entre essas" é irrealizável com essa assinatura: não há "essas" (plural) disponível pra escolher entre.

**Dois builders, ambos "corretos" pela letra:**
- **Builder A** implementa `bet_satisfies_rules` exatamente como a assinatura documentada (`str | None`) e, no relax, simplesmente desliga a única regra reportada — ignorando silenciosamente a instrução de "escolher a de maior `updated_at` entre as violadas", porque nunca teve acesso ao conjunto completo.
- **Builder B** leva a instrução de relax a sério, muda a assinatura de `bet_satisfies_rules` pra `tuple[bool, list[str]]` (todas as regras violadas pelo candidato) — quebrando o contrato documentado que qualquer outro consumidor (ex. uma reutilização em FR-18 pra pré-visualizar violações, ou um teste unitário escrito contra a assinatura do Structural Seed) já assume.

Os dois códigos resultantes têm outputs de relax diferentes sempre que há violação múltipla, e um terceiro leitor do spine não tem como saber qual comportamento é o "correto" — o texto autoriza os dois.

**Fecho sugerido:** decidir explicitamente uma das duas opções no próprio AD-12 e ajustar a assinatura por escrito: (a) `bet_satisfies_rules` retorna a lista completa de regras violadas pelo candidato e o relax escolhe o `max(updated_at)` dessa lista — como a prosa já descreve —, ou (b) a função retorna só a primeira violação encontrada e a frase "escolhe a de maior `updated_at` entre essas" é removida/corrigida pra "desliga a regra reportada" (sem comparação, já que só uma é conhecida). A opção (a) é a que a redação atual sugere ter pretendido; (b) é a mais barata de implementar. De qualquer forma, o spine precisa escolher — hoje ele não escolhe.

### F2 (Crítico) — AD-13 exige upsert-never-delete no caminho de escrita, mas AD-11/FR-18 nunca declaram isso como contrato de escrita

AD-13 é explícito: "A partir do primeiro `GenerationRule` salvo... a Regra de Sequência adaptativa para de ser consultada... incluindo o caso de todos desligados, que reduz a 0 regras ativas de fato, **não ao comportamento adaptativo de volta**." Isso só é verdade se "desligar uma regra" na UI **nunca apaga a linha** — só ajusta `enabled=False`. Se a última linha de um par (user, game) fosse deletada ao invés de marcada `enabled=False`, `GenerationRule.objects.filter(user=,game=).exists()` voltaria a `False` e o AD-13 seria violado pelo próprio código que o implementa.

Nada no AD-11 (que define o model) nem na entrada de FR-18 na Capability Map (`views.regras_geracao_view` — "AD-11, AD-13") declara isso como regra do **caminho de escrita**: nenhum dos dois ADs diz "desmarcar uma regra no formulário nunca deleta a linha, só grava `enabled=False`". É uma implicação que só se percebe cruzando duas frases de AD-13 — não está escrita como invariante da view.

**Dois builders, ambos "corretos" pela letra:** um implementa `regras_geracao_view` com `get_or_create` no check e **delete** no uncheck (padrão CRUD mais natural em Django, e "sem regra = não customizado" soa como leitura razoável de "ausência é o default" do AD-13 em isolamento); outro implementa upsert-only (`enabled=False`, nunca delete). O primeiro reabre a porta pro bug que AD-13 existe pra fechar — a única regra restante sendo apagada faz o par (user, game) voltar silenciosamente ao comportamento adaptativo legado, mesmo que o usuário achasse que só tinha "desligado" uma regra, não "resetado tudo".

**Fecho sugerido:** adicionar uma frase explícita em AD-13 (ou uma nova sub-regra em AD-11): "`regras_geracao_view` nunca deleta uma linha de `GenerationRule` ao desmarcar uma regra no formulário — grava `enabled=False` na linha existente. DELETE só ocorre... [nunca, ou definir o único caminho válido, se houver]."

### F3 (Crítico) — Filtro por `enabled=True` no caminho de avaliação de constraints não tem dono definido

AD-12 diz: `generate_bet(game, user)` consulta `GenerationRule.objects.filter(user=user, game=game)` — sem `enabled=True` no filtro descrito. Só o AD-13 (em outra seção, sem link cruzado) exige que regras `enabled=False` **não constranjam** a geração ("todos desligados... reduz a 0 regras ativas de fato"). Alguém precisa filtrar por `enabled=True` antes de `bet_satisfies_rules` avaliar os candidatos — mas o AD-13's próprio checagem de "é default?" precisa usar `.exists()` **sem** esse filtro (uma linha `enabled=False` ainda conta como "customizado", por F2/AD-13). São duas queries com semânticas opostas sobre a mesma tabela, e o spine nunca atribui a responsabilidade de cada uma a uma função específica.

**Dois builders, ambos "corretos" pela letra:** um reaproveita a mesma queryset (`filter(user=,game=)`) tanto pro `.exists()` de AD-13 quanto pro `rules=` passado a `bet_satisfies_rules` — nesse caso, desligar uma regra na UI **não tem efeito nenhum** na geração (ela continua sendo avaliada como se estivesse ligada, porque `bet_satisfies_rules` como descrito não tem instrução de pular linhas `enabled=False`). Outro builder, atento ao problema, adiciona `.filter(enabled=True)` só na chamada de `generate_bet`, e isso funciona — mas nada no texto força essa segunda leitura sobre a primeira, e a primeira é uma leitura literal totalmente defensável do texto de AD-12.

**Fecho sugerido:** AD-12 precisa dizer explicitamente qual queryset alimenta `bet_satisfies_rules` (`filter(user=, game=, enabled=True)`) e por que ela é diferente da usada pelo `.exists()` de AD-13 (que não filtra por `enabled`). Vale a pena inclusive nomear as duas queries com propósitos distintos no próprio texto (ex.: "verificação de modo" vs. "conjunto de regras ativas").

### F4 (Alto) — Capability Map contradiz a seção Deferred sobre quais Jogos recebem `limit_row_count`/`limit_column_count`

A linha de FR-19 na Capability Map lista `limit_row_count`, `limit_column_count` como parte do conjunto de `rule_name` válido pra **toda a família** (Mega-Sena, +Milionária, Quina, Dupla-Sena), sem ressalva. A seção Deferred diz o oposto: "PRD §8.5 — grid... só Mega-Sena (6×10) e Lotofácil (5×5) com fonte; os outros 3 [Quina, +Milionária, Dupla-Sena] não têm contagem de colunas confirmada... **verificar antes de implementar FR-19 pra esses 3 especificamente. Mega-Sena e Lotofácil podem prosseguir.**"

AD-11 aponta a Capability Map como a fonte de verdade pro conjunto de `rule_name` por família ("ver Capability → Architecture Map"), então um builder seguindo a letra do AD-11 exporia `limit_row_count`/`limit_column_count` como choices válidas pras 4 games da família, inclusive as 3 com grid não confirmado — contradizendo a Deferred, que é lida como um bloqueio explícito de implementação pra essas 3. Dois builders (ou o mesmo builder em duas sessões, cada uma priorizando uma seção diferente do documento) produzem conjuntos de `rule_name` válidos diferentes pra Quina/+Milionária/Dupla-Sena.

**Fecho sugerido:** a linha de FR-19 na Capability Map precisa carve-out explícito: "`limit_row_count`/`limit_column_count` válidos hoje só pra Mega-Sena; os outros 3 games da família ficam sem essas duas choices até o grid ser confirmado (ver Deferred)" — ou simplesmente remover as duas choices da lista de FR-19 até a pesquisa da Deferred ser resolvida, movendo-as pra lá.

### F5 (Alto) — Notação "+" nas linhas de FR-20/FR-21 não declara a base sobre a qual soma

A linha de FR-20: "`GenerationRule` (**+** `limit_min_gap_between_sequences`, `limit_min_sequences`)" nunca diz "+ em relação a quê". Lotofácil não é membro de `GAMES_WITH_SEQUENCE_RULE` (a família da Regra de Sequência adaptativa legada é Mega-Sena/+Milionária/Quina/Dupla-Sena, per CLAUDE.md/AD-13), então não é óbvio se o "+" soma ao conjunto de FR-19 (o que incluiria `distribution_type`, `limit_row_count`, `limit_column_count` — conceitos que não fazem sentido óbvio pro modelo de "gap entre sequências" que é o desenho próprio do FR-20) ou se é só uma forma abreviada de dizer "estas 2 choices novas são as de Lotofácil, ponto".

A linha de FR-21 (Lotomania) resolve essa ambiguidade explicitamente pra si mesma ("subconjunto: `limit_sequence_count` [de FR-19], `limit_min_gap_between_sequences`, `limit_min_sequences` [de FR-20] — sem linha/coluna/distribuição") — o que mostra que o padrão de reaproveitar nomes entre famílias é intencional. Mas a própria linha de FR-20 não recebe o mesmo tratamento explícito: não diz se Lotofácil herda `distribution_type` (plausível — "homogênea vs. totalmente aleatória" é um conceito game-agnóstico) ou não.

**Dois builders:** um implementa Lotofácil com 7 choices (5 de FR-19 + 2 de FR-20), incluindo `distribution_type`, `limit_row_count`, `limit_column_count` (esse último contradizendo também o grid 5×5 já confirmado — aumentando a confusão); outro implementa Lotofácil com só as 2 choices literais listadas na própria linha de FR-20. Ambos "cumprem" a tabela; produzem telas/formulários de regras diferentes pra Lotofácil.

**Fecho sugerido:** escrever o conjunto completo de `rule_name` válido por Jogo como uma lista fechada (não incremental/"+") em cada linha da Capability Map — o mesmo tratamento que FR-21 já recebe deveria ser aplicado a FR-19 e FR-20.

### F6 (Médio) — Exclusividade mútua de `numeric_value`/`choice_value` é só prosa, sem constraint nem validação

AD-11: "nunca ambos os campos populados na mesma linha" — mas não há `CheckConstraint` no model, nem menção de `clean()`/`full_clean()` sendo chamado no caminho de save de `regras_geracao_view`, em nenhuma parte do spine (Rule, Structural Seed ou Consistency Conventions). Nada impede uma implementação de gravar os dois campos preenchidos numa linha (ex. um form que sempre inclui `numeric_value=0` como default de campo numérico mesmo pra uma regra de `choice_value`). Se isso acontecer, o comportamento de leitura em `bet_satisfies_rules` — preferir `numeric_value` ou `choice_value` quando ambos estão presentes — também não está definido em lugar nenhum.

**Fecho sugerido:** adicionar `CheckConstraint` no model garantindo XOR entre os dois campos (ou ao menos "não ambos não-nulos"), e declarar isso como parte da Rule do AD-11 em vez de só descrever o campo.

### F7 (Médio) — Nenhum artefato de código único é a fonte de verdade do enum `rule_name`; a Capability Map (markdown) é a única referência

AD-11 aponta a Capability Map ("ver Capability → Architecture Map") como onde o conjunto de `rule_name` válido por família é definido — não um dicionário/constante em `models.py` ao lado de `GAMES_CONFIG` que todas as views/forms importariam. Essa é a causa-raiz de F4 e F5: sem um único artefato Python (`RULE_NAMES_BY_GAME` ou equivalente) importado por toda story que grava/valida `GenerationRule`, nada impede duas implementações de hardcodar subconjuntos ou grafias diferentes da mesma choice compartilhada entre famílias (ex. `limit_sequence_count`, que FR-19 e FR-21 dividem) — hoje a única coisa mantendo as duas consistentes é a atenção do dev ao reler a tabela markdown antes de cada story.

**Fecho sugerido:** AD-11 deveria mandar um dict Python único (ex. `RULE_NAMES_BY_GAME` em `models.py`, ao lado de `GAMES_CONFIG`) como a única fonte de verdade — a `Field.choices` do model e toda validação de view importam dali; a Capability Map markdown passa a ser só documentação derivada, não a fonte.

### F8 (Baixo) — AD-14: bordas do filtro de período (`created_at__range`) não especificadas

`created_at__range=(inicio, fim)` não diz se os limites são inclusive/exclusive, nem como um input de date-picker (só data, sem hora, per EXPERIENCE.md) mapeia pra um `DateTimeField` timezone-aware (`USE_TZ`). Baixo risco de incompatibilidade real porque FR-24 é uma view só, implementada por uma única story — mas vale uma frase de fecho caso um filtro de data futuro (ex. filtro por `LotteryResult.captured_at`) reuse a mesma convenção sem ela estar escrita.

## Resumo por AD

| AD | Achados que o expõem |
| --- | --- |
| AD-11 | F2, F6, F7 |
| AD-12 | F1, F3 |
| AD-13 | F2, F3 |
| AD-14 | F8 |
| Capability Map / Deferred (cross-cutting) | F4, F5, F7 |
