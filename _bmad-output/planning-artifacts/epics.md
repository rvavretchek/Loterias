---
stepsCompleted: [1, "1-confirmed", 2, 3, "3-confirmed", 4]
inputDocuments: ["_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md", "_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md"]
---

# Loterias - Detalhamento de Épicos

## Visão Geral

Este documento decompõe em epics e stories os requisitos da PRD `prd-Loterias-2026-09-07` (verificação/notificação diária de resultados + novo fluxo de cadastro em duas etapas) e as decisões técnicas da espinha de arquitetura `architecture-Loterias-2026-09-08` (9 ADs), incluindo a renomeação de código legado para inglês decidida durante a revisão da PRD (§3.1). Não há documento de UX formal para este projeto.

## Inventário de Requisitos

### Requisitos Funcionais

FR-1: Diariamente às 3h (horário de Brasília), o sistema executa uma rotina (`fetch_daily_results`) que, para cada Jogo com concursos em aberto (sem `LotteryResult` registrado), tenta capturar o resultado oficial via `fetch_cef_result` — números sorteados e, para cada faixa premiada daquele Jogo, **valor do prêmio e quantidade de ganhadores** — e grava em `LotteryResult`; idempotente, e uma falha num Jogo/Concurso não interrompe os demais. (`fetch_cef_result` hoje só extrai os números; a extração real de valor+ganhadores por faixa é lacuna a fechar nesta mesma frente — ver Story 2.11.)

FR-2: Ao gerar (automático ou manual) um `GeneratedBet`, o sistema pré-preenche o Concurso com uma sugestão mas aceita qualquer número; a única validação real é rejeitar se aquele Jogo+Concurso já tiver `LotteryResult` registrado (bloqueio, não aviso).

FR-3: Sempre que houver `LotteryResult` sem `HitNotification` correspondente para algum `GeneratedBet` daquele Jogo+Concurso, o sistema cria a Notificação de Acerto (premiada ou não, conforme `calculate_bet_prize`) — no máximo uma por `GeneratedBet`+`LotteryResult`, idempotente.

FR-4: Ao autenticar, o usuário com Notificação(ões) de Acerto não lida(s) vê um badge numérico no cabeçalho (sino + contador), resumindo a quantidade, diferenciando visualmente acertos premiados de não premiados — visível em toda página logada, decisão de UX já fechada nesta PRD.

FR-5: Clicar no indicador leva a uma tela listando as Notificações de Acerto pendentes, identificando pra cada uma o tipo de Jogo e o número do Concurso, com detalhe de números batidos e valor do prêmio; cada uma pode ser marcada como lida individualmente, sem afetar as demais.

FR-6: O usuário configura, em um único lugar, se deseja receber avisos de Acerto no site, por e-mail, ou ambos — default no cadastro: site ativo, e-mail desativado. Alterar a preferência não recria notificações passadas.

FR-7: Quando a preferência do usuário inclui e-mail, o sistema envia um e-mail (via SMTP Brevo já configurado) para cada Notificação de Acerto **premiada** criada — nunca para acerto sem prêmio; falha no envio não impede a notificação no site.

FR-8: No primeiro dia de cada mês, o sistema (`update_monthly_prize_values`) captura, para cada tipo de Jogo, as Faixas de Premiação vigentes (`PrizeTier`) — o valor oficial pra cada quantidade de acertos que dá prêmio naquele Jogo (ex.: Mega-Sena: 4, 5 e 6 acertos, cada um com seu valor; mesmo padrão pros 6 Jogos). Essas faixas são a regra de validação que `calculate_bet_prize` usa pra decidir se uma quantidade de acertos é premiada — substituem a lista fixa hoje hardcoded por Jogo. Mantém histórico só dos 3 meses mais recentes por (Jogo, quantidade de acertos), suficiente pra validar acertos retroativos.

FR-9: Dentro da mesma execução diária, se `fetch_cef_result` falhar para um Jogo/Concurso, o sistema tenta novamente até 3 vezes (15 min de intervalo); esgotadas as tentativas, envia exatamente um e-mail de alerta ao operador por Jogo/Concurso falho — nunca um resultado inventado ou estimado.

FR-15: `LotteryResult` (resultados oficiais) é retido integralmente por padrão — nenhuma exclusão automática. O admin ganha uma ação de "purge até uma data": o operador informa uma data de corte e o sistema apaga os `LotteryResult` anteriores a ela, sob demanda.

FR-10: A tela de "Criar conta" pede apenas e-mail; ao confirmar, cria uma conta pendente (sem senha utilizável) e envia o Vínculo de Confirmação de Cadastro por e-mail. Conta pendente não permite login antes da senha ser definida.

FR-11: Um botão "reenviar e-mail de cadastro" gera um novo Vínculo e invalida o anterior — cooldown de 60s entre cliques, limite de 5 reenvios por conta por dia.

