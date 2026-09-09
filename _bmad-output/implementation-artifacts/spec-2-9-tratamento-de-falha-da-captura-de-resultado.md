---
title: 'Tratamento de falha da captura de resultado'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '2b2709e8e1b258493160c7839dd9bcdac26b02a7'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hoje `fetch_daily_results` roda uma única vez por dia (3h). Se `fetch_cef_result` falhar pra um Jogo/Concurso (API fora do ar, erro de rede, mudança de formato), ninguém fica sabendo — o operador (Boss) só descobriria se um usuário reclamasse de não ver o resultado.

**Approach:** `fetch_daily_results` já é idempotente e sem estado entre execuções (recalcula `open_pairs` do zero a cada chamada, a partir do que falta em `LotteryResult`) — o "retry automático" pedido pelo Critério de Aceite não precisa de nenhuma lógica nova, só de rodar a mesma função mais vezes: 3 entradas em `CRONJOBS` (3h, 3h15, 3h30), a última com `--final` (a flag já existe desde a Story 2.1, sem uso até agora). Na execução `--final`, um par que continuar sem `LotteryResult` dispara um e-mail de alerta ao operador — mas só se estiver aberto há tempo suficiente pra ser genuinamente uma falha, não um concurso que simplesmente ainda não foi sorteado (ver próxima seção).

**Desvio necessário do Critério de Aceite literal (decisão desta implementação):** o AC fala em "se `fetch_cef_result` falha pra um Jogo/Concurso", mas o sistema não tem hoje (nem esta story pede) nenhuma forma de distinguir "a captura genuinamente falhou" de "o concurso ainda não foi sorteado" — `fetch_cef_result` devolve `None` nos dois casos. Como todo `GeneratedBet` é criado pra um concurso ainda não sorteado (`_block_if_contest_already_drawn`, Story 2.2, bloqueia o contrário), a esmagadora maioria dos pares "abertos" em qualquer dia são concursos futuros aguardando a data normal do sorteio — não falhas. Implementar o alerta literalmente (dispara pra todo par aberto na execução `--final`) inundaria o operador com um e-mail por dia por concurso ainda não sorteado, todo santo dia, destruindo o propósito do alerta (ruído afoga sinal) — exatamente o tipo de regra que quebra contra a realidade (mesmo princípio já aplicado nas Stories 2.3/2.8). Correção: o alerta só dispara pra um par aberto há `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` (8) dias ou mais, contados a partir do `GeneratedBet` mais antigo daquele par -- 8 é o maior intervalo real entre sorteios consecutivos entre os 6 Jogos suportados (semanal, 7 dias) mais 1 dia de folga pro ciclo de captura processar. **Este limiar é uma escolha de engenharia, não uma constante validada contra o calendário oficial de sorteios de cada Jogo — o Boss deve revisar e ajustar se tiver esse dado.**

## Fronteiras e Restrições

