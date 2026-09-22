---
title: Verificação de fatos externos — Architecture Spine (adendo 2026-09-17)
type: review
target: ARCHITECTURE-SPINE.md (mesmo diretório)
created: '2026-09-17'
---

# Verificação de fatos externos/técnicos — Architecture Spine (adendo 2026-09-17)

Escopo: checar contra a web, o código real do repositório e o `.memlog.md` da sessão toda
decisão comprometida no spine que dependa de um fato de biblioteca/framework/versão ou de uma
afirmação factual externa, em vez de aceitar como dada.

## Veredito geral

O spine está majoritariamente correto e bem verificado. A alegação "nenhuma dependência nova"
se confirma: AD-11 a AD-14 usam só Django ORM (inclusive um padrão já existente,
`unique_together`) e Python padrão — nada em `GenerationRule`, `bet_satisfies_rules` ou no loop
de retry/relax exige biblioteca nova. A representação da pesquisa web sobre grids do volante
(Mega-Sena 6×10, Lotofácil 5×5 confirmados; Quina/+Milionária/Dupla-Sena genuinamente em aberto)
está correta e consistente entre spine e memlog, com fontes citadas.

Foram encontrados **2 problemas** que deveriam ter sido checados contra o código real e não
foram — um deles (JSONField) é uma alegação factual comprovadamente falsa usada para justificar
uma decisão de arquitetura.

## Contagem por severidade

- Crítico: 0
- Alto: 0
- Médio: 1 (AD-11 — alegação factual falsa sobre precedente de `JSONField`)
- Baixo: 1 (AD-12 — precedente de `max_attempts` citado é o "errado" dentro da própria função)
- Confirmado sem problema: 4 (ver seção "Verificado e correto")

## Achados

### [Médio] AD-11: "JSONField sem precedente no projeto" é factualmente falso

**Onde:** `ARCHITECTURE-SPINE.md` linha 50 (AD-11, seção "Prevents") e a entrada espelhada em
`.memlog.md` ("JSONField (primeiro do projeto, sem precedente, admin mostra blob cru)").

**O que diz:** a rejeição de `JSONField` como forma de armazenar `GenerationRule` é justificada
citando "um `JSONField` sem precedente no projeto (nenhum model hoje usa...)".

**O que o código mostra:** `apps/loterias_core/models.py`, no mesmo arquivo onde `GenerationRule`
seria declarado, já usa `models.JSONField` em 6 campos diferentes:
- `GeneratedBet.numbers` (linha 49), `GeneratedBet.clovers` (linha 50)
- `LotteryResult.numbers` (linha 94), `LotteryResult.clovers` (linha 95),
  `LotteryResult.prizes` (linha 96), `LotteryResult.numbers_second_draw` (linha 97),
  `LotteryResult.prizes_second_draw` (linha 100)
- `GameStatistics.most_frequent_numbers` (linha 128)

Ou seja, `JSONField` não só tem precedente — é um padrão estabelecido e usado extensivamente
para os próprios models de domínio deste app.

