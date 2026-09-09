---
title: 'Rotina diária de resultados (fetch_daily_results)'
type: 'feature'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '68e4f27a724ce0e759ad41ee3bc4d12131a978ef'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hoje a captura de resultado oficial da CEF só acontece sob demanda (usuário clica em "verificar" num jogo específico). Não existe rotina automática — o jogador precisa lembrar de checar manualmente todo dia. `Celery`/`redis` estão no `requirements.txt` desde o início pra esse propósito, mas nunca ganharam nenhuma task definida (achado documentado em CLAUDE.md).

**Approach:** Criar `apps/loterias_core/jobs.py` com a função pura `fetch_daily_results(final: bool = False)` (AD-5): descobre todo par (Jogo, Concurso) que aparece em algum `GeneratedBet` mas ainda não tem `LotteryResult`, tenta capturar via `fetch_cef_result` (já existente, falha soft), e grava com `update_or_create` (idempotente, nunca duplica). Uma falha isolada num par não interrompe os demais. Um management command fino (`fetch_daily_results`) só repassa `--final` pra função. `CRONJOBS` (via `django-crontab`, adicionado ao `requirements.txt`) agenda uma execução às 3h (horário de Brasília). O container `loterias-cron` (sidecar, AD-7) roda esse cron — `loterias-web` continua só `gunicorn`. Remove `celery`/`redis` do `requirements.txt`/settings (Não-Objetivo da PRD §5, nunca tiveram task real, e agora têm substituto de verdade).

**Fora do escopo desta story (fica pras Stories 2.3/2.9):** criação de `HitNotification`, atualização dos campos-cache do `GeneratedBet` (`result_checked`/`hits`/`prize`/`prize_description`), e-mail de alerta ao operador quando `final=True` falha, e as 2 entradas adicionais de `CRONJOBS` (3h15/3h30) do retry de FR-9. O parâmetro `final` já existe na assinatura (AD-5 fixa o contrato desde já), mas nesta story ele não muda nenhum comportamento — só é aceito e repassado.

## Fronteiras e Restrições

**Sempre:**
- `fetch_daily_results` é função pura em `jobs.py`, chamada só pelo management command — nunca aponta o `CRONJOBS` direto pra função Python (AD-5).
- Descoberta de "concurso em aberto" é feita a partir de `GeneratedBet.objects.values_list('game', 'contest').distinct()` menos os pares que já têm `LotteryResult` — não existe (e esta story não cria) nenhuma tabela separada de "concursos conhecidos/agendados".
- `LotteryResult` só é escrito via `update_or_create(game=, contest=)` (convenção já estabelecida, Consistency Conventions do spine).
- Falha de captura (`fetch_cef_result` retorna `None`, ou qualquer exceção ao gravar aquele par específico) é isolada num `try/except` por par — não propaga e não interrompe os demais.
- Identificadores de código em inglês, sem exceção (parâmetros/locais inclusos) — convenção já estabelecida no Epic 1.
- `docker-compose.yml`/`Dockerfile` seguem exatamente o texto de AD-7 (mesma imagem, `TZ=America/Sao_Paulo`, `restart: unless-stopped`, volume `loterias_data` compartilhado).

**Nunca:**
- Não criar `HitNotification` nem tocar em campos-cache de `GeneratedBet` nesta story (Story 2.3).
- Não implementar o e-mail de alerta ao operador nem as 3 entradas de retry de `CRONJOBS` (Story 2.9) — só uma entrada, às 3h.
- Não deixar nenhum resquício de `celery`/`redis` em código funcional — só nas settings/requirements que já não eram usadas (confirmado por grep antes desta story: zero import de `celery`/`redis` em `apps/`).

