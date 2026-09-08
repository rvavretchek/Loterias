---
title: 'Cobrir reverse accessors renomeados e documentar runbook de migration para produção futura'
type: 'refactor'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'f338267a22cc1a36e49e44e26e8c59b903deabb0'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Os `related_name` `bets` e `statistics` (`User.bets`, `User.statistics`), renomeados na Story 1.1, nunca foram exercitados diretamente por um teste — só indiretamente via `GeneratedBet.objects.filter(user=...)`/`GameStatistics.objects.filter(user=...)` nas outras suites. Além disso, o épico assumia originalmente que poderia haver um banco de produção real a proteger antes de aplicar a `0001_initial` reescrita (Story 1.1); confirmado com o Boss nesta story que **não há produção ainda** — o deploy do lab (`ubt-host01`) é um ambiente de teste descartável, mesmo já tendo rodado `migrate` com o schema antigo (ver decisão registrada em memória, `project-loterias-dev-db-and-english-code-premise`). Isso elimina o risco de perda de dados hoje, mas o runbook de backup/validação continua útil para quando a produção existir de fato.

**Approach:** Adicionar uma classe de teste dedicada exercitando `user.bets`/`user.statistics` diretamente (isolamento entre usuários incluído). Documentar em `deploy/lab/README.md` o procedimento de backup do volume `loterias_data` + validação de migration contra uma cópia (não o arquivo real), explicitando que esse procedimento só é obrigatório a partir do dia em que o ambiente for declarado produção — hoje não se aplica.

## Fronteiras e Restrições

**Sempre:**
- Testes novos só leem/exercitam os reverse accessors já renomeados — não mudam nenhum model/campo.
- Runbook novo é aditivo em `deploy/lab/README.md` — não remove nem reescreve o conteúdo de deploy/validação já existente.

**Nunca:**
- Não tocar em `apps/accounts` (Story 1.5).
- Não abrir o PR único de merge do Epic 1 pra `main` nesta story — isso só acontece depois que a Story 1.5 (última do épico) também estiver concluída (AD-2).
- Não assumir status de produção pra nenhum ambiente sem declaração explícita do Boss — nem o lab, mesmo já tendo rodado `migrate` de verdade.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/tests.py` -- nova classe `ReverseAccessorTests` (4 métodos): `test_user_bets_retorna_jogos_do_usuario`, `test_user_bets_nao_inclui_jogo_de_outro_usuario`, `test_user_statistics_retorna_estatisticas_do_usuario`, `test_user_statistics_nao_inclui_estatistica_de_outro_usuario`. Import de `GameStatistics` adicionado ao topo do arquivo (faltava).
- `deploy/lab/README.md` -- nova seção "Backup e validação de migration antes de aplicar em produção": comandos de backup do volume `loterias_data`, validação da migration contra uma cópia (usando `DATABASE_NAME` -- a env var real que `loterias/settings/base.py` lê pra `DATABASES['default']['NAME']`), e nota explícita de que isso só é obrigatório quando o ambiente virar produção declarada.
- `_bmad-output/planning-artifacts/epics.md` -- Story 1.4 reescrita: título e critérios de aceite ajustados pra refletir a confirmação de que não há produção ainda (removida a exigência de rodar a migration contra um `db.sqlite3` de produção real nesta story), e corrigido "4 stories" → "5 stories" (a Story 1.5 foi adicionada depois que este critério foi escrito originalmente).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/tests.py` -- adicionar `ReverseAccessorTests` cobrindo `user.bets`/`user.statistics`, incluindo isolamento entre usuários
- [x] `deploy/lab/README.md` -- documentar o runbook de backup/validação de migration, com a ressalva de que hoje não se aplica (ambiente de teste confirmado)
- [x] `_bmad-output/planning-artifacts/epics.md` -- corrigir o critério de aceite da Story 1.4 pra refletir a confirmação do Boss

**Critérios de Aceite:**
- Dado que a suíte roda, quando `user.bets`/`user.statistics` são exercitados diretamente, então os testes passam e confirmam isolamento entre usuários (o jogo/estatística de um usuário não aparece no reverse accessor de outro)
- Dado `python manage.py test`, então 100% dos testes passam (74 no projeto inteiro)
- Dado o runbook de deploy, quando um dia o ambiente for declarado produção, então o procedimento de backup+validação de migration está documentado e pronto pra seguir
- Dado que a Story 1.5 ainda não foi implementada, então o PR único de merge do Epic 1 pra `main` (AD-2) não é aberto nesta story

## Notas de Implementação

Confirmação do Boss (2026-09-08, ver memória `project-loterias-dev-db-and-english-code-premise`): o lab (`ubt-host01`) já rodou `migrate` com o schema antigo em algum momento, mas é ambiente de teste — sem dados reais a proteger. Isso fecha o item de `deferred-work.md` que pedia essa confirmação (removido). O runbook de backup foi documentado de forma prospectiva (pra quando existir produção real), não executado agora.

Suíte final: 57 testes em `apps.loterias_core` (era 53 após a Story 1.3), 74 no projeto inteiro -- 100% passando. `manage.py check` sem erros (só o warning pré-existente de `staticfiles.W004`, não relacionado a este épico).

## Log de Triagem da Revisão

Story de baixo risco (só testes + documentação, nenhuma mudança de comportamento de código). Revisão em 3 camadas não foi acionada nesta story -- escopo é aditivo e verificável diretamente pela suíte de testes rodando 100%. Nenhum patch ou item adiado.

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 57 testes, 100% passando
- `python manage.py test` (suíte completa do projeto) -- 74 testes, 100% passando
- `python manage.py check` -- sem erros novos