FR-12: Clicar no Vínculo válido leva a uma tela de senha + confirmação + aceite dos termos de serviço; senhas divergentes são sinalizadas inline; ao confirmar, a conta passa a permitir login.

FR-13: Se o Vínculo expirar antes da senha ser definida, a conta permanece pendente; acessar o link vencido mostra mensagem clara e oferece o mesmo reenvio de FR-11 — nunca há "conta perdida para sempre".

FR-14: No primeiro login bem-sucedido após FR-12, antes de qualquer outra tela do sistema, o usuário é obrigado a informar nome e sobrenome; em logins subsequentes essa tela não aparece mais.

### Requisitos Não-Funcionais

NFR-1: Um valor de prêmio exibido numa Notificação sempre rastreia a um `LotteryResult.prizes` concreto ou a uma Faixa de Premiação (`PrizeTier`) oficial vigente (FR-8) — o sistema nunca estima ou arredonda prêmio na ausência de um desses dois dados oficiais confirmados (PRD §4.1/FR-9).

NFR-2: As rotinas agendadas respeitam uma cadência deliberadamente baixa (diária para resultado, mensal para valores) para não sobrecarregar nem ser bloqueadas pelo site da Caixa, que não tem API oficial (PRD §4.1/FR-9).

NFR-3: O Vínculo de Confirmação de Cadastro é de uso único e expira, via o mecanismo padrão do django-allauth (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) (PRD §4.2/FR-14).

NFR-4: Nenhuma senha é solicitada antes da confirmação do e-mail — elimina o caso de alguém criar senha para um e-mail que não controla (PRD §4.2/FR-14).

NFR-5: O volume de e-mails de acerto por usuário permanece baixo — um e-mail por Acerto Premiado real, nunca reenviado por reexecução da rotina diária (PRD §7, SM-C1, reforçado pela Arquitetura AD-4 via `get_or_create`+`created=True`).

### Requisitos Adicionais

*Extraídas de `ARCHITECTURE-SPINE.md` — decisões técnicas (AD-1 a AD-9) que moldam como as stories acima são implementadas.*

- **Renomeação de código legado (AD-1, AD-2):** épico técnico isolado, executado **antes** de qualquer story de FR-1 a FR-14, revisado como um único PR/commit (nunca dividido por model entre pessoas) — cobre `JogoGerado`→`GeneratedBet`, `ResultadoLoteria`→`LotteryResult`, `EstatisticaJogo`→`GameStatistics`, funções de `utils.py`/`views.py`, `related_name` e `JOGOS_CHOICES` compartilhado (mapeamento completo em PRD §3.1). Usa migrations `RenameModel`/`RenameField`; backup do volume `loterias_data` antes de aplicar em produção; suite de testes deve cobrir os reverse accessors renomeados (`user.bets`, `user.statistics`) e passar 100% antes de iniciar qualquer story nova.
- **Modelagem dos novos models (AD-3, AD-4):** `HitNotification` e `NotificationPreference` entram em `apps/loterias_core/models.py` (não um app novo). `NotificationPreference.user` é `OneToOneField`; ausência de linha lida como default de FR-6. `HitNotification.bet` é `OneToOneField` (unicidade garantida pelo banco); toda criação via `get_or_create(bet=...)`; cobertura de notificação recalculada por **estado** a cada execução do job (todo `GeneratedBet` com `LotteryResult` correspondente mas sem `HitNotification`), não disparada só pelo evento "acabei de escrever este resultado".
- **Forma dos jobs agendados (AD-5, AD-6):** lógica em `apps/loterias_core/jobs.py` como função pura (`fetch_daily_results(final: bool = False)`, `update_monthly_prize_values()`); cada uma com um management command fino homônimo; `CRONJOBS` aponta pro command via `call_command`, nunca pra função direto. Três entradas de `CRONJOBS` (3h00/3h15/3h30); só a das 3h30 passa `--final` (é a que dispara o alerta ao operador de FR-9).
- **Infraestrutura de deploy (AD-7):** novo serviço `loterias-cron` no `deploy/lab/docker-compose.yml` (sidecar, mesma imagem do `loterias-web`, `restart: unless-stopped`, `TZ=America/Sao_Paulo`, `CMD` diferente rodando `crontab add && cron -f`). `Dockerfile` precisa instalar `cron` e `tzdata` via `apt-get` (não instala hoje). `loterias/settings/base.py` ganha `DATABASES['default']['OPTIONS'] = {'timeout': 20}` (dois processos passam a escrever no mesmo SQLite).
- **Gate de conta incompleta (AD-8):** middleware único `RequireCompleteAccountMiddleware` (`apps/accounts/middleware.py`) com precedência explícita: `is_staff`/`is_superuser`/`/admin/` sempre passa; senão, `not user.profile_completed` redireciona pra tela de nome/sobrenome (exceto allowlist: a própria tela, estáticos, logout, endpoints auxiliares dela). Campo novo `User.profile_completed` (`BooleanField(default=True)`) com **migration de dados** marcando todo usuário pré-existente como `True` (grandfather) — sem essa migration, o deploy tranca todo usuário atual, inclusive o operador, fora do admin.
- **Inversão de settings do allauth (AD-9):** `ACCOUNT_SIGNUP_FIELDS` passa a `['email*']` (sem senha no cadastro); `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` passa a `False`. `CustomAccountAdapter.save_user()` cria o usuário com `set_unusable_password()` (única representação de "conta pendente" — sem campo novo); adapter sobrescreve o redirect pós-confirmação pra apontar pra uma view nova de criar senha, que é o único lugar que chama `user.set_password()` + login explícito.
- **Dependências (Stack):** adicionar `django-crontab==0.7.1` ao `requirements.txt` (não está lá hoje); remover `celery`/`redis` (não-objetivo explícito da PRD §5).
- **Starter template:** não aplicável — projeto brownfield existente, sem template novo envolvido.
- **Faixas de premiação e retenção de dados (AD-10, resolve a ambiguidade original de FR-8):** `PrizeTier` é um model novo (`game`, `hits`, `value`, `reference_month`) capturado mensalmente por `update_monthly_prize_values`, retendo só as 3 capturas mais recentes por (Jogo, quantidade de acertos). `calculate_bet_prize` valida contra `PrizeTier` em vez do `if/elif` hardcoded por Jogo. `LotteryResult` não tem purge automático (retenção integral por padrão); o Django admin ganha uma ação customizada de purge por data de corte (FR-15).