**Renegociação de fronteira (durante a implementação, 2026-09-08):** a fronteira original dizia "não remover `fetch_cef_result`/`calculate_bet_prize` de `utils.py` nem mudar seu comportamento". A revisão em 3 camadas achou um bug crítico pré-existente em `fetch_cef_result`: ele ignorava o parâmetro `contest` (scraping de HTML sempre retornava o resultado "atual" da página), então múltiplos concursos em aberto do mesmo Jogo acabariam gravados com o mesmo resultado errado sob `contest`s diferentes — e essa story é a primeira a expor isso em lote, sem supervisão, todo dia. O Boss autorizou explicitamente renegociar essa fronteira e investigar uma correção de verdade ("tente uma forma de trazer o número e data de cada jogo, pois não há como essa operação funcionar sem essa informação"). Isso levou à descoberta e adoção da API oficial da Caixa (`servicebus2.caixa.gov.br/portaldeloterias/api`, verificada ao vivo contra os 6 jogos) em substituição ao scraping de HTML — ver Notas de Implementação. `calculate_bet_prize` também precisou de um ajuste mínimo (busca por acertos reais em vez de uma chave de categoria única) pra não exibir valor de prêmio da faixa errada com os dados reais agora disponíveis.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/jobs.py` (**novo**) -- `fetch_daily_results(final: bool = False) -> None`: calcula `open_pairs = set(GeneratedBet.objects.values_list('game', 'contest').distinct()) - set(LotteryResult.objects.values_list('game', 'contest'))`; para cada `(game, contest)` em `open_pairs`, dentro de um `try/except Exception` isolado, chama `fetch_cef_result(game, contest)` e, se não for `None`, grava via `LotteryResult.objects.update_or_create(game=game, contest=contest, defaults={'numbers': ..., 'clovers': ..., 'prizes': ..., 'source': 'CEF'})` (mesmo padrão já usado em `views.py`/`utils.check_user_results`). `final` é aceito na assinatura mas não usado nesta story (comentário no docstring explicando que Story 2.9 o consome).
- `apps/loterias_core/management/__init__.py`, `apps/loterias_core/management/commands/__init__.py` (**novos**, vazios) -- exigidos pelo Django pra descobrir o command.
- `apps/loterias_core/management/commands/fetch_daily_results.py` (**novo**) -- `Command(BaseCommand)` com `add_arguments` registrando `--final` (`action='store_true'`, default `False`); `handle()` chama `jobs.fetch_daily_results(final=options['final'])`.
- `requirements.txt` -- adiciona `django-crontab==0.7.1`; remove `celery==5.4.0` e `redis==5.0.6` (confirmado sem uso real em código).
- `loterias/settings/base.py` -- adiciona `'django_crontab'` a `INSTALLED_APPS`; adiciona `CRONJOBS = [('0 3 * * *', 'django.core.management.call_command', ['fetch_daily_results'])]`; adiciona `DATABASES['default']['OPTIONS'] = {'timeout': 20}` (AD-7); remove o bloco `# Celery` (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_ACCEPT_CONTENT`, `CELERY_TASK_SERIALIZER`, `CELERY_RESULT_SERIALIZER`, `CELERY_TIMEZONE`).
- `Dockerfile` -- adiciona `RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && rm -rf /var/lib/apt/lists/*` antes do `pip install` (usado só pelo `loterias-cron`, mas construído a partir do mesmo Dockerfile, ver AD-7).
- `deploy/lab/docker-compose.yml` -- novo serviço `loterias-cron`: mesmo `build`, `restart: unless-stopped`, `environment` idêntico ao `loterias-web` (mesmas env vars de e-mail/`SECRET_KEY`/`DATABASE_NAME`) + `TZ: America/Sao_Paulo`, `command: sh -c "python manage.py crontab add && cron -f"`, mesmos `volumes` (`loterias_data`, `loterias_media`), mesma `network`.
- `apps/loterias_core/tests.py` -- nova classe `FetchDailyResultsJobTests`: (1) par sem `GeneratedBet` nenhum não é tocado; (2) par com `GeneratedBet` mas sem `LotteryResult`, com `fetch_cef_result` mockado retornando um resultado válido, gera exatamente 1 `LotteryResult` com os campos corretos; (3) rodar a função de novo pro mesmo par não cria um segundo `LotteryResult` (idempotência); (4) `fetch_cef_result` mockado levantando exceção pra um par não impede a captura bem-sucedida de outro par na mesma execução; (5) `fetch_cef_result` mockado retornando `None` não grava nada e não levanta; (6) dois `GeneratedBet` do mesmo par só disparam 1 chamada a `fetch_cef_result` na mesma execução. Nova classe `FetchDailyResultsCommandTests` cobrindo o repasse de `--final` pelo management command via `call_command`.
- **(Renegociado)** `apps/loterias_core/utils.py::fetch_cef_result` -- reescrita completa: troca o scraping de HTML (`loterias.caixa.gov.br`) pela API oficial JSON da Caixa (`https://servicebus2.caixa.gov.br/portaldeloterias/api/<slug>/<contest>`, slugs sem hífen: `megasena`, `quina`, `lotofacil`, `lotomania`, `maismilionaria`, `duplasena`). Verifica `int(data.get('numero')) != int(contest)` e retorna `None` se não bater (nunca aceita resultado de outro concurso). Todo o parsing (incluindo `data.get('numero')`) fica dentro do mesmo `try/except Exception` que cobre a chamada HTTP — falha soft garantida ponta a ponta, mesma paridade de robustez do scraper antigo. `import re` volta (usado só por `PRIZE_TIER_PATTERN` agora, não mais scraping).
- **(Novo)** `apps/loterias_core/utils.py::_extract_prize_tiers(tiers)` -- converte `listaRateioPremio` num dict `{"<acertos>": {'value':..., 'winners':...}}` (chave STRING, não int -- `prizes` é `JSONField`, e JSON só tem chave string; usar int quebraria silenciosamente a leitura de volta do banco em `bet_detail_view`) com uma entrada por quantidade real de acertos (não só a faixa de acerto máximo). Casamento por regex `PRIZE_TIER_PATTERN = r'^(\d+) acertos$'` contra `descricaoFaixa`. Dupla-Sena tem `descricaoFaixa` duplicada (2 sorteios) -- fica com a primeira ocorrência (1º sorteio); resolver os 2 sorteios completos é um item adiado (`deferred-work.md`).
- **(Renegociado)** `apps/loterias_core/utils.py::calculate_bet_prize` -- 1 linha mudada: `prizes.get(prize_key, {})` → `prizes.get(str(hits), {})`. Antes, com `prizes` sempre `{'sena': {'value': 'R$ 0,00'}}` (stub), isso nunca importava; agora que `prizes` tem dado real por faixa, buscar pela chave de categoria (que cobre uma faixa ampla de acertos, ex. `hits >= 4` pra Mega-Sena) mostraria o valor da faixa de acerto MÁXIMO pra qualquer acerto acima do piso -- bug achado por 2 revisores independentes na revisão desta story. `prize_key`/`category` (rótulo de exibição) não mudam -- só o valor monetário passa a vir da faixa certa.
- `apps/loterias_core/tests.py::FetchCefResultTests` -- reescrita pro novo formato JSON (mock de `response.json()` em vez de `response.text`); +9 testes novos cobrindo: URL/slug correto (`assert_called_once_with`), erro HTTP (`raise_for_status`), corpo de erro sem `numero`, corpo JSON não-dict, Dupla-Sena com faixa duplicada, Lotomania com faixa de 0 acertos.
- `apps/loterias_core/tests.py::CalculateBetPrizeTests` -- 2 testes existentes atualizados pro novo formato de `prizes` (chave string por acertos); +1 teste novo (`test_mega_sena_with_four_hits_uses_quadra_tier_not_sena_tier`) cobrindo a regressão do bug de faixa errada.
- `CLAUDE.md` -- seção "Lógica de domínio das loterias" reescrita com os nomes em inglês (item de `deferred-work.md` da Story 1.1, ainda pendente) e o novo mecanismo de captura via API oficial + rotina de cron; seção "Settings"/"Deploy" atualizadas pra mencionar `django-crontab`/`loterias-cron`. Traduzido o arquivo inteiro pro português (estava em inglês, violando a convenção do projeto).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/jobs.py` -- criar `fetch_daily_results(final=False)` conforme Code Map, com logging (`logging.exception`) por falha
- [x] `apps/loterias_core/management/commands/fetch_daily_results.py` (+ `__init__.py`s) -- command fino com `--final`
- [x] `requirements.txt` -- `+django-crontab==0.7.1`, `-celery`, `-redis`
- [x] `loterias/settings/base.py` -- `INSTALLED_APPS`, `CRONJOBS`, `DATABASES[...]['OPTIONS']`, remover bloco Celery
- [x] `Dockerfile` -- instalar `cron`/`tzdata` + fixar fuso horário do SO (`/etc/localtime`/`/etc/timezone`)
- [x] `deploy/lab/docker-compose.yml` -- serviço `loterias-cron` (com `crontab remove` defensivo antes do `add`)
- [x] `apps/loterias_core/tests.py` -- `FetchDailyResultsJobTests` (7 casos) + `FetchDailyResultsCommandTests` (2 casos)
- [x] **(Renegociado)** `apps/loterias_core/utils.py::fetch_cef_result` -- reescrita pra API oficial, com verificação de concurso e falha soft ponta a ponta
- [x] **(Renegociado)** `apps/loterias_core/utils.py::calculate_bet_prize` -- busca por acertos reais em vez de categoria única
- [x] `CLAUDE.md` -- seção de domínio atualizada + arquivo inteiro traduzido pro português

**Critérios de Aceite:**
- Dado as 3h da manhã (horário de Brasília) chegam e há Jogos com concursos em aberto (sem `LotteryResult` registrado), quando a rotina `fetch_daily_results` roda (via management command chamado pelo `CRONJOBS` do container `loterias-cron`), então o sistema tenta capturar o resultado oficial via `fetch_cef_result` pra cada Jogo/Concurso em aberto e grava em `LotteryResult`
- E rodar a rotina de novo pro mesmo Jogo/Concurso que já tem `LotteryResult` não recria nem duplica o registro (idempotente)
- E uma falha de captura num Jogo/Concurso específico não interrompe a tentativa dos demais
- E o container `loterias-cron` existe no docker-compose, com `cron`/`tzdata` instalados na imagem, `TZ=America/Sao_Paulo` configurado, e `DATABASES[...]['OPTIONS']={'timeout': 20}` no settings

## Notas de Implementação

**A descoberta que resolveu o bug crítico:** o Boss sugeriu procurar por um projeto conhecido de API de loterias no GitHub ("loteriascaixa-api"). A investigação (via WebSearch/WebFetch/curl direto) confirmou que existe uma **API JSON oficial da própria Caixa** (não um espelho de terceiros) em `https://servicebus2.caixa.gov.br/portaldeloterias/api/<jogo>/<concurso>`, usada por vários wrappers de terceiros no GitHub. Testada ao vivo contra os 6 jogos (`megasena`, `quina`, `lotofacil`, `lotomania`, `maismilionaria`, `duplasena`) via `curl` direto do sandbox -- todos responderam com JSON estruturado, incluindo o número do concurso confirmado (`numero`), dezenas sorteadas (`listaDezenas`), trevos (`trevosSorteados`, só +Milionária), e prêmio por faixa com ganhadores (`listaRateioPremio`). Essa API substitui o scraping de HTML frágil por completo, e de brinde já popula os dados de prêmio real por faixa que a Story 2.11 (extração de valor/ganhadores) vai precisar -- adiantamento não solicitado, mas natural dado que os dados já vêm na mesma resposta.

