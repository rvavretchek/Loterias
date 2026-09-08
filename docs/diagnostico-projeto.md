# Diagnóstico do Projeto Loterias

**Data:** 2026-09-07
**Objetivo do projeto:** portfólio pessoal (currículo), com possibilidade futura de publicação gratuita com monetização (AdSense/publicidade) — não é o foco agora.

**Status:** ✅ Fundação corrigida e verificada no mesmo dia (seção 7). Gerar jogo volta a funcionar.

Este documento registra: (1) o que está quebrado hoje e por quê, com evidência reproduzida; (2) a decisão de arquitetura tomada para destravar o projeto; (3) o que falta para as melhorias pedidas; (4) o que foi encontrado em `legado/` que já apontava o caminho mais simples.

---

## 1. Causa-raiz confirmada: "não consigo mais gerar jogos"

O projeto usa `django-sqlite-tenants` para multitenancy: cada organização ("tenant") teria seu próprio arquivo SQLite. `apps.accounts` (Tenant, Domain, User) vive no banco público (`default`); `apps.loterias_core` (JogoGerado, ResultadoLoteria, EstatisticaJogo) vive em bancos por-tenant.

O problema: **um usuário comum não tem tenant nenhum.** Fora de um contexto de tenant (ou seja, qualquer acesso que não venha por um subdomínio/subpasta de organização — o caminho *normal* de uso), `get_current_tenant_slug()` retorna `None`, e o roteador (`vendor/django_sqlite_tenants/db_routers.py`) manda toda leitura/escrita de `JogoGerado` para o banco `default`. Só que o banco `default` **nunca recebe as tabelas do `loterias_core`** — o próprio roteador bloqueia isso de propósito (`allow_migrate` só permite apps do `TENANT_APPS` fora do `default`).

### Reproduzido de ponta a ponta

Ambiente isolado, criado fiel ao `requirements.txt` (Python 3.11, Django 5.0.6, django-allauth 0.63.3 — as versões que o projeto declara usar):

```
>>> get_current_tenant_slug()
None
>>> JogoGerado.objects.create(usuario=u, jogo='Mega-sena', concurso='2500', numeros=[1,2,3,4,5,6], ...)
OperationalError: no such table: loterias_core_jogogerado
```

Isto não é um caso extremo — é o caminho feliz. Qualquer usuário que loga pela URL normal do site (sem estar sob um subdomínio de tenant) recebe este erro ao tentar gerar ou salvar um jogo.

### Bugs adicionais encontrados na reprodução

1. **`init_tenant` está quebrado.** O comando (`apps/accounts/management/commands/init_tenant.py`) faz `Tenant.objects.filter(schema_name='public')`, mas o modelo `Tenant` não tem campo `schema_name` (os campos reais são `slug`, `nome`, `email`, ...). O comando explode com `FieldError` assim que é executado — ou seja, o primeiro passo documentado no `README.md` não funciona hoje.
2. **Criação de usuário pelo caminho padrão do Django está quebrada.** `apps.accounts.models.User` mudou `USERNAME_FIELD` para `'email'`, mas não define um `UserManager` customizado. O `UserManager` herdado do Django ainda exige `username` como argumento obrigatório em `create_user()`, então `createsuperuser`, o admin e qualquer script que use o manager padrão falham com `ValueError: The given username must be set`. A versão embrionária em `legado/Loterias/accounts/models.py` já tinha isso resolvido com um `CustomUserManager` — foi perdido nas iterações seguintes.

### Por que isso aconteceu (evidência do histórico)

O repositório atual tem 7 commits, e o primeiro (`df70ab0 feat: deploy Django loterias app`) já chega com multitenancy, Argon2id e pepper todos juntos — não há histórico incremental para comparar "antes/depois" de cada pedido. O commit `927f19f fix: resolve authenticated tenant database routing` tentou mitigar sintomas (removeu `.select_related('usuario')` de duas queries, o que evita um `JOIN` entre bancos separados) mas não resolveu a causa: o desenho continua exigindo que todo usuário tenha uma organização/tenant, quando o requisito real sempre foi multi-user simples.

