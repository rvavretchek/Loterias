---
title: 'Novo fluxo de cadastro (Epic 3 completo -- Stories 3.1 a 3.5)'
type: 'feature'
created: '2026-09-09'
status: 'review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '48d5150e24393a0bef5b616ace9259fddd708c21'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O cadastro atual (`CustomSignupForm`) pede nome, sobrenome, e-mail e senha (2x) tudo de uma vez, na tela genérica do allauth -- exatamente o oposto do que a PRD/`epics.md` descreve pra Epic 3. Achado ao vivo pelo usuário testando o site após o deploy do Epic 2.

**Approach:** As 5 stories de `epics.md` (3.1-3.5) descrevem uma única jornada contínua (UJ-2: cadastro só com e-mail → confirmação → criação de senha → login → nome/sobrenome → home) e são tecnicamente inseparáveis -- a tela pós-cadastro (3.1) já precisa do botão de reenvio (3.2), a tela de confirmação já precisa saber pra onde redirecionar (3.3), o link expirado (3.4) reusa o mesmo botão de reenvio (3.2), e o nome/sobrenome (3.5) só faz sentido depois que a senha já foi definida (3.3). Por isso esta spec cobre o épico inteiro como uma unidade, em vez de 5 ciclos de revisão isolados -- o próprio critério de aceite de fechamento da Story 3.5 já pede um smoke test da UJ-2 inteira numa passada só.

**Decisões de design descobertas durante a investigação (iguais em espírito às da Story 2.8/2.9: preferir mecanismo já existente e testado a reinventar):**

