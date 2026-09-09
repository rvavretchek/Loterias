---
title: 'Rotina mensal de valores de premiação por faixa (PrizeTier)'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '1af9a3e2c6895efbc2c01831a3eca007b5516ba1'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `calculate_bet_prize` hoje decide "essa quantidade de acertos é premiada?" com uma lista fixa de `if/elif` por Jogo em `utils.py` (ex. `hits >= 4` pra Mega-Sena) — qualquer mudança real nas faixas de premiação da Caixa exigiria alterar código e fazer deploy. Além disso, quando o `LotteryResult` de um concurso específico não traz o valor de uma faixa (ex. captura parcial, jogo manual sem verificação), não existe nenhuma fonte de valor de referência pra mostrar ao usuário.

**Approach:** Criar `PrizeTier` (`game`, `hits`, `value`, `winners`, `reference_month`; `unique_together = ('game', 'hits', 'reference_month')`, AD-10). Uma rotina (`update_monthly_prize_values`, AD-5) captura, a partir do `LotteryResult` mais recente de cada Jogo, uma linha de `PrizeTier` por faixa de acerto que aparece no `prizes` desse resultado (a "estrutura" de faixas do Jogo, não só as que tiveram valor/ganhador naquele concurso específico) e mantém só os 3 meses mais recentes por (Jogo, acertos). `calculate_bet_prize` passa a consultar `PrizeTier` (pelo `reference_month` mais próximo do `captured_at` do `LotteryResult`, sem ultrapassar) pra decidir se uma quantidade de acertos é premiada, em vez do `if/elif` fixo — usando o valor do `LotteryResult.prizes` daquele concurso quando presente, ou o do `PrizeTier` vigente como alternativa.

**Robustez adicional (decisão desta implementação, não pedida literalmente pelo Critério de Aceite):** se `calculate_bet_prize` dependesse só de `PrizeTier` sem nenhum resguardo, a tabela ficaria vazia até a rotina rodar pela primeira vez (dia 1 do mês) — nesse intervalo, **nenhum acerto de nenhum jogador seria reconhecido como premiado**, uma regressão grave. Uma regra que quebra na prática está errada (mesmo princípio já aplicado na Story 2.3, prêmio de 0 acertos da Lotomania): `calculate_bet_prize` cai de volta pro `if/elif` legado **somente quando não existe nenhum `PrizeTier` pra aquele Jogo ainda** (nunca quando já existe `PrizeTier` pro Jogo mas não pra aquela quantidade específica de acertos — nesse caso é genuinamente inválida). `update_monthly_prize_values` também é chamada ao final de `fetch_daily_results` (idempotente via `update_or_create`, sem risco de duplicar) — assim o mês corrente nunca fica sem `PrizeTier` esperando o dia 1, além da entrada dedicada de `CRONJOBS`.

## Fronteiras e Restrições