**As pastas em `legado/` confirmam isso.** `legado/Loterias/` — o embrião mais antigo — já era multi-user simples: `CustomUser` por e-mail, sem tenant, sem Argon2/pepper, e já trazia `django-crontab` e `django-anymail` no `requirements.txt`, exatamente as ferramentas certas para as melhorias 1 e 2 pedidas hoje (busca periódica de resultado + notificação por e-mail). Essas dependências e a simplicidade se perderam nas iterações seguintes (`legado/WebLoteria`, `legado/WebLoto`), que já introduziam `vendor/django_sqlite_tenants`.

---

## 2. Risco adicional confirmado: ambiente não corresponde ao `requirements.txt`

O `requirements.txt` declara `Django==5.0.6` e `django-allauth==0.63.3`. O ambiente Python usado para desenvolver/testar tinha **Django 6.0.5** e **django-allauth 65.19.2** instalados — uma diferença de dezenas de versões maiores no allauth. `python manage.py check` já acusa configurações depreciadas (`ACCOUNT_AUTHENTICATION_METHOD`, `ACCOUNT_EMAIL_REQUIRED`, `ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE`, `ACCOUNT_USERNAME_REQUIRED`) que mudaram de nome/formato entre essas versões. Isso por si só é capaz de causar comportamento inesperado no cadastro/login, e torna impossível saber com certeza qual versão está rodando em produção sem checar o ambiente real.

**Decisão tomada:** recriar o ambiente de desenvolvimento fiel ao `requirements.txt` antes de qualquer correção, para trabalhar sobre uma base reprodutível. Um venv de diagnóstico foi criado e usado para as reproduções acima e depois descartado.

## 3. Cobertura de testes

`apps/loterias_core/tests.py` tem 26 linhas e testa apenas `normalizar_numeros` e `calcular_premiacao_jogo` isoladamente. Nenhum teste cobre `gerar_aposta` de ponta a ponta, a criação de `JogoGerado`, nem o middleware de tenant — por isso nenhum dos três bugs acima teria sido detectado rodando `manage.py test`.

---

## 4. Decisão de arquitetura

**Remover a multitenancy por completo** e voltar a um modelo multi-user simples (decisão tomada em 2026-09-07):

- Remover `apps.accounts.models.Tenant` e `Domain`, `vendor/django_sqlite_tenants`, `DATABASE_ROUTERS`, `SHARED_APPS`/`TENANT_APPS`, `DJANGO_TENANT_SQLITE`, e o campo `tenant` em `User`.
- Um único banco (`DATABASES['default']`), todos os apps nele.
- Argon2id + salt + pepper (`apps.accounts.hashers.PepperedArgon2PasswordHasher`) **permanece** — nunca teve relação com multitenancy, é só o password hasher, e já está implementado corretamente.
- Adicionar um `UserManager` customizado em `apps.accounts.models` (`create_user`/`create_superuser` por e-mail, sem exigir `username`), corrigindo o bug 2 acima.

## 5. O que falta para as três melhorias pedidas

1. **Verificação automática de resultado a cada jogo, com notificação de acerto.** `apps/loterias_core/utils.py` já tem `capturar_resultado_cef()` (scraping de `loterias.caixa.gov.br`, frágil a mudanças de layout — falha em silêncio hoje) e `verificar_resultados_usuarios()`. Falta orquestrar isso automaticamente (hoje só roda quando o usuário clica em "verificar") e notificar em acerto.
2. **Busca periódica de resultados oficiais (semanal/mensal/etc.) e notificação configurável (site e/ou e-mail).** Não existe agendamento no projeto hoje. `legado/Loterias/requirements.txt` já apontava `django-crontab` para isso; `Celery`/`Redis` já estão no `requirements.txt` atual e não são usados em nenhum lugar do código — são a alternativa mais robusta a `django-crontab` e já estão instalados, só faltam tasks. `django-anymail` (visto no embrião) ou o backend SMTP Brevo já configurado (`_bmad`/`.env.example`) cobrem o envio de e-mail. Precisa de: tabela de preferência de notificação por usuário (site/e-mail/ambos), uma tarefa periódica de captura de resultados, e o disparo de notificação ao detectar prêmio.
3. **Fluxo de cadastro: e-mail → link → cria senha → primeiro login pede nome/sobrenome.** Hoje o signup pede e-mail + senha (duas vezes) de uma vez, via `django-allauth` padrão com confirmação de e-mail obrigatória. O fluxo pedido inverte a ordem (senha só é criada depois de confirmar o e-mail pelo link) e adia nome/sobrenome para o primeiro login — precisa de uma view de "definir senha" customizada acionada pelo link de confirmação, e um passo obrigatório de completar perfil no primeiro acesso autenticado.