- **Criação de senha (3.3) reaproveita o fluxo de "esqueci minha senha" já existente do allauth** (`PasswordResetFromKeyView`, token `uidb36`+`key`, template `password_reset_from_key.html` já existente no projeto) em vez de uma tela nova do zero -- é literalmente a mesma UX (senha + confirmação, define e loga). A única diferença da Story 3.3 é o aceite dos termos, que só aparece quando o usuário ainda não tem senha usável (`not user.has_usable_password()`) -- resolvido com um form customizado (`InitialOrResetPasswordKeyForm`) registrado via `ACCOUNT_FORMS['reset_password_from_key']`, sem subclassar a view (evita reimplementar a lógica de anti-vazamento de token via Referer que a view original já tem).
- **Redirecionamento pós-confirmação (3.3)** via `CustomAccountAdapter.get_email_verification_redirect_url` (hook atual do allauth 0.63, não o `get_email_confirmation_redirect_url` antigo/depreciado): se `not user.has_usable_password()`, gera um token de reset via `default_token_generator`/`user_pk_to_url_str` (mesmas funções que a própria `PasswordResetFromKeyView` usa) e redireciona pra lá; senão, redireciona pro login com mensagem "cadastro já confirmado" (resolve as duas situações da Story 3.3 e o caso do link expirado ser uma questão à parte, ver abaixo).
- **Vínculo expirado (3.4)** já é o comportamento nativo do allauth quando a chave HMAC de confirmação (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=3`, já configurado) expira ou é inválida -- `ConfirmEmailView` renderiza `email_confirm.html` com `object=None` nesse caso (não há redirecionamento a considerar). O template só precisava ser reescrito pra mostrar essa mensagem + botão de reenvio, já que hoje mostra um formulário de "clique pra confirmar" que nunca é o caminho real percorrido (`ACCOUNT_CONFIRM_EMAIL_ON_GET=True` já confirma direto no GET).
- **Reenvio com limite (3.2) reaproveita o rate limiter nativo do allauth** (`allauth.core.ratelimit`, ação `confirm_email`, já embutido em `should_send_confirmation_mail`/`send_email_confirmation`) via `ACCOUNT_RATE_LIMITS = {'confirm_email': '1/60s/key,5/1d/key'}` -- sem precisar de nenhum campo novo em `User` pra rastrear reenvio. Achado importante: esse rate limiter usa o cache padrão do Django (`django.core.cache.cache`), e o projeto não tinha `CACHES` configurado (cai no `LocMemCache`, por processo -- com 3 workers do gunicorn, o limite seria inconsistente/mais fraco que o configurado). Corrigido configurando `CACHES` com `DatabaseCache` (sem precisar de Redis, que já foi removido do projeto na Story 2.1) + `python manage.py createcachetable` no `Dockerfile`.
- **Anti-enumeração (3.1, 2º AC)** já é o comportamento padrão do allauth 0.63 (`ACCOUNT_PREVENT_ENUMERATION` default `True`) -- setting adicionada explicitamente só pra deixar a decisão documentada, sem mudança de comportamento real.
- **Gate de nome/sobrenome (3.5)** via `RequireCompleteAccountMiddleware` novo + campo `User.profile_completed` (`default=False` pra contas novas; migration de dados marca `True` pra toda conta que já existir no momento do deploy -- grandfather clause exigido pelo AC).
- **E-mail de boas-vindas** (`apps/accounts/signals.py`, pré-existente) disparava incondicionalmente na criação do `User` -- com o novo fluxo, a conta é criada com senha inutilizável (pendente), então o e-mail "sua conta foi criada com sucesso, acesse agora" chegaria ao mesmo tempo que o e-mail de confirmação, sobre uma conta que ainda não pode ser usada. Corrigido: o sinal só dispara na criação se `has_usable_password()` já for `True` naquele momento (cobre `createsuperuser`/criação administrativa direta, inalterado); pro fluxo público novo, o mesmo e-mail é disparado explicitamente quando a senha é definida pela primeira vez (dentro de `InitialOrResetPasswordKeyForm.save()`).

## Fronteiras e Restrições

**Sempre:**
- `ACCOUNT_SIGNUP_FIELDS` pede só e-mail -- nenhum campo de senha nem nome/sobrenome na tela de cadastro.
- A conta criada no cadastro tem senha inutilizável (`set_unusable_password()`, comportamento padrão do allauth quando não há `password1` no form) até a Story 3.3 ser concluída.
- Cadastro com e-mail já existente (pendente ou confirmado) mostra a mesma tela genérica de "verifique seu e-mail" -- nenhuma conta duplicada, nenhuma pista de que a conta já existe.
- `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False` -- confirmar o e-mail nunca loga automaticamente antes da senha ser definida.
- O aceite dos termos de serviço só é exigido quando `not user.has_usable_password()` no momento em que a tela de definição de senha é aberta -- uma redefinição de senha genuína (usuário já ativo) nunca precisa reaceitar termos.
- `RequireCompleteAccountMiddleware` nunca bloqueia staff/superuser nem qualquer rota `/admin/`.
- Usuários que já existiam antes desta mudança (`profile_completed=True` via migration de dados) nunca são pegos pelo gate de nome/sobrenome.
- Identificadores de código em inglês, sem exceção -- convenção já estabelecida.

**Nunca:**
- Não reimplementar manualmente o rate limiting de reenvio nem o fluxo de definição de senha -- reusar os mecanismos nativos do allauth já testados (ver Decisões acima).
- Não introduzir Redis/Celery pro cache do rate limiter -- `DatabaseCache` é suficiente e consistente com a decisão já tomada na Story 2.1 de não depender de infra externa.
- Não mudar o comportamento de login/"esqueci minha senha" de usuários já confirmados antes desta mudança -- ambos continuam funcionando exatamente como antes.

</frozen-after-approval>

## Code Map

- `loterias/settings/base.py` -- `ACCOUNT_SIGNUP_FIELDS = ['email*']`; `ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE = False`; `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False`; `ACCOUNT_PREVENT_ENUMERATION = True` (explícito); remove `ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE` (morto, sem campo de senha no cadastro); `ACCOUNT_RATE_LIMITS = {'confirm_email': '1/60s/key'}` -- **só a regra de cooldown** (ver Notas de Implementação pro motivo de o limite diário ter sido movido pra fora do rate limiter nativo); `ACCOUNT_FORMS` ganha `'signup': 'apps.accounts.forms.CustomSignupForm'` e `'reset_password_from_key': 'apps.accounts.forms.InitialOrResetPasswordKeyForm'`; `CACHES` novo (`DatabaseCache`, tabela `django_cache_table`); `MIDDLEWARE` ganha `apps.accounts.middleware.RequireCompleteAccountMiddleware` (depois de `AuthenticationMiddleware`).
- `Dockerfile` -- `CMD` roda `migrate && createcachetable && collectstatic && gunicorn`. `deploy/lab/docker-compose.yml::loterias-cron` **não** roda `createcachetable` (só `loterias-web` faz, pra evitar corrida de duas execuções simultâneas de `createcachetable` contra o mesmo SQLite compartilhado -- ver Notas de Implementação).
- `apps/accounts/models.py::User.profile_completed` (**novo campo**, `BooleanField(default=False)`); `UserManager.create_user()` ganha `extra_fields.setdefault('profile_completed', True)` (só o manager -- o fluxo público de cadastro constrói o `User` direto via adapter do allauth e nunca passa por aqui).
- `apps/accounts/migrations/0002_user_profile_completed.py` (**novo**) -- `AddField` + `RunPython` marcando `profile_completed=True` pra toda conta já existente (grandfather clause).
- `apps/accounts/forms.py::CustomSignupForm` -- simplificado pra só o campo `email` (remove `password1`/`password2` explicitamente no `__init__`, ver Notas); `InitialOrResetPasswordKeyForm(ResetPasswordKeyForm)` (**novo**) -- adiciona `terms_accepted` (BooleanField required) só quando `self.user` ainda não tem senha usável **e** `last_login is None` (checagem composta, ver Notas); `save()` sobrescrito chama `super().save()` e, se era o fluxo inicial, dispara o e-mail de boas-vindas; `ProfileCompletionForm(forms.ModelForm)` (**novo**) -- `first_name`/`last_name` obrigatórios, marca `profile_completed=True` no `save()`.
- `apps/accounts/adapter.py::CustomAccountAdapter` -- `get_email_verification_redirect_url(self, email_address)` (**novo**, sobrescreve) -- se o usuário logado é o próprio dono do e-mail confirmado, delega pro `super()` (evita regressão na confirmação de e-mail secundário de quem já está logado); senão, gera link de definição de senha (`default_token_generator`/`user_pk_to_url_str`) se `not user.has_usable_password()`, senão redireciona pro login com mensagem "cadastro já confirmado". Não há mais `respond_email_verification_sent` no adapter -- o e-mail da sessão é guardado direto em `CustomSignupView.form_valid()` (ver Notas, achado da revisão sobre vazamento de enumeração).
- `apps/accounts/views.py::CustomSignupView(SignupView)` (**novo**) -- guarda `request.session['pending_signup_email']` no `form_valid()`, antes de qualquer processamento do allauth. `ResendConfirmationEmailView` (**novo**, `View`, só POST) -- lê `email` do POST ou da sessão; se existir `User`, aplica um limite diário próprio (`RESEND_DAILY_LIMIT = 5`, cache key dedicada por e-mail, independente do rate limiter do allauth) antes de chamar `send_email_confirmation(request, user, signup=False, email=email)`; sempre mostra a mesma mensagem genérica (anti-enumeração). `ProfileCompletionView` (**novo**, `LoginRequiredMixin` + `FormView`) -- formulário de nome/sobrenome, valida `next` contra open redirect (`url_has_allowed_host_and_scheme`) antes de redirecionar, senão cai pra home.
- `apps/accounts/middleware.py` (**novo arquivo**) -- `RequireCompleteAccountMiddleware`: pra usuário autenticado, não-staff, não-superuser, com `profile_completed=False`, fora de `/admin/`/`/static/`/`/media/` e das rotas exentas (`complete_profile`, `account_logout`, `toggle_theme` -- essa última descoberta na revisão, ver Notas), redireciona pra `complete_profile?next=<path original>`.
- `apps/accounts/urls.py` -- novas rotas `confirm-email/resend/` (`resend_confirmation`) e `complete-profile/` (`complete_profile`).
- `apps/accounts/signals.py::send_welcome_email` -- lógica de envio extraída pra função reutilizável, chamada tanto pelo sinal `post_save` (só dispara na criação se `instance.has_usable_password()` já for `True` -- cobre `createsuperuser`/admin) quanto explicitamente por `InitialOrResetPasswordKeyForm.save()` quando a senha é definida pela primeira vez.
- `templates/accounts/signup.html` -- simplificado (só o campo e-mail).
- `templates/account/verification_sent.html` -- usa `request.session.pending_signup_email`; adiciona form de reenvio (POST pra `resend_confirmation`).
- `templates/account/email_confirm.html` -- reescrito com `{% if confirmation %}...{% else %}` pra mostrar "vínculo expirado/inválido" + o mesmo form de reenvio no caminho real (`object=None`).
- `templates/account/password_reset_from_key.html` -- alternância mostrar/ocultar senha (JS inline) e, condicionalmente (`'terms_accepted' in form.fields`), checkbox de aceite dos termos + título "Criar senha"; branch `{% if token_fail %}`.
- `templates/accounts/complete_profile.html` (**novo**) -- formulário de nome/sobrenome.
- `apps/accounts/tests.py` -- 58 testes novos/estendidos cobrindo todo o Code Map acima (classes `SignupFlowTests`, `EmailVerificationRedirectTests`, `InitialPasswordCreationTests`, `ResendConfirmationEmailTests`, `ExpiredConfirmationLinkTests`, `RequireCompleteAccountMiddlewareTests`, `ProfileCompletedDataMigrationTests`, `FullSignupJourneyTests` -- essa última percorre a UJ-2 inteira numa passada só, extraindo o link de confirmação real de `mail.outbox`).

## Tarefas e Aceite

**Execução:**
- [x] `loterias/settings/base.py` -- todas as settings novas/alteradas
- [x] `Dockerfile` -- `createcachetable`
- [x] `apps/accounts/models.py` + migration -- `profile_completed`
- [x] `apps/accounts/forms.py` -- `CustomSignupForm` simplificado, `InitialOrResetPasswordKeyForm`, `ProfileCompletionForm`
- [x] `apps/accounts/adapter.py` -- redirecionamentos e stash de sessão
- [x] `apps/accounts/views.py` -- `ResendConfirmationEmailView`, `ProfileCompletionView`
- [x] `apps/accounts/middleware.py` -- `RequireCompleteAccountMiddleware`
- [x] `apps/accounts/urls.py` -- novas rotas
- [x] `apps/accounts/signals.py` -- condição de senha usável
- [x] Templates (signup, verification_sent, email_confirm, password_reset_from_key, complete_profile)
- [x] `apps/accounts/tests.py` -- casos do Code Map

**Critérios de Aceite:** (consolidados de `epics.md`, Stories 3.1-3.5)
- Cadastro pede só e-mail; conta pendente criada com senha inutilizável; e-mail de confirmação enviado; tela pós-envio orienta checar e-mail/spam e oferece reenvio
- E-mail já cadastrado mostra a mesma tela genérica, sem duplicar conta nem revelar existência prévia
- Reenvio: novo vínculo gerado, botão desabilitado 60s (rate limit real), limite de 5/dia orienta tentar amanhã sem travar a conta
- Clicar no vínculo válido abre tela de senha + confirmação (mostrar/ocultar) + aceite de termos; termos não aceitos não conclui; ao confirmar, senha definida, login automático, conta passa a logar normalmente
- Clicar de novo num vínculo já usado mostra "cadastro já confirmado, faça login" -- distinto de vínculo expirado
- Vínculo expirado mostra mensagem clara + botão de reenvio; conta nunca fica "perdida pra sempre"; vínculo vencido nunca autentica
- Primeiro login após definir senha exige nome/sobrenome antes de qualquer outra tela; staff/admin nunca são pegos; usuários pré-existentes nunca são pegos; não aparece de novo em logins seguintes
- Usuário já confirmado antes desta mudança continua logando/resetando senha exatamente como antes

## Notas de Implementação

- **`SignupForm.__init__` do allauth adiciona `password1` incondicionalmente**, independente de `ACCOUNT_SIGNUP_FIELDS` (essa setting só controla campos tipo email/username nesta versão) -- `CustomSignupForm` precisa remover `password1`/`password2` manualmente (`self.fields.pop(...)`) pra virar cadastro só-com-email de verdade. `DefaultAccountAdapter.save_user` já chama `set_unusable_password()` sozinho quando não há `password1` no `cleaned_data`, então nenhuma sobrescrita de `save_user` foi necessária.
- **Reaproveitamento deliberado do fluxo de "esqueci minha senha"** (`PasswordResetFromKeyView`) pra criação de senha inicial (3.3), em vez de uma tela nova -- mesma UX, evita reimplementar a lógica de anti-vazamento de token via Referer que a view original já tem (o primeiro GET com a chave real é trocado por sessão + redirect pra `.../set-password/`). Resolvido via `ACCOUNT_FORMS['reset_password_from_key']` customizado, sem subclassar a view.
- **Falha crítica de design encontrada na revisão: o rate limiter nativo do allauth (`allauth.core.ratelimit`) não suporta combinar duas regras pra a mesma ação/chave.** `_cache_key()` monta a chave só com `action`+`source` (sem a taxa/duração da regra), então múltiplas regras configuradas pra `confirm_email` (`'1/60s/key,5/1d/key'`) compartilhavam UM ÚNICO histórico de timestamps no cache -- um clique impaciente dentro do cooldown de 60s ainda inseria um timestamp que a regra diária via, esgotando a cota de 5/dia sem nenhum e-mail extra ser enviado; e o TTL final do cache era decidido pela ÚLTIMA regra processada (ordem de string), não pela mais restritiva. Confirmado empiricamente por um reviewer (Edge Case Hunter) rodando o cenário, não só por leitura do código. **Correção:** `ACCOUNT_RATE_LIMITS` ficou só com a regra de cooldown (`'1/60s/key'`); o limite diário de 5 envios foi implementado em código de aplicação (`ResendConfirmationEmailView`), com sua própria cache key dedicada por e-mail, totalmente independente do histórico do allauth.
- **Vazamento de enumeração encontrado na revisão:** a primeira versão guardava o e-mail pendente na sessão via `adapter.respond_email_verification_sent(request, user)` -- mas o próprio `try_save()` do allauth chama esse hook com `user=None` no branch anti-enumeração (`ACCOUNT_PREVENT_ENUMERATION=True`, e-mail já existente), o que também tornava a mensagem pós-cadastro capaz de distinguir os dois casos indiretamente. Corrigido guardando o e-mail *submetido* (não o `user`) direto em `CustomSignupView.form_valid()`, antes de qualquer lógica do allauth rodar -- elimina a dependência do hook e a distinção observável.
- **Checagem "isso é uma criação inicial de conta?" refinada durante a revisão:** usar só `not user.has_usable_password()` é verdadeiro também pra uma conta ATIVA que teve a senha invalidada por outro motivo (ex.: um admin chamando `set_unusable_password()` por segurança) -- nesse caso, exigir reaceite de termos e mandar o e-mail de boas-vindas de novo seria enganoso. Corrigido com a checagem composta `not user.has_usable_password() and user.last_login is None` (aplica-se em `InitialOrResetPasswordKeyForm`).
- **`UserManager.create_user()` ganhou `extra_fields.setdefault('profile_completed', True)`** -- decisão deliberada de uma linha só, em vez de tocar as dezenas de testes/scripts pré-existentes que chamam `User.objects.create_user(...)` esperando uma conta já pronta pra uso. Justificado porque o fluxo público de cadastro NUNCA passa por este manager (constrói o `User` direto via o adapter do allauth) -- `create_user()` só é usado por `createsuperuser`, scripts e factories de teste.
- **Achados de UX/segurança adicionais da revisão, todos corrigidos:** open redirect no parâmetro `next` de `ProfileCompletionView` (validado com `url_has_allowed_host_and_scheme`); `toggle_theme` ficava mudo sob o gate de perfil incompleto (form no cabeçalho, presente em toda página) -- adicionado à lista de exceções do middleware; usuário já autenticado confirmando um segundo e-mail (`/accounts/email/`, rota nativa sempre ativa) caía na mensagem "cadastro já confirmado, faça login" em vez de simplesmente continuar logado -- corrigido delegando pro `super()` quando `request.user` já é o dono do e-mail confirmado.
- **Corrida de `createcachetable` no deploy:** rodar em `loterias-web` e `loterias-cron` simultaneamente contra o mesmo SQLite compartilhado (volume `loterias_data`) é uma corrida real (`createcachetable` faz check-then-create não atômico). Removido do comando do container de cron -- ele nunca usa o cache do rate limiter (isso só acontece em requisições web).
- **Bug pré-existente encontrado ao rodar a suite completa (não introduzido por esta mudança), diagnosticado e corrigido:** 5 testes de `LotteryResultPurgeAdminTests` (Story 2.10) calculavam a data de corte "ontem" via `timezone.now().date() - timedelta(days=1)` (data UTC), enquanto `PurgeUntilDateForm.clean_cutoff_date` valida contra `timezone.localdate()` (data no fuso `America/Sao_Paulo`, `TIME_ZONE` do projeto). Perto da virada de dia (horário UTC já no dia seguinte, horário local ainda no dia anterior), "ontem em UTC" coincide com "hoje" em horário local -- o form corretamente rejeita como "data de corte precisa ser anterior a hoje", e a purga nunca roda, exatamente o comportamento (200 OK, nada apagado) que o próprio teste `test_action_without_apply_...` descreve como "achado empírico" de uma falha silenciosa. Reproduzido e confirmado via `timezone.now().date()` vs `timezone.localdate()` no shell no momento da falha. Corrigido trocando os 9 usos do padrão nos testes pra `timezone.localdate() - timedelta(days=1)`, alinhado com o que o form realmente usa como "hoje".

## Log de Triagem da Revisão

Revisão cega em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer), 2ª rodada (a 1ª rodada do Blind Hunter/Edge Case Hunter caiu por rate limit de sessão e foi relançada). Todos os achados abaixo foram corrigidos -- nenhum foi deliberadamente adiado pra `deferred-work.md`.

| Achado | Reviewer | Disposição |
|---|---|---|
| Rate limiter nativo compartilha uma única cache key entre a regra de cooldown e a diária, esgotando a cota diária com cliques dentro do cooldown | Edge Case Hunter | Corrigido -- limite diário movido pra código de aplicação com cache key própria |
| `respond_email_verification_sent` recebe `user=None` no branch anti-enumeração, e o próprio mecanismo de guardar o e-mail na sessão via esse hook vazava a distinção "existe/não existe" | Blind Hunter | Corrigido -- e-mail submetido guardado em `CustomSignupView.form_valid()`, sem depender do hook |
| `not user.has_usable_password()` sozinho confunde conta pendente com conta ativa com senha invalidada por admin (reaceite de termos + e-mail de boas-vindas indevidos) | Verification Gap Reviewer | Corrigido -- checagem composta com `last_login is None` |
| `next` de `ProfileCompletionView` nunca validado -- open redirect | Blind Hunter | Corrigido -- `url_has_allowed_host_and_scheme` |
| `toggle_theme` inacessível sob o gate de perfil incompleto (form no `base.html`, presente em toda página) | Edge Case Hunter | Corrigido -- adicionado a `EXEMPT_URL_NAMES` |
| Usuário já autenticado confirmando e-mail secundário via `/accounts/email/` regressava pra mensagem "cadastro já confirmado" | Verification Gap Reviewer | Corrigido -- delega pro `super()` quando é o próprio usuário logado |
| `createcachetable` rodando em 2 containers contra o mesmo SQLite -- corrida check-then-create | Edge Case Hunter | Corrigido -- removido do comando do container de cron |
| `test_admin_path_is_never_gated` usava superuser, cujo bypass por role mascarava o bypass por path -- não testava o que afirmava testar | Verification Gap Reviewer | Corrigido -- variante com usuário staff-não-superuser + teste direto de instanciação do middleware |
| Teste do limite diário do rate limiter seedava histórico direto no cache interno do allauth -- não provava nada de real (passava mesmo trocando o limite configurado) | Verification Gap Reviewer | Corrigido -- teste reescrito contra a cache key própria da view, com `@override_settings`/mock provando reação a mudança de limite |

## Verificação

**Comandos executados (todos passando na versão final):**
- `python manage.py makemigrations --check --dry-run` -- `No changes detected`
- `python manage.py test apps.accounts` -- 58/58 passando
- `python manage.py test` -- 278/278 passando (suite completa, nenhuma regressão)
- `python manage.py check` -- sem erro novo (só o warning pré-existente de `STATICFILES_DIRS` em dev, não relacionado)