**Peculiaridade confirmada da Dupla-Sena:** tem 2 sorteios por concurso (`listaDezenas` traz só o 1º; `listaDezenasSegundoSorteio` existe separado), e `listaRateioPremio` repete a mesma `descricaoFaixa` uma vez por sorteio (ex. "6 acertos" aparece na faixa 1 -- 1º sorteio -- e na faixa 5 -- 2º sorteio). `_extract_prize_tiers` fica com a primeira ocorrência; suporte completo aos 2 sorteios é um item adiado.

**Bug crítico achado e corrigido durante a própria revisão desta story** (não estava no Code Map original, veio da revisão em 3 camadas): `_extract_prize_tier` (nome original, singular) só extraía a faixa de acerto MÁXIMO do Jogo, mas `calculate_bet_prize` usa uma única chave de categoria pra qualquer acerto acima de um piso bem mais baixo (ex. Mega-Sena: `hits >= 4` → `'sena'`, cobrindo quadra/quina/sena). Isso faria o app mostrar o valor da faixa de 6 acertos pra alguém que bateu só 4 ou 5 -- prêmio incorreto exibido ao usuário. Achado independentemente por 2 revisores (Blind Hunter e Edge Case Hunter). Corrigido renomeando a função pra `_extract_prize_tiers` (plural), extraindo TODA faixa premiada (não só a máxima) indexada por quantidade real de acertos, e mudando `calculate_bet_prize` pra buscar pela quantidade de acertos real em vez da categoria. Verificado contra a API real: concurso 2740 da Mega-Sena, simulação de 5 acertos retorna corretamente o valor da faixa de 5 acertos (R$ 38.469,76, 108 ganhadores), não o da faixa de 6.

