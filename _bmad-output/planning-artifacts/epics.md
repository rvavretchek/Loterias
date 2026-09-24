---
stepsCompleted: [1, "1-confirmed", 2, 3, "3-confirmed", 4, "adendo-2026-09-17:1", "adendo-2026-09-17:1-confirmed", "adendo-2026-09-17:2-approved", "adendo-2026-09-17:3", "adendo-2026-09-17:4-complete", "epic-5:sem-prd-direto", "epic-6:sem-prd-direto", "epic-6:1", "epic-6:1-confirmed", "epic-6:2-approved", "epic-6:3", "epic-6:4-complete", "epic-7:sem-prd-direto", "epic-7:1", "epic-7:1-confirmed", "epic-7:2-approved", "epic-7:3", "epic-7:4-complete"]
inputDocuments: ["_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md", "_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md", "_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md", "_bmad-output/planning-artifacts/ux-designs/ux-Loterias-2026-09-17/DESIGN.md", "_bmad-output/planning-artifacts/ux-designs/ux-Loterias-2026-09-17/EXPERIENCE.md"]
---

# Loterias - Detalhamento de Épicos

## Visão Geral

Este documento decompõe em epics e stories os requisitos da PRD `prd-Loterias-2026-09-07` (verificação/notificação diária de resultados + novo fluxo de cadastro em duas etapas) e as decisões técnicas da espinha de arquitetura `architecture-Loterias-2026-09-08` (9 ADs — 10 após a Story 2.8/2.11), incluindo a renomeação de código legado para inglês decidida durante a revisão da PRD (§3.1). Não havia documento de UX formal pros Epics 1-3.

**Adendo 2026-09-17:** Epic 4 adicionado a partir do adendo do mesmo PRD (§4.3-§4.5, FR-16 a FR-24) — home reorganizada, Regras de Geração personalizadas por usuário+Jogo, histórico com filtros. Espinha de arquitetura própria (`architecture-Loterias-2026-09-17`, AD-11 a AD-14, herda AD-1 a AD-10 acima) e primeiro par de spine de UX formal do projeto (`ux-Loterias-2026-09-17/DESIGN.md`+`EXPERIENCE.md`).

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

*Adendo 2026-09-17 (PRD §4.3-§4.5) — FR-16 a FR-24:*

FR-16: O resumo de atividade (jogos gerados/tipos/recentes) sai do topo da área útil da home e vira uma barra lateral fixa; a área central abre direto na área de "jogo selecionado", com o seletor de jogos logo abaixo — gerar um jogo não exige scroll em viewports ≥1280×720.

FR-17: Cada um dos 6 Jogos no seletor exibe um ícone visualmente distinto dos demais (hoje todos usam o mesmo ícone genérico).

FR-18: A partir do seletor de jogos, uma ação "editar" por Jogo abre uma tela de edição da Regra de Geração daquele Jogo específico pra aquele usuário — pré-carregada com os valores atuais (default do sistema, se nunca personalizado). Salvar aplica a partir da próxima geração; jogos já gerados antes não são recalculados.

FR-19: Regras de Geração pra Mega-Sena/+Milionária/Quina/Dupla-Sena (mesmo conjunto pras 4): limite de números em sequência, limite de sequências no jogo, limite por linha do volante, limite por coluna do volante (liga/desliga + valor cada), e Tipo de distribuição (Homogênea/Totalmente Aleatória). Grid de linha/coluna = volante oficial de cada Jogo na Caixa.

FR-20: Regras de Geração pra Lotofácil (conjunto próprio, 7 regras): as mesmas 5 de FR-19, mais limite de espaço mínimo entre sequências e limite de quantidade mínima de sequências no jogo.

FR-21: Regras de Geração pra Lotomania (conjunto reduzido, 3 regras): limite de números em sequência, limite de espaço mínimo entre sequências, limite de quantidade mínima de sequências — sem linha/coluna/distribuição.

FR-22: Quando as Regras de Geração ligadas por um usuário pra um Jogo são, em conjunto, impossíveis de satisfazer, a geração tenta um número limitado de vezes respeitando todas; se não conseguir, relaxa a regra mais recentemente alterada (entre as que causaram o conflito) e avisa qual foi relaxada — nunca falha silenciosamente nem trava sem gerar.

FR-23: A Regra de Sequência adaptativa hoje existente continua sendo o default de todo usuário. As novas Regras de Geração personalizadas só entram em vigor pra um Jogo depois que o usuário efetivamente edita e salva a Regra de Geração daquele Jogo — os dois mecanismos nunca coexistem pro mesmo Jogo+usuário.

FR-24: A tela de histórico ganha filtros cumulativos (Jogo, período, só premiados) sempre visíveis no topo da lista. A exibição de números continua legível mesmo pra Jogos com muitos números (Lotomania: 50; Lotofácil: 15) e pra Dupla-Sena (2 sorteios).

*Rodada de pré-homologação 2026-09-23 (decidida em `bmad-party-mode`, sem PRD formal por trás — ver `_bmad-output/party-mode/2026-09-23-pre-homologacao.html`) — FR-25 a FR-28:*

FR-25: O sistema recusa registrar um jogo — gerado automaticamente, regenerado, ou digitado como palpite manual — pra um Jogo+Concurso cujo resultado oficial já foi capturado (`LotteryResult` existente). O comportamento já existe (`_block_if_contest_already_drawn`), mas só tem teste explícito pra parte dos 3 pontos de entrada.

FR-26: Um palpite manual salvo pra um Jogo+Concurso cujo resultado oficial AINDA não foi capturado é conferido retroativamente (marcado premiado/sem prêmio corretamente, número a número) assim que a captura acontecer — seja pela rotina diária, seja por verificação manual — sem nenhuma ação adicional do usuário.

FR-27: Toda combinação possível de Regras de Geração habilitadas por Jogo (dentro do universo de regras daquele Jogo) produz um jogo que satisfaz todas as regras ligadas simultaneamente, ou relaxa exatamente uma delas quando genuinamente inatingível (Story 4.5) — nunca devolve silenciosamente um jogo que viola uma regra ligada.

FR-28: `normalize_contest` nunca aceita/normaliza silenciosamente uma entrada vazia ou não numérica vinda de formulário — sempre rejeita com erro claro; ao gravar direto num model (dado legado, sem passar por formulário), preserva o valor original sem quebrar.

*Rodada de pré-homologação 2026-09-23/24 (decidida em `bmad-party-mode` + feedback direto do Boss após a esposa dele testar o Lottiq, sem PRD formal por trás) — FR-29 a FR-33:*

FR-29: A tela de gerar jogo (home) explica como fazer um jogo de forma que não exija já saber usar o sistema — a frase atual ("Selecione um jogo abaixo") não foi suficiente pra uma pessoa testando pela primeira vez.

FR-30: A tela de Regras de Geração explica o que cada regra faz, em linguagem comum, pra cada uma das 7 regras possíveis (`RULE_DEFINITIONS`) — não só o rótulo curto que já existe hoje.

FR-31: Existe uma zona reservada no layout, visível mas fora do fluxo de gerar/conferir jogo, pra exibição futura de anúncios do Google AdSense — sem conta AdSense nem integração real ainda (isso só entra se e quando o Boss decidir colocar o produto em produção de verdade).

FR-32: A interface oferece tema escuro, usando os tokens de cor escura que já existem no Lottiq Design System de origem (nunca antes aplicados à UI) — alternável pelo usuário, preferência lembrada.

FR-33: Antes de qualquer rastreamento por cookie (preparação pro AdSense futuro), o visitante vê uma tela de consentimento com 3 opções — aceitar, recusar, ou configurar parcialmente por categoria — e pode revisitar essa escolha depois.

### Requisitos Não-Funcionais

NFR-1: Um valor de prêmio exibido numa Notificação sempre rastreia a um `LotteryResult.prizes` concreto ou a uma Faixa de Premiação (`PrizeTier`) oficial vigente (FR-8) — o sistema nunca estima ou arredonda prêmio na ausência de um desses dois dados oficiais confirmados (PRD §4.1/FR-9).

NFR-2: As rotinas agendadas respeitam uma cadência deliberadamente baixa (diária para resultado, mensal para valores) para não sobrecarregar nem ser bloqueadas pelo site da Caixa, que não tem API oficial (PRD §4.1/FR-9).