**Sempre:**
- `fetch_daily_results` continua a mesma função idempotente e sem estado entre chamadas (Stories 2.1/2.3/2.8) — o retry automático das 3h/3h15/3h30 é só a mesma função chamada 3x por 3 entradas de `CRONJOBS`, nenhuma lógica de "tentativa" nova.
- O alerta ao operador só é avaliado na execução `--final` (3h30) — as execuções das 3h e 3h15 nunca alertam, só tentam capturar.
- Um par só dispara alerta se estiver aberto (sem `LotteryResult`) há `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` dias ou mais desde o `GeneratedBet` mais antigo daquele par — nunca no primeiro dia em que fica aberto.
- Exatamente 1 e-mail de alerta por par Jogo/Concurso, pra sempre — `CaptureFailureAlert` (novo model, `unique_together=('game','contest')`) registra que o alerta já foi enviado; execuções `--final` seguintes (mesmo dia ou dias futuros) nunca reenviam pro mesmo par.
- `OPERATOR_ALERT_EMAIL` (nova env var) define o destinatário; se vazia/não configurada, o envio é pulado com log de aviso (fail-soft, mesmo padrão de `NotificationPreference`/e-mail de acerto) — nunca levanta exceção.
- Uma falha ao enviar o e-mail de alerta (ou ao avaliar um par) é isolada e nunca interrompe a avaliação dos demais pares nem o resto de `fetch_daily_results`.
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não criar nenhuma lógica de calendário de sorteio por Jogo (dias da semana de cada loteria) — fora do escopo, e o projeto não tem hoje essa informação de forma confiável; o limiar de dias é a mitigação deliberadamente simples adotada.
- Não mudar `_notify_covered_bets`/geração de `HitNotification` — uma falha de captura já não gera notificação nenhuma pra aquele par (ausência de `LotteryResult` já impede isso na lógica existente, Stories 2.1/2.3); nenhuma mudança de código é necessária pra esse Critério de Aceite, só confirmação por teste.
- Não implementar o smoke test de fechamento de épico (Critério de Aceite final: "pelo menos um ciclo completo e não assistido do cron rodando no lab") como parte desta story de código — é uma verificação operacional pós-deploy que exige acesso ao ambiente do lab e observação ao vivo por várias horas; fica registrado como passo manual do Boss antes de fechar o Epic 2 (ver Notas de Implementação).
- Não introduzir fila assíncrona nem mudar o mecanismo de e-mail (mesmo padrão síncrono/fail-soft de `send_mail`, Stories 2.7/accounts).

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py::CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` (**novo**, constante de módulo) -- `8`.
- `apps/loterias_core/models.py::CaptureFailureAlert` (**novo model**) -- `game` (`CharField`, `choices=GeneratedBet.GAME_CHOICES`), `contest` (`CharField`), `created_at` (`DateTimeField(auto_now_add=True)`); `Meta.unique_together = ('game', 'contest')`.
- `apps/loterias_core/migrations/0005_capturefailurealert.py` (**novo**, via `makemigrations`).
- `apps/loterias_core/emails.py::send_capture_failure_alert(game, contest)` (**novo**) -- lê `settings.OPERATOR_ALERT_EMAIL`; se vazio, `logger.warning` e retorna sem enviar; senão monta assunto/corpo (mesmo padrão fail-soft de `send_hit_notification_email`, `try/except` cobrindo a função inteira) e chama `send_mail(..., fail_silently=True)`.
- `apps/loterias_core/jobs.py::fetch_daily_results` -- troca a variável local `resolved`-only por também coletar `still_open` (pares que continuam sem `LotteryResult` depois da tentativa desta execução); ao final, se `final=True`, chama `_alert_operator_of_stale_capture_failures(still_open)`.
- `apps/loterias_core/jobs.py::_alert_operator_of_stale_capture_failures(open_pairs)` (**novo**, privada): pré-carrega em lote (evita N+1 -- ajuste da revisão) 3 conjuntos: pares já alertados (`CaptureFailureAlert`), pares já resolvidos nesta mesma execução (`LotteryResult` -- recheck contra o snapshot congelado de `open_pairs`, ajuste da revisão) e o `created_at` mínimo por par (`GeneratedBet.objects.values(...).annotate(oldest=Min('created_at'))`). Pra cada par: pula se já alertado ou já resolvido; pula se o mais antigo não passou do limiar; senão chama `send_capture_failure_alert(game, contest)` e só grava `CaptureFailureAlert.objects.get_or_create(...)` se a função retornar `True` (envio confirmado -- ajuste crítico da revisão, ver Notas). Falha isolada por par (`try/except` + `logger.exception`).
- `loterias/settings/base.py` -- `OPERATOR_ALERT_EMAIL = os.getenv('OPERATOR_ALERT_EMAIL', '')`; `CRONJOBS` ganha 2 novas entradas (3h15 sem `--final`, 3h30 com `--final`) além da já existente (3h).
- `.env.example` -- nova entrada `OPERATOR_ALERT_EMAIL=boss@example.com`.
- `apps/loterias_core/admin.py` -- registro simples de `CaptureFailureAlert` (mesmo padrão dos demais).
- `apps/loterias_core/tests.py` -- novos testes: (1) uma falha isolada num par não bloqueia os demais (já coberto por teste existente da Story 2.1, confirmar que segue valendo); (2) execução sem `--final` nunca avalia/envia alerta, mesmo com par velho o bastante; (3) par aberto há menos de `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` dias não dispara alerta mesmo em `--final`; (4) par aberto há `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` dias ou mais dispara exatamente 1 e-mail em `--final`; (5) uma segunda execução `--final` (mesmo dia ou dia seguinte) pro mesmo par já alertado não reenvia (via `CaptureFailureAlert`); (6) `OPERATOR_ALERT_EMAIL` vazio não levanta exceção, só loga aviso e não envia; (7) uma falha de captura nunca gera `HitNotification` pra aquele par (confirma comportamento já existente, sem mudança de código); (8) `--final` com múltiplos pares velhos envia um e-mail por par, não um agregado; (9) o management command `fetch_daily_results --final` repassa `final=True` (teste de integração já existe da Story 2.1, `FetchDailyResultsCommandTests` -- confirmar que segue cobrindo).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/models.py::CaptureFailureAlert` + `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` -- novo model e constante
- [x] `apps/loterias_core/migrations/0005_capturefailurealert.py` -- via `makemigrations`
- [x] `apps/loterias_core/emails.py::send_capture_failure_alert` -- novo e-mail fail-soft (retorna `True`/`False` conforme envio real, ver Notas)
- [x] `apps/loterias_core/jobs.py::fetch_daily_results` + `_alert_operator_of_stale_capture_failures` -- alerta condicionado a `--final` e ao limiar de dias
- [x] `loterias/settings/base.py` -- `OPERATOR_ALERT_EMAIL` + 2 novas entradas de `CRONJOBS` (3h15, 3h30 `--final`)
- [x] `.env.example` -- nova variável documentada
- [x] `apps/loterias_core/admin.py` -- registro de `CaptureFailureAlert`
- [x] `apps/loterias_core/tests.py` -- 15 casos novos (Code Map original + reforços da revisão)