**Sempre:**
- `PrizeTier.hits` aceita `0` como faixa válida (`PositiveIntegerField`, que no Django aceita 0) — a Lotomania paga por 0 acertos.
- `update_monthly_prize_values` é idempotente (`update_or_create` por `game`+`hits`+`reference_month`) — pode rodar mais de uma vez no mesmo mês sem duplicar nem corromper dado.
- A cada execução, mantém só os 3 `reference_month` mais recentes por (`game`, `hits`) — captura de um mês novo remove automaticamente o mais antigo além dos 3 retidos.
- `calculate_bet_prize` escolhe o `PrizeTier` cujo `reference_month` é o mês do `captured_at` do resultado sendo avaliado, ou o mês retido mais próximo **sem ultrapassar** (nunca um `reference_month` posterior ao `captured_at`) — nunca simplesmente "o mais recente disponível", já que até 3 meses diferentes podem estar retidos ao mesmo tempo.
- Valor exibido: `LotteryResult.prizes` do concurso específico quando a chave daquela quantidade de acertos existir (mesmo que seja `R$ 0,00` — um valor real de "não houve prêmio nesse concurso" não é "indisponível"), senão o `value` do `PrizeTier` vigente — nunca um valor estimado ou inventado.
- Fallback legado (`if/elif` por Jogo, o comportamento já existente) só se aplica quando **não existe nenhum `PrizeTier` pro Jogo** — cold start / jogo novo / rotina que ainda não rodou. Uma vez que `PrizeTier` tem pelo menos 1 linha pro Jogo, uma quantidade de acertos sem `PrizeTier` correspondente é tratada como genuinamente não premiada (não cai no legado).
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não filtrar/pular faixas com `value` zerado ou `winners=0` ao capturar -- uma faixa "estrutural" do Jogo (ex. a faixa "sena" da Mega-Sena) continua válida mesmo num concurso acumulado sem ganhador; só o `value` daquele mês fica zerado, a faixa em si não deixa de existir.
- Não mudar `HitNotification`/`fetch_daily_results`'s lógica de captura de resultado ou de geração de notificação (Stories 2.1/2.3) além de acrescentar a chamada a `update_monthly_prize_values` no fim e passar `captured_at` pro `calculate_bet_prize`.
- Não implementar purge automático de `LotteryResult` nesta story (isso é FR-15/Story 2.10, e AD-10 é explícito: `LotteryResult` não ganha purge automático).

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py::PrizeTier` (**novo**) -- `game` (`CharField`, `choices=GeneratedBet.GAME_CHOICES`), `hits` (`PositiveIntegerField`), `value` (`DecimalField(max_digits=12, decimal_places=2)`), `winners` (`PositiveIntegerField(default=0)`), `reference_month` (`DateField`, sempre normalizado pro dia 1); `Meta.unique_together = ('game', 'hits', 'reference_month')`, `ordering = ['-reference_month']`.
- `apps/loterias_core/migrations/0004_prizetier.py` (**novo**, via `makemigrations`).
- `apps/loterias_core/jobs.py::update_monthly_prize_values()` (**novo**): `reference_month = timezone.localdate().replace(day=1)` (fuso local, não UTC -- ver Notas de Implementação); pra cada Jogo em `GAMES_CONFIG`, pega o `LotteryResult` mais recente via `_latest_result_for_game()` (ordenado pelo número do concurso, não por `captured_at` -- ver Notas), itera `latest_result.prizes.items()` (`{hits_str: {'value':..., 'winners':...}}`, formato já estabelecido na Story 2.1), grava via `PrizeTier.objects.update_or_create(game=game, hits=int(hits_str), reference_month=reference_month, defaults={'value': ..., 'winners': ...})` -- sem filtrar por valor/ganhadores (ver Fronteiras); falha isolada **por faixa** (não por Jogo inteiro -- ver Notas), `try/except` + `logger.exception`; ao final, chama `_prune_old_prize_tiers()`.
- `apps/loterias_core/jobs.py::_latest_result_for_game(game)` (**novo**, privada): escolhe o `LotteryResult` mais recente do Jogo pelo número do concurso (`int(contest)`, mesmo padrão de `utils.suggest_next_contest`), não por `captured_at` -- ver Notas de Implementação.
- `apps/loterias_core/jobs.py::_prune_old_prize_tiers()` (**novo**, privada): pra cada `(game, hits)` distinto em `PrizeTier`, mantém só os 3 `reference_month` mais recentes, apaga o resto.
- `apps/loterias_core/jobs.py::fetch_daily_results` -- ao final (depois da varredura de notificação), chama `update_monthly_prize_values()` (robustez de cold-start, ver Intent) -- resultado ignorado/logado, uma falha aqui não afeta o retorno da função.
- `apps/loterias_core/management/commands/update_monthly_prize_values.py` (**novo**) -- command fino, mesmo padrão de `fetch_daily_results.py` (AD-5): sem argumentos, só chama `jobs.update_monthly_prize_values()`.
- `loterias/settings/base.py::CRONJOBS` -- nova entrada: `('0 4 1 * *', 'django.core.management.call_command', ['update_monthly_prize_values'])` (dia 1 do mês, horário de Brasília, depois da rotina diária das 3h).
- `apps/loterias_core/utils.py::calculate_bet_prize` -- reescrita: calcula `reference_month` via `_reference_month_for(official_result.get('captured_at'))` (nova função privada, converte pro fuso local antes de truncar -- ver Notas); decide validade nesta ordem de prioridade: (1) a própria faixa de premiação do concurso (`prizes.get(str(hits))`, se a chave existir) -- é sempre válida, é dado real e definitivo daquele sorteio específico, nunca podado; (2) `PrizeTier` via `_find_prize_tier(game, hits, reference_month)` (`reference_month__lte=reference_month`, `order_by('-reference_month')`, `.first()`), se achou; (3) se nem um nem outro, mas `PrizeTier.objects.filter(game=game).exists()`, é inválido (não cai no legado); (4) se não existe `PrizeTier` nenhum pro Jogo, usa `_legacy_hits_is_valid(game, hits)`. Esta reordenação (concurso específico antes do `PrizeTier`) foi um ajuste feito durante a revisão -- ver Log de Triagem. Valor: usa `prizes.get(str(hits))['value']` se a chave existir (mesmo que zerado), senão `tier.value` se achou um `PrizeTier`, senão `0`.
- `apps/loterias_core/utils.py::_reference_month_for(captured_at)` (**novo**, privada): converte `captured_at` (aware ou `None`) pro primeiro dia do mês no fuso local (`timezone.localtime`/`timezone.localdate`), nunca em UTC -- ver Notas de Implementação.
- `apps/loterias_core/views.py::bet_detail_view` -- ao montar `official_result`, adiciona `'captured_at': official_result.captured_at` (o próprio `LotteryResult` já tem esse campo).
- `apps/loterias_core/jobs.py::_notify_covered_bets` -- ao montar `official_result`, adiciona `'captured_at': result.captured_at`.
- `apps/loterias_core/admin.py` -- registro simples de `PrizeTier` (mesmo padrão dos demais).
- `apps/loterias_core/tests.py` -- novos testes: (1) `update_monthly_prize_values` captura uma linha por faixa presente no `prizes` do `LotteryResult` mais recente de cada Jogo, incluindo faixa com valor zerado; (2) idempotência (rodar 2x no mesmo mês não duplica, `update_or_create` atualiza o valor); (3) retenção de só 3 meses -- um 4º mês capturado remove o mais antigo; (4) `calculate_bet_prize` usa o `PrizeTier` correto por `reference_month` quando há 3 meses retidos com valores diferentes, escolhendo o mês do `captured_at`, nunca o mais recente; (5) `captured_at` mais antigo que todos os meses retidos não usa nenhum `PrizeTier` (não ultrapassa); (6) `PrizeTier` existente pro Jogo mas não pra aquela quantidade de acertos é tratado como inválido, não cai no legado; (7) sem nenhum `PrizeTier` pro Jogo, cai no `if/elif` legado (testes existentes de `CalculateBetPrizeTests` continuam passando sem modificação -- é exatamente esse o caminho que eles exercitam); (8) valor do `PrizeTier` usado quando a chave da faixa não existe no `prizes` do concurso específico; (9) `fetch_daily_results` chama `update_monthly_prize_values` ao final (cold-start); (10) `PrizeTier.hits=0` (Lotomania) funciona pelo caminho novo.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/models.py::PrizeTier` -- novo model conforme Code Map
- [x] `apps/loterias_core/migrations/0004_prizetier.py` -- via `makemigrations`
- [x] `apps/loterias_core/jobs.py::update_monthly_prize_values` + `_prune_old_prize_tiers` -- nova rotina
- [x] `apps/loterias_core/jobs.py::fetch_daily_results` -- chama a rotina mensal ao final (cold-start)
- [x] `apps/loterias_core/management/commands/update_monthly_prize_values.py` -- novo command
- [x] `loterias/settings/base.py::CRONJOBS` -- nova entrada mensal
- [x] `apps/loterias_core/utils.py::calculate_bet_prize` -- reescrita pra consultar `PrizeTier`, com fallback legado
- [x] `apps/loterias_core/views.py::bet_detail_view`, `jobs.py::_notify_covered_bets` -- passam `captured_at`
- [x] `apps/loterias_core/admin.py` -- registro de `PrizeTier`
- [x] `apps/loterias_core/tests.py` -- 22 casos novos (10+ do Code Map original, mais os que a revisão em 3 camadas exigiu)

