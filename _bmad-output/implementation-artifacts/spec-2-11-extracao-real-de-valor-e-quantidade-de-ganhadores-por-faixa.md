---
title: 'Extração real de valor e quantidade de ganhadores por faixa na captura de resultado'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '82773fe1947a88cd9ba16b21701270cc40704dfe'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O texto original desta story em `epics.md` foi escrito quando `fetch_cef_result` ainda fazia scraping de HTML da CEF sem extrair valor de prêmio nem quantidade de ganhadores reais (usava `R$ 0,00` hardcoded). A Story 2.1 (2026-09-08), ao trocar o scraping pela API oficial da Caixa, **já implementou a maior parte do que esta story pede** como efeito colateral da adoção da API: `_extract_prize_tiers` já extrai `valorPremio` e `numeroDeGanhadores` reais por faixa (`descricaoFaixa`), pra todas as faixas premiadas de cada Jogo (não só a de acerto máximo), e grava as duas informações em `LotteryResult.prizes`. A Story 2.8 (AD-10) já implementou o fallback pro `PrizeTier` quando o concurso específico não tem a faixa, e já faz `calculate_bet_prize` priorizar o valor do concurso específico sobre o `PrizeTier` genérico.

**Approach:** Esta story fecha a única lacuna real que sobrou entre o que `epics.md` pede e o que já existe: o AC de "uma faixa premiada nunca é gravada com `ganhadores` zerado ou ausente -- inconsistência de dado é tratada como falha de extração, não como zero ganhadores" **não estava implementado** -- `_extract_prize_tiers` fazia `tier.get('numeroDeGanhadores') or 0`, que colapsa "campo ausente" (falha de extração) e "campo presente e igual a 0" (dado real, ex. concurso acumulado sem valor) no mesmo resultado. Corrigido: se uma faixa tem `valorPremio` positivo (é uma faixa efetivamente premiada) mas `numeroDeGanhadores` está ausente (`None`, não simplesmente `0`), `winners` é gravado como `None` (falha isolada só daquele campo) -- **nunca descartando a faixa inteira**, decisão revisada durante a revisão em 3 camadas (ver Fronteiras e Notas de Implementação: descartar a faixa jogaria fora justamente o `value`, que é o único campo que `calculate_bet_prize` de fato usa pra decidir o prêmio).

Os demais Critérios de Aceite (extração real de valor+ganhadores por faixa, fallback pro `PrizeTier` quando ausente, Notificação de Acerto usando o valor real do concurso) já estão implementados desde as Stories 2.1/2.8 -- esta story adiciona testes diretos confirmando cada um deles nominalmente (não só como efeito colateral de outros testes), fechando a rastreabilidade entre `epics.md` e o código.

**Nota sobre um comentário de código incorreto (achado ao investigar esta story):** o docstring de `_extract_prize_tiers` (escrito durante a Story 2.1) afirmava que "extração completa por sorteio [da Dupla-Sena, que tem 2 sorteios por concurso] é a Story 2.11" -- mas o `epics.md` real de Story 2.11 nunca tratou disso; é sobre valor/ganhadores por faixa (resolvido acima). Essa era uma suposição de uma sessão anterior sobre o que uma story futura ainda não escrita cobriria, que não se confirmou. Corrigido o docstring pra não fazer essa associação incorreta -- o caso da Dupla-Sena continua registrado em `deferred-work.md` sem número de story prometido (já estava correto lá), aguardando decisão de produto.

## Fronteiras e Restrições

**Sempre:**
- Uma faixa com `valorPremio` positivo e `numeroDeGanhadores` ausente (`None`) tem `winners` gravado como `None` (falha de extração isolada a esse campo) -- a faixa em si (com seu `value` correto) permanece no dict de `prizes`, nunca é descartada por inteiro, e nunca recebe `winners=0` fabricado.
- Uma faixa com `valorPremio` igual a `0`/ausente e `numeroDeGanhadores` igual a `0`/ausente continua sendo um dado legítimo (concurso acumulado, sem prêmio nem ganhador naquela faixa) -- não é tratada como falha.
- Um `valorPremio` negativo ou de tipo inválido (não numérico) descarta a faixa inteira -- dado corrompido, sem uso possível.
- A dedup de faixas repetidas (`hits_key in result`) sempre reserva a chave na primeira ocorrência que casar o regex, mesmo quando `winners` vira `None` -- nunca deixa uma ocorrência posterior (ex. 2º sorteio da Dupla-Sena) substituir silenciosamente a primeira.
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não reabrir o caso da Dupla-Sena (2 sorteios por concurso) nesta story -- continua fora de escopo, registrado em `deferred-work.md` sem story dedicada ainda.
- Não mudar `calculate_bet_prize`/`PrizeTier` (Story 2.8) -- o fallback já existente já satisfaz o AC de "resultado salvo sem prêmio populado cai pro PrizeTier".

