---
title: 'Purge manual de resultados oficiais antigos'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'fa93bbd6ec43bf6f76c8a7374e3f9690d09c1c47'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `LotteryResult` nunca é purgado automaticamente (AD-10, decisão explícita) — a tabela cresce pra sempre. O operador (Boss) precisa de uma forma de controlar esse crescimento quando decidir que não precisa mais do histórico completo, sem risco de apagar dado que ainda importa (um concurso premiado que um usuário ainda pode querer conferir).

**Approach:** `LotteryResult` ainda não está registrado no Django Admin — esta story registra e adiciona uma ação de admin ("Purgar resultados até uma data") que recebe uma data de corte via uma página intermediária de confirmação (mesmo padrão do "delete selected" nativo do Django, que também usa uma tela intermediária) e apaga todo `LotteryResult` com `captured_at` anterior à data informada — **exceto** um que tenha pelo menos um `GeneratedBet` (mesmo `game`+`contest`) com uma `HitNotification` associada (lida ou não). `PrizeTier` e `GeneratedBet` nunca são tocados por esta ação (não têm FK pra `LotteryResult`, então não há cascata a evitar — a proteção real é toda no filtro de exclusão da consulta).

## Fronteiras e Restrições

**Sempre:**
- Retenção integral por padrão — nenhum `LotteryResult` é apagado automaticamente; a purga só acontece quando o operador executa a ação manualmente.
- A ação ignora a seleção de checkboxes da changelist (é uma ação por data de corte, não por linha selecionada) — qualquer linha selecionada apenas habilita o botão "Executar" do Django Admin; a purga real sempre avalia **todos** os `LotteryResult` com `captured_at` anterior à data informada, não só os selecionados. Isso é documentado na `description` da ação e na tela intermediária, pra não confundir o operador.
- Um `LotteryResult` é protegido da purga (nunca apagado, mesmo mais antigo que a data de corte) se existir pelo menos um `GeneratedBet` com o mesmo `game`+`contest` que tenha uma `HitNotification` associada — `lida` ou não, tanto faz.
- A comparação usa `captured_at` (quando o resultado foi capturado/gravado no sistema), não uma data de sorteio (que o sistema não guarda separadamente).
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não implementar purge automático/agendado — só a ação manual do admin (Story 2.10 é exatamente o oposto disso, uma ferramenta sob controle humano).
- Não apagar nem alterar `PrizeTier` ou `GeneratedBet` nesta ação — a purga afeta somente `LotteryResult`.
- Não confirmar a purga sem uma tela intermediária — apagar em massa direto ao clicar "Ir" seria destrutivo demais sem uma etapa de confirmação explícita com a contagem do que será apagado.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/admin.py::LotteryResultAdmin` (**novo**, `LotteryResult` nunca esteve registrado no admin) -- `list_display = ('game', 'contest', 'captured_at', 'source')`, `list_filter = ('game', 'source')`, `search_fields = ('contest',)`, `actions = ['purge_until_date']`.
- `apps/loterias_core/admin.py::PurgeUntilDateForm` (**novo**, `forms.Form`) -- 1 campo `cutoff_date` (`DateField`, widget `type='date'`).
- `apps/loterias_core/admin.py::LotteryResultAdmin.purge_until_date` (**novo**, admin action, `permissions=['delete']` -- ajuste da revisão): sem `'apply' in request.POST`, renderiza a tela intermediária (`templates/admin/loterias_core/lotteryresult/purge_until_date.html`) com a contagem total de `LotteryResult` existentes, o nome da ação e os pks selecionados (pra reembutir como campos ocultos no form -- ajuste crítico da revisão, ver Notas). Com `'apply' in request.POST` e form válido: monta `cutoff_datetime` (meia-noite local da `cutoff_date`, `timezone.make_aware`), calcula candidatos via `LotteryResult.objects.filter(captured_at__lt=cutoff_datetime).annotate(is_protected=Exists(GeneratedBet.objects.filter(game=OuterRef('game'), contest=OuterRef('contest'), notification__isnull=False))).filter(is_protected=False)`, apaga (`.delete()`, usando a contagem real do retorno, não uma contagem separada) e mostra `self.message_user(...)`.
- `apps/loterias_core/admin.py::PurgeUntilDateForm.clean_cutoff_date` (**novo**, ajuste da revisão) -- rejeita `cutoff_date >= timezone.localdate()` (hoje ou futuro), evitando que a purga também apague resultados recém-capturados.
- `templates/admin/loterias_core/lotteryresult/purge_until_date.html` (**novo**) -- estende `admin/base_site.html`, formulário com o campo de data, campos ocultos `action`/`_selected_action` reembutidos (ajuste crítico da revisão -- sem eles o fluxo real de 2 requests do navegador nunca disparava a purga de verdade), link "Cancelar" via `{% url %}` (não um caminho relativo hard-coded), e um aviso explícito de que a seleção de linhas é ignorada e que resultados com `HitNotification` associada são protegidos.
- `apps/loterias_core/tests.py` -- novos testes: (1) `LotteryResult` aparece na lista de admin (smoke test, mesmo padrão de `AdminSmokeTests`); (2) a ação existe e está registrada; (3) GET na ação (sem `apply`) renderiza a tela intermediária sem apagar nada; (4) POST com data de corte apaga só os `LotteryResult` com `captured_at` anterior à data e sem `HitNotification` associada; (5) um `LotteryResult` mais antigo que a data mas com `HitNotification` associada (via `GeneratedBet` do mesmo game+contest) sobrevive à purga; (6) `PrizeTier` e `GeneratedBet` não são afetados pela purga; (7) nenhum `LotteryResult` é apagado sem a ação ser executada manualmente (confirma que não há purge automático); (8) a purga aplica-se a todos os `LotteryResult` elegíveis, não só aos selecionados na changelist.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/admin.py::LotteryResultAdmin` + `PurgeUntilDateForm` + `purge_until_date` -- novo registro e ação
- [x] `templates/admin/loterias_core/lotteryresult/purge_until_date.html` -- tela intermediária de confirmação
- [x] `apps/loterias_core/tests.py` -- 21 casos novos (Code Map original + reforços críticos da revisão)