**Critérios de Aceite:**
- Dado `fetch_cef_result` falha pra um Jogo/Concurso na execução das 3h, quando a rotina roda de novo às 3h15 e 3h30, então o sistema tenta a captura de novo automaticamente, sem intervenção
- E se um par continuar sem resultado por `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` dias ou mais, o operador recebe exatamente um e-mail de alerta por Jogo/Concurso falho, disparado só pela execução `--final` das 3h30
- E uma falha de captura nunca gera uma Notificação de Acerto incorreta ou inventada
- E uma falha num Jogo/Concurso não bloqueia a tentativa dos demais
- E o smoke test de fechamento do épico (ciclo completo e não assistido do cron no lab) fica registrado como passo manual do Boss antes de fechar o Epic 2 -- fora do escopo de código desta story

## Notas de Implementação

Implementação inicial conforme o Code Map original: `CaptureFailureAlert`, `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS`, `send_capture_failure_alert`, `_alert_operator_of_stale_capture_failures`, as 2 novas entradas de `CRONJOBS`, `OPERATOR_ALERT_EMAIL`, registro no admin.

A revisão em 3 camadas encontrou, de forma independente por 2 dos 3 revisores (Blind Hunter e Verification Gap Reviewer) e reforçada por um terceiro ângulo do Edge Case Hunter, o bug mais grave de toda a implementação: `CaptureFailureAlert.objects.get_or_create(...)` era chamado **antes** de `send_capture_failure_alert` confirmar que o e-mail realmente saiu. Como o model existe justamente pra garantir "exatamente 1 e-mail por par, pra sempre", isso significava que uma `OPERATOR_ALERT_EMAIL` esquecida no primeiro deploy do lab (cenário extremamente provável -- é uma env var nova) ou uma falha transiente de SMTP silenciaria aquele par **permanentemente**, mesmo depois de tudo corrigido -- o oposto exato do que a story deveria resolver. Corrigido invertendo a ordem: `send_capture_failure_alert` agora retorna `True`/`False` conforme o envio foi de fato despachado (usa o retorno de `send_mail`, que conta e-mails realmente entregues mesmo com `fail_silently=True`), e `CaptureFailureAlert` só é gravado quando o retorno é `True`. Um teste de regressão dedicado (`test_missing_operator_email_does_not_permanently_silence_the_alert`) prova o ciclo completo: falha sem e-mail configurado → nenhum registro → configura a variável → roda de novo → alerta finalmente sai.

O Edge Case Hunter também encontrou uma janela de corrida real: `_alert_operator_of_stale_capture_failures` recebia `still_open`, um snapshot congelado no início de `fetch_daily_results`, sem reconsultar `LotteryResult` antes de alertar -- um par resolvido por uma verificação manual (`check_bet_result_view`) durante a janela desta mesma execução do cron geraria um alerta obsoleto. Corrigido com uma reconsulta em lote (não por par, pra não introduzir N+1 -- achado à parte do Blind Hunter, corrigido junto) logo antes de decidir alertar.

O limiar de 8 dias (`CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS`) mede a idade do `GeneratedBet` mais antigo do par, não a distância real até a data do sorteio -- limitação já reconhecida no Intent da spec e reafirmada de forma independente por Blind Hunter e Edge Case Hunter (um usuário pode criar uma aposta manual pra um concurso muito distante no futuro, sem validação de teto). Não corrigido nesta story (exigiria conhecer o calendário real de sorteio de cada Jogo, fora de escopo per "Nunca"); registrado em `deferred-work.md`.

