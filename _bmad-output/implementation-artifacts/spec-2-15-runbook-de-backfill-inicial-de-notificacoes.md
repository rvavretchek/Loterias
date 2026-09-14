---
title: 'Runbook de Backfill Inicial de Notificações'
type: 'feature'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'd9fc762'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Todo `GeneratedBet` histórico com `hits > 0` já verificado via caminho sob demanda, mas
sem `HitNotification` correspondente, gera uma `HitNotification` nova na primeira execução real da
varredura por estado (AD-4, `_notify_covered_bets`) — o usuário veria "notificação nova" de um acerto
que já conhecia. Urgência elevada porque o pipeline de deploy do cron esteve quebrado desde ~09/09 e
o primeiro ciclo real e não assistido já ocorreu (verificado nesta mesma sessão) — o lab já tem 4
`HitNotification` não lidas geradas dessa forma hoje.

**Approach:** Management command dedicado
`apps/loterias_core/management/commands/mark_initial_notifications_read.py`: marca
`is_read=True` em toda `HitNotification` existente no momento da chamada — nunca apaga
`HitNotification`/`GeneratedBet`/`LotteryResult`, só ajusta o estado de leitura (claramente
distinguível de purga, per AC). Dry-run por padrão (lista quantas seriam marcadas, não grava nada);
só aplica de verdade com `--apply`. Sendo uma ação manual pontual (nunca chamada pelo cron), qualquer
notificação genuína futura nunca é afetada — ela simplesmente não existe ainda no momento em que o
comando roda. Documentar o passo em `deploy/lab/README.md`: quando rodar (uma vez, logo depois de
confirmar que o primeiro ciclo real e não assistido do cron terminou) e o comando exato.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/management/commands/mark_initial_notifications_read.py` -- comando novo,
  dry-run por padrao, `--apply` pra gravar. So `HitNotification.is_read`, nunca deleta nada.
- `apps/loterias_core/tests.py::MarkInitialNotificationsReadCommandTests` -- 8 casos (dry-run,
  apply, nao deleta nada, nao mexe em ja lida, nao afeta notificacao futura, nao mexe em
  LotteryResult, lote misto com asserção de stdout).
- `deploy/lab/README.md` -- secao "Runbook: backfill inicial de notificacoes (Story 2.15)" com o
  passo a passo, aviso sobre a janela do cron, e nota sobre o limite de escopo (e-mail ja enviado
  nao e desfeito).

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff
(~6.3kB, N=3). Patches aplicados: teste de lote misto com asserção de stdout (protege a contagem
impressa, que é o gate de segurança que o operador usa antes de `--apply`); teste confirmando que
`LotteryResult` sobrevive intacto; runbook ajustado (aviso pra evitar a janela 3h-3h30 do cron, nota
explícita sobre o limite de escopo em relação a e-mail já disparado, removida referência vaga a
"histórico de commits"). Três achados reais fora do escopo trivial desta revisão deferidos: e-mail
de acerto já disparado antes do backfill não é desfeito (confirmado no lab que isso não aconteceu de
verdade ainda -- nenhum usuário tem `email_enabled=True`); falta de tratamento de `OperationalError`
sob concorrência com o cron (mesma categoria já deferida nas Stories 2.1/2.9); ausência geral de
teste de stdout nos outros comandos do projeto (não é regressão desta story).

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **305 testes, OK**,
  `.venv` pinado (Python 3.11/Django 5.0.6).