**Segundo problema achado na mesma revisão:** `prizes.get(hits, {})` (chave int) quebraria silenciosamente depois de um ciclo de gravação/leitura no banco, já que `LotteryResult.prizes` é `JSONField` e JSON só tem chave string -- um dict Python com chave int, ao ser lido de volta via `LotteryResult.objects.get(...)`, teria as chaves convertidas pra string pelo desserializador JSON. Isso quebraria silenciosamente `bet_detail_view` (que monta `official_result` a partir de um `LotteryResult` já salvo no banco), mesmo funcionando nos outros dois caminhos que usam o dict direto em memória (`save_manual_bet_view`/`check_bet_result_view`). Corrigido usando chave string (`str(hits)`) desde a extração.

**Robustez restaurada:** o scraper de HTML antigo nunca lançava exceção por formato inesperado (na pior hipótese, lista vazia). A primeira versão da reescrita tinha 2 pontos sem proteção (`data.get('numero')` fora do `try/except` de parse, e as list comprehensions de números/trevos/moeda sem proteção contra elemento não numérico) -- corrigido movendo todo o parsing pra dentro do mesmo `try/except Exception`, restaurando a paridade de robustez ("falha soft, nunca lança") com o comportamento anterior.

Suíte final: 95 testes no projeto inteiro (era 77 no fim do Epic 1) -- 100% passando. `manage.py check` sem erro novo. Verificação ao vivo contra a API real da Caixa confirmou o fluxo completo (captura → verificação de concurso → cálculo de prêmio) com dado real do concurso 2740 da Mega-Sena.

