---
title: 'Geração de Notificação de Acerto (HitNotification)'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '52c474d268c44a6fa3f72f0a76df222724ad4dd6'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hoje o usuário precisa abrir cada jogo salvo e clicar em "verificar" pra saber se bateu com o resultado oficial — não existe nenhum registro de "isso aqui é um acerto" que o sistema possa usar depois pra avisar o usuário (site ou e-mail, Stories 2.4/2.5/2.7).

**Approach:** Criar o model `HitNotification` (`apps/loterias_core/models.py`, AD-3) — um marcador `OneToOneField` pra `GeneratedBet`, com unicidade garantida pelo banco. Estender `jobs.fetch_daily_results` (AD-4) com uma segunda varredura, além da captura de resultado (Story 2.1): pra todo `GeneratedBet` que ainda não tem `HitNotification`, busca o `LotteryResult` do seu Jogo+Concurso (se existir), calcula `calculate_bet_prize`, atualiza os campos-cache do `GeneratedBet` (`result_checked`/`hits`/`prize`/`prize_description` — já existentes, hoje só atualizados pelos caminhos sob demanda), e cria a `HitNotification` **só se houve interseção** (`hits > 0`) — um jogo sem nenhum acerto não gera notificação. A varredura é por **estado**, não por evento: cobre tanto o `LotteryResult` que a própria rotina acabou de gravar quanto um já existente antes (caminho sob demanda, ou uma execução anterior que morreu no meio) — nunca conta só com o que essa chamada específica gravou.

**Aproveitamento:** o parsing de `calculate_bet_prize` → campos-cache do `GeneratedBet` já está duplicado em 3 lugares (`views.check_bet_result_view`, `views.save_manual_bet_view`, `utils.check_user_results`) — extraído pra uma função `apply_prize_to_bet(bet, prize)` em `utils.py`, reusada por esses 3 e pelo novo código desta story. Refactor puro, sem mudança de comportamento (mesmos testes existentes continuam cobrindo).

## Fronteiras e Restrições