### Requisitos de UX

Não há documento de UX formal para este projeto (não existe `DESIGN.md`/`EXPERIENCE.md` nem doc de UX legado). A PRD originalmente deixava "local exato definido por UX" em dois pontos; FR-4 já foi fechado durante a criação destas stories (badge no cabeçalho — ver Story 2.4). Resta só o layout fino da tela de detalhe (FR-5), tratado como decisão de implementação dentro da própria story.

### Mapa de Cobertura de FRs

FR-1: Epic 2 - Rotina diária de resultados (inclui Story 2.11, extração real do valor de prêmio)
FR-2: Epic 2 - Bloqueio de concurso já sorteado
FR-3: Epic 2 - Geração de Notificação de Acerto
FR-4: Epic 2 - Exibição da notificação ao logar
FR-5: Epic 2 - Detalhe e leitura da notificação
FR-6: Epic 2 - Preferência de canal de notificação
FR-7: Epic 2 - Envio de e-mail de acerto
FR-8: Epic 2 - Rotina mensal de valores de premiação por faixa (PrizeTier)
FR-9: Epic 2 - Tratamento de falha da captura de resultado
FR-10: Epic 3 - Cadastro inicial só com e-mail
FR-11: Epic 3 - Reenvio do e-mail de confirmação
FR-12: Epic 3 - Definição de senha via link
FR-13: Epic 3 - Vínculo expirado
FR-14: Epic 3 - Nome e sobrenome obrigatórios no primeiro login
FR-15: Epic 2 - Purge manual de resultados oficiais antigos
rename-legado-§3.1: Epic 1 - Renomeação do código legado para inglês (sem FR numerada própria)

## Lista de Épicos

### Epic 1: Renomeação do Código Legado para Inglês
Alinha todo o código já existente (models, funções, views) à convenção de inglês fixada na PRD §3.1, sem alterar comportamento nem dados — pré-requisito de sequenciamento (AD-1/AD-2) antes de qualquer story dos Epics 2 e 3.
**FRs cobertos:** nenhuma FR numerada (débito técnico do PRD §6.1 + AD-1/AD-2 da Arquitetura)

### Epic 2: Verificação e Notificação Diária de Resultados
O jogador sabe se ganhou sem precisar lembrar de checar manualmente — o sistema vigia os resultados oficiais da Caixa sozinho e avisa ao logar, diferenciando acerto premiado de não premiado.
**FRs cobertos:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-15

### Epic 3: Novo Fluxo de Cadastro
Uma pessoa se cadastra só com e-mail, confirma, cria senha, e só depois informa nome/sobrenome — cadastro deliberado em vez do genérico do allauth.
**FRs cobertos:** FR-10, FR-11, FR-12, FR-13, FR-14

## Epic 1: Renomeação do Código Legado para Inglês

Alinha todo o código já existente (models, funções, views) à convenção de inglês fixada na PRD §3.1, sem alterar comportamento nem dados — pré-requisito de sequenciamento (AD-1/AD-2) antes de qualquer story dos Epics 2 e 3. As 4 stories abaixo são sequenciais e mergeadas como **um único PR/commit** (AD-2), não incrementalmente.

### Story 1.1: Renomear models e constantes de loterias_core para inglês