## Log de Triagem da Revisão

Revisão em 3 camadas rodada 2x nesta story (v1 antes da descoberta da API oficial, v2 depois da reescrita de `fetch_cef_result`).

**Patches aplicados (v1 → v2, resolvidos pela reescrita da API):**
1. `fetch_cef_result` ignorava o `contest` ao raspar HTML -- bug crítico de dado incorreto, resolvido adotando a API oficial com verificação de concurso. *(Blind Hunter + Edge Case Hunter, achado independente)*

**Patches aplicados (v2, achados na segunda rodada):**
2. `_extract_prize_tier`/`calculate_bet_prize` usavam faixa de acerto máximo pra qualquer acerto acima do piso -- valor de prêmio incorreto pra hits abaixo do máximo. Corrigido extraindo todas as faixas por acertos reais. *(Blind Hunter + Edge Case Hunter, achado independente)*
3. Chave int em `prizes` quebraria após ciclo de gravação/leitura no `JSONField` -- achado por mim mesmo ao rastrear os consumidores de `LotteryResult.prizes` antes de fechar a story (não veio dos 3 revisores diretamente, mas da mesma investigação).
4. `fetch_cef_result` tinha 2 pontos sem proteção contra formato inesperado (`data.get('numero')` fora do try/except; list comprehensions sem proteção) -- restaurada a falha-soft ponta a ponta. *(Blind Hunter, "regressão de robustez em relação ao scraper antigo")*
5. `jobs.py`'s `except Exception: continue` sem nenhum log -- adicionado `logging.exception`/`logging.info`. *(Blind Hunter + Edge Case Hunter, achado independente, "rotina operacionalmente muda")*
6. Dockerfile não fixava o fuso horário do SO (`TZ` env var sozinha não muda o horário que o `cron` do Debian usa) -- adicionado symlink `/etc/localtime` + `/etc/timezone`. *(Edge Case Hunter)*
7. `crontab add` sem `remove` antes, risco de entrada duplicada em reinício de container -- adicionado `crontab remove` defensivo antes do `add`. *(Edge Case Hunter)*
8. 11 testes novos/estendidos cobrindo os gaps achados pela Verification Gap Reviewer: URL/slug da API, erro HTTP, corpo sem `numero`, corpo não-dict, Dupla-Sena duplicada, Lotomania 0 acertos, conteúdo real gravado em `LotteryResult` (não só contagem), dedup de `fetch_cef_result` dentro da mesma execução (`call_count`), e o management command (`--final` repassado corretamente).

**Adiado (`deferred-work.md`, 6 itens):** Dupla-Sena 2º sorteio nunca verificado; `contest` sem normalização (zeros à esquerda/espaço); SQLite sem modo WAL; `fetch_daily_results` sem rate-limiting/backoff em backlog grande; `category` (rótulo, não valor) ainda colapsado numa faixa ampla; casamento de `descricaoFaixa` por texto exato falha em silêncio se a API mudar o wording.

**Falso positivo (sem ação):** nenhum -- todos os achados dos 3 revisores foram confirmados como reais (patch ou defer), nenhum foi descartado como não-problema.

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core.tests.FetchDailyResultsJobTests` -- 7 testes, 100% passando
- `python manage.py test apps.loterias_core.tests.FetchCefResultTests` -- 13 testes, 100% passando
- `python manage.py test` (suíte completa) -- 95 testes, 100% passando
- `python manage.py check` -- sem erro novo
- `python manage.py crontab show` -- não executável no Windows local (`django-crontab` depende de `fcntl`, POSIX-only); verificação real fica pro container Linux
- Chamada real (fora de mock) contra `https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/2740` -- confirmou `fetch_cef_result`/`calculate_bet_prize` funcionando ponta a ponta com dado real, valor de prêmio (R$ 38.469,76, faixa de 5 acertos) batendo exatamente com o concurso real
- `docker-compose.yml` validado via `yaml.safe_load` (parser Python, já que `docker` CLI não está disponível no sandbox) -- estrutura do serviço `loterias-cron` confirmada sintaticamente válida
