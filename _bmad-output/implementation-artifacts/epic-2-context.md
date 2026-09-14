# Epic 2 Context: Verificação e Notificação Diária de Resultados

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

O jogador descobre que ganhou sem precisar lembrar de checar manualmente: uma rotina diária vigia os resultados oficiais da Caixa por conta própria, cruza contra as apostas salvas de cada usuário e avisa ao logar, diferenciando claramente acerto premiado de acerto sem prêmio. Fecha o segundo dos dois momentos em que hoje o sistema empurra trabalho pro usuário (o primeiro é o cadastro, tratado no Epic 3). Depende do Epic 1 (renomeação de código legado) já mergeado — nenhuma story deste épico começa antes disso.

## Stories

- Story 2.1: Rotina diária de resultados
- Story 2.2: Bloqueio de concurso já sorteado
- Story 2.3: Geração de Notificação de Acerto
- Story 2.4: Exibição da notificação ao logar
- Story 2.5: Detalhe e leitura da notificação
- Story 2.6: Preferência de canal de notificação
- Story 2.7: Envio de e-mail de acerto premiado
- Story 2.8: Rotina mensal de valores de premiação por faixa
- Story 2.9: Tratamento de falha da captura de resultado
- Story 2.10: Purge manual de resultados oficiais antigos
- Story 2.11: Extração real de valor e quantidade de ganhadores por faixa
- Story 2.12: Normalização de Concurso
- Story 2.13: Validação de Jogo em api_create_bet_view
- Story 2.14: Bloqueio real de concurso duplicado
- Story 2.15: Runbook de backfill inicial de notificações

## Requirements & Constraints

- A captura diária é idempotente (não recria `LotteryResult` já existente) e uma falha num Jogo/Concurso nunca interrompe os demais; retry automático até 3x (15 min de intervalo) na mesma execução diária, com exatamente um e-mail de alerta ao operador por Jogo/Concurso que esgotar as tentativas — nunca um resultado inventado ou estimado.
- Gerar/salvar um jogo pra um Jogo+Concurso que já tem resultado é bloqueado (não apenas avisado), de qualquer usuário; concursos especiais/fora de sequência sem resultado continuam aceitos.
- Notificação de Acerto é criada para qualquer interseção não vazia OU prêmio real (cobre a Lotomania, que premia com 0 acertos); nunca duplicada pro mesmo jogo salvo; cada uma é lida individualmente sem afetar as demais.
- Badge do cabeçalho distingue visualmente premiado de não-premiado e some por completo quando não há pendência (nunca sino vazio ou contador zerado).
- Preferência de canal (site/e-mail) fica num único lugar, default site ativo + e-mail desativado; mudar a preferência nunca recria notificações passadas; desativar os dois canais ao mesmo tempo é bloqueado.
- E-mail de acerto só é enviado para acerto premiado, nunca pra acerto sem prêmio; falha de envio nunca impede a notificação no site; nunca é reenviado numa reexecução da rotina.
- Valor de prêmio exibido sempre rastreia a `LotteryResult.prizes` daquele concurso específico ou, na ausência, a `PrizeTier` vigente — nunca estimado; `PrizeTier` retém só os 3 meses mais recentes por (Jogo, quantidade de acertos) e aceita 0 acertos como faixa válida (Lotomania).
- `LotteryResult` tem retenção integral por padrão (sem purge automático); purge manual via admin por data de corte nunca apaga um resultado com `HitNotification` associada (lida ou não), e nunca afeta `PrizeTier`/`GeneratedBet`.
- Métricas de sucesso do épico: todo acerto premiado real vira notificação visível no próximo login sem intervenção manual (SM-1); zero falso-positivo de premiação sem `LotteryResult` oficial por trás (SM-3); volume de e-mail por usuário permanece baixo, nunca reenviado por reexecução (SM-C1).
- Fora de escopo: notificação em tempo real/push/SMS, Celery/Redis, painel dedicado de histórico de falhas, paginação/arquivamento de notificações antigas, cadência configurável por usuário.

## Technical Decisions

