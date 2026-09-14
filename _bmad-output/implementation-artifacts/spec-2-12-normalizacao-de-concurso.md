---
title: 'Normalização de Concurso'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'd521d7b'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `GeneratedBet.contest` é texto livre, só passa por `.strip()` em `create_bet_view`,
`save_manual_bet_view` e `api_create_bet_view`. Duas grafias do mesmo concurso real (ex. `'2500'` e
`'02500'`) geram pares distintos em `fetch_daily_results`, furam o bloqueio de concurso já sorteado
(`_block_if_contest_already_drawn`, Story 2.2) e furam a proteção contra apagar um resultado premiado
na purga manual (Story 2.10, que casa `game`+`contest` por igualdade textual exata via `OuterRef`).

**Approach:** Adicionar `normalize_contest(raw: str) -> str` em `utils.py`: valida que o valor
stripado é só dígitos (`str.isdigit()`) e devolve `str(int(raw))` (remove zeros à esquerda); levanta
`ValueError` pra qualquer valor não numérico ou vazio. Chamar essa função nos 3 pontos de entrada
(`create_bet_view`, `save_manual_bet_view`, `api_create_bet_view`) logo após extrair `contest` do
POST/JSON, antes de qualquer uso — assim `_block_if_contest_already_drawn`, a checagem de duplicata
(`GeneratedBet.objects.filter(...contest=contest)`), `fetch_cef_result` e o `GeneratedBet.objects.create`
já recebem sempre o valor normalizado, sem tocar essas funções. `suggest_next_contest` já devolve
`str(max(...) + 1)` (sem zero à esquerda) — nenhuma mudança necessária lá. A proteção da purga manual
(Story 2.10) não muda: como passa a comparar valores já normalizados dos dois lados (`GeneratedBet` e
`LotteryResult`, ambos escritos só através dos pontos de entrada corrigidos), o problema de duas
grafias distintas deixa de existir na prática. Dado atual do lab já confirmado limpo (nenhum concurso
com zero à esquerda armazenado hoje) — sem necessidade de migration de backfill.

**Decisão do Boss (2026-09-14):** Opção B — a AC de `epics.md` vale ao pé da letra, todo concurso
não numérico é sempre rejeitado. Correção de premissa: mesmo um concurso especial/comemorativo (ex.
Mega da Virada) tem um número de concurso ordinário e numérico na CEF — não existe concurso
genuinamente alfanumérico na realidade. O suporte anterior a `'ESPECIAL-2026'` como concurso válido
modelava uma premissa incorreta sobre o domínio, não um requisito de produto real; os 2 testes que o
cobriam foram corrigidos pra usar um concurso numérico comum (ex. `'9999'`) sem `LotteryResult` ainda,
preservando a intenção real do teste (aceitar concurso sem resultado ainda) sem a premissa errada.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/utils.py::normalize_contest` -- valida `raw.strip().isdigit()`, devolve
  `str(int(raw))`; levanta `ValueError` pra qualquer valor nao totalmente numerico ou vazio.
- `apps/loterias_core/views.py` -- `normalize_contest` importada e chamada em `create_bet_view`
  (apos a checagem de jogo valido), `save_manual_bet_view` (idem) e `api_create_bet_view` (apos a
  checagem de dados incompletos), sempre antes de qualquer uso downstream (bloqueio de concurso ja
  sorteado, checagem de duplicata, `fetch_cef_result`, `GeneratedBet.objects.create`).
- `apps/loterias_core/tests.py` -- `NormalizeContestTests` (6 casos da funcao pura); renomeados
  `test_allows_special_contest_without_lottery_result` -> `test_allows_numeric_contest_without_lottery_result`
  em `CreateBetViewTests`/`SaveManualBetViewTests` (usa `'9999'` em vez de `'ESPECIAL-2026'`); novos
  `test_rejects_non_numeric_contest` (as 2 mesmas classes + `test_api_create_bet_rejects_non_numeric_contest`),
  `test_saves_contest_normalized_without_leading_zeros`,
  `test_blocks_leading_zero_spelling_of_already_drawn_contest`,
  `test_leading_zero_spelling_counts_as_duplicate_bet` (`CreateBetViewTests`).

## Tasks & Acceptance

**Execução:**
- [x] `apps/loterias_core/utils.py` -- adicionar `normalize_contest`
- [x] `apps/loterias_core/views.py` -- aplicar `normalize_contest` nos 3 pontos de entrada
- [x] `apps/loterias_core/tests.py` -- cobrir normalização, rejeição de não numérico e as 2
  reescritas de teste que dependiam da premissa incorreta de concurso alfanumérico

**Critérios de Aceite:**
- Dado um usuário digita um Concurso em `create_bet_view`, `save_manual_bet_view` ou via
  `api_create_bet_view`, quando o valor é salvo em `GeneratedBet.contest`, então o valor é
  normalizado (convertido pra inteiro e re-serializado sem zeros à esquerda) antes de gravar --
  verificado por `test_saves_contest_normalized_without_leading_zeros` nas 2 views que persistem.
- E a mesma normalização se aplica ao bloqueio de concurso já sorteado (Story 2.2) -- verificado por
  `test_blocks_leading_zero_spelling_of_already_drawn_contest` nas 2 views.
- E `suggest_next_contest` continua devolvendo valores no mesmo formato normalizado -- já garantido
  antes desta story (`str(max(...) + 1)`), sem alteração.
- E concursos com valor não numérico continuam rejeitados com mensagem clara, nunca gravados --
  verificado por `test_rejects_non_numeric_contest` nas 3 views.

## Implementation Notes

**Parada e retomada (2026-09-14):** a implementação inicial (`normalize_contest` rejeitando todo
valor não numérico) quebrou 2 testes existentes que cobriam `'ESPECIAL-2026'` como concurso válido —
comportamento documentado como requisito no `epic-2-context.md`. Virou `## Open Questions` em vez de
decidir sozinho (regra do workflow: parar quando o pedido, como escrito, quebraria algo que o usuário
notaria). O Boss decidiu manter a AC ao pé da letra (rejeitar sempre) e corrigiu a premissa: mesmo um
concurso especial/comemorativo tem um número ordinário e numérico na CEF, então o teste antigo
modelava uma suposição errada sobre o domínio. Os 2 testes foram reescritos (trocando o concurso
alfanumérico por um numérico comum) preservando sua intenção real (aceitar concurso sem
`LotteryResult` ainda), e novos testes de rejeição foram adicionados nas 3 views.

