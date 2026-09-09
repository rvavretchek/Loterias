---
title: 'Preferência de canal de notificação'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '217a8b6994bf44158479e8f3eac6d98f30e4c98a'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Não existe hoje nenhum jeito do usuário controlar como quer ser avisado de um acerto — a Story 2.7 (envio de e-mail) vai precisar dessa preferência pra decidir se dispara e-mail ou não, mas o model e a tela ainda não existem.

**Approach:** Criar o model `NotificationPreference` (`apps/loterias_core/models.py`, AD-3): `OneToOneField` pra `User`, `site_enabled` (default `True`) e `email_enabled` (default `False`). Uma tela nova de preferências (formulário simples com 2 checkboxes) que lê a preferência atual via `get_or_create` (a ausência de linha é lida como os defaults, sem contar como "escrita do usuário" — AD-3) e salva a mudança. Validação: desativar os dois canais ao mesmo tempo é bloqueado com mensagem clara — pelo menos um precisa ficar ativo.

## Fronteiras e Restrições

**Sempre:**
- `NotificationPreference.user` é `OneToOneField` — no máximo 1 preferência por usuário (AD-3).
- Ausência de linha pro usuário é lida como os defaults (`site_enabled=True`, `email_enabled=False`) — o `get_or_create` de leitura não conta como escrita do usuário pra efeito da convenção "`NotificationPreference` só é escrito pela própria tela de preferências" (AD-3/Consistency Conventions).
- Mudar a preferência nunca recria ou reprocessa notificações passadas — só afeta a exibição/envio dali pra frente.
- Validação de "pelo menos 1 canal ativo" acontece no `clean()` do **model** (não do form) — assim vale pra qualquer caminho de escrita (a própria tela, o Django admin, um script futuro), não só quando passa pelo form da tela de preferências. Reforçada por uma `CheckConstraint` no banco como backstop (`Model.save()` não chama `full_clean()` sozinho — sem a constraint, um `.objects.create()` direto contornaria a validação Python).
- `site_enabled=False` tem efeito real e imediato: o badge (Story 2.4, `notifications_context`) para de contar/mostrar notificações não lidas pra esse usuário. Sem isso, desmarcar a caixa não mudaria nada pro usuário, contrariando o propósito da própria story ("escolher... se recebo avisos... no site").
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não implementar o envio de e-mail em si (Story 2.7) — essa story só guarda a preferência; `email_enabled` ainda não é consumido por nenhum código de envio.
- Não criar um segundo model/campo pra "conta pendente"/estado — só os 2 booleans já descritos.
- Não mexer em `HitNotification`/`fetch_daily_results` (Stories 2.3/2.1) — a preferência não influencia a **geração** da notificação (isso continua acontecendo sempre, independente da preferência), só a **exibição**/envio.
- Não esconder a tela de notificações (`notifications_view`, Story 2.5) quando `site_enabled=False` — só o badge (aviso proativo) é afetado; a lista continua acessível por navegação direta, e "marcar como lida" continua funcionando independente da preferência.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py` -- novo model `NotificationPreference`: `user` (`OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preference', verbose_name='Usuario')`), `site_enabled` (`BooleanField(default=True, verbose_name='Aviso no site')`), `email_enabled` (`BooleanField(default=False, verbose_name='Aviso por e-mail')`).
- `apps/loterias_core/migrations/0003_notificationpreference.py` (**novo**, via `makemigrations`).
- `apps/loterias_core/forms.py` (**novo arquivo** -- não existe form.py em `loterias_core` ainda, só em `accounts`) -- `NotificationPreferenceForm(forms.ModelForm)`: `Meta.model = NotificationPreference`, `fields = ['site_enabled', 'email_enabled']`; `clean()` levanta `ValidationError` clara se `site_enabled` e `email_enabled` vierem os dois `False`.
- `apps/loterias_core/views.py::notification_preferences_view` (**novo**) -- `@login_required`; `GET`: `preference, _ = NotificationPreference.objects.get_or_create(user=request.user)`, monta o form com essa instância; `POST`: valida e salva, `messages.success`; renderiza `loterias_core/preferencias_notificacao.html`.
- `apps/loterias_core/urls.py` -- nova rota `path('notificacoes/preferencias/', views.notification_preferences_view, name='notification_preferences')`.
- `templates/loterias_core/preferencias_notificacao.html` (**novo**) -- formulário simples com os 2 checkboxes e botão salvar.
- `templates/loterias_core/notificacoes.html` -- link "Preferências" no cabeçalho da tela, apontando pra `notification_preferences`.
- `apps/loterias_core/admin.py` -- registro simples de `NotificationPreference` (mesmo padrão de `HitNotificationAdmin`).
- `apps/loterias_core/tests.py` -- novos testes: (1) primeiro acesso sem preferência configurada mostra os defaults (site ativo, e-mail desativado) sem gravar nada até o usuário salvar (ou grava via `get_or_create` mas isso não é uma "mudança do usuário" -- confirmar que não aparece nenhuma mensagem de "salvo" no GET); (2) salvar com só site ativo funciona; (3) salvar com só e-mail ativo funciona; (4) salvar com os dois ativos funciona; (5) tentar salvar com os dois desativados é bloqueado, com mensagem clara, e a preferência anterior não é sobrescrita; (6) mudar a preferência não cria/altera nenhuma `HitNotification` existente; (7) rota exige login; (8) `NotificationPreference` é única por usuário (unicidade do `OneToOneField`, mesmo padrão de teste do `HitNotification.bet`).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/models.py::NotificationPreference` -- novo model conforme Code Map, + `CheckConstraint` e `clean()` (achado na revisão: validação só no form não protege admin/scripts)
- [x] `apps/loterias_core/migrations/0003_notificationpreference.py` -- via `makemigrations` (inclui a constraint)
- [x] `apps/loterias_core/forms.py::NotificationPreferenceForm` -- novo arquivo (validação delegada ao `model.clean()`, não duplicada aqui)
- [x] `apps/loterias_core/views.py::notification_preferences_view` -- nova view
- [x] `apps/loterias_core/urls.py` -- rota `notification_preferences`
- [x] `templates/loterias_core/preferencias_notificacao.html` -- novo template
- [x] `templates/loterias_core/notificacoes.html` -- link pra preferências
- [x] `apps/loterias_core/admin.py` -- registro de `NotificationPreference`
- [x] `apps/loterias_core/context_processors.py::notifications_context` -- respeita `site_enabled` (achado na revisão, corrigindo escopo mal definido no Fronteiras original)
- [x] `apps/loterias_core/tests.py` -- 8 casos do Code Map + 15 casos adicionais da revisão

**Critérios de Aceite:**
- Dado que o usuário acessa a tela de preferências de notificação pela primeira vez, quando ele ainda não configurou nada, então o default é notificação no site ativa e e-mail desativado
- Dado que o usuário já tem uma preferência configurada, quando ele altera essa preferência, então a mudança não recria notificações passadas — só afeta notificações futuras
- Dado que o usuário tenta desativar tanto o site quanto o e-mail ao mesmo tempo, quando ele salva essa configuração, então o sistema bloqueia com uma mensagem clara — pelo menos um canal precisa continuar ativo

## Notas de Implementação

**Correção de escopo achada por mim mesmo ao revisar a própria spec (antes mesmo da revisão em 3 camadas):** a versão original das Fronteiras dizia "a preferência não influencia a geração da notificação, só o canal de aviso (decisão que fica pra Story 2.7)" -- isso escondia um erro: o canal **site** também precisa ter efeito imediato nesta story (só o **e-mail** de fato depende da Story 2.7 pra ter efeito). Sem consultar `site_enabled` em algum lugar, desmarcar essa caixa não mudaria nada pro usuário -- exatamente o tipo de "regra que não se sustenta na prática" que já foi corrigido antes nesta mesma sessão (Story 2.3, prêmio de 0 acertos da Lotomania). Corrigido: `notifications_context` (o badge, Story 2.4) agora consulta `NotificationPreference.site_enabled` e zera a contagem quando desativado. A lista de notificações (`notifications_view`, Story 2.5) continua sempre acessível por navegação direta -- só o aviso proativo (badge) é afetado.

A revisão em 3 camadas achou um segundo problema real: a validação "pelo menos 1 canal ativo" só existia no `clean()` do form da tela de preferências -- o Django Admin usa seu próprio `ModelForm` gerado automaticamente pra `NotificationPreference`, que não herda essa validação. Um admin conseguiria salvar os 2 canais desativados direto pela tela de admin, sem bloqueio nenhum. Corrigido movendo a validação pro `NotificationPreference.clean()` (o model, não o form) -- `full_clean()` do Django chama `Model.clean()` automaticamente em qualquer `ModelForm`, inclusive o do admin, então a regra passa a valer nos dois lugares sem duplicar código. Reforçado ainda com uma `CheckConstraint` no banco, já que `Model.save()` não chama `full_clean()` sozinho (gotcha conhecido do Django) -- um `.objects.create()` direto (script, data migration futura) ainda contornaria a validação Python, mas não a constraint do banco.

(Tentativa inicial: colocar `form = NotificationPreferenceForm` no `NotificationPreferenceAdmin`, mas isso fez o campo `user` sumir do formulário de admin -- porque `NotificationPreferenceForm.Meta.fields` não inclui `user`, e o admin usa o form informado como base pros campos exibidos. Verificado ao vivo com um GET real na tela de admin antes de descartar essa abordagem.)

Suíte final: 171 testes no projeto inteiro (era 159 no fim da Story 2.5) -- 100% passando.

## Log de Triagem da Revisão

**Patches aplicados:**
1. `site_enabled=False` não tinha nenhum efeito -- corrigido escopo, badge agora consulta a preferência. *(Achado por mim mesmo ao revisar a spec antes da revisão formal)*
2. Validação "pelo menos 1 canal" só no form da tela, não no admin -- movida pro `model.clean()` + `CheckConstraint` no banco. *(Blind Hunter + Edge Case Hunter, achado independente)*
3. `require_http_methods(['GET', 'POST'])` adicionado à view, por consistência com `mark_notification_read_view` (que já usa `@require_POST`). *(Blind Hunter)*
4. 15 testes novos cobrindo os gaps achados pela Verification Gap Reviewer e pelos outros 2 revisores: smoke test do admin (list + add form com `user` presente + bloqueio de validação), link "Preferências" testado indiretamente via rota, texto exato da mensagem de validação, mensagem de sucesso após salvar (com `follow=True`), estado real dos checkboxes no HTML renderizado (`checked`/não `checked`), isolamento entre usuários na view de preferências, POST anônimo, badge zerado/mantido conforme `site_enabled`, `clean()` do model rejeitando os 2 desativados, `CheckConstraint` rejeitando via `.objects.create()` direto (bypass do `full_clean()`).

**Adiado (`deferred-work.md`, 2 itens):** concorrência entre 2 abas salvando preferências diferentes quase ao mesmo tempo ("last write wins" sem aviso, mesmo padrão já adiado em Stories 2.2/2.5); linha de `NotificationPreference` materializada por um GET incidental não se distingue de uma escolha real do usuário (decisão de design já aceita pelo spec original, que proíbe campo de estado extra).

**Falso positivo (sem ação):** re-renderizar o form com os valores inválidos do POST (não os valores salvos) quando a validação falha -- comportamento padrão e esperado de qualquer `ModelForm` do Django (mostrar de volta o que o usuário submeteu), não um bug.

## Verificação

**Comandos executados:**
- `python manage.py makemigrations --check --dry-run` -- nenhuma migration pendente
- `python manage.py test apps.loterias_core` -- 151 testes, 100% passando
- `python manage.py test` (suíte completa) -- 171 testes, 100% passando
- `python manage.py check` -- sem erro novo
- Verificação manual ao vivo (fora dos testes automatizados): confirmado via GET/POST reais no admin que o campo `user` está presente e a validação bloqueia os 2 canais desativados