- Integração via banco compartilhado (Shared Database): jobs de cron (`jobs.py`) e views HTTP nunca se chamam nem compartilham estado em memória — todo dado passa por uma tabela do SQLite.
- `HitNotification`, `NotificationPreference` e `PrizeTier` são novos models em `apps/loterias_core/models.py` (sem app novo). `NotificationPreference.user` é `OneToOneField`; ausência de linha é lida como os defaults de FR-6. `HitNotification.bet` é `OneToOneField` (unicidade garantida no banco), criado só via `get_or_create(bet=...)` — nenhum outro caminho de código cria essa entidade.
- Cobertura de notificação é derivada por **estado**, não por evento: a cada execução, a rotina varre todo `GeneratedBet` com `LotteryResult` correspondente mas sem `HitNotification` ainda — cobre tanto o resultado gravado pelo caminho sob demanda quanto uma execução anterior que morreu no meio. O e-mail de acerto só dispara quando o `get_or_create` retorna `created=True`, protegendo contra reenvio em execuções concorrentes/repetidas.
- Jobs são funções puras em `apps/loterias_core/jobs.py` (`fetch_daily_results(final: bool = False)`, `update_monthly_prize_values()`), cada uma com um management command fino homônimo; `CRONJOBS` sempre aponta pro command via `call_command`, nunca pra função direto.
- Retry de FR-9 é reexecução idempotente (3 entradas de `CRONJOBS`, 3h00/3h15/3h30 horário de Brasília), não sleep bloqueante; só a execução `--final` das 3h30 dispara o alerta ao operador.
- `loterias-cron` roda como container sidecar (mesma imagem do `loterias-web`, `CMD` diferente), nunca dentro do processo web; `Dockerfile` precisa instalar `cron`/`tzdata`; `TZ=America/Sao_Paulo`; `DATABASES[...]['OPTIONS'] = {'timeout': 20}` porque dois processos passam a escrever no mesmo SQLite.
- `LotteryResult` só é escrito via `update_or_create(game=, contest=)`, nunca `create()` cru, pelos dois caminhos (view sob demanda e job).
- `PrizeTier` (`game`, `hits`, `value`, `reference_month`, `unique_together` nos três primeiros) substitui a lista fixa de `if/elif` por Jogo em `calculate_bet_prize`; validação de acerto retroativo usa o `reference_month` mais próximo do mês de captura do `LotteryResult`, nunca simplesmente o mais recente disponível. Valores monetários em `Decimal`.

## UX & Interaction Patterns

- Badge do cabeçalho (sino + contador) injetado via context processor, igual ao padrão já usado hoje — sem depender de JS/tempo real; clicar leva direto à tela de detalhe.
- Tela de detalhe lista as notificações pendentes identificando Jogo e Concurso, números batidos e valor do prêmio; marcação de lida é por item.
- Campo de Concurso continua pré-preenchido com uma sugestão de próximo concurso sequencial, mas sempre aceita qualquer número digitado (cobre concursos especiais/comemorativos fora da sequência normal).

## Cross-Story Dependencies

- Todo o épico depende do Epic 1 (renomeação de código legado) já concluído e mergeado.
- Stories 2.12 a 2.15 são lacunas/bugs promovidos de `deferred-work.md`, achados em revisões das Stories 1.3, 2.1, 2.2, 2.3 e 2.10 — não são FRs novas, mas correções que qualquer story deste épico pode tocar (ex.: normalização de Concurso afeta o bloqueio de 2.2 e a purga de 2.10).
- Story 2.9 carrega o smoke test de fechamento do épico: pelo menos um ciclo completo e não assistido do cron (3h/3h15/3h30) precisa rodar de ponta a ponta no lab antes do épico ser considerado concluído.
- Story 2.14 está bloqueada numa decisão de produto do Boss (bloquear totalmente a duplicata vs. permitir com aviso mais claro) antes de ser implementada.
- Story 2.15 ganhou urgência elevada em 2026-09-11: o pipeline de deploy do cron esteve quebrado desde ~09/09, então o primeiro ciclo real e não assistido está iminente e pode gerar uma enxurrada de notificações de acertos históricos já conhecidos pelos usuários.