A parte "admin mostra só um blob cru" da justificativa **é verdadeira** (checado
`apps/loterias_core/admin.py` — nenhum widget customizado pra campo JSON, é o textarea padrão
do Django), e "sem validação de schema no banco" também é verdade genérica de `JSONField`. Então
a decisão em si (campos relacionais `numeric_value`/`choice_value` em vez de um blob JSON) pode
muito bem continuar sendo a correta — há razões independentes válidas (granularidade de 1 linha
por regra, sem precisar de uma segunda tabela ou de parsing pra saber "qual regra mudou por
último"). O problema é que o argumento usado é uma alegação verificável, tratada como fato, que
uma checagem rápida no próprio `models.py` teria refutado — e ela aparece tanto no spine quanto
no memlog, sugerindo que não foi checada em nenhum dos dois pontos da sessão.

**Recomendação:** corrigir a frase em AD-11 (e no memlog, se for reaberto) para não afirmar
"sem precedente" — a justificativa real e defensável é granularidade/auditoria por linha e
evitar duplicar a primeira abstração JSON-schema-less pra configuração de regra por regra,
não ineditismo do tipo de campo.

### [Baixo] AD-12: precedente de `max_attempts=1000` ignora o precedente já existente na própria `generate_bet()`

**Onde:** `ARCHITECTURE-SPINE.md` linha 57 (AD-12) e `.memlog.md` ("mesmo padrao max_attempts ja
usado em regenerate_bet_view").

**O que diz:** o novo loop de retry/relax dentro de `generate_bet()` deve rodar
"`max_attempts=1000`", justificado como "mesmo padrão `max_attempts` já usado em
`regenerate_bet_view`" (`apps/loterias_core/views.py`, linhas 100 e 330, ambas de fato
`max_attempts = 1000`).

**O que o código mostra:** a citação de `regenerate_bet_view` está correta — essa função usa
1000 mesmo. Só que a função que o AD-12 está de fato estendendo, `generate_bet()` em
`apps/loterias_core/utils.py`, **já tem seu próprio precedente diferente**: linha 72,
`max_attempts = 10000`. Esse valor não foi checado/mencionado em nenhum dos dois documentos —
a comparação foi feita só contra `regenerate_bet_view` (uma view diferente, com outro
propósito: evitar duplicata, não satisfazer regras).

Rastreei a origem: o próprio addendum do PRD (`prd.md`'s companion
`_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/addendum.md`, linha 9) já sugere
"`regenerate_bet_view` ... já implementa um loop de tentativas (`max_attempts = 1000`)... FR-22
pode reaproveitar o mesmo padrão" — então o spine herdou a citação do PRD sem comparar contra o
comportamento atual da função que está de fato sendo modificada.

**Por que importa:** não é necessariamente errado escolher 1000 pro novo caminho
(regras-personalizadas); mas a frase "mesmo padrão já usado" implica consistência com o
comportamento atual de `generate_bet()`, que é falsa — o caminho novo (quando há
`GenerationRule`) vai tolerar 10× menos tentativas que o caminho default (quando não há) da
mesma função, antes de desistir/relaxar. Isso é uma escolha que vale a pena tornar explícita e
deliberada (ex.: "novo `max_attempts=1000` reaproveita `regenerate_bet_view`, mesmo sendo 10×
menor que o `max_attempts=10000` já usado no caminho default de `generate_bet()` — aceitável
porque X") em vez de ficar implícito como se fosse só reaproveitar um padrão já usado ali mesmo.

**Recomendação:** ajustar a redação de AD-12 pra reconhecer explicitamente a diferença de escala
com o `max_attempts=10000` já existente em `generate_bet()`, e confirmar que 1000 é
intencional (não um número herdado por engano de uma função vizinha).

## Verificado e correto (sem achado)

- **Stack/versões:** `Django==5.0.6`, `django-allauth==0.63.3` em `requirements.txt` batem com
  o que o spine e o `CLAUDE.md` afirmam. Python 3.11 e SQLite bundled — sem contradição, sem
  necessidade de dependência nova pra nenhum dos AD-11 a AD-14.
- **Grids do volante (pesquisa web desta sessão):** Mega-Sena 6×10 e Lotofácil 5×5 aparecem
  corretamente marcados como confirmados-com-fonte tanto no spine (seção Deferred) quanto no
  memlog (com URLs: megaloterias.com.br e lottocap.com.br). Quina, +Milionária e Dupla-Sena
  aparecem corretamente marcados como não confirmados/em aberto nos dois documentos — nenhum
  dos três está sendo silenciosamente assumido como igual aos outros dois jogos confirmados.
- **`unique_together`:** o spine usa `unique_together = ('user', 'game', 'rule_name')` pra
  `GenerationRule` — não é um padrão novo/arriscado; `LotteryResult.Meta` já usa
  `unique_together = ['game', 'contest']` no código atual (`models.py` linha 109).
- **Citações de seção do PRD (§8.5, §8.6, §8.9):** resolvidas contra `prd.md` — correspondem
  exatamente aos itens 5, 6 e 9 da seção "8. Questões em Aberto" (o `addendum.md` em si não tem
  numeração `§8.x` própria; o conteúdo do adendo foi integrado à numeração existente do
  `prd.md`, que é onde o spine efetivamente aponta). Citação de `epic-2-retro-2026-09-16.md`
  (retro do Epic 2) e dos arquivos `DESIGN.md`/`EXPERIENCE.md` em
  `ux-designs/ux-Loterias-2026-09-17/` também conferidas — todos existem no repositório.