## Log de Triagem da Revisão

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) rodada em paralelo sobre o diff da implementação inicial (~18,9 kB, N=5 pro Blind Hunter). Achados e disposição:

**Corrigidos:**
- (Blind Hunter + Verification Gap Reviewer + Edge Case Hunter, achado crítico convergente) `CaptureFailureAlert` gravado antes de confirmar o envio do e-mail -- causava silenciamento permanente de um par após uma `OPERATOR_ALERT_EMAIL` vazia ou falha transiente de SMTP. Corrigido invertendo a ordem (só grava após `send_capture_failure_alert` retornar `True`). Ver Notas de Implementação.
- (Edge Case Hunter) `_alert_operator_of_stale_capture_failures` não reconsultava `LotteryResult` antes de alertar -- um par resolvido durante a janela da própria execução do cron geraria alerta obsoleto. Corrigido com reconsulta em lote.
- (Blind Hunter) N+1 de `GeneratedBet.objects.filter(...).first()` por par dentro do loop de alerta -- corrigido pré-carregando os 3 conjuntos de apoio (já alertados, já resolvidos, `created_at` mínimo por par) em 3 queries totais, não por par.
- (Blind Hunter) Docstring de `send_capture_failure_alert` afirmava que a função inteira ficava dentro do `try/except`, mas o guard de `OPERATOR_ALERT_EMAIL` vazio ficava fora -- docstring corrigida pra descrever o comportamento real.
- (Verification Gap Reviewer) `test_failure_in_one_pair_does_not_block_alert_evaluation_of_another` isolava a exceção no loop de CAPTURA (Story 2.1), não no `try/except` novo desta story -- mantido (renomeado pra deixar claro o que prova) e adicionado `test_exception_evaluating_one_pairs_alert_does_not_block_another`, que injeta a exceção dentro de `send_capture_failure_alert` pra exercitar de fato o isolamento novo.
- (Verification Gap Reviewer) Nenhum teste distinguia "o bet mais antigo" de "o único bet" -- adicionado `test_alert_based_on_the_oldest_bet_when_multiple_bets_exist_for_the_pair` com 2 bets de idades diferentes pro mesmo par.
- (Verification Gap Reviewer) Nenhum teste simulava o ciclo real de 3 execuções diárias (3h/3h15/3h30) -- adicionado `test_three_daily_runs_retry_automatically_and_alert_only_on_final`.
- (Verification Gap Reviewer) `test_missing_operator_email_does_not_raise_and_does_not_send` não verificava `CaptureFailureAlert.objects.exists()` -- adicionada a asserção, e o teste de regressão crítico já citado.

**Aceitos como corretos (falsos positivos ou já cobertos):**
- Edge Case Hunter confirmou que a cadência 3x/dia de `_notify_covered_bets`/`update_monthly_prize_values` não gera duplicação (ambas já eram idempotentes antes desta story), que o dedup de `CaptureFailureAlert` sobrevive a um container de cron fora do ar por vários dias sem gerar múltiplos alertas no catch-up, e que uma falha de captura genuinamente nunca gera `HitNotification` (nenhuma mudança de código necessária, só teste de confirmação).
- Blind Hunter confirmou que não há bug de correção na cadência 3x/dia em si (só custo redundante, já esperado).

**Deferidos (registrados em `deferred-work.md`, não bloqueiam esta story):**
- Limiar de 8 dias medindo idade da aposta, não distância real até o sorteio -- limitação já reconhecida na spec, sem correção completa possível dentro do escopo (exigiria calendário de sorteio por Jogo, explicitamente fora de escopo).
- Ausência de lock/mutex entre as 3 execuções diárias, agora com 3x mais chamadas do que antes -- mesma categoria de risco já registrada na Story 2.1 (SQLite sem WAL), amplificada mas não nova.

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- nenhuma migration pendente.
- `python manage.py check` -- sem erro novo (só o warning pré-existente de `STATICFILES_DIRS`).
- `python manage.py test apps.loterias_core` -- **198 testes, 100% passando**.
- `python manage.py test` -- **218 testes, 100% passando** (suíte completa do projeto, nenhuma regressão).

**Fora do escopo de código (Critério de Aceite final):** o smoke test de fechamento do Epic 2 ("pelo menos um ciclo completo e não assistido do cron rodando no lab") exige deploy real e observação ao vivo do ambiente do lab por várias horas -- não executável a partir desta sessão de desenvolvimento. Fica registrado como passo manual pendente do Boss antes de declarar o Epic 2 concluído.