**Critérios de Aceite:**
- Dado que estou logado no painel de administração do Django, quando acesso a lista de `LotteryResult`, então existe uma ação "Purge até a data" que recebe uma data de corte e apaga os registros capturados antes dela
- E por padrão, nenhum `LotteryResult` é apagado automaticamente -- a retenção é integral até uma purga manual ser executada
- E a ação de purge não afeta os `PrizeTier` nem os `GeneratedBet` dos usuários
- E a ação de purge nunca apaga em cascata as `HitNotification` associadas -- um `LotteryResult` com pelo menos uma `HitNotification` (lida ou não) é protegido da purge, preservando o histórico de prêmios do usuário

## Notas de Implementação

Implementação inicial conforme o Code Map original: `LotteryResultAdmin` (nunca registrado antes), `PurgeUntilDateForm`, a ação `purge_until_date` com a tela intermediária, e a proteção via `Exists` correlacionada por `game`+`contest`.

A revisão em 3 camadas encontrou dois bugs críticos, ambos verificados **empiricamente** pelo Blind Hunter (rodando o fluxo real, não só lendo o código):

1. **A purga nunca disparava de verdade pelo navegador.** O template da tela intermediária não reembutia `action`/`_selected_action` como campos ocultos -- exatamente o que o `changelist_view` do Django exige pra chamar a action de novo no segundo POST (mesmo padrão do `delete_selected_confirmation.html` nativo). Sem isso, o segundo POST (só com `apply`+`cutoff_date`, do jeito que um formulário real geraria) caía fora das duas branches de despacho de `response_action` e o admin simplesmente recarregava a changelist normal -- **sem erro, sem mensagem, sem apagar nada**. Todos os 8 testes originais passavam porque cada um mandava `action`+`_selected_action`+`apply`+`cutoff_date` juntos num único POST -- um payload que um navegador de verdade nunca produziria em uma única requisição. Corrigido reembutindo os campos ocultos no template e passando `selected_pks`/`action_checkbox_name` no contexto; um teste novo (`test_full_two_step_browser_flow_actually_purges`) reproduz os 2 requests HTTP separados de verdade (o primeiro extrai os campos ocultos do HTML renderizado, como um navegador faria) e comprova a purga de ponta a ponta.

2. **A ação não exigia permissão de delete.** `@admin.action(...)` sem `permissions=[...]` inclui a ação pra qualquer staff que consiga acessar a changelist (só permissão de `view`/`change`), sem checar `has_delete_permission`. Um usuário de auditoria/leitura conseguia apagar em massa. Corrigido com `permissions=['delete']`; teste `test_staff_without_delete_permission_cannot_purge` confirma que um staff só com `view_lotteryresult` não consegue mais executar a purga.

Também corrigidos, achados menores mas reais: (3) o link "Cancelar" usava um caminho relativo hard-coded (`href="../"`) que resolvia pro índice do app, não pra changelist -- trocado por `{% url 'admin:loterias_core_lotteryresult_changelist' %}`; (4) a mensagem de sucesso usava uma contagem (`.count()`) calculada antes do `.delete()` em vez do retorno real de `.delete()` -- trocado pra usar `deleted_count, _ = candidates.delete()` diretamente, eliminando qualquer chance de a mensagem divergir do que foi de fato apagado; (5) adicionado `PurgeUntilDateForm.clean_cutoff_date` rejeitando data de hoje ou futura -- sem isso, um erro de digitação na data apagaria resultados recém-capturados junto (achado do Edge Case Hunter).