**Critérios de Aceite:**
- Dado o primeiro dia de um novo mês, quando a rotina `update_monthly_prize_values` roda, então o sistema captura, pra cada tipo de Jogo, uma Faixa de Premiação (`PrizeTier`) por quantidade de acertos premiada naquele Jogo
- E `calculate_bet_prize` passa a validar se uma quantidade de acertos é premiada consultando `PrizeTier`, em vez da lista fixa de `if/elif` por Jogo
- E o sistema mantém só os 3 meses mais recentes de `PrizeTier` por (Jogo, quantidade de acertos) -- capturar um mês novo remove automaticamente o mais antigo além dos 3 retidos
- E uma Notificação de Acerto premiada criada depois da rotina mensal usa os valores atualizados, não os anteriores
- E o valor exibido numa notificação vem do `LotteryResult.prizes` daquele concurso específico quando disponível, ou do `PrizeTier` vigente quando não -- nunca um valor estimado ou inventado
- E ao validar um acerto retroativo, o sistema usa o `PrizeTier` cujo `reference_month` é o mês do `captured_at` daquele `LotteryResult` (ou o mês retido mais próximo, sem ultrapassar)
- E `PrizeTier.hits` aceita o valor `0` como faixa premiada válida

## Notas de Implementação

Implementação inicial conforme o Code Map original: `PrizeTier`, `update_monthly_prize_values`/`_prune_old_prize_tiers`, a chamada de cold-start em `fetch_daily_results`, o command, a entrada em `CRONJOBS`, o registro no admin e a reescrita de `calculate_bet_prize` (validade via `PrizeTier`, fallback legado só em cold-start total do Jogo). Confirmado que os 8 testes pré-existentes de `CalculateBetPrizeTests`/`ApplyPrizeToBetTests` continuam passando sem nenhuma modificação (bancos de teste frescos não têm `PrizeTier`, então exercitam exatamente o caminho de fallback legado).