**Sempre:**
- `HitNotification.bet` é `OneToOneField` pra `GeneratedBet` — unicidade garantida pelo banco, não só por convenção (AD-4).
- Toda criação de `HitNotification` usa `get_or_create(bet=bet, defaults={...})` — nunca `create()` cru (AD-4, previne segunda notificação em execução concorrente/repetida).
- `GeneratedBet` com `hits == 0` (nenhuma interseção) **não** gera `HitNotification` — mas os campos-cache (`result_checked`/`hits`/`prize`/`prize_description`) são atualizados normalmente mesmo sem gerar notificação (mesmo padrão já usado pelos caminhos sob demanda: `result_checked=True` significa "já sabemos o resultado", não "ganhou algo").
- A varredura de notificação roda dentro da mesma `fetch_daily_results` (não uma função nova) — usa `GeneratedBet.objects.filter(notification__isnull=True)` (o `related_name` do `OneToOneField`) pra achar candidatos, e só processa os que já têm `LotteryResult` pro seu Jogo+Concurso.
- Nenhum outro caminho de código cria `HitNotification` além de `fetch_daily_results` (Consistency Conventions do spine) — `check_bet_result_view`/`save_manual_bet_view` continuam só atualizando os campos-cache do bet que eles mesmos verificaram, sem criar notificação (isso fica só pra próxima execução da rotina, que vai achar esse bet via a varredura por estado).
- Falha ao processar 1 `GeneratedBet` na varredura é isolada (mesmo padrão de `try/except` + log já estabelecido na Story 2.1) — não interrompe os demais.
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não criar `NotificationPreference` nesta story — isso é Story 2.6 (preferência de canal). `HitNotification` não depende desse model pra ser criada.
- Não implementar exibição (badge, Story 2.4), tela de detalhe/leitura (Story 2.5) nem envio de e-mail (Story 2.7) — só a geração do registro.
- Não mudar o comportamento de `check_bet_result_view`/`save_manual_bet_view`/`check_user_results` além do refactor mecânico pra `apply_prize_to_bet` — mesmos efeitos observáveis de antes.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py` -- novo model `HitNotification`: `bet` (`OneToOneField(GeneratedBet, on_delete=models.CASCADE, related_name='notification', verbose_name='Jogo')`), `won` (`BooleanField(default=False, verbose_name='Premiado')`), `is_read` (`BooleanField(default=False, verbose_name='Lida')`), `created_at` (`DateTimeField(auto_now_add=True, verbose_name='Criado em')`); `Meta.verbose_name`/`verbose_name_plural` em português.
- `apps/loterias_core/migrations/0002_hitnotification.py` (**novo**, via `makemigrations`) -- `CreateModel` de `HitNotification`.
- `apps/loterias_core/utils.py` -- nova função `apply_prize_to_bet(bet, prize)`: aplica `result_checked=True`, `hits=prize['hits']`, `prize=Decimal(...)` (mesmo parsing já usado nos 3 call sites), `prize_description=prize['category']`, e `bet.save(update_fields=[...])`. `check_user_results` refatorada pra chamar essa função em vez de duplicar as 4 linhas.
- `apps/loterias_core/views.py::check_bet_result_view` e `save_manual_bet_view` -- refatoradas pra chamar `apply_prize_to_bet(bet, prize)` em vez de duplicar as 4 linhas (mesmo comportamento, sem mudança visível).
- `apps/loterias_core/jobs.py::fetch_daily_results` -- nova varredura após a captura de resultado (Story 2.1, inalterada): `GeneratedBet.objects.filter(notification__isnull=True)`, pra cada um busca `LotteryResult.objects.filter(game=bet.game, contest=bet.contest).first()` (`continue` se não existir ainda), calcula `calculate_bet_prize`, chama `apply_prize_to_bet(bet, prize)`, e se `prize['hits'] > 0` cria `HitNotification.objects.get_or_create(bet=bet, defaults={'won': prize['won']})`. Falha isolada por bet (`try/except` + `logger.exception`), mesmo padrão da captura.
- `apps/loterias_core/admin.py` -- registro simples de `HitNotification` no admin (`list_display`, sem customização elaborada — só pra inspeção manual durante o desenvolvimento do Epic 2).
- `apps/loterias_core/tests.py` -- novos testes: (1) `GeneratedBet` com interseção não vazia e `LotteryResult` existente gera `HitNotification` com `won` correto; (2) `GeneratedBet` com `hits == 0` não gera `HitNotification` (mas os campos-cache são atualizados); (3) rodar a varredura de novo pro mesmo bet não cria uma segunda `HitNotification` (idempotência via `get_or_create`); (4) a varredura cobre um `LotteryResult` já existente antes da chamada (caminho sob demanda), não só o que a própria chamada gravou; (5) falha ao processar 1 bet não impede o processamento de outro; (6) `GeneratedBet` sem `LotteryResult` pro seu Jogo+Concurso ainda não é processado (fica candidato pra próxima execução); (7) `apply_prize_to_bet` isolada (utils); testes existentes de `check_bet_result_view`/`save_manual_bet_view`/`check_user_results` continuam passando sem alteração de asserção (refactor puro).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/models.py::HitNotification` -- novo model conforme Code Map (+ `ordering`/índice em `is_read`, achado na revisão)
- [x] `apps/loterias_core/migrations/0002_hitnotification.py` -- via `makemigrations`
- [x] `apps/loterias_core/utils.py::apply_prize_to_bet` -- nova função, `check_user_results` refatorada pra usá-la
- [x] `apps/loterias_core/views.py` -- `check_bet_result_view`/`save_manual_bet_view` refatoradas pra `apply_prize_to_bet`
- [x] `apps/loterias_core/jobs.py::fetch_daily_results` -- varredura de notificação conforme Code Map (+ pré-busca de `LotteryResult` em lote, achado na revisão)
- [x] `apps/loterias_core/admin.py` -- registro simples de `HitNotification`
- [x] `apps/loterias_core/tests.py` -- 7 casos do Code Map + 6 casos adicionais da revisão
- [x] **(Renegociado)** `apps/loterias_core/utils.py::calculate_bet_prize` -- corrigido `won` pra não exigir `hits > 0` (Lotomania paga por 0 acertos)

**Critérios de Aceite:**
- Dado um `LotteryResult` sem `HitNotification` correspondente pra algum `GeneratedBet` daquele Jogo+Concurso (de qualquer usuário), quando a rotina `fetch_daily_results` roda, então o sistema cria uma `HitNotification` pra cada `GeneratedBet` com interseção não vazia, marcada como premiada ou não conforme `calculate_bet_prize`
- E a varredura considera todo `GeneratedBet` ainda sem cobertura, não só o que a rotina gravou nesta execução — cobre também `LotteryResult` escrito pelo caminho sob demanda
- E `GeneratedBet` sem interseção nenhuma não gera Notificação
- E uma execução concorrente ou repetida nunca cria uma segunda `HitNotification` pro mesmo `GeneratedBet` (unicidade garantida no banco via `get_or_create`)