A fragilidade de `GeneratedBet.contest`/`LotteryResult.contest` não serem normalizados (zeros à esquerda, já documentada desde a Story 2.1) foi reencontrada pelo Edge Case Hunter como um risco herdado pela proteção desta story (casamento por igualdade textual exata) -- não corrigida aqui (normalização de `contest` é mudança cross-cutting, story própria), cross-referenciada em `deferred-work.md`.

## Log de Triagem da Revisão

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) rodada em paralelo sobre o diff da implementação inicial (~10,6 kB, N=4 pro Blind Hunter). Achados e disposição:

**Corrigidos:**
- (Blind Hunter, crítico, comprovado empiricamente) Template não reembutia `action`/`_selected_action` -- a purga nunca disparava pelo fluxo real de 2 requests do navegador. Corrigido; novo teste reproduz o fluxo real de ponta a ponta.
- (Blind Hunter, crítico, comprovado empiricamente) Ação sem `permissions=['delete']` -- qualquer staff com view/change conseguia purgar. Corrigido; novo teste com staff view-only confirma o bloqueio.
- (Blind Hunter) Link "Cancelar" resolvia pra URL errada (`href="../"`) -- trocado por `{% url %}`.
- (Edge Case Hunter) `cutoff_date` sem teto superior -- data de hoje/futura apagaria resultados recém-capturados. Corrigido com `clean_cutoff_date`.
- (Verification Gap Reviewer) `deleted_count` calculado via `.count()` separado do `.delete()` -- podia divergir da mensagem exibida em teoria. Corrigido usando o retorno de `.delete()` diretamente.
- (Verification Gap Reviewer) `test_action_without_apply_shows_confirmation_and_deletes_nothing` só verificava `status_code == 200` (indistinguível de uma falha silenciosa) -- reforçado com `assertContains` no campo de data e no nome da ação.
- (Verification Gap Reviewer) Nenhum teste verificava a mensagem de sucesso exibida ao operador -- adicionado `test_success_message_reports_the_real_deleted_count`.
- (Verification Gap Reviewer) Faltava teste de proteção por PAR com múltiplos `GeneratedBet` (só um com notificação) -- adicionado `test_purge_protects_pair_even_when_only_one_of_several_bets_has_a_notification`.
- (Verification Gap Reviewer) "Par sem nenhum `GeneratedBet`" só era coberto como efeito colateral de outro teste -- nomeado explicitamente em `test_pair_with_no_generatedbet_at_all_is_eligible_for_purge`.
- (Blind Hunter) A suíte original era estruturalmente incapaz de detectar o bug do fluxo de 2 passos (todos os testes enviavam tudo num único POST) -- resolvido junto com o próprio bug crítico #1.

**Aceitos como corretos (falsos positivos ou já cobertos):**
- Edge Case Hunter confirmou que proteção por par funciona independente de `is_read`, que um form inválido (data vazia/malformada) não apaga nada, que `PrizeTier`/`GeneratedBet` genuinamente não têm FK pra `LotteryResult` (sem cascata a evitar), e que a interação com `update_monthly_prize_values`/`fetch_daily_results` rodando perto no tempo não deixa dado órfão.
- Blind Hunter confirmou que confirmar a ação sem nenhum checkbox marcado é bloqueado nativamente pelo Django antes mesmo de chamar a action, e que a comparação de fuso horário (`timezone.make_aware` com `America/Sao_Paulo`) está correta.

**Deferidos (registrados em `deferred-work.md`, não bloqueiam esta story):**
- Fragilidade de `contest` sem normalização (zeros à esquerda) herdada pela proteção via `Exists` -- já documentada desde a Story 2.1, cross-referenciada com o achado específico desta story.

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- nenhuma migration pendente (nenhuma mudança de model nesta story).
- `python manage.py check` -- sem erro novo (só o warning pré-existente de `STATICFILES_DIRS`).
- `python manage.py test apps.loterias_core.tests.LotteryResultPurgeAdminTests` -- **13 testes, 100% passando**, incluindo os 2 testes de regressão crítica (`test_full_two_step_browser_flow_actually_purges`, `test_staff_without_delete_permission_cannot_purge`).
- `python manage.py test apps.loterias_core` -- **212 testes, 100% passando**.
- `python manage.py test` -- **232 testes, 100% passando** (suíte completa do projeto, nenhuma regressão).