A revisão em 3 camadas (ver Log de Triagem) encontrou um problema de design real na primeira versão: `calculate_bet_prize` usava `PrizeTier` como único árbitro de validade de uma quantidade de acertos, *antes* de checar se o próprio `LotteryResult.prizes` daquele concurso específico já continha a faixa. Como `LotteryResult` nunca é podado (AD-10) mas `PrizeTier` só retém 3 meses, isso significava que uma aposta antiga genuinamente premiada podia perder o reconhecimento do prêmio assim que a retenção descartasse o `reference_month` dela -- exatamente o tipo de regra que quebra contra um fato real (mesmo princípio já aplicado na Story 2.3 com a Lotomania). Corrigido invertendo a prioridade: a faixa de premiação do próprio concurso (`prizes.get(str(hits))`) é checada primeiro e, se existir, é sempre válida; `PrizeTier` só entra como alternativa quando o concurso específico não tem essa faixa registrada. Isso também reduz bastante o impacto prático de duas outras lacunas encontradas (fuso horário do `reference_month` e call sites que nunca propagam `captured_at`): como a maior parte dos casos reais passa a resolver pelo dado do próprio concurso, o `reference_month`/`PrizeTier` só influencia o resultado no caminho de fallback.

Além disso, corrigidos: (1) fuso horário -- `reference_month` usava `timezone.now().date()`/`captured_at.date()` direto, que pega a data em UTC; com `TIME_ZONE='America/Sao_Paulo'` isso podia cair no mês seguinte perto da meia-noite local (nova função `_reference_month_for`, via `timezone.localtime`/`timezone.localdate`); (2) `update_monthly_prize_values` escolhia "o resultado mais recente" do Jogo por `captured_at` (data de gravação no banco), que não reflete a ordem real dos concursos quando um concurso antigo é verificado tardiamente via `check_bet_result_view`/`save_manual_bet_view` -- corrigido pra escolher pelo número do concurso (`_latest_result_for_game`, mesmo padrão de `utils.suggest_next_contest`); (3) a falha ao gravar uma faixa específica abortava as faixas seguintes do mesmo Jogo na mesma execução -- o `try/except` foi movido pra granularidade por faixa, não por Jogo inteiro.

## Log de Triagem da Revisão

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) rodada em paralelo sobre o diff da implementação inicial (~24,3 kB, N=5 pro Blind Hunter). Achados e disposição:

**Corrigidos:**
- (Blind Hunter + Edge Case Hunter) `PrizeTier` como único árbitro de validade ignorava a faixa de premiação do próprio concurso (ground truth, nunca podada) -- causava perda permanente de reconhecimento de prêmio pra apostas antigas após a poda de 3 meses. Corrigido reordenando a prioridade em `calculate_bet_prize` (concurso específico > `PrizeTier` > legado). Ver Notas de Implementação.
- (Edge Case Hunter) `reference_month` calculado em UTC, não no fuso local (`America/Sao_Paulo`) -- corrigido com `_reference_month_for`/`timezone.localtime`/`timezone.localdate`.
- (Blind Hunter) `update_monthly_prize_values` escolhia "o resultado mais recente" por `captured_at` em vez do número do concurso -- corrigido com `_latest_result_for_game` (mesmo padrão de `suggest_next_contest`).
- (Edge Case Hunter) Falha ao gravar uma faixa abortava as faixas seguintes do mesmo Jogo na mesma execução -- `try/except` movido pra granularidade por faixa.
- (Verification Gap Reviewer, 2 itens) Teste de retenção criava os `PrizeTier` na mesma ordem cronológica da PK (mascararia uma ordenação por PK em vez de `reference_month`); teste de seleção de mês nunca tinha mais de 1 `PrizeTier` elegível simultaneamente (não provava escolher o mais próximo, só o "não ultrapassar"). Ambos reescritos.
- (Verification Gap Reviewer) Teste de idempotência só provava "não duplica", nunca "atualiza o valor" -- reescrito pra mudar o valor de origem entre as duas chamadas e conferir o valor final.
- (Verification Gap Reviewer, 2 lacunas do Code Map) Faltavam testes pra "`captured_at` mais antigo que todos os meses retidos" e "Lotomania `hits=0` pelo caminho novo (`PrizeTier`)" -- adicionados.
- (Verification Gap Reviewer) Faltava teste provando que `update_monthly_prize_values` roda *depois* da varredura de notificação dentro de `fetch_daily_results` (só a chamada em si e a robustez a falha estavam cobertas) -- adicionado teste de ordem de chamada.

**Aceitos como corretos (falsos positivos ou já cobertos):**
- Blind Hunter/Edge Case Hunter confirmaram que a idempotência entre o cron diário (cold-start) e o mensal, a captura de faixa zerada, o skip sem erro pra Jogo sem `LotteryResult`, e a conversão de chave string→inteiro do JSON já estavam corretos.
- Edge Case Hunter confirmou que a limitação conhecida da Dupla-Sena (2 sorteios, Story 2.1) e a ausência de purge de `LotteryResult` (AD-10, Story 2.10) são decisões de escopo já documentadas, não bugs desta story.

**Deferidos (registrados em `deferred-work.md`, não bloqueiam esta story):**
- N+1 de consultas a `PrizeTier` por bet dentro de `_notify_covered_bets`/`check_user_results` quando a faixa do concurso específico não cobre a quantidade de acertos -- avaliado como de baixo impacto prático (tabela `PrizeTier` é pequena por natureza) e registrado pra revisitar se o volume crescer.
- Entrada mensal redundante em `CRONJOBS` (o cold-start diário já cobre o mesmo trabalho) -- mantida como defesa em profundidade, comentário adicionado no settings explicando o porquê.
- 3 call sites de `calculate_bet_prize` (`check_user_results`, `save_manual_bet_view`, `check_bet_result_view`) nunca propagam `captured_at` -- investigado e considerado correto por design (são buscas ao vivo, "agora" é o `reference_month` certo); risco residual baixo após a correção de prioridade do concurso específico.

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- nenhuma migration pendente.
- `python manage.py check` -- sem erro novo (só o warning pré-existente de `STATICFILES_DIRS`).
- `python manage.py test apps.loterias_core` -- **184 testes, 100% passando**, incluindo os 8 testes pré-existentes de `CalculateBetPrizeTests`/`ApplyPrizeToBetTests` sem nenhuma modificação (fallback legado intacto).
- `python manage.py test` -- **204 testes, 100% passando** (suíte completa do projeto, nenhuma regressão).