</frozen-after-approval>

## Code Map

- `apps/loterias_core/utils.py::_extract_prize_tiers` -- `raw_value = float(tier.get('valorPremio') or 0)` (dentro de `try/except (TypeError, ValueError): continue`, descarta faixa com valor de tipo inválido); se `raw_value < 0`, descarta a faixa; senão `winners = None if (raw_value and raw_winners is None) else (raw_winners or 0)` -- a faixa É gravada com `winners=None` no caso de falha, nunca descartada por inteiro (ajuste da revisão, ver Notas). Corrige também o docstring (remove a associação incorreta com "Story 2.11" pro caso da Dupla-Sena, documenta a garantia de dedup).
- `apps/loterias_core/tests.py` -- novos testes em `FetchCefResultTests`: (1) faixa com `valorPremio` positivo e `numeroDeGanhadores` ausente mantém a faixa com `winners=None` (não descarta, não fabrica `0`); (2) faixa com `valorPremio` zerado e `numeroDeGanhadores` zerado/ausente continua sendo extraída normalmente com `winners=0`; (3) `valorPremio` negativo ou de tipo inválido descarta a faixa; (4) dedup da Dupla-Sena: 1º sorteio com `winners` ausente (fica `None`) não é substituído pelo 2º sorteio com dado completo -- confirma que a chave é reservada mesmo no caso de falha; (5) extração real de valor e quantidade de ganhadores por faixa, múltiplas faixas do mesmo Jogo (teste nominal, referencia explicitamente a Story 2.11, ainda que o mecanismo já existisse desde a Story 2.1); (6) resultado com `listaRateioPremio` vazio (falha de extração completa, independente do mecanismo novo) ainda é salvo com números sorteados e `calculate_bet_prize` cai pro `PrizeTier`; (7) teste de traceability confirmando que o valor do concurso específico tem prioridade sobre o `PrizeTier` genérico (mecanismo já existente desde a Story 2.8, nomeado explicitamente aqui pra fechar o AC desta story).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/utils.py::_extract_prize_tiers` -- validação de consistência ganhadores/valor + correção do docstring
- [x] `apps/loterias_core/tests.py` -- 9 casos novos (Code Map original + reforços da revisão)

**Critérios de Aceite:**
- Dado que a página oficial da Caixa pro Jogo/Concurso publica valor e quantidade de ganhadores por faixa de acerto, quando `fetch_cef_result` captura o resultado, então o sistema extrai, pra cada faixa premiada daquele Jogo, tanto o valor do prêmio quanto a quantidade de ganhadores daquela faixa naquele concurso específico, e grava as duas informações em `LotteryResult.prizes`
- E se a extração falhar ou a página não trouxer esses dados, o resultado ainda é salvo sem prêmio populado, e `calculate_bet_prize` cai pro `PrizeTier` vigente como fonte
- E uma faixa marcada como premiada nunca é gravada com `ganhadores` zerado ou ausente -- inconsistência de dado é tratada como falha de extração daquela faixa
- E uma Notificação de Acerto criada usa o valor real daquele concurso quando disponível -- mais preciso que o `PrizeTier` genérico nos casos em que os dois divergem

## Notas de Implementação

A implementação inicial fazia `continue` (descartava a faixa inteira do dict de `prizes`) quando `valorPremio` era positivo e `numeroDeGanhadores` estava ausente. A revisão em 3 camadas encontrou, de forma convergente entre Blind Hunter e Edge Case Hunter, um problema sério com essa abordagem: `calculate_bet_prize` nunca lê o campo `winners` pra decidir se a aposta ganhou ou qual o valor do prêmio -- só usa `value`. Descartar a faixa inteira jogava fora justamente o `value`, que estava correto, por causa de um problema isolado no `winners`. Consequência prática: uma aposta genuinamente premiada podia deixar de mostrar o valor real do concurso (caindo pro `PrizeTier` genérico do mês, ou até sendo negada se não existisse `PrizeTier` pra aquela faixa) -- o oposto do que a Story 2.11 quer (mostrar o valor real e preciso do concurso específico).

Corrigido: a faixa nunca é mais descartada por causa de `winners` ausente -- `winners` passa a ser gravado como `None` (falha isolada e explícita daquele campo, distinguível de um `0` legítimo), enquanto `value` é sempre preservado quando veio numérico e não-negativo da API. Esse ajuste também resolveu, como efeito colateral, uma segunda regressão que o Blind Hunter e o Edge Case Hunter encontraram de forma independente: a dedup de faixas repetidas da Dupla-Sena (`if hits_key in result: continue`) dependia da faixa ser sempre registrada em `result` na primeira ocorrência processada -- com o `continue` antigo, uma falha de `winners` no 1º sorteio fazia a chave nunca ser reservada, e o 2º sorteio (2ª ocorrência da mesma faixa) acabava silenciosamente tomando o lugar do 1º, quebrando a garantia "fica com a primeira ocorrência" já estabelecida desde a Story 2.1. Com o novo design (a faixa é sempre registrada, só o campo `winners` muda), essa garantia volta a valer automaticamente.

Também adicionada uma validação de sanidade pro próprio `valorPremio`: um valor negativo ou de tipo não numérico (dado corrompido da API) descarta a faixa inteira -- diferente do caso de `winners` ausente, aqui o próprio `value` não é confiável, então não há nada a preservar.

## Log de Triagem da Revisão

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) rodada em paralelo sobre o diff da implementação inicial (~6,4 kB, N=3 pro Blind Hunter). Achados e disposição:

**Corrigidos:**
- (Blind Hunter, crítico) Descartar a faixa inteira jogava fora um `value` correto, podendo negar/subestimar um prêmio real -- corrigido gravando `winners=None` em vez de descartar a faixa.
- (Blind Hunter + Edge Case Hunter, convergente) A dedup de faixas repetidas da Dupla-Sena quebrava silenciosamente quando a 1ª ocorrência falhava a checagem de `winners` -- resolvido junto com o ajuste acima (a chave volta a ser sempre reservada).
- (Blind Hunter) Nenhuma validação contra `valorPremio` negativo/tipo inválido -- adicionada, com teste dedicado.
- (Edge Case Hunter) O comportamento "fica com a primeira ocorrência" que a spec/docstring afirmavam preservado na verdade tinha sido quebrado pela implementação inicial -- corrigido junto com os itens acima; docstring atualizado pra documentar a garantia explicitamente.
- (Verification Gap Reviewer) Faltava teste nominal pro AC principal (extração de valor+ganhadores de múltiplas faixas) -- adicionado `test_extracts_real_value_and_winners_for_multiple_tiers_of_the_same_game`, referenciando a Story 2.11 explicitamente (mesmo o mecanismo já existindo desde a Story 2.1).
- (Verification Gap Reviewer) O teste de "prizes vazio" usava o próprio mecanismo novo (winners ausente) como precondição, em vez de um cenário genuinamente independente -- corrigido pra usar `listaRateioPremio: []`.
- (Verification Gap Reviewer) O teste de "notificação usa valor real" não exercitava nem `HitNotification` nem o pipeline real -- renomeado (`test_prize_value_traceability_...`) pra não superclaimar, com docstring honesto sobre o que de fato confirma (rastreabilidade do AC, não um caminho de código novo).
- (Verification Gap Reviewer) Ambiguidade não testada: `numeroDeGanhadores` explicitamente `0` com valor positivo -- adicionado teste documentando que esse caso (diferente de `None`) está fora do escopo desta story, decisão já implícita na seção Fronteiras congelada.

**Aceitos como corretos (falsos positivos ou já cobertos):**
- Edge Case Hunter confirmou que `prizes == {}` completo não recebe tratamento especial em nenhum outro ponto do código (já cai no fallback pro `PrizeTier` corretamente), e que não há interação com a purga da Story 2.10.

**Deferidos (registrados em `deferred-work.md` ou já cobertos por itens existentes, não bloqueiam esta story):**
- Edge Case Hunter apontou um cenário composto (falha de extração *persistente*, não isolada, numa faixa específica, combinada com a poda de 3 meses do `PrizeTier`) que poderia eventualmente negar um prêmio genuíno -- o redesenho desta story (preservar `value` sempre que a falha for só de `winners`) já resolve a causa raiz na prática, já que a faixa continua presente em `prizes` como fonte de verdade do concurso.
- O caso da Dupla-Sena ter 2 sorteios com faixas de fato diferentes (não uma repetição de dado, mas 2 sorteios genuinamente distintos) continua fora de escopo, já registrado em `deferred-work.md` desde a Story 2.1.

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- nenhuma migration pendente (nenhuma mudança de model nesta story).
- `python manage.py check` -- sem erro novo (só o warning pré-existente de `STATICFILES_DIRS`).
- `python manage.py test apps.loterias_core.tests.FetchCefResultTests` -- **21 testes, 100% passando**.
- `python manage.py test apps.loterias_core` -- **220 testes, 100% passando**.
- `python manage.py test` -- **240 testes, 100% passando** (suíte completa do projeto, nenhuma regressão).