NFR-3: O Vínculo de Confirmação de Cadastro é de uso único e expira, via o mecanismo padrão do django-allauth (`ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) (PRD §4.2/FR-14).

NFR-4: Nenhuma senha é solicitada antes da confirmação do e-mail — elimina o caso de alguém criar senha para um e-mail que não controla (PRD §4.2/FR-14).

NFR-5: O volume de e-mails de acerto por usuário permanece baixo — um e-mail por Acerto Premiado real, nunca reenviado por reexecução da rotina diária (PRD §7, SM-C1, reforçado pela Arquitetura AD-4 via `get_or_create`+`created=True`).

NFR-6 *(adendo 2026-09-17)*: A geração de um jogo com Regras de Geração personalizadas ativas responde na mesma ordem de grandeza de tempo que a geração hoje (sem Regras) percebe como instantânea — o caminho de conflito do FR-22 (até 2×`max_attempts` no pior caso) não introduz espera perceptível, já que cada tentativa é trabalho em memória sem I/O (PRD §4.4, Architecture Spine `architecture-Loterias-2026-09-17` §Stack).

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

*Adendo 2026-09-17 — extraídas de `architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md` (AD-11 a AD-14, herda AD-1 a AD-10 acima como read-only):*

- **`GenerationRule` (AD-11):** uma tabela relacional só, uma linha por (`user`, `game`, `rule_name`) — `unique_together`. `numeric_value`/`choice_value` nullable, `CheckConstraint` garantindo XOR entre os dois. O conjunto de `rule_name` válido por Jogo vive num dict Python único, `RULE_NAMES_BY_GAME` em `models.py` (ao lado de `GAMES_CONFIG`) — nunca hardcoded em mais de um lugar. `updated_at` por linha é o que sustenta "regra mais recentemente alterada" do FR-22.
- **`generate_bet()`/`bet_satisfies_rules()` (AD-12):** nova função pura `bet_satisfies_rules(numbers, clovers, game, rules) -> (bool, list[str])` (lista completa de regras violadas, não só a primeira). `generate_bet()` usa duas queries distintas — `has_customization` (sem filtro `enabled`, decide o modo) e `active_rules` (com `enabled=True`, alimenta a checagem) — e o mesmo `max_attempts=10000` já existente na função (não um valor novo). Relaxa no máximo 1 regra por chamada, a de maior `updated_at` entre as que o último candidato violou.
- **Default vs. personalizado, sem campo de estado novo (AD-13):** ausência de qualquer linha `GenerationRule` pra um (user, game) é o único "default". `regras_geracao_view` nunca deleta uma linha ao desmarcar um toggle — sempre `update_or_create` com `enabled=False`. O único caminho que deleta é o botão "Restaurar padrão" (apaga todas as linhas daquele user+game).
- **Filtros de histórico (AD-14):** `GeneratedBet.objects.filter(...)` direto — Jogo, `prize__gt=0` (premiado, reusa o cache existente), `created_at__range` (período, limites inclusivos convertidos pro início/fim do dia no `TIME_ZONE` do projeto) — cumulativos via `AND`, sem join novo.
- **Sem infraestrutura/dependência nova:** mesmo stack do spine pai; nenhuma migration além de `CREATE TABLE GenerationRule`.

*Rodada de pré-homologação 2026-09-23 — decisões de processo/qualidade (sem AD de arquitetura por trás, decididas em `bmad-party-mode`):*

- **Convenção de teste em 4 categorias:** toda cobertura de teste nova (não retroativa a todo teste já existente) cobre caminho feliz, entrada inválida (formato errado/fora do intervalo), entrada vazia/ausente, e fronteira/concorrência (duplicata, corrida, estado já existente) — documentada no `CLAUDE.md`.
- **`apps/loterias_core/tests.py` dividido por área funcional** (geração/regras, histórico, notificações, admin etc.) — consequência natural de organizar a cobertura nova por área, não uma reforma isolada à parte.
- **Runbook de backup/restore exercitado de verdade:** o procedimento já documentado em `deploy/lab/README.md` (nunca rodado até hoje, porque o volume do lab sempre pôde ser recriado livremente) roda ao menos uma vez, ponta a ponta, com evidência registrada.
- **Postura de dados do lab muda:** a partir de agora, o volume `loterias_data` deixa de ser tratado como descartável (o Boss trata a homologação como produção pra fins de preservação de dado, mesmo sem usuário real ainda) — `deploy/lab/README.md` atualizado pra refletir isso.

### Requisitos de UX

*Épicos 1-3 (originais): não havia documento de UX formal — FR-4 foi fechado durante a criação das stories (badge no cabeçalho, Story 2.4); FR-5 tratou o layout como decisão de implementação dentro da própria story.*

*Adendo 2026-09-17 — extraídas de `ux-Loterias-2026-09-17/DESIGN.md` + `EXPERIENCE.md` (primeiro par de spine de UX formal do projeto):*

UX-DR1: Cada um dos 6 Jogos no `game-selector` ganha um ícone Bootstrap Icons distinto: Mega-Sena `bi-trophy`, +Milionária `bi-flower1`, Lotomania `bi-123`, Lotofácil `bi-lightning`, Quina `bi-star`, Dupla-Sena `bi-stack` — todos `aria-hidden="true"` (decorativos, o nome do Jogo já é texto visível).

UX-DR2: O resumo (`sidebar-summary`) migra dos 3 `stat-card` horizontais no topo pra uma coluna lateral fixa em viewports ≥1280px; abaixo disso empilha abaixo da área principal (scroll aceitável, não é meta).

UX-DR3: `rule-toggle-row` — quando o switch está NÃO, o campo Valor fica visível porém desabilitado (`disabled` nativo, nunca `display:none`) — com uma região `aria-live="polite"` anunciando a transição de habilitado/desabilitado no momento do toggle.

UX-DR4: A área "jogo selecionado" no topo da home atualiza via JS ao trocar de jogo no seletor, sem reload — região `aria-live="polite" aria-atomic="true"` pra leitores de tela perceberem a troca de conteúdo.

UX-DR5: `filter-bar` do histórico sempre visível no topo (nunca colapsável); cada filtro ativo é um `<button>` com `aria-label` nomeando a ação de remover (não só o glifo "✕"); foco pós-remoção de filtro vai pro heading da barra, não pro topo do documento.

UX-DR6: `number-badge` quebra linha (`flex-wrap`) pra jogos com muitos números, com `role="list"`/`role="listitem"` na sequência; Dupla-Sena mostra 2 grupos `role="group"` rotulados "1º sorteio"/"2º sorteio", empilhados (nunca lado a lado).

UX-DR7: Estado "selecionado" do `game-selector` usa um indicador não-cromático (ícone de check) além de cor de borda/fundo — acessível a quem depende só de percepção de cor.

UX-DR8: Confirmação ao desligar a última proteção de sequência (FR-23) é um modal Bootstrap (`.modal`) com gerenciamento de foco completo (foco move pro modal, preso dentro, volta ao botão "Salvar" ao fechar, fecha via Esc) — não um `window.confirm()` nativo.

UX-DR9: Texto de ajuda das regras de linha/coluna (grid do volante) associado ao campo via `aria-describedby`, não só posicionamento visual.

*Rodada de pré-homologação 2026-09-23/24 — sem UX spine formal, decidido direto com o Boss:*

UX-DR10: Dica explicativa na home não compete com o fluxo de gerar jogo — aparece perto do seletor, não bloqueia a ação, some ou fica discreta depois que o usuário já gerou pelo menos um jogo (não precisa reexplicar pra quem já sabe usar).

UX-DR11: Explicação de cada Regra de Geração fica perto do campo (mesmo padrão de `aria-describedby` do UX-DR9), não num texto solto fora de contexto — quem está configurando "limite de números em sequência" vê a explicação junto do campo, sem precisar procurar em outro lugar da tela.

UX-DR12: A zona reservada pro AdSense (FR-31) nunca fica dentro do fluxo de gerar/conferir jogo — Sally (persona da rodada) definiu rodapé do conteúdo ou coluna lateral no desktop, empilhada no celular, com moldura própria, sem nenhuma cor "de anúncio" enquanto não for ativado de verdade.

UX-DR13: Tema escuro (FR-32) reusa os tokens `--dark-*` já definidos no projeto de origem do Lottiq Design System (`tokens/colors.css` do Claude Design, nunca importados pro `static/css/lottiq-tokens.css` do app) — troca por `[data-theme="dark"]`, preferência lembrada (o toggle foi removido do cabeçalho no Epic 5 de propósito, pra essa rodada; precisa voltar).

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
FR-16: Epic 4 - Reorganização da área útil da home
FR-17: Epic 4 - Ícone por Jogo no seletor
FR-18: Epic 4 - Edição de Regra de Geração por usuário+Jogo
FR-19: Epic 4 - Regras de Geração (Mega-Sena/+Milionária/Quina/Dupla-Sena)
FR-20: Epic 4 - Regras de Geração (Lotofácil)
FR-21: Epic 4 - Regras de Geração (Lotomania)
FR-22: Epic 4 - Resolução de conflito entre Regras de Geração
FR-23: Epic 4 - Regra de Sequência atual permanece o default
FR-24: Epic 4 - Filtros cumulativos e exibição legível no histórico
FR-25: Epic 6 - Bloqueio de concurso já sorteado testado nos 3 pontos de entrada
FR-26: Epic 6 - Conferência retroativa de palpite manual salvo antes da captura do resultado
FR-27: Epic 6 - Cobertura de todas as combinações possíveis de Regras de Geração
FR-28: Epic 6 - Cobertura de `normalize_contest` (entrada inválida/vazia)
sem-fr-propria: Epic 5 - Migração pro Lottiq Design System e renomeação do produto (sem FR numerada própria — decidida direto em conversa, sem PRD formal)
FR-29: Epic 7 - Dicas explicativas na tela de gerar jogo
FR-30: Epic 7 - Dicas explicativas na tela de Regras de Geração
FR-31: Epic 7 - Zona reservada pro Google AdSense
FR-32: Epic 7 - Tema escuro
FR-33: Epic 7 - Tela de consentimento de cookies/LGPD

## Lista de Épicos

### Epic 1: Renomeação do Código Legado para Inglês
Alinha todo o código já existente (models, funções, views) à convenção de inglês fixada na PRD §3.1, sem alterar comportamento nem dados — pré-requisito de sequenciamento (AD-1/AD-2) antes de qualquer story dos Epics 2 e 3.
**FRs cobertos:** nenhuma FR numerada (débito técnico do PRD §6.1 + AD-1/AD-2 da Arquitetura)

### Epic 2: Verificação e Notificação Diária de Resultados
O jogador sabe se ganhou sem precisar lembrar de checar manualmente — o sistema vigia os resultados oficiais da Caixa sozinho e avisa ao logar, diferenciando acerto premiado de não premiado.
**FRs cobertos:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-15

#### Story 2.20: Permitir vários jogos por Jogo+Concurso

Como jogador,
Eu quero gerar e guardar quantos jogos eu quiser pro mesmo Jogo+Concurso,
Para montar vários palpites pro mesmo sorteio.

**Critérios de Aceite:**

**Dado** o usuário já tem um ou mais `GeneratedBet` pro mesmo Jogo+Concurso ainda sem resultado
**Quando** ele gera (`create_bet_view`) ou guarda um jogo manual (`save_manual_bet_view`) pra esse mesmo par
**Então** um novo `GeneratedBet` é criado normalmente, sem bloqueio nem erro
**E** o bloqueio de concurso já sorteado (Story 2.2) continua valendo, inclusive com jogos já existentes do usuário pro par
**E** "Refazer" (Story 2.17) segue substituindo o jogo in-place — trocar os números de um jogo não é criar outro

*Sem FR numerada nova — reverte a decisão (a) da Story 2.14 (2026-09-14), por decisão do Boss em 2026-09-18 ("isso é bug": a intenção sempre foi gerar quantos jogos quiser por concurso, como no PRD UJ-1).*

## Epic 3: Novo Fluxo de Cadastro
Uma pessoa se cadastra só com e-mail, confirma, cria senha, e só depois informa nome/sobrenome — cadastro deliberado em vez do genérico do allauth.
**FRs cobertos:** FR-10, FR-11, FR-12, FR-13, FR-14

### Epic 4: Home Reorganizada, Regras de Geração Personalizadas e Histórico com Filtros
*(adendo 2026-09-17, PRD §4.3-§4.5)* Gerar um jogo não exige mais scroll (resumo vira sidebar, jogo selecionado sobe pro topo, cada Jogo com seu ícone); cada usuário pode personalizar como cada Jogo é gerado pra ele (regras de sequência/linha/coluna/distribuição, por família de Jogo); e o histórico ganha filtros cumulativos com exibição legível mesmo pra Jogos com muitos números. Depende dos Epics 1-3 concluídos (código já em inglês, app já em produção).
**FRs cobertos:** FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-22, FR-23, FR-24

### Epic 5: Migração para o Lottiq Design System e Renomeação do Produto
*(decidido em conversa direta com o Boss, 2026-09-21/22, sem PRD formal)* Produto renomeado de "Gerador de Loterias" pra Lottiq; toda a UI migrada do Bootstrap pro Lottiq Design System (tokens/componentes próprios, Material Symbols Rounded), Bootstrap/Bootstrap Icons/crispy-forms removidos por completo.
**FRs cobertos:** nenhuma FR numerada própria

### Epic 6: Cobertura Sistemática de Testes e Validação do Runbook
*(rodada de pré-homologação 2026-09-23, decidida em `bmad-party-mode`, sem PRD formal)* Fecha lacunas de teste identificadas na rodada — concurso já sorteado, conferência retroativa de palpite manual, todas as combinações possíveis de Regras de Geração, `normalize_contest` — sob uma convenção nova de 4 categorias (feliz/inválido/vazio/fronteira), com `tests.py` reorganizado por área como consequência. Fecha também validando de verdade o runbook de backup/restore do lab, cuja postura de descartabilidade de dado muda a partir de agora.
**FRs cobertos:** FR-25, FR-26, FR-27, FR-28

### Epic 7: Layout — Dicas Explicativas, Tema Escuro, Zona de AdSense e Consentimento de Cookies
*(rodada de pré-homologação 2026-09-23/24, sem PRD formal)* Fecha o segundo item do backlog de pré-homologação: dicas explicativas na home e nas Regras de Geração (feedback direto da esposa do Boss testando o produto — "não pareceu claro o suficiente"), tema escuro (tokens já existem, só nunca foram importados), zona reservada pro Google AdSense (só o espaço, sem conta/integração real), e tela de consentimento de cookies/LGPD (pré-requisito legal pro AdSense futuro). Depende do Epic 6 concluído (ordem pedida pelo Boss: testes antes de layout).
**FRs cobertos:** FR-29, FR-30, FR-31, FR-32, FR-33

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

### Story 2.12: Normalização de Concurso

Como operador (Boss),
Eu quero que o campo Concurso seja normalizado de forma consistente em todos os pontos que o recebem,
Para que duas grafias do mesmo concurso real (ex. `'2500'` e `'02500'`) nunca sejam tratadas como concursos distintos.

**Contexto (promovido de `deferred-work.md`, achado independentemente nas revisões das Stories 2.1, 2.2 e 2.10):** `GeneratedBet.contest` é texto livre, só passa por `.strip()`. Isso permite que duas grafias do mesmo concurso real gerem dois pares distintos em `fetch_daily_results` (potencialmente dois `LotteryResult` diferentes pro mesmo concurso real), furem o bloqueio de concurso já sorteado (Story 2.2), e furam a proteção contra apagar um resultado premiado na purga manual (Story 2.10, que casa `game`+`contest` por igualdade textual exata).

**Critérios de Aceite:**

**Dado** um usuário digita um Concurso em `create_bet_view`, `save_manual_bet_view` ou via `api_create_bet_view`
**Quando** o valor é salvo em `GeneratedBet.contest`
**Então** o valor é normalizado de forma consistente (ex. convertido pra inteiro e re-serializado sem zeros à esquerda) antes de gravar
**E** a mesma normalização se aplica na leitura/comparação usada pelo bloqueio de concurso já sorteado (Story 2.2) e pela proteção da purga manual (Story 2.10)
**E** `suggest_next_contest` continua devolvendo valores no mesmo formato normalizado
**E** concursos com valor não numérico continuam rejeitados com mensagem clara (nunca gravados)

*Sem FR numerada nova — correção de lacuna de validação já existente antes do Epic 2, achada em revisão.*

### Story 2.13: Validação de Jogo em api_create_bet_view

Como consumidor da API de criação de jogo,
Eu quero receber um erro 400 claro quando informo um Jogo inválido,
Para não receber um erro 500 não tratado.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 1.3):** diferente de `create_bet_view`, `api_create_bet_view` não valida `selected_game not in GAMES_CONFIG` antes de chamar `generate_bet()`. Com um `jogo` inválido no payload JSON, `generate_bet()` retorna `(None, None)` e a chamada seguinte (`count_sequential_pairs(nums)`) faz `len(None)`, levantando `TypeError` não tratado (500).

**Critérios de Aceite:**

**Dado** um payload JSON com `jogo` que não existe em `GAMES_CONFIG`
**Quando** `api_create_bet_view` recebe a requisição
**Então** o sistema responde 400 com uma mensagem clara, replicando a validação que `create_bet_view` já faz — nunca um 500 não tratado
**E** o comportamento com um `jogo` válido permanece inalterado

*Sem FR numerada nova — correção de bug pré-existente, achado em revisão.*

### Story 2.14: Bloqueio Real de Concurso Duplicado

Como jogador,
Eu quero que o sistema realmente me impeça de gerar duas apostas pro mesmo Jogo+Concurso quando ele avisa que é duplicado,
Para que o aviso não seja apenas cosmético.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 1.3):** `create_bet_view`/`save_manual_bet_view` mostram `messages.warning()` sobre concurso duplicado mas criam o registro duplicado mesmo assim (falta `return`/interrupção após o aviso).

**Critérios de Aceite:**

**Dado** um usuário já tem um `GeneratedBet` pro mesmo Jogo+Concurso que está tentando gerar/salvar de novo
**Quando** ele confirma a ação
**Então** o Boss decide e a story implementa um dos dois comportamentos: (a) bloquear totalmente a duplicata (sem gravar, com mensagem clara), ou (b) permitir a duplicata mas deixar claro no aviso que ela será mesmo criada — a decisão fica registrada nesta story antes da implementação
**E** o comportamento escolhido é aplicado de forma consistente em `create_bet_view` e `save_manual_bet_view`

**Decisão do Boss (2026-09-14):** opção (a) — bloquear totalmente a duplicata. Implementado via
`_block_if_duplicate_bet` (mesmo padrão de `_block_if_contest_already_drawn`) em
`apps/loterias_core/views.py`, ver `_bmad-output/implementation-artifacts/spec-2-14-bloqueio-real-de-concurso-duplicado.md`.

*Sem FR numerada nova — correção de bug pré-existente, achado em revisão.*

**Revertida em 2026-09-18 (Story 2.20):** o Boss esclareceu que a intenção do produto é gerar e guardar quantos jogos quiser por Jogo+Concurso (até o concurso ser sorteado) — a opção (a) acima contradizia isso. `_block_if_duplicate_bet` foi removido; o bloqueio de concurso já sorteado (Story 2.2) continua.

### Story 2.15: Runbook de Backfill Inicial de Notificações

Como operador (Boss),
Eu quero um jeito documentado (ou automatizado) de tratar a enxurrada de notificações do primeiro rollout real do Epic 2,
Para que usuários não vejam como "notificação nova" um acerto que já sabiam há dias.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 2.3; urgência elevada em 2026-09-11 ao se descobrir que o pipeline de deploy estava silenciosamente quebrado desde ~09/09 — o Epic 2 nunca tinha rodado de verdade contra o ambiente do lab até o fix daquele dia, então o primeiro ciclo real e não assistido do cron é iminente):** todo `GeneratedBet` histórico com `hits > 0` já verificado via caminho sob demanda, mas sem `HitNotification` correspondente, vai gerar uma `HitNotification` nova na primeira execução real da varredura por estado (AD-4) — o usuário veria "notificação nova" de um acerto que já conhecia.

**Critérios de Aceite:**

**Dado** o primeiro deploy real do Epic 2 num ambiente com `GeneratedBet` histórico pré-existente
**Quando** a rotina diária roda pela primeira vez de verdade
**Então** existe um passo documentado no runbook de deploy (`deploy/lab/README.md`) — ou um management command dedicado — pra marcar como lida (`is_read=True`) toda `HitNotification` gerada nesse backfill inicial, sem impedir notificações genuínas futuras
**E** o passo é claramente distinguível de uma purga de dados — nenhuma `HitNotification`/`GeneratedBet`/`LotteryResult` é apagado, só o estado de leitura é ajustado

*Sem FR numerada nova — consequência operacional do rollout, achada em revisão da Story 2.3.*

### Story 2.16: Travar Concurso Não Normalizado no Django Admin

Como operador (Boss),
Eu quero que o campo Concurso também seja normalizado quando editado direto pelo admin,
Para que a garantia da Story 2.12 (uma grafia canônica por concurso real) valha em todos os pontos que recebem esse campo, não só nas 3 views públicas.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 2.12):** `contest` continua editável como texto livre em `GeneratedBetAdmin`/`LotteryResultAdmin` (ausente de `readonly_fields`), nunca passando por `normalize_contest`.

**Critérios de Aceite:**
**Dado** um operador edita/cria um `GeneratedBet` ou `LotteryResult` direto pelo Django admin
**Quando** ele salva com um Concurso não normalizado (ex. `'02500'`) ou não numérico
**Então** o admin normaliza/rejeita da mesma forma que `normalize_contest` já faz nas views públicas — nunca grava um valor não canônico
**E** o comportamento de edição de campos não relacionados ao Concurso permanece inalterado

*Sem FR numerada nova — fecha lacuna já registrada na Story 2.12, decisão do Boss em 2026-09-14.*

### Story 2.17: Refazer Segue a Regra de Bloqueio de Duplicata

Como jogador,
Eu quero que "Refazer" um jogo siga a mesma regra de duplicata que gerar/salvar já segue,
Para que o sistema não me deixe com 2 jogos pro mesmo Jogo+Concurso por um caminho enquanto bloqueia por outro.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 2.14):** `regenerate_bet_view` cria um segundo `GeneratedBet` pro mesmo usuário+Jogo+Concurso do jogo original sem nenhuma checagem, inconsistente com o bloqueio real que a Story 2.14 adicionou em `create_bet_view`/`save_manual_bet_view`.

**Critérios de Aceite:**
**Dado** um usuário clica em "Refazer" num `GeneratedBet` existente
**Quando** a view gera o novo jogo
**Então** o `GeneratedBet` original é substituído (números/trevos/pares sequenciais atualizados in-place) em vez de um segundo registro ser criado pro mesmo Jogo+Concurso
**E** o teste existente `test_regenerating_bet_creates_new_record_and_redirects` é atualizado pra refletir esse novo comportamento (substituição, não duplicação)

*Sem FR numerada nova — fecha lacuna já registrada na Story 2.14, decisão do Boss em 2026-09-14.*

### Story 2.18: Suporte ao 2º Sorteio da Dupla-Sena

Como jogador da Dupla-Sena,
Eu quero que meu jogo seja conferido contra os 2 sorteios do concurso, não só o 1º,
Para que eu não perca a notificação de um acerto real no 2º sorteio.

**Contexto (promovido de `deferred-work.md`, achado na Story 2.1):** a Dupla-Sena tem 2 sorteios por concurso (confirmado ao vivo contra a API oficial, campos `listaDezenas`/`listaDezenasSegundoSorteio`), mas `fetch_cef_result`/`LotteryResult` só capturam e conferem o 1º.

**Critérios de Aceite:**
**Dado** um concurso de Dupla-Sena já sorteado, com os 2 sorteios disponíveis na API oficial
**Quando** `fetch_cef_result` captura o resultado
**Então** os números do 2º sorteio são capturados num campo novo (`LotteryResult.numbers_second_draw` ou equivalente), sem afetar `numbers` (1º sorteio) já usado pelos demais jogos
**E** `calculate_bet_prize` para Dupla-Sena confere o jogo do usuário contra os 2 sorteios separadamente, usando o de maior prêmio quando os 2 têm acerto
**E** os demais jogos (sem 2º sorteio) continuam funcionando exatamente como hoje

*Sem FR numerada nova — fecha lacuna já registrada desde a Story 2.1, decisão do Boss em 2026-09-14.*

### Story 2.19: Renomear Arquivos de Template pra Inglês

Como desenvolvedor,
Eu quero que nomes de arquivo de template sigam a mesma convenção em inglês já usada por views/rotas,
Para eliminar a inconsistência de rotas em inglês apontando pra arquivos com nome em português.

**Contexto (promovido de `deferred-work.md`, achado na revisão da Story 1.3):** `historico.html`, `detalhes_jogo.html`, `estatisticas.html` continuam em português; a Story 1.3 deixou esse nível fora do mapeamento oficial (nome de arquivo não é identificador de código Python).

**Critérios de Aceite:**
**Dado** os templates `templates/loterias_core/historico.html`, `detalhes_jogo.html`, `estatisticas.html`
**Quando** são renomeados pra `history.html`, `bet_detail.html`, `statistics.html`
**Então** toda referência (`render()`, `{% extends %}`, `{% include %}`) é atualizada de acordo
**E** o comportamento das telas permanece idêntico — nenhuma mudança de conteúdo/estilo, só o nome do arquivo

*Sem FR numerada nova — fecha lacuna já registrada na Story 1.3, decisão do Boss em 2026-09-14.*

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

## Epic 4: Home Reorganizada, Regras de Geração Personalizadas e Histórico com Filtros

*(adendo 2026-09-17, PRD §4.3-§4.5)* Gerar um jogo não exige mais scroll (resumo vira sidebar, jogo selecionado sobe pro topo, cada Jogo com seu ícone); cada usuário pode personalizar como cada Jogo é gerado pra ele (regras de sequência/linha/coluna/distribuição, por família de Jogo); e o histórico ganha filtros cumulativos com exibição legível mesmo pra Jogos com muitos números. Depende dos Epics 1-3 concluídos. Arquitetura própria em `architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md` (AD-11 a AD-14); UX em `ux-Loterias-2026-09-17/DESIGN.md`+`EXPERIENCE.md` (mockups em `mockups/`).

### Story 4.1: Reorganização da área útil da home

Como jogador autenticado,
Eu quero que a home abra direto na área de gerar um jogo, sem precisar rolar a tela,
Para gerar uma aposta rapidamente sem esforço extra.

**Critérios de Aceite:**

**Dado** a home autenticada carrega
**Quando** a página abre
**Então** a área de "jogo selecionado" (formulário de geração, incl. campo Concurso) fica no topo da área útil central
**E** o seletor de jogos fica logo abaixo
**E** o resumo de atividade (jogos gerados/tipos/recentes) fica numa barra lateral fixa, fora do fluxo principal, em viewports ≥1280×720
**Dado** nenhum jogo foi selecionado ainda
**Quando** a home carrega
**Então** a área de "jogo selecionado" mostra um prompt leve convidando a escolher um jogo abaixo, sem ficar em branco
**Dado** um viewport abaixo de 1280px
**Quando** a home carrega
**Então** a sidebar de resumo empilha abaixo da área principal (scroll aceitável, não é meta desta story)
**E** nenhum dado do resumo (jogos gerados/tipos/recentes) muda de conteúdo — só posição/tamanho
**Dado** o campo de Concurso (editável, aceita concursos especiais/comemorativos — FR-2/UJ-1)
**Quando** a área "jogo selecionado" é reposicionada
**Então** o campo continua existindo exatamente como hoje — a reorganização muda posição, nunca remove ou esconde esse campo

*Referências: FR-16, UX-DR2, `mockups/home.html`.*

### Story 4.2: Ícone por Jogo no seletor

Como jogador,
Eu quero que cada Jogo no seletor tenha um ícone diferente,
Para identificar visualmente qual jogo é qual, sem depender só do nome.

**Critérios de Aceite:**

**Dado** o seletor de jogos na home
**Quando** a página renderiza
**Então** cada um dos 6 Jogos exibe um ícone Bootstrap Icons distinto: Mega-Sena `bi-trophy`, +Milionária `bi-flower1`, Lotomania `bi-123`, Lotofácil `bi-lightning`, Quina `bi-star`, Dupla-Sena `bi-stack`
**E** nenhum ícone é compartilhado entre dois Jogos (hoje todos usam `bi-dice-5`)
**E** cada ícone tem `aria-hidden="true"` (decorativo — o nome do Jogo já é texto visível ao lado)
**Dado** um jogo é selecionado no seletor
**Quando** o clique acontece
**Então** a área "jogo selecionado" no topo atualiza via JS sem reload (mesma função `selectGame()` já existente, estendida)
**E** a atualização acontece numa região `aria-live="polite" aria-atomic="true"`, pra leitores de tela perceberem a troca de conteúdo
**Dado** um Jogo está selecionado no seletor
**Quando** o card renderiza
**Então** o estado "selecionado" usa um indicador não-cromático (ícone de check no canto do card) além da cor de borda/fundo — nunca só cor sozinha carregando o significado

*Referências: FR-17, UX-DR1, UX-DR4, UX-DR7.*

### Story 4.3: Model GenerationRule e tela de edição de Regras de Geração por Jogo

Como jogador,
Eu quero abrir uma tela de edição das regras de geração de um Jogo específico a partir do seletor,
Para poder personalizar como aquele Jogo é gerado pra mim.

**Critérios de Aceite:**

**Dado** o model `GenerationRule` (novo, `apps/loterias_core/models.py`)
**Quando** a migration é aplicada
**Então** a tabela tem os campos `user`, `game`, `rule_name`, `enabled`, `numeric_value`, `choice_value`, `updated_at`, com `unique_together = (user, game, rule_name)`
**E** um `CheckConstraint` garante que `numeric_value` e `choice_value` nunca estão ambos preenchidos na mesma linha
**E** `RULE_NAMES_BY_GAME` (dict Python, ao lado de `GAMES_CONFIG`) define o conjunto de `rule_name` válido por Jogo — fonte única, nenhuma outra parte do código hardcoda esse conjunto separadamente
**Dado** um usuário clica no ícone de editar de um Jogo no seletor (sem selecionar o jogo pra gerar)
**Quando** a página `/regras/<jogo>/` abre
**Então** vejo o formulário de Regras de Geração daquele Jogo, pré-carregado com os valores atuais
**E** se eu nunca personalizei esse Jogo, vejo um indicador "Usando regras padrão do sistema" e todos os toggles em NÃO, com os campos Valor visíveis-porém-desabilitados (nunca escondidos)
**E** se eu já personalizei, vejo "Personalizado por você" com os valores salvos
**Dado** eu desmarco um toggle e salvo
**Quando** o formulário é submetido
**Então** a linha correspondente em `GenerationRule` é gravada com `enabled=False` (nunca deletada) — `update_or_create`, nunca `DELETE`
**E** uma linha é gravada por `rule_name` mostrado na tela daquele Jogo (ligadas e desligadas), de modo que `GenerationRule.objects.filter(user=, game=).exists()` reflita corretamente que esse Jogo foi configurado
**Dado** eu nunca abri a tela de edição de um Jogo
**Quando** um jogo desse tipo é gerado
**Então** a geração usa a Regra de Sequência adaptativa de hoje (comportamento inalterado) — `GenerationRule.exists()` é `False` pra esse par
**Dado** eu salvei ao menos uma vez a Regra de Geração de um Jogo
**Quando** um jogo desse tipo é gerado
**Então** a Regra de Sequência adaptativa não é mais consultada pra esse Jogo+usuário — só os toggles explícitos valem, mesmo que todos estejam desligados
**E** uma confirmação (modal Bootstrap, foco gerenciado) é mostrada se eu estou desligando a última proteção de sequência ativa
**Dado** eu clico em "Restaurar padrão" na tela de edição
**Quando** confirmo
**Então** todas as linhas de `GenerationRule` daquele user+game são apagadas — único caminho que deleta linhas — e o Jogo volta ao comportamento adaptativo de antes
**Dado** esta story ainda não implementa nenhuma família de regra concreta (isso é escopo das Stories 4.4/4.6/4.7)
**Quando** ela é entregue
**Então** a tela de edição já funciona ponta a ponta pro fluxo de "nenhum `rule_name` real cadastrado ainda" — as próximas stories só adicionam entradas em `RULE_NAMES_BY_GAME` e os campos correspondentes no template

*Referências: FR-18, FR-23, AD-11, AD-13, UX-DR3, UX-DR8, UX-DR9, `mockups/regras-geracao.html`.*

### Story 4.4: Regras de Geração — Mega-Sena, +Milionária, Quina, Dupla-Sena

Como jogador dessas 4 loterias,
Eu quero configurar limites de sequência, linha, coluna e tipo de distribuição,
Para que a geração respeite exatamente o padrão que eu quero.

**Critérios de Aceite:**

**Dado** a tela de edição de Regras de Geração de um desses 4 Jogos
**Quando** ela carrega
**Então** vejo os 5 campos: limite de números em sequência, limite de sequências no jogo, limite por linha do volante, limite por coluna do volante (cada um liga/desliga+valor), e Tipo de distribuição (Homogênea/Totalmente Aleatória)
**E** pra Mega-Sena, os campos de linha/coluna usam o grid confirmado do volante oficial (6 linhas × 10 colunas, PRD §8.5) com texto de ajuda associado via `aria-describedby`
**E** +Milionária/Quina/Dupla-Sena têm os mesmos 5 campos (inclusive linha/coluna), com grid em `GAME_GRID` (5×10, 8×10, 5×10 — confirmadas pelo Boss em 2026-09-19; a tela já os mostra desde a Story 4.3)
**Dado** eu ativo Regras de Geração pra um desses Jogos e gero uma aposta
**Quando** `generate_bet()` roda
**Então** a nova função `bet_satisfies_rules(numbers, clovers, game, rules)` checa cada candidato contra as regras ativas (`enabled=True`), retornando a lista completa de `rule_name` violadas
**E** o loop de tentativas usa `max_attempts=10000` (mesmo valor já existente na função) antes de considerar relaxar (Story 4.5)
**E** um candidato que satisfaz todas as regras ativas é aceito
**Dado** "Totalmente Aleatória" está selecionado
**Quando** um jogo é gerado
**Então** o comportamento é o sorteio uniforme de hoje, sem restrição de distribuição
**Dado** "Homogênea" está selecionado
**Quando** um jogo é gerado
**Então** os números são sorteados um por faixa de largura igual do intervalo do Jogo (`numbers_count` dividido em `bets_count` faixas), garantindo espalhamento pelas dezenas
**Dado** uma regra de linha/coluna está ativa pra Mega-Sena
**Quando** um candidato tem mais números na mesma linha/coluna do que o limite configurado
**Então** o candidato é rejeitado e uma nova tentativa acontece

*Referências: FR-19, AD-11, AD-12, AD-13, PRD §8.5/§8.9, NFR-6.*

### Story 4.5: Resolução de conflito entre Regras de Geração

Como jogador que personalizou regras,
Eu quero que a geração ainda funcione mesmo se minhas regras forem difíceis de satisfazer juntas,
Para nunca ficar sem conseguir gerar um jogo.

**Critérios de Aceite:**

**Dado** as Regras de Geração ativas de um usuário pra um Jogo são, em conjunto, impossíveis de satisfazer dentro de `max_attempts=10000`
**Quando** `generate_bet()` esgota as tentativas
**Então** identifica quais `rule_name` o último candidato violou
**E** escolhe a de maior `updated_at` entre essas (nunca a mais recente entre todas as regras do usuário — relaxar uma regra que não causou o conflito não ajudaria)
**E** desliga só essa regra em memória (nunca grava no banco) e roda mais até 10000 tentativas com o conjunto reduzido
**Dado** a segunda rodada de tentativas também esgota
**Quando** isso acontece
**Então** a geração cai na mensagem já existente "Não foi possível gerar um jogo único" — nunca tenta relaxar uma segunda regra
**Dado** uma regra foi relaxada com sucesso na segunda rodada
**Quando** o jogo é gerado
**Então** uma mensagem nomeia qual regra foi relaxada e em qual Jogo — nunca um aviso genérico
**E** o jogo é salvo normalmente, como um sucesso (não um erro)

*Referências: FR-22, AD-12, EXPERIENCE.md Voice and Tone.*

### Story 4.6: Regras de Geração — Lotofácil

Como jogador de Lotofácil,
Eu quero configurar regras específicas de espaço mínimo e quantidade mínima de sequências, além das já disponíveis pro grupo principal,
Para ter mais controle sobre um jogo com mais números disponíveis.

**Critérios de Aceite:**

**Dado** a tela de edição de Regras de Geração da Lotofácil
**Quando** ela carrega
**Então** vejo 7 campos: os 5 já existentes pro grupo principal (Story 4.4) mais limite de espaço mínimo entre sequências e limite de quantidade mínima de sequências no jogo
**E** os campos de linha/coluna usam o grid confirmado do volante oficial (5×5, PRD §8.5)
**Dado** a regra de espaço mínimo entre sequências está ativa
**Quando** um candidato tem duas sequências mais próximas que o valor configurado
**Então** o candidato é rejeitado
**Dado** a regra de quantidade mínima de sequências está ativa
**Quando** um candidato tem menos sequências que o valor configurado
**Então** o candidato é rejeitado
**Dado** as regras compartilhadas com o grupo principal (sequência/linha/coluna/distribuição, Story 4.4)
**Quando** ativas pra Lotofácil
**Então** se comportam exatamente como especificado na Story 4.4, sem lógica duplicada — reusam a mesma `bet_satisfies_rules()`

*Referências: FR-20, AD-11, PRD §8.5.*

### Story 4.7: Regras de Geração — Lotomania

Como jogador de Lotomania,
Eu quero configurar um conjunto reduzido de regras (sem linha/coluna/distribuição, que não fazem sentido pra esse Jogo),
Para ter controle sobre sequências sem opções que não se aplicam.

**Critérios de Aceite:**

**Dado** a tela de edição de Regras de Geração da Lotomania
**Quando** ela carrega
**Então** vejo só 3 campos: limite de números em sequência, limite de espaço mínimo entre sequências, limite de quantidade mínima de sequências
**E** nenhum campo de linha/coluna/distribuição aparece — `RULE_NAMES_BY_GAME` pra Lotomania não os inclui
**Dado** essas 3 regras reusam a mesma lógica já implementada nas Stories 4.4/4.6
**Quando** ativas pra Lotomania
**Então** `bet_satisfies_rules()` as avalia sem código novo — só a entrada em `RULE_NAMES_BY_GAME` muda

*Referências: FR-21, AD-11.*

### Story 4.8: Filtros cumulativos e exibição legível no histórico

Como jogador,
Eu quero filtrar meu histórico por Jogo, período e se ganhei,
Para revisitar jogos antigos sem rolar a lista inteira procurando manualmente.

**Critérios de Aceite:**

**Dado** a tela de histórico
**Quando** ela carrega
**Então** uma barra de filtros (Jogo, período, só premiados) fica sempre visível no topo da lista, nunca colapsável
**Dado** eu aplico um ou mais filtros
**Quando** a página recarrega (GET com querystring)
**Então** os filtros combinam por `AND` (cumulativos) — Jogo via `filter(game=)`, premiado via `filter(prize__gt=0)`, período via `filter(created_at__range=(inicio, fim))` com limites inclusivos convertidos pro início/fim do dia no `TIME_ZONE` do projeto
**E** cada filtro ativo aparece como um badge removível com `aria-label` nomeando a ação (ex. "Remover filtro Jogo: Lotomania")
**E** remover um filtro individual preserva os demais, e o foco pós-reload vai pro heading da barra de filtros
**Dado** nenhum resultado bate com os filtros aplicados
**Quando** a lista renderiza
**Então** uma mensagem nomeia o que foi filtrado (não um vazio genérico) com um botão "Limpar filtros"
**Dado** um jogo de Lotomania (50 números) ou Lotofácil (15 números) aparece na lista
**Quando** a linha renderiza
**Então** as bolinhas de número quebram linha naturalmente (`flex-wrap`), com `role="list"`/`role="listitem"`, sem cortar/sobrepor nem exigir scroll horizontal
**Dado** um jogo de Dupla-Sena (2 sorteios) aparece na lista
**Quando** a linha renderiza
**Então** os 2 conjuntos de números aparecem empilhados, rotulados "1º sorteio:"/"2º sorteio:", cada um num container `role="group"` com `aria-label` próprio

*Referências: FR-24, AD-14, UX-DR5, UX-DR6, `mockups/historico.html`.*


## Epic 5: Migração para o Lottiq Design System e Renomeação do Produto

Adotar o Lottiq Design System (projeto "Lottiq Design System" no Claude Design; tokens, componentes, 10 telas de referência em `images/Lottiq Telas.dc.html`) em toda a interface e renomear o produto de "Gerador de Loterias" para **Lottiq** (decisão do Boss, 2026-09-21). Bootstrap e Bootstrap Icons saem por completo; ícones passam a Material Symbols Rounded; tema escuro fica para uma rodada futura. Regras de conteúdo do DS valem em toda tela: vocabulário "palpite → jogo → conferir" (nunca "verificar"/"validar"), sem emoji, âmbar só em contexto de prêmio, um botão primário por tela.

**Estratégia de transição:** o CSS do DS é carregado ao lado do Bootstrap enquanto há telas não migradas; o Bootstrap só é removido na última story, quando nenhuma tela depende dele. Cada story deixa o app inteiro funcionando e é validada no navegador pelo Boss antes da próxima.

### Story 5.1: Fundação do Lottiq Design System e renomeação para Lottiq

Como pessoa que usa o produto,
Eu quero que o app carregue a identidade visual do Lottiq (cores, tipografia, componentes) e se chame Lottiq,
Para que toda tela migrada depois tenha base consistente.

**Critérios de Aceite:**

**Dado** o app carregando
**Quando** qualquer página renderiza
**Então** os tokens do DS (cor, tipografia Sora/Figtree/JetBrains Mono, espaço, raio, sombra) estão disponíveis como variáveis CSS em `static/`, e as fontes e Material Symbols Rounded carregam via Google Fonts
**E** existe um CSS de componentes do DS (botão, campo, switch, bola de número, cartão, banner/aviso, badge de status, estado vazio) usável por classe nos templates Django
**Dado** o cabeçalho e o rodapé em `base/base.html`
**Quando** renderizam
**Então** usam a marca Lottiq (símbolo + wordmark de `images/`), navegação e estados de foco do DS, e o título das páginas e dos e-mails do app diz "Lottiq"
**E** as telas ainda não migradas continuam funcionando (Bootstrap segue carregado até a Story 5.7)

*Referências: DS `tokens/*.css`, `components/`, `ui_kits/app/AppShell.jsx`.*

### Story 5.2: Landing page

Como visitante,
Eu quero uma landing page clara do Lottiq,
Para entender o produto e criar minha conta.

**Critérios de Aceite:**

**Dado** um visitante não autenticado em `/`
**Quando** a página carrega
**Então** vê a landing do Claude Design (tela 01 de `Lottiq Telas.dc.html`), com o texto e o vocabulário do DS, as fotos de `images/` (Jogadora/Ganhador) nos espaços reservados, sem o card Multitenant nem os 3 cards antigos, e CTAs "Criar conta grátis"/"Entrar"
**E** a página funciona em celular sem rolagem horizontal

### Story 5.3: Entrar, criar conta e telas de conta

Como visitante ou usuário,
Eu quero as telas de entrar, cadastro, confirmação de e-mail, senha e perfil no visual do Lottiq,
Para ter uma experiência consistente desde o primeiro acesso.

**Critérios de Aceite:**

**Dado** as telas de `templates/account/` e `templates/accounts/`
**Quando** renderizam
**Então** usam os componentes do DS (campos, botões, avisos), sem classes Bootstrap, e mantêm todo o comportamento existente (cooldown de reenvio, mensagens genéricas, validações)

### Story 5.4: Home e geração de jogo

Como usuário logado,
Eu quero a home (seletor de Jogo, resumo, gerar/guardar) no visual do Lottiq,
Para gerar jogos com a clareza do design de referência (telas 04/05).

**Critérios de Aceite:**

**Dado** a home autenticada
**Quando** renderiza em desktop e celular
**Então** segue as telas 04/05 do DS, mantendo o seletor acessível por teclado, o resumo ao lado, o ícone por Jogo (Material Symbols) e todo o comportamento das Stories 4.1/4.2

### Story 5.5: Regras de Geração

Como usuário logado,
Eu quero a tela de Regras de Geração no visual do Lottiq,
Para configurar regras com os controles do DS (tela 06).

**Critérios de Aceite:**

**Dado** `/regras/<jogo>/`
**Quando** renderiza
**Então** usa `Switch`, `Stepper`/campos, `Select` e avisos do DS, sem Bootstrap (inclusive os modais de confirmação, hoje Bootstrap JS), mantendo as regras de acessibilidade e o comportamento da Story 4.3

### Story 5.6: Histórico, detalhe, notificações, estatísticas e preferências

Como usuário logado,
Eu quero histórico, detalhe do jogo, avisos, estatísticas e preferências no visual do Lottiq,
Para acompanhar meus jogos e acertos (telas 07-10).

**Critérios de Aceite:**

**Dado** as telas restantes de `templates/loterias_core/`
**Quando** renderizam
**Então** usam os componentes do DS (`GameCard`, `NumberBall`, `StatusBadge`, `CelebrationCard` no acerto, `EmptyState`), mantêm os filtros, a legibilidade da Lotomania/Lotofácil/Dupla-Sena e a semântica das Stories 4.8/2.x, e trocam "verificar" por "conferir" na interface

### Story 5.7: Remover o Bootstrap e fechar a migração

Como mantenedor,
Eu quero remover o Bootstrap e o Bootstrap Icons,
Para não carregar dois sistemas de estilo.

**Critérios de Aceite:**

**Dado** todas as telas migradas
**Quando** o Bootstrap (CSS/JS) e o Bootstrap Icons são removidos de `base/base.html`
**Então** nenhum template usa classe Bootstrap ou `bi-*`, todas as telas seguem íntegras, e README/`CLAUDE.md` documentam o Lottiq e o Design System


## Epic 6: Cobertura Sistemática de Testes e Validação do Runbook

Fecha lacunas de teste identificadas numa rodada de `bmad-party-mode` de pré-homologação (2026-09-23, registro completo em `_bmad-output/party-mode/2026-09-23-pre-homologacao.html`), sob uma convenção nova de 4 categorias, e valida de verdade — pela primeira vez — o runbook de backup/restore do lab, cuja postura de descartabilidade de dado muda a partir de agora (homologação tratada como produção pra fins de preservação de dado, mesmo sem usuário real ainda). Ordem pedida pelo Boss: este épico vem antes do Epic 7 (layout/AdSense-zone/tema-escuro/consentimento-LGPD).

### Story 6.1: Convenção de teste em 4 categorias

Como mantenedor,
Eu quero uma convenção documentada de cobertura de teste,
Para que toda cobertura nova siga o mesmo padrão sem precisar redecidir a cada story.

**Critérios de Aceite:**

**Dado** o `CLAUDE.md`
**Quando** alguém for escrever teste novo pra uma funcionalidade
**Então** encontra a convenção de 4 categorias (caminho feliz, entrada inválida, entrada vazia/ausente, fronteira/concorrência) documentada, com um exemplo real do próprio código
**E** a convenção deixa claro que não é retroativa — não é preciso reescrever todo teste já existente, só aplicar em cobertura nova

*Referências: decisão da rodada de pré-homologação 2026-09-23.*

### Story 6.2: Cobertura de `normalize_contest`

Como mantenedor,
Eu quero `normalize_contest` coberto nas 4 categorias,
Para confiar que concurso normaliza certo e nunca aceita lixo vindo de formulário.

**Critérios de Aceite:**

**Dado** `normalize_contest` (FR-28)
**Quando** recebe concurso com zero à esquerda, vazio, não numérico, ou com espaço/whitespace
**Então** normaliza ('02500'→'2500'), rejeita com `ValueError` claro (vazio/não numérico), conforme o caso
**Dado** um model com `NormalizesContestOnSave` recebendo um `contest` legado não numérico direto no `save()` (sem passar por formulário)
**Quando** salva
**Então** preserva o valor original sem quebrar (comportamento já implementado na retro do Epic 2/5 — esta story garante teste explícito das 4 categorias, não reimplementa)

### Story 6.3: Bloqueio de concurso já sorteado nos 3 pontos de entrada

Como mantenedor,
Eu quero o bloqueio de concurso já sorteado testado explicitamente pra criação, regeneração e palpite manual,
Para confiar que os 3 pontos de entrada tratam esse caso do mesmo jeito.

**Critérios de Aceite:**

**Dado** um Jogo+Concurso com `LotteryResult` já capturado (FR-25)
**Quando** o usuário tenta gerar (`create_bet_view`), regenerar (`regenerate_bet_view`), ou guardar um palpite manual (`save_manual_bet_view`) pra esse mesmo par
**Então** os 3 são bloqueados com a mesma mensagem clara, nenhum `GeneratedBet` novo é criado, e existe um teste nomeado pra cada um dos 3 pontos de entrada (hoje só parte deles tem)

### Story 6.4: Conferência retroativa de palpite manual salvo antes da captura

Como mantenedor,
Eu quero um teste de ponta a ponta pro cenário de corrida entre palpite manual e captura de resultado,
Para confiar que um jogo salvo antes do resultado sair é conferido certo depois.

**Critérios de Aceite:**

**Dado** um palpite manual salvo pra um Jogo+Concurso cujo `LotteryResult` AINDA não existe (FR-26)
**Quando** a captura do resultado acontece depois — pela rotina diária (`fetch_daily_results`) ou por verificação manual (`check_bet_result_view`)
**Então** o jogo é conferido retroativamente e marcado premiado/sem prêmio corretamente, número a número, sem nenhuma ação adicional do usuário
**E** o teste cobre tanto o caso "bate e ganha" quanto "não bate" (nunca falso positivo)

### Story 6.5: Todas as combinações possíveis de Regras de Geração

Como mantenedor,
Eu quero as Regras de Geração testadas em todas as combinações possíveis por Jogo,
Para confiar que nenhuma combinação realista de regras ligadas gera um jogo inválido silenciosamente.

**Critérios de Aceite:**

**Dado** o universo de regras de cada Jogo (`RULE_NAMES_BY_GAME`) (FR-27)
**Quando** cada combinação possível de regras habilitadas (com valores realistas, não o produto cartesiano infinito de valores — combinações que um usuário poderia genuinamente configurar) é testada
**Então** `generate_bet_with_relaxation` sempre devolve um jogo que satisfaz todas as regras ligadas simultaneamente, ou relaxa exatamente 1 regra quando genuinamente inatingível (Story 4.5), nunca devolvendo um jogo que viola silenciosamente uma regra ligada

### Story 6.6: Fluxo ponta a ponta de uma aposta, manual e automática

Como mantenedor,
Eu quero um teste de ponta a ponta cobrindo o ciclo completo de uma aposta,
Para confiar que geração/registro, captura de resultado, cálculo de prêmio e notificação nunca pulam etapa.

**Critérios de Aceite:**

**Dado** uma aposta automática e uma manual, cada uma do início ao fim
**Quando** o ciclo completo roda — geração ou registro → captura de resultado oficial → cálculo de prêmio (`calculate_bet_prize`) → criação de `HitNotification`
**Então** cada etapa produz o estado esperado na próxima (nenhuma etapa é pulada ou mockada por inteiro), com um teste de integração nomeado pra cada um dos 2 fluxos (manual e automático)

### Story 6.7: Dividir `tests.py` por área funcional

Como mantenedor,
Eu quero `apps/loterias_core/tests.py` organizado por área funcional,
Para navegar e adicionar cobertura nova sem um arquivo de ~4000 linhas em ordem cronológica de story.

**Critérios de Aceite:**

**Dado** `apps/loterias_core/tests.py` hoje (um arquivo, ordem cronológica de story)
**Quando** a cobertura nova das Stories 6.2-6.6 é organizada
**Então** os testes ficam divididos em módulos por área (ex.: geração/regras, histórico, notificações, admin), a suíte inteira continua passando 100%, e a divisão acontece como parte de organizar a cobertura nova — não uma reforma isolada tocando testes que já passavam sem necessidade

*Decisão de processo: reverte a avaliação anterior ("sem benefício", retro Epic 2/4) — a nova convenção de 4 categorias cria estrutura repetida por área que justifica a divisão agora.*

### Story 6.8: Validar o runbook de backup/restore e atualizar a postura de dados do lab

Como mantenedor,
Eu quero o runbook de backup/restore do lab exercitado de verdade,
Para confiar nele antes de precisar dele de verdade, e deixar de tratar o volume do lab como descartável.

**Critérios de Aceite:**

**Dado** o runbook já documentado em `deploy/lab/README.md` (nunca exercitado até hoje)
**Quando** o drill completo roda — backup do volume, validação da migration contra a cópia, aplicação no volume real
**Então** cada passo funciona como documentado (ou o runbook é corrigido), com evidência registrada (contagem de linhas antes/depois batendo)
**Dado** a decisão do Boss de tratar a homologação como produção pra fins de dado
**Quando** `deploy/lab/README.md` é revisado
**Então** a nota "enquanto lab de teste, o volume pode ser recriado livremente" é substituída por uma postura condizente — dados não devem mais ser destruídos livremente a partir de agora, mesmo sem prejuízo real hoje

*Referências: `deploy/lab/README.md` (seção de smoke-test de ambiente adicionada na retro do Epic 5, e seção de backup/validação de migration já existente).*


## Epic 7: Layout — Dicas Explicativas, Tema Escuro, Zona de AdSense e Consentimento de Cookies

Fecha o segundo item do backlog de pré-homologação (rodada de `bmad-party-mode` 2026-09-23, mais feedback direto do Boss em 2026-09-24 após a esposa dele testar o Lottiq). Ordem pedida pelo Boss: dicas explicativas primeiro (feedback de uso real, mais simples e mais urgente), depois a zona do AdSense, tema escuro, e consentimento de cookies. Vem depois do Epic 6 (testes primeiro).

### Story 7.1: Dicas explicativas na tela de gerar jogo

Como visitante testando o Lottiq pela primeira vez,
Eu quero entender como fazer um jogo sem precisar adivinhar,
Para não desistir antes de conseguir gerar meu primeiro jogo.

**Critérios de Aceite:**

**Dado** a tela de gerar jogo (home autenticada), sem nenhum jogo selecionado ainda (FR-29)
**Quando** ela carrega
**Então** uma dica visível (não só a frase "Selecione um jogo abaixo para começar", que já existe e não foi suficiente) explica os passos — escolher a loteria no seletor, informar o concurso, clicar em gerar — sem depender de já saber usar o sistema
**Dado** um usuário que já gerou pelo menos 1 jogo alguma vez
**Quando** ele volta à tela de gerar jogo
**Então** a dica fica discreta ou desaparece (UX-DR10) — não reexplica pra quem já sabe

*Referências: FR-29, UX-DR10.*

### Story 7.2: Dicas explicativas na tela de Regras de Geração

Como jogador configurando Regras de Geração pela primeira vez,
Eu quero entender o que cada regra faz,
Para configurar a regra certa em vez de adivinhar pelo nome curto.

**Critérios de Aceite:**

**Dado** a tela de Regras de Geração de qualquer Jogo (FR-30)
**Quando** ela carrega
**Então** cada uma das regras aplicáveis àquele Jogo (`RULE_DEFINITIONS`) tem uma explicação em linguagem comum perto do campo (mesmo padrão `aria-describedby` do UX-DR9/UX-DR11) — não só o rótulo curto que já existe (ex. "Limita quantidade de números em sequência" ganha uma frase explicando o que isso muda no jogo gerado)
**E** a explicação cobre as 7 regras possíveis: sequência, sequências no jogo, linha, coluna, distribuição, espaço mínimo entre sequências, mínimo de sequências

*Referências: FR-30, UX-DR9, UX-DR11.*

### Story 7.3: Zona reservada pro Google AdSense

Como Boss,
Eu quero um espaço reservado no layout pra futuros anúncios,
Para não precisar redesenhar a página se um dia eu ativar o AdSense de verdade.

**Critérios de Aceite:**

**Dado** o layout das páginas principais (FR-31)
**Quando** renderiza
**Então** existe uma zona visualmente reservada — rodapé do conteúdo ou coluna lateral no desktop, empilhada no celular (UX-DR12) — fora do fluxo de gerar/conferir jogo, sem nenhuma integração real do AdSense (sem conta, sem script do Google) e sem nenhuma cor "de anúncio" enquanto não for ativado
**E** nenhuma conta AdSense nem provisionamento de infraestrutura (OCI) é criado nesta story — só o espaço no layout

*Referências: FR-31, UX-DR12. Fora de escopo: ativação real do AdSense (fica pra quando/se o Boss decidir produção).*

### Story 7.4: Tema escuro

Como usuário,
Eu quero alternar entre tema claro e escuro,
Para usar o Lottiq confortavelmente em qualquer condição de luz.

**Critérios de Aceite:**

**Dado** os tokens de cor escura já definidos no Lottiq Design System de origem (nunca importados pro app) (FR-32)
**Quando** o usuário aciona o alternador de tema (que volta ao cabeçalho, removido no Epic 5 de propósito pra essa rodada)
**Então** a interface inteira troca pro tema escuro (`[data-theme="dark"]`) sem quebrar nenhum componente do Lottiq Design System (UX-DR13), a preferência é lembrada entre visitas
**E** todas as telas migradas no Epic 5 ficam legíveis e consistentes no tema escuro, não só a home

*Referências: FR-32, UX-DR13.*

### Story 7.5: Tela de consentimento de cookies (LGPD)

Como visitante,
Eu quero decidir se aceito rastreamento por cookie,
Para ter controle sobre meus dados antes de qualquer anúncio ou analytics rodar.

**Critérios de Aceite:**

**Dado** um visitante acessando o Lottiq pela primeira vez, antes de qualquer cookie de rastreamento ser setado (FR-33)
**Quando** a página carrega
**Então** vê uma tela/banner de consentimento com 3 opções claras — aceitar tudo, recusar tudo, configurar por categoria — nenhum cookie de rastreamento é setado antes da escolha
**Dado** um usuário que já escolheu antes
**Quando** ele quiser revisar a escolha
**Então** existe um jeito de reabrir as preferências de cookie e mudar a decisão

*Referências: FR-33. Pré-requisito legal pro AdSense (Story 7.3) ser ativado de verdade no futuro — não bloqueia a Story 7.3 em si, que só reserva o espaço.*
