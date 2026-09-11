- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "PROMOVIDO para Story 2.13 (Validação de Jogo em api_create_bet_view) em `epics.md`, 2026-09-11 — ver lá."

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "PROMOVIDO para Story 2.14 (Bloqueio Real de Concurso Duplicado) em `epics.md`, 2026-09-11 — ver lá."

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: Nomes de arquivo de template (`historico.html`, `detalhes_jogo.html`, `estatisticas.html`) continuam em português; considerar renomear pro inglês (`history.html`, `bet_detail.html`, `statistics.html`) numa story futura.
  evidence: Não são identificador de código Python (são string literal de caminho passada pra `render()`, análogo a uma rota) — por isso ficaram fora do mapeamento oficial da Story 1.3, mas o Blind Hunter apontou a inconsistência de views/rotas em inglês apontando pra arquivos com nome em português. Decisão do Boss pendente sobre se vale ampliar o escopo do rename até esse nível.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "`config.clovers` (o jogo usa trevo?) e `config.clovers_count` (quantos trevos sortear) em `GAMES_CONFIG` têm nomes muito parecidos e nenhum comentário os distingue — risco de confusão futura em `home.html` e em qualquer código novo que leia esse dict."
  evidence: Achado pelo Blind Hunter na Story 1.3; não é um bug hoje (o uso atual está correto), só um risco de manutenção. Bastaria um comentário no dict `GAMES_CONFIG` em `models.py` explicando a diferença.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "Dupla-Sena tem 2 sorteios por concurso (confirmado ao vivo contra a API oficial), mas `fetch_cef_result` só captura o `listaDezenas` do 1º sorteio -- o 2º sorteio (`listaDezenasSegundoSorteio` na API) nunca é verificado contra o jogo do usuário."
  evidence: Achado durante a Story 2.1 ao investigar a API oficial da Caixa. `LotteryResult.numbers` é um único `JSONField` (sem campo separado pro 2º sorteio), e `calculate_bet_prize` faz uma interseção simples sem noção de "sorteio 1"/"sorteio 2" -- suportar a Dupla-Sena de verdade exigiria um campo novo no model (`numbers_second_draw` ou similar) e mudar `calculate_bet_prize` pra considerar os dois sorteios separadamente. Fora do escopo de uma story de captura de resultado; precisa de decisão de produto (vale o esforço pra um jogo específico?) antes de uma story dedicada.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "PROMOVIDO para Story 2.12 (Normalização de Concurso) em `epics.md`, 2026-09-11 — ver lá."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "SQLite não está configurado em modo WAL (`journal_mode=WAL`) -- só `OPTIONS: {'timeout': 20}` foi adicionado nesta story pra mitigar `database is locked` entre `loterias-web` e `loterias-cron` escrevendo no mesmo arquivo."
  evidence: Achado pelo Blind Hunter/Edge Case Hunter na revisão da Story 2.1 (AD-7 já previa o timeout, mas não WAL). WAL reduziria bem mais a contenção entre os dois processos, mas exige configurar o modo na conexão (via um sinal `connection_created` ou engine customizada) e testar comportamento sob concorrência real -- mudança de infraestrutura maior que um ajuste de settings, melhor como story própria se a contenção se mostrar um problema real em uso.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`fetch_daily_results` processa todos os pares Jogo/Concurso em aberto sequencialmente, sem limite/atraso entre chamadas -- um backlog grande (muitos concursos pendentes acumulados) dispara N requisições imediatas e seguidas contra a API oficial da Caixa, sem proteção contra rate limiting do lado deles."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.1. Hoje o volume é baixo (poucos usuários, poucos concursos em aberto por vez), então não é um problema prático ainda -- mas fica registrado pra revisitar se o volume de usuários/jogos crescer (ex. adicionar um pequeno atraso entre chamadas, ou processar em lotes).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`calculate_bet_prize`'s campo `category` (usado como rótulo de exibição, ex. 'sena'/'quina') continua colapsando toda faixa de acerto acima de um piso num rótulo único por jogo (ex. Mega-Sena mostra 'sena' tanto pra quem bateu 4 quanto 6 acertos) -- só o VALOR do prêmio foi corrigido nesta story pra usar a faixa real."
  evidence: A Story 2.1 corrigiu o bug de valor de prêmio errado (faixa de acerto máximo sendo usada indiscriminadamente), mas o rótulo `category` em si (não o valor monetário) ainda usa a lógica de threshold simplificada já existente antes desta story (`hits >= 4` -> `'sena'` pra Mega-Sena, cobrindo quadra/quina/sena sob o mesmo rótulo). Não é um bug de dado incorreto (o valor exibido já está certo), só um rótulo pouco preciso -- ex. o usuário vê "categoria: sena" tendo batido só quadra. Ajustar exigiria mudar `calculate_bet_prize`/templates pra mostrar um rótulo por quantidade real de acertos (ex. "quadra"/"quina"/"sena" como rótulos distintos), fora do escopo desta story.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`descricaoFaixa == f'{max_hits} acertos'`/`PRIZE_TIER_PATTERN` em `_extract_prize_tiers` casam por texto exato -- qualquer mudança de wording da API oficial da Caixa faz a extração de prêmio falhar em silêncio (retorna dict vazio), sem log nem alerta."
  evidence: Achado pelo Blind Hunter/Edge Case Hunter na revisão da Story 2.1. Como a API é de terceiro (ainda que oficial da Caixa), uma mudança de formato não é impossível. Hoje não há verificação ativa de "a extração de prêmio parou de funcionar" -- só se perceberia se um usuário reclamasse. Um alerta/log quando `listaRateioPremio` vem não-vazio mas `_extract_prize_tiers` devolve `{}` seria uma melhoria barata, mas nenhuma foi implementada nesta story (mantendo o escopo focado na captura de números/concurso, que era o bug crítico original).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-bloqueio-de-concurso-ja-sorteado.md`
  summary: "Mesma causa raiz da Story 2.1 (contest não normalizado) — PROMOVIDO junto para Story 2.12 (Normalização de Concurso) em `epics.md`, 2026-09-11 — ver lá. Nota adicional: `suggest_next_contest` também devolve o valor sem padding (`str(max+1)`), considerar ao implementar."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-bloqueio-de-concurso-ja-sorteado.md`
  summary: "`save_manual_bet_view` grava seu próprio `LotteryResult` (via `fetch_cef_result`+`update_or_create`) logo depois de passar pelo bloqueio que acabou de checar a ausência desse mesmo `LotteryResult` -- em caso de 2 submissões quase simultâneas pro mesmo Jogo+Concurso ainda sem resultado, a primeira a terminar 'fecha a porta' pra segunda, que passa a ser bloqueada mesmo sendo o mesmo caso de uso legítimo (registro retroativo)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.2. Não é uma condição de corrida que quebra (o `unique_together` + o `get_or_create` interno do Django já resolvem colisão sem `IntegrityError` não tratado), só um comportamento dependente de quem submete primeiro -- decisão de produto sobre se isso é aceitável ou se merece um tratamento diferente (ex. avisar em vez de bloquear quando o próprio usuário acabou de gerar aquele resultado).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-bloqueio-de-concurso-ja-sorteado.md`
  summary: "`home` view chama `suggest_next_contest(game_name)` uma vez por Jogo em `GAMES_CONFIG` (6 queries) a cada carregamento da home por usuário autenticado -- N+1 numa página de alto tráfego, sem cache."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.2. Não é um bug funcional, e o volume atual (poucos usuários, poucos concursos por Jogo) não torna isso um problema prático hoje. Resolver com uma única query agregada exigiria lidar com `contest` sendo `CharField` (SQLite `CAST` pra inteiro de string não numérica não levanta erro, silenciosamente vira `0`, arriscando poluir o `MAX()` com concursos especiais) -- revisitar se o volume crescer.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-geracao-de-notificacao-de-acerto.md`
  summary: "Todo `GeneratedBet` com `hits == 0` (a maioria, estatisticamente) nunca sai do filtro `notification__isnull=True` -- é reprocessado (busca `LotteryResult`, roda `calculate_bet_prize`, regrava o bet) em **toda** execução futura de `fetch_daily_results`, pra sempre, já que só ganhar uma `HitNotification` remove um bet desse candidate set."
  evidence: Achado pelo Blind Hunter e Edge Case Hunter, independentemente, na revisão da Story 2.3. É consequência direta do desenho da AD-4 (cobertura por estado via `notification__isnull=True`), não um bug de implementação -- mas o candidate set só cresce com o tempo. Filtrar também por `result_checked=False` pareceria a correção óbvia, mas quebraria o próprio requisito da story de "cobrir também `LotteryResult` escrito pelo caminho sob demanda" (que já marca `result_checked=True` sem nunca criar `HitNotification`). Resolver de verdade exigiria um terceiro estado (ex. um campo "já varrido pra notificação, sem necessidade de nova varredura" distinto de "resultado verificado") -- decisão de arquitetura, não cabe numa correção pontual desta story. Baixo impacto prático hoje (volume pequeno).


- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-geracao-de-notificacao-de-acerto.md`
  summary: "Uma vez que um `GeneratedBet` ganha `HitNotification`, ele nunca mais é revisitado -- se o `LotteryResult` correspondente for corrigido depois (`update_or_create` permite sobrescrever), `bet.hits`/`bet.prize`/`bet.prize_description` e `HitNotification.won` ficam congelados com o valor da primeira passagem, divergindo silenciosamente do resultado oficial atualizado."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.3. Cenário raro (correção de resultado oficial após já notificado) e não coberto pela arquitetura atual, que assume resultado imutável uma vez capturado. Resolver exigiria uma trilha de "resultado mudou de conteúdo" (não só de disponibilidade), fora do escopo desta story.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-geracao-de-notificacao-de-acerto.md`
  summary: "PROMOVIDO para Story 2.15 (Runbook de Backfill Inicial de Notificações) em `epics.md`, 2026-09-11 — urgência elevada porque o Epic 2 nunca tinha rodado de verdade no lab antes de 2026-09-11 (pipeline de deploy estava silenciosamente quebrado, ver [deploy/lab/README.md](deploy/lab/README.md)) — ver lá."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "O badge de notificação some completamente quando a contagem chega a 0 (por design, AC explícito) -- mas isso significa que, depois da Story 2.5 permitir marcar como lida, não sobra nenhum link permanente na navbar pra revisitar notificações já lidas/histórico."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.4. Não é um bug desta story (o AC pede exatamente esse comportamento -- "sem sino vazio, sem contador zerado"), mas fica sem solução até a Story 2.5 decidir se um link permanente de histórico faz sentido (ex. um item fixo "Notificações" na navbar, distinto do badge, ou uma seção na tela de perfil).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "O contador do badge não tem teto visual (ex. '99+') -- um usuário com centenas de notificações não lidas acumuladas veria um número de 3+ dígitos dentro do pill circular, arriscando quebrar o layout do cabeçalho."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.4. Baixo risco prático hoje (poucos usuários, e a Story 2.5 vai permitir marcar como lida, reduzindo o acúmulo) -- revisitar se o volume real se mostrar um problema.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "Sem índice composto cobrindo a consulta real do badge/lista (`bet__user` + `is_read` juntos) -- só `is_read` tem índice próprio (Story 2.3)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.4. Baixo impacto no volume atual; revisitar se o número de `GeneratedBet`/`HitNotification` por usuário crescer o suficiente pra tornar essa junção uma consulta lenta.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-5-detalhe-e-leitura-da-notificacao.md`
  summary: "A busca em lote de `LotteryResult` em `notifications_view` (e também em `jobs._notify_covered_bets`, Story 2.3) usa `game__in=[...], contest__in=[...]` separados -- um produto cartesiano que pode trazer registros 'cruzados' que não correspondem a nenhum par real da página, sem causar dado errado (a chave do dict vem do próprio registro retornado), só desperdiçando linhas buscadas."
  evidence: Achado pelo Blind Hunter e confirmado (sem ser um bug de correção) pelo Edge Case Hunter na revisão da Story 2.5 -- o mesmo padrão já existia em `jobs.py` desde a Story 2.3, não foi introduzido agora. Resolver de verdade exigiria uma query por pares exatos (`Q(game=g1,contest=c1) | Q(game=g2,contest=c2) | ...`), mais complexa de montar dinamicamente; o volume atual (página de 20 notificações) não torna isso um problema prático.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-5-detalhe-e-leitura-da-notificacao.md`
  summary: "Marcar como lida não tem confirmação nem desfazer -- um clique acidental é permanente (só reversível via admin/shell)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.5. Comportamento comum em apps similares (ex. notificações do GitHub também não confirmam), e nenhum FR pede confirmação/desfazer -- documentado como decisão de produto em aberto, não um bug.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-preferencia-de-canal-de-notificacao.md`
  summary: "Duas abas do mesmo usuário salvando `NotificationPreference` diferentes quase ao mesmo tempo -- 'last write wins' silencioso, sem aviso pra aba que 'perdeu'."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.6. Mesmo padrão de concorrência já adiado nas Stories 2.2 (bloqueio de concurso) e 2.5 (marcar como lida) -- resolver exigiria `select_for_update`/versionamento otimista, fora do escopo de uma tela de preferências simples com baixo volume de uso concorrente esperado.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-preferencia-de-canal-de-notificacao.md`
  summary: "Uma linha de `NotificationPreference` materializada por um GET incidental (visita à tela sem nunca clicar em salvar) não se distingue, olhando só a tabela, de uma escolha real e consciente do usuário -- não há `created_at`/`updated_at` nem flag de origem."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.6. Decisão de design já aceita explicitamente pelo spec original ("Nunca: não criar um segundo model/campo pra 'conta pendente'/estado"). Só vira um problema real se uma feature futura (ex. auditoria, ou a Story 2.7 decidindo se o usuário "escolheu" e-mail de propósito) precisar distinguir os dois casos -- revisitar se isso surgir.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "O envio de e-mail é síncrono, dentro do próprio loop de `_notify_covered_bets` -- cada acerto premiado bloqueia a rotina de cron até o SMTP responder (até o timeout configurado). Sem fila assíncrona (Celery foi removido do projeto na Story 2.1, decisão explícita)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.7. Comportamento aceito conscientemente pela própria fronteira desta story ("Não implementar... fila assíncrona -- Celery já foi removido do projeto"), não uma omissão -- revisitar só se o volume de acertos premiados por execução crescer o suficiente pra tornar isso um problema prático de duração do job.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "`bet.prize_description` expõe a chave interna de `calculate_bet_prize` (ex. `'dupla_sena'`, `'milionaria'` sem acento/formatação) diretamente no corpo do e-mail, como 'Categoria: dupla_sena' -- destoa da linha 'Jogo:' logo acima, que usa `bet.game` com capitalização/acentuação de exibição."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.7. Mesma causa raiz já registrada como rótulo pouco preciso na Story 2.1 (`category` colapsado numa faixa ampla) -- agora também visível no e-mail, não só na tela. Resolver exigiria uma tabela de rótulos amigáveis por categoria, fora do escopo de uma story de envio de e-mail.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "O corpo do e-mail não inclui os números da aposta nem um link/URL clicável pro detalhe do jogo -- só um texto genérico 'Acesse o site para ver os detalhes completos', sem endereço (diferente do welcome e-mail, que tem uma URL fixa pro localhost)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.7. Nenhuma FR exige link/CTA concreto; o projeto não tem hoje um domínio configurado de forma reutilizável fora do `ALLOWED_HOSTS` (não usa `django.contrib.sites` pra isso) -- adicionar um link real exigiria decidir essa configuração primeiro, fora do escopo desta story.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-rotina-mensal-de-valores-de-premiacao.md`
  summary: "`calculate_bet_prize` consulta o banco (`_find_prize_tier` + `PrizeTier.objects.filter(game=game).exists()`) toda vez que a faixa de acertos do usuário não bate com a faixa premiada do concurso específico -- dentro de `_notify_covered_bets` (varredura de cron por bet) isso reintroduz até 2 queries por bet não pré-carregadas, o mesmo padrão de N+1 que `results_by_pair`/`preferences_by_user_id` foram escritos pra evitar nesta mesma função."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.8. Avaliado conscientemente e não corrigido agora: a tabela `PrizeTier` é pequena por natureza (6 jogos x poucas dezenas de faixas possíveis x 3 meses retidos -- no máximo algumas centenas de linhas, índice simples), então o custo por query é desprezível comparado aos N+1 anteriores (que envolviam tabelas crescendo com o número de usuários, ou I/O de rede/SMTP). Revisitar só se o volume de `GeneratedBet` por execução de cron crescer o suficiente pra tornar mensurável, ou se `PrizeTier` deixar de ser pequena (ex. se a retenção de 3 meses for aumentada).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-rotina-mensal-de-valores-de-premiacao.md`
  summary: "3 dos 5 pontos de chamada de `calculate_bet_prize` (`check_user_results`, `save_manual_bet_view`, `check_bet_result_view`) nunca populam `official_result['captured_at']` -- sempre caem no default de `reference_month` (mês corrente local)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.8; investigado e considerado correto por design, não um bug: os 3 pontos fazem uma busca ao vivo via `fetch_cef_result` bem no momento da chamada (não leem um `LotteryResult` histórico já salvo), então tratar o mês corrente como `reference_month` é exatamente certo -- é uma captura acontecendo agora. Além disso, com a correção desta revisão que faz `calculate_bet_prize` priorizar a faixa de premiação do próprio concurso (`official_result['prizes']`, que é a fonte da verdade e nunca some) sobre o `PrizeTier` mensal, o `reference_month` só influencia o resultado no caminho de fallback (concurso sem essa faixa específica) -- risco residual baixo. Revisitar só se a CAIXA fornecer a data real de apuração do concurso (`dataApuracao` na API) e `fetch_cef_result` passar a propagá-la (ligação natural com a Story 2.11).

- source_spec: `_bmad-output/implementation-artifacts/spec-2-9-tratamento-de-falha-da-captura-de-resultado.md`
  summary: "O limiar `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` (8 dias) mede a idade do `GeneratedBet` mais antigo do par, não a distância real até a data em que o concurso deveria ter sido sorteado -- um usuário pode criar uma aposta manual pra um concurso muito distante no futuro (nenhuma validação de teto superior existe hoje, só `_block_if_contest_already_drawn` bloqueando concurso já sorteado) e isso soaria como falha de captura passados 8 dias, mesmo sendo normal."
  evidence: Achado independentemente pelo Blind Hunter e pelo Edge Case Hunter na revisão da Story 2.9; já reconhecido na própria spec (seção Intent) como "escolha de engenharia, não constante validada contra o calendário oficial de sorteios". Corrigir de verdade exigiria ou uma validação de teto superior pro concurso digitado manualmente (`save_manual_bet_view`/`api_create_bet_view`), ou conhecer o calendário real de sorteio de cada Jogo (dado que o projeto não tem hoje e que fabricar seria arriscado) -- fora do escopo desta story (explicitamente listado em "Nunca"). Revisitar se o volume de alertas falsos-positivos no lab/produção se mostrar um problema real.

- source_spec: `_bmad-output/implementation-artifacts/spec-2-9-tratamento-de-falha-da-captura-de-resultado.md`
  summary: "As 3 execuções diárias de `fetch_daily_results` (3h/3h15/3h30) não têm nenhum lock/mutex contra sobreposição -- se o backlog de pares abertos crescer o suficiente pra uma execução ultrapassar 15 minutos, a próxima pode começar antes da anterior terminar, triplicando picos de tráfego simultâneo contra a API oficial da Caixa."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.9. Mesma categoria de risco já registrada na Story 2.1 (SQLite sem modo WAL, só timeout de 20s via AD-7) -- esta story amplifica o risco (3x mais execuções/dia) sem introduzir mecanismo de lock novo. Não corrigido agora porque o volume real de pares abertos é baixo hoje (poucos usuários); revisitar junto com a entrada de WAL já registrada se o tempo de execução se aproximar de 15 minutos na prática.