Como desenvolvedor do Loterias,
Eu quero que JogoGerado, ResultadoLoteria e EstatisticaJogo (e as constantes/atributos compartilhados entre elas) sejam renomeados num único commit,
Para que o código novo das próximas features nasça consistente, sem misturar português e inglês no mesmo módulo.

**Critérios de Aceite:**

**Dado** o mapeamento de nomes da PRD §3.1
**Quando** os models são renomeados (`GeneratedBet`, `LotteryResult`, `GameStatistics`) via migrations `RenameModel`/`RenameField`
**Então** nenhuma linha existente no SQLite é perdida ou alterada
**E** `GAME_CHOICES`, os `related_name` (`bets`, `statistics`) e os campos internos (`user`, `game`, `contest`, `numbers`, `clovers` etc.) são renomeados na mesma leva, cobrindo as referências cruzadas entre as 3 classes
**E** `GAMES_CONFIG`, `GAMES_WITH_SEQUENCE_RULE`, `MIN_SEQUENCE_INTERVAL` (e as chaves dos dicts de jogo) são renomeados no mesmo módulo
**E** a suite de testes existente roda sem alteração de comportamento — só os nomes de símbolo mudam

### Story 1.2: Renomear funções de domínio em utils.py

Como desenvolvedor do Loterias,
Eu quero que as funções de utils.py sejam renomeadas para os nomes em inglês da PRD §3.1,
Para que a lógica de domínio já use os nomes que os jobs e views dos próximos épicos vão chamar.

**Critérios de Aceite:**

**Dado** os models já renomeados (Story 1.1)
**Quando** as funções são renomeadas (`normalize_numbers`, `count_sequential_pairs`, `generate_bet`, `check_duplicate_bet`, `calculate_statistics`, `calculate_bet_prize`, `fetch_cef_result`, `check_user_results`, `recent_bets_had_sequence`)
**Então** todas as chamadas internas do próprio utils.py usam os novos nomes
**E** nenhuma mudança de comportamento é introduzida — mesma lógica, nomes novos

### Story 1.3: Renomear views, admin.py e atualizar urls.py/templates

Como desenvolvedor do Loterias,
Eu quero que as views e as classes de admin.py de loterias_core sejam renomeadas conforme §3.1 e as referências em urls.py/templates atualizadas,
Para que rotas, páginas e o painel de administração continuem funcionando com os novos nomes.

**Critérios de Aceite:**

**Dado** utils.py já renomeado (Story 1.2)
**Quando** as views são renomeadas (`create_bet_view`, `bet_detail_view`, `history_view`, `save_manual_bet_view`, `check_bet_result_view`, `regenerate_bet_view`, `statistics_view`, `delete_bet_view`, `api_create_bet_view`)
**Então** urls.py referencia as novas funções pelos novos nomes
**E** os templates com `{% url %}` continuam resolvendo corretamente
**E** uma navegação manual pelas páginas principais (home, gerar jogo, detalhes, histórico) funciona sem erro novo de 500/404
**E** `apps/loterias_core/admin.py` é renomeado junto (`JogoGeradoAdmin`→`GeneratedBetAdmin`, `EstatisticaJogoAdmin`→`GameStatisticsAdmin`), incluindo `list_display`/`list_filter`/`search_fields`/`readonly_fields` que hoje referenciam os campos antigos — o painel de administração continua funcionando sem erro

### Story 1.4: Cobrir reverse accessors renomeados e documentar o runbook de migration para produção futura

Como desenvolvedor do Loterias,
Eu quero testes cobrindo user.bets/user.statistics e o runbook de backup documentado para quando existir produção real,
Para que a renomeação não vire uma regressão silenciosa hoje, nem um risco de perda de dados no dia em que houver produção.

**Critérios de Aceite:**

**Dado** as views renomeadas (Story 1.3)
**Quando** a suite roda
**Então** existem casos de teste exercitando explicitamente `user.bets` e `user.statistics` (que a suite atual não cobre)
**E** `python manage.py test` retorna 100% de sucesso
**E** o runbook de deploy (`deploy/lab/README.md`) documenta o procedimento de backup do volume `loterias_data` e de validação de migration contra uma cópia real do `db.sqlite3`, a ser seguido **quando** o ambiente for declarado produção pelo Boss — hoje (2026-09-08) o lab é confirmadamente um ambiente de teste descartável, sem dados reais a proteger (ver [[project-loterias-dev-db-and-english-code-premise]] na memória), então não há backup/validação de dados reais a executar nesta story
**E** as 5 stories deste épico (1.1 a 1.5) são mergeadas em `main` como um único PR quando a última (1.5) estiver concluída (AD-2) — não incrementalmente; Story 1.4 não abre esse PR sozinha

### Story 1.5: Renomear campos remanescentes em português no model User