Nenhuma migration de backfill necessária -- dado atual do lab (verificado via SSH antes desta story)
não tem nenhum concurso com zero à esquerda armazenado.

Purga manual (Story 2.10) não precisou de mudança de código: a proteção já compara `GeneratedBet` e
`LotteryResult` por igualdade, e ambos passam a ser sempre normalizados nos pontos de escrita.

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **295 testes, OK**
  (era 281 antes desta story; 14 novos/reescritos), rodado no `.venv` pinado (Python 3.11/Django
  5.0.6 -- o interpretador default da máquina é 3.14/Django 6.0.5 e quebra `NotificationPreference`,
  aviso já existente no CLAUDE.md). Reexecutado depois dos patches da revisão -- mesmo resultado.

## Review Triage Log

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff desde
`d521d7b` (~12kB, N=4 pro Blind Hunter).

**Patch (corrigidos nesta revisão):**
- (Blind Hunter) `normalize_contest` usava `str.isdigit()`, que aceita digitos Unicode nao-decimais
  (ex. superscript) que `int()` nao parseia -- trocado pra `str.isdecimal()`.
- (Blind Hunter) Docstring de `suggest_next_contest` ainda descrevia concurso nao numerico como
  "especiais/comemorativos", contradizendo a correcao de premissa desta story -- reescrito pra deixar
  claro que e so parse defensivo contra dado legado, nao um caso de uso valido.
- (Blind Hunter) `medium` -- mensagem `'Numero de concurso invalido.'` generica nao ajuda o usuario a
  saber o que foi rejeitado, inconsistente com o estilo ja usado em `_block_if_contest_already_drawn`
  (que interpola `{contest}`) -- interpolado o valor rejeitado nas 3 mensagens (2 `messages.error` +
  1 `JsonResponse`), testes atualizados.
- (Blind Hunter) `f'Ja existe um jogo de Mega-sena para o concurso 2500.'` em
  `test_leading_zero_spelling_counts_as_duplicate_bet` -- f-string sem interpolacao (flake8 F541) --
  removido o prefixo `f` morto.

**Deferidos (`deferred-work.md`):**
- (Blind Hunter + Edge Case Hunter, convergente) `contest` continua editavel como texto livre no
  Django admin (`GeneratedBetAdmin`/`LotteryResultAdmin`), nunca passando por `normalize_contest` --
  `medium`, verificado lendo `admin.py` (`contest` ausente de `readonly_fields`). Pre-existente, fora
  do Given/When/Then literal da AC, mas contradiz o objetivo da story. Corrigir exige logica de
  `ModelAdmin` fora do escopo de patch trivial.
- (Blind Hunter + Edge Case Hunter, convergente) `normalize_contest('0')`/`'00'` aceitos, sem
  concurso real numerado 0 -- `low`/pre-existente na mesma categoria da lacuna ja deferida na Story
  2.9 (sem validacao de faixa/plausibilidade). AC desta story pede so formato, nao faixa.

**Rejeitados:**
- (Edge Case Hunter) `normalize_contest` recebendo `raw` nao-string (`None`) causaria `AttributeError`
  -- `false`: todo call site em `views.py` ja chama `.strip()` antes (linha pre-existente, nao parte
  deste diff), entao `normalize_contest` nunca recebe nao-string na pratica atual.
- (Blind Hunter) `api_create_bet_view` sem validacao de `jogo invalido` -- `false` como achado *desta*
  story: e exatamente o escopo ja planejado da Story 2.13 (proxima na fila), nao uma lacuna introduzida
  aqui.
- (Blind Hunter) Falta de migration de backfill pra dado legado -- rejeitado como achado: a
  `<frozen-after-approval>` ja documenta a decisao (dado do lab verificado limpo via SSH antes da
  story), exclusao explicita de intent, nao uma omissao.
- (Blind Hunter) Falta teste com separador de milhar/espaco embutido (ex. `'2.500'`) -- `low`,
  rejeitado: comportamento ja uniforme (qualquer caractere nao-decimal e rejeitado pela mesma checagem
  generica ja testada), Verification Gap Reviewer confirmou cobertura suficiente sem essa variante
  especifica.
- (Verification Gap Reviewer) Nenhuma lacuna de verificacao encontrada.