## Notas de Implementação

A revisão em 3 camadas achou um bug real na fórmula de `won` de `calculate_bet_prize` (não tocada pelo Code Map original, mas exposta pela mesma investigação): `won = bool(prize_key and hits > 0 and amount > 0)` nunca reconhecia o prêmio de 0 acertos da Lotomania (regra real do jogo -- `prize_key` já era sempre `'lotomania'` independente de `hits`, numa linha claramente tautológica que sugeria uma tentativa incompleta de tratar esse caso: `'lotomania' if hits >= 0 else 'lotomania'`). Corrigido removendo a exigência de `hits > 0` -- `amount > 0` sozinho já é o gate correto, porque os demais Jogos só têm `prize_key` setado (e portanto `amount` calculado) quando `hits` já atinge o piso de cada um.

Isso não resolve por completo o caso da Lotomania: o gatilho de notificação em `_notify_covered_bets` (`if prize['hits'] > 0`) continua sem criar `HitNotification` pra esse prêmio específico, porque o Critério de Aceite desta story diz literalmente "GeneratedBet sem interseção nenhuma não gera Notificação", sem ressalva. Documentado como decisão de produto pendente em `deferred-work.md` -- não decidi unilateralmente abrir essa exceção, já que contraria o texto explícito do Critério de Aceite.

A revisão também achou uma consequência arquitetural real do desenho da AD-4 (cobertura por estado): todo bet com `hits == 0` nunca ganha `HitNotification` e por isso nunca sai do candidate set (`notification__isnull=True`) -- é reprocessado em toda execução futura, pra sempre. Não é um bug de implementação (é exatamente o que a AD-4/spec pedem), mas documentado como um trade-off que vale revisitar se o volume de jogos crescer (ver `deferred-work.md`).

Suíte final: 119 testes no projeto inteiro (era 107 no fim da Story 2.2) -- 100% passando. `manage.py check`/`makemigrations --check` sem erro novo.

## Log de Triagem da Revisão

**Patches aplicados:**
1. `calculate_bet_prize`'s `won` exigia `hits > 0`, impedindo o reconhecimento do prêmio de 0 acertos da Lotomania. *(Blind Hunter + Edge Case Hunter, achado independente)*
2. N+1 de `LotteryResult.objects.filter(...).first()` por bet dentro do loop de `_notify_covered_bets` -- corrigido com uma pré-busca em lote (dict `{(game,contest): LotteryResult}`). *(Blind Hunter)*
3. `HitNotification` sem `Meta.ordering`/índice em `is_read` -- adicionado agora (momento mais barato, antes de qualquer outra story consumir o model). *(Blind Hunter)*
4. Mensagem de log imprecisa (`'falha ao gerar notificacao'` cobria também falha na busca do `LotteryResult`/`apply_prize_to_bet`) -- renomeada pra `'falha ao processar o bet ... pra notificacao'`. *(Blind Hunter)*
5. 8 testes novos/estendidos cobrindo os gaps achados pela Verification Gap Reviewer: `hits > 0` mas `won=False` a nível de job (não só de `calculate_bet_prize` isolada), unicidade garantida pelo banco (`IntegrityError` direto, não só via `get_or_create`), smoke test HTTP do admin de `HitNotification`, e reforço das asserções de `hits`/`prize`/`prize_description` nos 3 call sites refatorados pra `apply_prize_to_bet` (antes só verificavam `result_checked`).

**Adiado (`deferred-work.md`, 4 itens):** reprocessamento perpétuo de bets com `hits == 0` (trade-off da AD-4, não um bug); Lotomania de 0 acertos não gera `HitNotification` mesmo com `won` já corrigido (tensão com o texto literal do Critério de Aceite, decisão de produto pendente); `LotteryResult` corrigido depois de já notificado não re-sincroniza `HitNotification`/campos-cache (cenário raro); enxurrada de notificações de backfill no primeiro deploy real (nota operacional pro runbook, não bug de código).

**Falso positivo (sem ação):** nenhum -- todos os achados dos 3 revisores foram confirmados como reais (patch ou defer).

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- sem migration pendente
- `python manage.py test apps.loterias_core` -- 99 testes, 100% passando
- `python manage.py test` (suíte completa) -- 119 testes, 100% passando
- `python manage.py check` -- sem erro novo