Como desenvolvedor do Loterias,
Eu quero renomear `User.tema_preferido` e `User.telefone` (`apps/accounts`) pros nomes em inglês,
Para que a convenção de nomenclatura fique completa — a PRD original afirmava que `apps/accounts` já seguia a convenção, mas esses 2 campos escaparam da varredura e só foram achados durante a implementação do Epic 1.

**Critérios de Aceite:**

**Dado** `User.tema_preferido` e `User.telefone`
**Quando** renomeados pra `preferred_theme` e `phone` (migration `RenameField`/`RenameModel` como as demais, ou banco recriado — mesma regra de dev descartável da Story 1.1)
**Então** `apps/accounts/admin.py`, `forms.py`, `views.py`, `apps/loterias_core/context_processors.py` e o template `accounts/profile.html` são atualizados juntos — nenhuma referência aos nomes antigos sobra em código
**E** `verbose_name`/`choices`/labels em português (`'Tema Preferido'`, `'Telefone'`, `'Claro'`/`'Escuro'`) continuam inalterados — só os identificadores de código mudam

O jogador sabe se ganhou sem precisar lembrar de checar manualmente — o sistema vigia os resultados oficiais da Caixa sozinho e avisa ao logar, diferenciando acerto premiado de não premiado. Depende do Epic 1 concluído.

### Story 2.1: Rotina diária de resultados

Como jogador de loteria,
Eu quero que o sistema busque os resultados oficiais sozinho todo dia,
Para que eu não precise lembrar de verificar manualmente.

**Critérios de Aceite:**

**Dado** as 3h da manhã (horário de Brasília) chegam e há Jogos com concursos em aberto (sem `LotteryResult` registrado)
**Quando** a rotina `fetch_daily_results` roda (via management command chamado pelo `CRONJOBS` do container `loterias-cron`)
**Então** o sistema tenta capturar o resultado oficial via `fetch_cef_result` pra cada Jogo/Concurso em aberto e grava em `LotteryResult`
**E** rodar a rotina de novo pro mesmo Jogo/Concurso que já tem `LotteryResult` não recria nem duplica o registro (idempotente)
**E** uma falha de captura num Jogo/Concurso específico não interrompe a tentativa dos demais
**E** o container `loterias-cron` existe no docker-compose, com `cron`/`tzdata` instalados na imagem, `TZ=America/Sao_Paulo` configurado, e `DATABASES[...]['OPTIONS']={'timeout': 20}` no settings

### Story 2.2: Bloqueio de concurso já sorteado

Como jogador,
Eu quero que o sistema me impeça de gerar/salvar um jogo pra um concurso que já tem resultado,
Para que eu não gere apostas inúteis por engano.

**Critérios de Aceite:**

**Dado** um Jogo+Concurso que já tem `LotteryResult` registrado
**Quando** eu tento gerar (automático) ou salvar (manual) um `GeneratedBet` pra esse mesmo Jogo+Concurso
**Então** o sistema bloqueia com uma mensagem clara, sem gravar o registro
**E** um Concurso fora da sequência normal (especial/comemorativo) sem `LotteryResult` é aceito normalmente
**E** o campo de Concurso continua pré-preenchido com uma sugestão (próximo concurso sequencial), mas aceita qualquer número informado

### Story 2.3: Geração de Notificação de Acerto

Como jogador,
Eu quero que o sistema crie automaticamente um aviso quando um dos meus jogos bate com o resultado oficial,
Para que eu não precise comparar número por número manualmente.

**Critérios de Aceite:**

**Dado** um `LotteryResult` sem `HitNotification` correspondente pra algum `GeneratedBet` daquele Jogo+Concurso (de qualquer usuário)
**Quando** a rotina `fetch_daily_results` roda
**Então** o sistema cria uma `HitNotification` pra cada `GeneratedBet` com interseção não vazia **ou com prêmio real** (`won=True` segundo `calculate_bet_prize` — cobre a Lotomania, que paga por 0 acertos), marcada como premiada ou não
**E** a varredura considera todo `GeneratedBet` ainda sem cobertura, não só o que a rotina gravou nesta execução — cobre também `LotteryResult` escrito pelo caminho sob demanda
**E** `GeneratedBet` sem interseção nenhuma e sem prêmio real não gera Notificação
**E** uma execução concorrente ou repetida nunca cria uma segunda `HitNotification` pro mesmo `GeneratedBet` (unicidade garantida no banco via `get_or_create`)

### Story 2.4: Exibição da notificação ao logar

Como jogador,
Eu quero ver um indicador ao entrar no site quando tenho acertos não lidos,
Para que eu saiba imediatamente se ganhei algo sem precisar procurar.

**Critérios de Aceite:**