## 6. Pastas `legado/`

`legado/Loterias`, `legado/WebLoteria` e `legado/WebLoto` eram as três iterações anteriores deste projeto (a mais simples, mais recente com multitenancy, e a atual). Serviram para confirmar que a arquitetura multi-user simples e as dependências certas (`django-crontab`, `django-anymail`) já existiam antes da multitenancy ser introduzida. **Removidas do repositório em 2026-09-07** depois de extraído o que interessava (documentado acima) — incluíam `.venv` versionado, o que não deveria estar num repositório Git.

---

## 7. Correção aplicada e verificada (2026-09-07)

Decisão tomada: remover a multitenancy por completo (seção 4), em vez de mantê-la corrigida.

### O que foi feito

- `apps/accounts/models.py`: removidos `Tenant`, `Domain` e o campo `tenant` de `User`; adicionado `UserManager` customizado (`create_user`/`create_superuser` por e-mail, sem exigir `username`) — corrige o bug 2 da seção 1.
- `apps/accounts/admin.py`: removidos `TenantAdmin`/`DomainAdmin` e as referências a `tenant` no `CustomUserAdmin`.
- `apps/accounts/management/commands/init_tenant.py`: removido (comando não faz mais sentido; também corrigia sozinho o bug 1 da seção 1, já que deixou de existir).
- `loterias/settings/base.py`: `INSTALLED_APPS` unificado (fim da divisão `SHARED_APPS`/`TENANT_APPS`), removidos `DATABASE_ROUTERS`, `DJANGO_TENANT_SQLITE` e o `TenantMiddleware`.
- `vendor/django_sqlite_tenants/` removido por completo (e a linha correspondente no `Dockerfile`).
- `deploy/lab/docker-compose.yml`: removido o volume `loterias_tenants` (não é mais usado). *Isto altera a configuração de deploy do laboratório — o host remoto (`ubt-host01`) não foi tocado nesta sessão; um novo `docker compose up -d --build` lá vai aplicar a mudança quando alguém decidir fazer o deploy.*
- Migrações `apps/accounts/migrations/0001_initial.py` e `apps/loterias_core/migrations/0001_initial.py` regeneradas do zero (não havia dados reais em produção que justificassem uma migração incremental).
- `README.md` e `CLAUDE.md` atualizados para não descreverem mais uma arquitetura que não existe mais.

### Bug adicional encontrado e corrigido durante a verificação

`apps/__init__.py` não existia — `apps` era um pacote-namespace (PEP 420) sem `__file__`, e por isso `python manage.py test` (sem argumentos) reportava **"Found 0 test(s)"** silenciosamente, e rodar com o nome do app explícito (`manage.py test apps.loterias_core`) quebrava com `TypeError` dentro do `unittest`. Criado `apps/__init__.py` vazio; depois disso os 3 testes existentes são encontrados e passam.

### Verificação de ponta a ponta

Ambiente recriado do zero, fiel ao `requirements.txt` (Python 3.11, Django 5.0.6, django-allauth 0.63.3 — via `uv venv --python 3.11 .venv`, sem mais precisar do vendor):

```
>>> User.objects.create_user(email='teste@example.com', password='SenhaForte123', ...)
user criado via UserManager.create_user(): 1 teste@example.com

>>> nums, trevos = gerar_aposta('Mega-sena', u)
>>> JogoGerado.objects.create(usuario=u, jogo='Mega-sena', concurso='2500', numeros=nums, ...)
JOGO GERADO E SALVO: 1 08   15   27   32   50   52
```

`python manage.py check` não acusa mais os avisos de configurações depreciadas do allauid vistos na seção 2 (eram causados pelo ambiente desatualizado, não pelo código). `python manage.py test` roda os 3 testes existentes e passa.

### O que ficou pendente (fora do escopo desta correção)

- As 3 melhorias pedidas (seção 5) — verificação automática de resultado, busca periódica + notificação, novo fluxo de cadastro — ainda não foram implementadas.
- O bug 1 original do `UserManager` (allauth cria usuário sem passar por `create_user()`) significa que o fluxo de cadastro via site nunca foi afetado por aquele bug especificamente — só `createsuperuser`/admin/scripts.
- Nada foi comitado nem enviado ao host de laboratório nesta sessão; as mudanças estão no working tree, aguardando revisão.