**Dado** eu tenho Notificação(ões) de Acerto não lida(s)
**Quando** eu autentico no sistema
**Então** vejo um badge numérico no cabeçalho (ícone de sino + contador, junto do nome/avatar do usuário), resumindo a quantidade de notificações não lidas — visível em toda página enquanto eu estiver logado, sem depender de JS/tempo real (injetado via context processor, como `loterias_core/context_processors.py` já faz hoje)
**E** o badge diferencia visualmente acertos premiados de não premiados no resumo (ex.: cor ou ícone distinto)
**E** clicar no badge leva direto à tela de detalhe (FR-5)
**E** se eu não tenho notificação pendente, o badge não aparece (sem sino vazio, sem contador zerado)

### Story 2.5: Detalhe e leitura da notificação

Como jogador,
Eu quero clicar no indicador e ver o detalhe de cada acerto — incluindo qual jogo e qual concurso,
Para que eu saiba exatamente o que ganhei e em qual jogo/concurso.

**Critérios de Aceite:**

**Dado** eu cliquei no indicador de notificações
**Quando** a tela de detalhe abre
**Então** vejo a lista de Notificações de Acerto pendentes, cada uma identificando claramente o tipo de Jogo (ex.: Mega-Sena) e o número do Concurso
**E** cada item mostra os números batidos e o valor do prêmio (se houver)
**E** posso marcar cada notificação como lida individualmente, sem afetar as demais
**E** uma notificação marcada como lida não volta a aparecer no indicador de FR-4

### Story 2.6: Preferência de canal de notificação

Como jogador,
Eu quero escolher, num único lugar, se recebo avisos de acerto no site, por e-mail, ou nos dois,
Para que eu controle como sou avisado sem precisar configurar notificação por notificação.

**Critérios de Aceite:**

**Dado** eu acesso a tela de preferências de notificação pela primeira vez
**Quando** eu ainda não configurei nada
**Então** o default é notificação no site ativa e e-mail desativado
**Dado** eu já tenho uma preferência configurada
**Quando** eu altero essa preferência
**Então** a mudança não recria notificações passadas — só afeta notificações futuras
**Dado** eu tento desativar tanto o site quanto o e-mail ao mesmo tempo
**Quando** eu salvo essa configuração
**Então** o sistema bloqueia com uma mensagem clara — pelo menos um canal precisa continuar ativo, pra eu nunca ficar sem nenhuma forma de saber que ganhei

### Story 2.7: Envio de e-mail de acerto premiado

Como jogador que ativou e-mail na preferência,
Eu quero receber um e-mail quando eu ganho um prêmio,
Para que eu saiba mesmo sem abrir o site.

**Critérios de Aceite:**

**Dado** minha preferência de notificação inclui e-mail
**Quando** uma Notificação de Acerto premiada é criada pra mim
**Então** recebo um e-mail via SMTP Brevo já configurado
**E** um acerto não premiado nunca dispara e-mail, independente da minha preferência
**E** se o envio de e-mail falhar, a notificação continua sendo criada/exibida normalmente no site
**E** uma reexecução da rotina nunca reenvia o e-mail da mesma notificação — só dispara quando a notificação é criada pela primeira vez (`get_or_create` com `created=True`)

### Story 2.8: Rotina mensal de valores de premiação por faixa

Como jogador,
Eu quero que o valor de prêmio exibido reflita a faixa de premiação oficial vigente pra cada quantidade de acertos,
Para que eu saiba quanto realmente ganhei mesmo quando o resultado do meu concurso específico não traz o valor exato.

**Critérios de Aceite:**

**Dado** o primeiro dia de um novo mês chega
**Quando** a rotina `update_monthly_prize_values` roda
**Então** o sistema captura, pra cada tipo de Jogo, uma Faixa de Premiação (`PrizeTier`) por quantidade de acertos premiada naquele Jogo (ex.: Mega-Sena: 4, 5 e 6 acertos, cada um com seu valor vigente — o mesmo padrão vale pros 6 Jogos)
**E** `calculate_bet_prize` passa a validar se uma quantidade de acertos é premiada consultando `PrizeTier`, em vez da lista fixa de `if/elif` por Jogo que existe hoje em `utils.py`
**E** o sistema mantém só os 3 meses mais recentes de `PrizeTier` por (Jogo, quantidade de acertos) — capturar um mês novo remove automaticamente o mais antigo além dos 3 retidos
**E** uma Notificação de Acerto premiada criada depois da rotina mensal usa os valores atualizados, não os anteriores
**E** o valor exibido numa notificação vem do `LotteryResult.prizes` daquele concurso específico quando disponível, ou do `PrizeTier` vigente quando não — nunca um valor estimado ou inventado
**E** ao validar um acerto retroativo, o sistema usa o `PrizeTier` cujo `reference_month` é o mês do `captured_at` daquele `LotteryResult` (ou o mês retido mais próximo, sem ultrapassar) — nunca simplesmente o `PrizeTier` mais recente disponível, já que até 3 meses diferentes podem estar retidos ao mesmo tempo para o mesmo (Jogo, quantidade de acertos)
**E** `PrizeTier.hits` aceita o valor `0` como faixa premiada válida — a Lotomania paga por 0 acertos (regra especial já existente em `calculate_bet_prize`), então essa faixa precisa ser capturada e validada como qualquer outra

### Story 2.9: Tratamento de falha da captura de resultado

Como operador (Boss),
Eu quero ser avisado por e-mail se a captura de resultado falhar todas as tentativas do dia,
Para que eu saiba que preciso investigar, sem depender do usuário final notar.

**Critérios de Aceite:**

**Dado** `fetch_cef_result` falha pra um Jogo/Concurso na execução das 3h
**Quando** a rotina roda de novo às 3h15 e 3h30 (mesma execução diária, via 3 entradas de `CRONJOBS`)
**Então** o sistema tenta a captura de novo automaticamente, sem intervenção
**E** se todas as 3 tentativas falharem, recebo exatamente um e-mail de alerta por Jogo/Concurso falho — disparado só pela execução `--final` das 3h30
**E** uma falha de captura nunca gera uma Notificação de Acerto incorreta ou inventada — o usuário final simplesmente não vê notificação naquele Jogo/Concurso até funcionar num dia seguinte
**E** uma falha num Jogo/Concurso não bloqueia a tentativa dos demais
**E** (smoke test de fechamento do épico) depois do deploy no ambiente do lab, pelo menos um ciclo completo e não assistido do cron (3h/3h15/3h30) roda de ponta a ponta — captura `LotteryResult`, gera `HitNotification` e é visível ao logar — sem qualquer intervenção manual, antes de o Epic 2 ser considerado concluído

### Story 2.10: Purge manual de resultados oficiais antigos

Como operador (Boss),
Eu quero poder apagar manualmente resultados oficiais antigos a partir de uma data,
Para controlar o crescimento da base quando eu decidir que não preciso mais do histórico completo.

**Critérios de Aceite:**

**Dado** estou logado no painel de administração do Django
**Quando** acesso a lista de `LotteryResult`
**Então** existe uma ação "Purge até a data" que recebe uma data de corte e apaga os registros capturados antes dela
**E** por padrão, nenhum `LotteryResult` é apagado automaticamente — a retenção é integral até uma purga manual ser executada
**E** a ação de purge não afeta os `PrizeTier` nem os `GeneratedBet` dos usuários
**E** a ação de purge nunca apaga em cascata as `HitNotification` associadas — um `LotteryResult` com pelo menos uma `HitNotification` (lida ou não) é protegido da purge, preservando o histórico de prêmios do usuário

### Story 2.11: Extração real de valor e quantidade de ganhadores por faixa na captura de resultado

Como jogador,
Eu quero ver o valor exato do prêmio do concurso que joguei e saber se dividi a faixa com outros ganhadores — não só a faixa oficial genérica,
Para que eu saiba quanto realmente ganhei quando o valor daquele sorteio específico for maior que o mínimo da faixa (ex.: jackpot acumulado).

**Critérios de Aceite:**

**Dado** a página oficial da Caixa pro Jogo/Concurso publica valor e quantidade de ganhadores por faixa de acerto
**Quando** `fetch_cef_result` captura o resultado
**Então** o sistema extrai, pra **cada** faixa premiada daquele Jogo (ex.: Mega-Sena: quadra, quina e sena), tanto o **valor do prêmio** quanto a **quantidade de ganhadores** daquela faixa naquele concurso específico — substitui o valor fixo `R$ 0,00` hoje hardcoded — e grava as duas informações em `LotteryResult.prizes` (formato `{faixa: {'valor': ..., 'ganhadores': N}}`, uma entrada por faixa)
**E** se a extração falhar ou a página não trouxer esses dados (mas os números sorteados vierem normalmente), o resultado ainda é salvo sem prêmio populado, e `calculate_bet_prize` cai pro `PrizeTier` vigente como fonte (comportamento já existente, AD-10)
**E** uma faixa marcada como premiada nunca é gravada com `ganhadores` zerado ou ausente — inconsistência de dado é tratada como falha de extração daquela faixa, não como "zero ganhadores"
**E** uma Notificação de Acerto criada depois desta mudança usa o valor real daquele concurso quando disponível — mais preciso que o `PrizeTier` genérico nos casos em que os dois divergem (ex.: jackpot acumulado)

## Epic 3: Novo Fluxo de Cadastro

Uma pessoa se cadastra só com e-mail, confirma, cria senha, e só depois informa nome/sobrenome — cadastro deliberado em vez do genérico do allauth. Depende do Epic 1 concluído (independente do Epic 2).

### Story 3.1: Cadastro inicial só com e-mail

Como pessoa se cadastrando,
Eu quero informar só meu e-mail pra criar conta,
Para não precisar escolher senha antes de confirmar que o e-mail é meu.

**Critérios de Aceite:**

**Dado** a tela de "Criar conta"
**Quando** eu informo meu e-mail e confirmo
**Então** o sistema cria uma conta pendente (sem senha utilizável, via `set_unusable_password()`) e envia o Vínculo de Confirmação de Cadastro por e-mail
**E** a conta pendente não permite login antes da senha ser definida — login com essa conta falha naturalmente, sem checagem extra
**E** a tela pós-envio informa claramente pra checar e-mail (incluindo SPAM) e oferece um botão de reenvio
**E** `ACCOUNT_SIGNUP_FIELDS` pede só e-mail (sem campos de senha)
**Dado** o e-mail informado já tem uma conta (pendente ou confirmada)
**Quando** eu tento me cadastrar de novo com ele
**Então** vejo a mesma mensagem genérica de "verifique seu e-mail" de um cadastro novo — sem revelar se a conta já existe ou não (evita enumeração de contas) — e nenhuma conta duplicada é criada
**Dado** um usuário que já existia e já estava confirmado antes desta mudança de settings
**Quando** ele faz login normal ou usa "esqueci minha senha"
**Então** ambos continuam funcionando exatamente como antes — a inversão de `ACCOUNT_SIGNUP_FIELDS`/`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` não tem efeito colateral fora do fluxo de cadastro novo

### Story 3.2: Reenvio do e-mail de confirmação

Como pessoa que ainda não recebeu ou perdeu o e-mail de confirmação,
Eu quero poder pedir reenvio,
Para não ficar travada esperando um e-mail que não chegou.

**Critérios de Aceite:**

**Dado** estou na tela pós-cadastro (ou na tela de link expirado)
**Quando** clico em "reenviar e-mail de cadastro"
**Então** um novo Vínculo é gerado e o anterior é invalidado, reenviando pro mesmo e-mail
**E** o botão fica desabilitado por 60 segundos após cada envio
**E** esgotado o limite de 5 reenvios por conta por dia, a tela orienta checar SPAM e tentar no dia seguinte, sem travar a conta

### Story 3.3: Definição de senha via link

Como pessoa que clicou no link de confirmação,
Eu quero criar minha senha numa tela dedicada,
Para só então poder usar minha conta.

**Critérios de Aceite:**

**Dado** eu clico num Vínculo válido
**Quando** a tela de criação de senha abre (via redirect do `CustomAccountAdapter`, não o login automático padrão do allauth)
**Então** vejo campos de senha + confirmação (com alternância mostrar/ocultar) e o aceite dos termos de serviço
**E** senhas divergentes entre os dois campos são sinalizadas inline, sem submeter o formulário
**E** confirmar sem marcar o aceite dos termos não conclui o cadastro
**E** ao confirmar, minha senha é definida (`user.set_password()`), sou autenticado explicitamente, e a conta passa a permitir login normal dali em diante
**E** `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION` está desativado — clicar no link não me loga automaticamente antes de eu escolher uma senha
**Dado** eu clico de novo num Vínculo que já foi usado (senha já definida, mas ainda dentro da validade)
**Quando** a tela abre
**Então** vejo uma mensagem clara de "cadastro já confirmado, faça login" — distinta da mensagem de link expirado (Story 3.4) — e sou direcionado à tela de login

### Story 3.4: Vínculo expirado

Como pessoa cujo link demorou a ser usado,
Eu quero uma mensagem clara quando ele expirar,
Para saber que ainda posso pedir um novo em vez de achar que perdi a conta.

**Critérios de Aceite:**

**Dado** meu Vínculo expirou antes de eu definir a senha
**Quando** eu tento acessar o link vencido
**Então** vejo uma mensagem clara de que o link expirou, com o mesmo botão de reenvio de FR-11
**E** minha conta continua pendente — nunca existe um estado de "conta perdida pra sempre"
**E** o link vencido nunca me autentica na tela de criação de senha

### Story 3.5: Nome e sobrenome obrigatórios no primeiro login

Como pessoa que acabou de criar minha senha,
Eu quero informar meu nome/sobrenome antes de usar o sistema,
Para completar meu cadastro.

**Critérios de Aceite:**

**Dado** meu primeiro login bem-sucedido após definir a senha (Story 3.3)
**Quando** eu tento acessar qualquer tela do sistema
**Então** sou redirecionado pra tela de nome/sobrenome, obrigatória, antes de qualquer outra tela (via `RequireCompleteAccountMiddleware`)
**E** usuários staff/superuser ou acessando `/admin/` nunca são pegos por esse gate
**E** usuários que já existiam antes desta feature (`profile_completed=True` via migration de dados) não são pegos por esse gate
**E** depois de salvar nome/sobrenome, essa tela não aparece mais em logins subsequentes
**E** (smoke test de fechamento do épico) uma pessoa nova completa a UJ-2 inteira numa passada só — cadastro só com e-mail → confirmação → criação de senha → login → nome/sobrenome → home — sem travar em nenhum ponto, antes de o Epic 3 ser considerado concluído
