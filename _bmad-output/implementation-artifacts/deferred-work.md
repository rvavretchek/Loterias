- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "SQLite não está configurado em modo WAL (`journal_mode=WAL`) -- só `OPTIONS: {'timeout': 20}` foi adicionado nesta story pra mitigar `database is locked` entre `loterias-web` e `loterias-cron` escrevendo no mesmo arquivo."
  evidence: Achado pelo Blind Hunter/Edge Case Hunter na revisão da Story 2.1 (AD-7 já previa o timeout, mas não WAL). WAL reduziria bem mais a contenção entre os dois processos, mas exige configurar o modo na conexão (via um sinal `connection_created` ou engine customizada) e testar comportamento sob concorrência real -- mudança de infraestrutura maior que um ajuste de settings, melhor como story própria se a contenção se mostrar um problema real em uso. **Reafirmado independentemente nas revisões das Stories 2.9 (3 execuções diárias sem lock) e 2.15 (`mark_initial_notifications_read --apply` sem tratamento de `OperationalError`)** -- mesma causa raiz, mesma decisão de não corrigir agora nas 3 vezes.
  status: accepted
  resolution: "Finalizado na remediação pós-Epic 7, 2026-09-28, como risco aceito: mudar o modo do SQLite às pressas antes de um merge pra produção (homologação) é exatamente o tipo de mudança de infraestrutura que merece sua própria story com teste de concorrência dedicado, não um patch de última hora. Sem evidência de contenção real no lab até hoje. Proposto como story própria (`PRAGMA journal_mode=WAL` via sinal `connection_created`, com teste de concorrência real) se a contenção virar problema prático -- cobre também os 2 itens irmãos abaixo (3 execuções diárias sem lock, `mark_initial_notifications_read` sem tratamento de `OperationalError`)."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`fetch_daily_results` processa todos os pares Jogo/Concurso em aberto sequencialmente, sem limite/atraso entre chamadas -- um backlog grande (muitos concursos pendentes acumulados) dispara N requisições imediatas e seguidas contra a API oficial da Caixa, sem proteção contra rate limiting do lado deles."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.1. Hoje o volume é baixo (poucos usuários, poucos concursos em aberto por vez), então não é um problema prático ainda -- mas fica registrado pra revisitar se o volume de usuários/jogos crescer (ex. adicionar um pequeno atraso entre chamadas, ou processar em lotes).
  status: accepted
  resolution: "Finalizado 2026-09-28 como risco aceito -- volume real de concursos em aberto por execução continua baixo. Revisitar se o backlog crescer o suficiente pra virar risco real de rate-limit da API da Caixa."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`calculate_bet_prize`'s campo `category` (usado como rótulo de exibição, ex. 'sena'/'quina') continua colapsando toda faixa de acerto acima de um piso num rótulo único por jogo (ex. Mega-Sena mostra 'sena' tanto pra quem bateu 4 quanto 6 acertos) -- só o VALOR do prêmio foi corrigido nesta story pra usar a faixa real."
  evidence: A Story 2.1 corrigiu o bug de valor de prêmio errado (faixa de acerto máximo sendo usada indiscriminadamente), mas o rótulo `category` em si (não o valor monetário) ainda usa a lógica de threshold simplificada já existente antes desta story (`hits >= 4` -> `'sena'` pra Mega-Sena, cobrindo quadra/quina/sena sob o mesmo rótulo). Não é um bug de dado incorreto (o valor exibido já está certo), só um rótulo pouco preciso -- ex. o usuário vê "categoria: sena" tendo batido só quadra. Ajustar exigiria mudar `calculate_bet_prize`/templates pra mostrar um rótulo por quantidade real de acertos (ex. "quadra"/"quina"/"sena" como rótulos distintos), fora do escopo desta story.
  status: accepted
  resolution: "Finalizado 2026-09-28 como risco aceito -- valor monetário exibido já está correto (só o rótulo de categoria é impreciso). Trocar `category` por um rótulo real por quantidade de acertos (quadra/quina/sena distintos) é uma mudança de dado exibido, não um patch seguro de última hora antes do merge pra homologação -- precisa de decisão de produto sobre o texto exato de cada rótulo. Sinalizado ao Boss como item pra próxima rodada de produto."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-1-rotina-diaria-de-resultados.md`
  summary: "`descricaoFaixa == f'{max_hits} acertos'`/`PRIZE_TIER_PATTERN` em `_extract_prize_tiers` casam por texto exato -- qualquer mudança de wording da API oficial da Caixa faz a extração de prêmio falhar em silêncio (retorna dict vazio), sem log nem alerta."
  evidence: Achado pelo Blind Hunter/Edge Case Hunter na revisão da Story 2.1. Como a API é de terceiro (ainda que oficial da Caixa), uma mudança de formato não é impossível. Hoje não há verificação ativa de "a extração de prêmio parou de funcionar" -- só se perceberia se um usuário reclamasse. Um alerta/log quando `listaRateioPremio` vem não-vazio mas `_extract_prize_tiers` devolve `{}` seria uma melhoria barata, mas nenhuma foi implementada nesta story (mantendo o escopo focado na captura de números/concurso, que era o bug crítico original).
  status: resolved
  resolution: "`fetch_cef_result` (apps/loterias_core/utils.py) agora loga `logger.warning` quando `listaRateioPremio` chega não-vazia mas `_extract_prize_tiers` devolve `{}` -- fechado na remediação pós-Epic 7, 2026-09-28, com 2 testes novos (`test_logs_warning_when_prize_tiers_present_but_extraction_yields_nothing`/`test_no_warning_logged_when_prize_tiers_list_is_genuinely_empty`)."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-bloqueio-de-concurso-ja-sorteado.md`
  summary: "`save_manual_bet_view` grava seu próprio `LotteryResult` (via `fetch_cef_result`+`update_or_create`) logo depois de passar pelo bloqueio que acabou de checar a ausência desse mesmo `LotteryResult` -- em caso de 2 submissões quase simultâneas pro mesmo Jogo+Concurso ainda sem resultado, a primeira a terminar 'fecha a porta' pra segunda, que passa a ser bloqueada mesmo sendo o mesmo caso de uso legítimo (registro retroativo)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.2. Não é uma condição de corrida que quebra (o `unique_together` + o `get_or_create` interno do Django já resolvem colisão sem `IntegrityError` não tratado), só um comportamento dependente de quem submete primeiro -- decisão de produto sobre se isso é aceitável ou se merece um tratamento diferente (ex. avisar em vez de bloquear quando o próprio usuário acabou de gerar aquele resultado).
  status: accepted
  resolution: "Risco aceito pelo Boss (2026-09-28) junto com os demais itens de concorrência check-then-write (Stories 2.6/2.14/2.17) -- baixo volume de uso concorrente não justifica lock/tratamento diferenciado hoje."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-2-bloqueio-de-concurso-ja-sorteado.md`
  summary: "`home` view chama `suggest_next_contest(game_name)` uma vez por Jogo em `GAMES_CONFIG` (6 queries) a cada carregamento da home por usuário autenticado -- N+1 numa página de alto tráfego, sem cache."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.2. Não é um bug funcional, e o volume atual (poucos usuários, poucos concursos por Jogo) não torna isso um problema prático hoje. Resolver com uma única query agregada exigiria lidar com `contest` sendo `CharField` (SQLite `CAST` pra inteiro de string não numérica não levanta erro, silenciosamente vira `0`, arriscando poluir o `MAX()` com concursos especiais) -- revisitar se o volume crescer.
  status: accepted
  resolution: "Finalizado 2026-09-28 como risco aceito -- 6 queries fixas (1 por Jogo em GAMES_CONFIG, nunca cresce com usuários) num volume baixo de tráfego não é N+1 na acepção que preocupa. Revisitar só se o volume de usuários simultâneos crescer o suficiente pra tornar mensurável."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-geracao-de-notificacao-de-acerto.md`
  summary: "Todo `GeneratedBet` com `hits == 0` (a maioria, estatisticamente) nunca sai do filtro `notification__isnull=True` -- é reprocessado (busca `LotteryResult`, roda `calculate_bet_prize`, regrava o bet) em **toda** execução futura de `fetch_daily_results`, pra sempre, já que só ganhar uma `HitNotification` remove um bet desse candidate set."
  evidence: Achado pelo Blind Hunter e Edge Case Hunter, independentemente, na revisão da Story 2.3. É consequência direta do desenho da AD-4 (cobertura por estado via `notification__isnull=True`), não um bug de implementação -- mas o candidate set só cresce com o tempo. Filtrar também por `result_checked=False` pareceria a correção óbvia, mas quebraria o próprio requisito da story de "cobrir também `LotteryResult` escrito pelo caminho sob demanda" (que já marca `result_checked=True` sem nunca criar `HitNotification`). Resolver de verdade exigiria um terceiro estado (ex. um campo "já varrido pra notificação, sem necessidade de nova varredura" distinto de "resultado verificado") -- decisão de arquitetura, não cabe numa correção pontual desta story. Baixo impacto prático hoje (volume pequeno).
  status: accepted
  resolution: "Finalizado 2026-09-28 como item de arquitetura, não corrigido agora -- exige um campo novo (migration) e mudança do critério da varredura de `fetch_daily_results`, risco desproporcional pra um patch de última hora antes do merge. Proposto como story própria (novo campo tipo `notification_checked_at` ou similar, distinto de `result_checked`) se o volume de `GeneratedBet` sem premio crescer o suficiente pra tornar a reprocessagem mensurável."


- source_spec: `_bmad-output/implementation-artifacts/spec-2-3-geracao-de-notificacao-de-acerto.md`
  summary: "Uma vez que um `GeneratedBet` ganha `HitNotification`, ele nunca mais é revisitado -- se o `LotteryResult` correspondente for corrigido depois (`update_or_create` permite sobrescrever), `bet.hits`/`bet.prize`/`bet.prize_description` e `HitNotification.won` ficam congelados com o valor da primeira passagem, divergindo silenciosamente do resultado oficial atualizado."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.3. Cenário raro (correção de resultado oficial após já notificado) e não coberto pela arquitetura atual, que assume resultado imutável uma vez capturado. Resolver exigiria uma trilha de "resultado mudou de conteúdo" (não só de disponibilidade), fora do escopo desta story.
  status: accepted
  resolution: "Finalizado 2026-09-28 como risco aceito -- cenário raro (correção manual de um LotteryResult já notificado), nunca observado no lab. Exigiria uma trilha de 'conteúdo mudou' nova, fora do escopo de um patch de última hora."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "O badge de notificação some completamente quando a contagem chega a 0 (por design, AC explícito) -- mas isso significa que, depois da Story 2.5 permitir marcar como lida, não sobra nenhum link permanente na navbar pra revisitar notificações já lidas/histórico."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.4. Não é um bug desta story (o AC pede exatamente esse comportamento -- "sem sino vazio, sem contador zerado"), mas fica sem solução até a Story 2.5 decidir se um link permanente de histórico faz sentido (ex. um item fixo "Notificações" na navbar, distinto do badge, ou uma seção na tela de perfil).
  status: resolved
  resolution: "Adicionado item fixo 'Notificações' em `lq-nav` (templates/base/base.html), ao lado de Gerar/Meus jogos/Estatísticas -- independente da contagem de não lidas, distinto do sino/badge (que continua condicional, sinalizando algo novo). A pedido explícito do Boss, 2026-09-28. Teste novo `test_notifications_nav_link_is_permanent_even_with_zero_unread`."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "O contador do badge não tem teto visual (ex. '99+') -- um usuário com centenas de notificações não lidas acumuladas veria um número de 3+ dígitos dentro do pill circular, arriscando quebrar o layout do cabeçalho."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.4. Baixo risco prático hoje (poucos usuários, e a Story 2.5 vai permitir marcar como lida, reduzindo o acúmulo) -- revisitar se o volume real se mostrar um problema.
  status: resolved
  resolution: "templates/base/base.html: o badge agora mostra '99+' quando `unread_notifications_count > 99`, sem alterar o `aria-label` (que continua com a contagem exata pra leitor de tela) -- fechado na remediação pós-Epic 7, 2026-09-28, com 2 testes novos (`test_badge_shows_exact_count_at_99`/`test_badge_caps_display_at_99_plus`)."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-4-exibicao-da-notificacao-ao-logar.md`
  summary: "Sem índice composto cobrindo a consulta real do badge/lista (`bet__user` + `is_read` juntos) -- só `is_read` tem índice próprio (Story 2.3)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.4. Baixo impacto no volume atual; revisitar se o número de `GeneratedBet`/`HitNotification` por usuário crescer o suficiente pra tornar essa junção uma consulta lenta.
  status: accepted
  resolution: "Reavaliado na remediação pós-Epic 7, 2026-09-28: `HitNotification.bet` é `OneToOneField` pra `GeneratedBet`, sem campo `user` direto -- um índice composto real (`bet__user`, `is_read`) exigiria denormalizar um `user` redundante em `HitNotification` só pra viabilizar o índice, mudança de schema desproporcional ao ganho no volume atual. Aceito como está; revisitar só se o volume crescer o suficiente pra justificar a denormalização."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-5-detalhe-e-leitura-da-notificacao.md`
  summary: "A busca em lote de `LotteryResult` em `notifications_view` (e também em `jobs._notify_covered_bets`, Story 2.3) usa `game__in=[...], contest__in=[...]` separados -- um produto cartesiano que pode trazer registros 'cruzados' que não correspondem a nenhum par real da página, sem causar dado errado (a chave do dict vem do próprio registro retornado), só desperdiçando linhas buscadas."
  evidence: Achado pelo Blind Hunter e confirmado (sem ser um bug de correção) pelo Edge Case Hunter na revisão da Story 2.5 -- o mesmo padrão já existia em `jobs.py` desde a Story 2.3, não foi introduzido agora. Resolver de verdade exigiria uma query por pares exatos (`Q(game=g1,contest=c1) | Q(game=g2,contest=c2) | ...`), mais complexa de montar dinamicamente; o volume atual (página de 20 notificações) não torna isso um problema prático.
  status: accepted
  resolution: "Finalizado 2026-09-28 como risco aceito -- confirmado que não causa dado errado (a chave do dict vem do próprio registro retornado, nunca de uma combinação cruzada), só desperdiça linhas buscadas; página de 20 itens não torna isso mensurável. Reavaliado o padrão Q() OR exato na remediação de hoje (usado no item novo de limpeza de CaptureFailureAlert na purga do admin, onde o risco de cruzamento seria uma correção incorreta, não só desperdício) -- mas replicar aqui só por consistência arriscaria uma regressão sem ganho real de correção."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-5-detalhe-e-leitura-da-notificacao.md`
  summary: "Marcar como lida não tem confirmação nem desfazer -- um clique acidental é permanente (só reversível via admin/shell)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.5. Comportamento comum em apps similares (ex. notificações do GitHub também não confirmam), e nenhum FR pede confirmação/desfazer -- documentado como decisão de produto em aberto, não um bug.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- nenhuma FR pede confirmação/desfazer, comportamento comum em apps similares (GitHub); mantido como está."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-preferencia-de-canal-de-notificacao.md`
  summary: "Duas abas do mesmo usuário salvando `NotificationPreference` diferentes quase ao mesmo tempo -- 'last write wins' silencioso, sem aviso pra aba que 'perdeu'."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.6. Mesmo padrão de concorrência já adiado nas Stories 2.2 (bloqueio de concurso) e 2.5 (marcar como lida) -- resolver exigiria `select_for_update`/versionamento otimista, fora do escopo de uma tela de preferências simples com baixo volume de uso concorrente esperado.
  status: accepted
  resolution: "Risco aceito pelo Boss (2026-09-28) junto com os demais itens de concorrência check-then-write (Stories 2.2/2.14/2.17)."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-6-preferencia-de-canal-de-notificacao.md`
  summary: "Uma linha de `NotificationPreference` materializada por um GET incidental (visita à tela sem nunca clicar em salvar) não se distingue, olhando só a tabela, de uma escolha real e consciente do usuário -- não há `created_at`/`updated_at` nem flag de origem."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.6. Decisão de design já aceita explicitamente pelo spec original ("Nunca: não criar um segundo model/campo pra 'conta pendente'/estado"). Só vira um problema real se uma feature futura (ex. auditoria, ou a Story 2.7 decidindo se o usuário "escolheu" e-mail de propósito) precisar distinguir os dois casos -- revisitar se isso surgir.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- decisão de design já explícita no spec original ('Nunca' criar campo novo pra isso), reafirmada."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "O envio de e-mail é síncrono, dentro do próprio loop de `_notify_covered_bets` -- cada acerto premiado bloqueia a rotina de cron até o SMTP responder (até o timeout configurado). Sem fila assíncrona (Celery foi removido do projeto na Story 2.1, decisão explícita)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.7. Comportamento aceito conscientemente pela própria fronteira desta story ("Não implementar... fila assíncrona -- Celery já foi removido do projeto"), não uma omissão -- revisitar só se o volume de acertos premiados por execução crescer o suficiente pra tornar isso um problema prático de duração do job.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- decisão de arquitetura já explícita (Celery removido deliberadamente na Story 2.1), reafirmada."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "`bet.prize_description` expõe a chave interna de `calculate_bet_prize` (ex. `'dupla_sena'`, `'milionaria'` sem acento/formatação) diretamente no corpo do e-mail, como 'Categoria: dupla_sena' -- destoa da linha 'Jogo:' logo acima, que usa `bet.game` com capitalização/acentuação de exibição."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.7. Mesma causa raiz já registrada como rótulo pouco preciso na Story 2.1 (`category` colapsado numa faixa ampla) -- agora também visível no e-mail, não só na tela. Resolver exigiria uma tabela de rótulos amigáveis por categoria, fora do escopo de uma story de envio de e-mail.
  status: resolved
  resolution: "`PRIZE_CATEGORY_LABELS`/`get_prize_category_label()` (apps/loterias_core/utils.py) traduz a chave crua (`dupla_sena`, `milionaria`, ...) pro rótulo de exibição (`Dupla-Sena`, `+Milionária`, ...); `emails.py` usa a função em vez de `bet.prize_description` cru -- fechado na remediação pós-Epic 7, 2026-09-28. `GeneratedBet.prize_description` continua guardando a chave crua no banco (não é um dado incorreto, só de exibição). O rótulo continua colapsado por faixa ampla (item da Story 2.1, logo acima) -- não resolvido por este fix, só o formato de exibição."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-7-envio-de-email-de-acerto-premiado.md`
  summary: "O corpo do e-mail não inclui os números da aposta nem um link/URL clicável pro detalhe do jogo -- só um texto genérico 'Acesse o site para ver os detalhes completos', sem endereço (diferente do welcome e-mail, que tem uma URL fixa pro localhost)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.7. Nenhuma FR exige link/CTA concreto; o projeto não tem hoje um domínio configurado de forma reutilizável fora do `ALLOWED_HOSTS` (não usa `django.contrib.sites` pra isso) -- adicionar um link real exigiria decidir essa configuração primeiro, fora do escopo desta story.
  status: resolved
  resolution: "Totalmente resolvido 2026-09-29: `send_hit_notification_email` (apps/loterias_core/emails.py) inclui os números da aposta (e trevos, quando o jogo tem) e um link clicável (`{SITE_URL}{reverse('bet_detail', ...)}`) pro detalhe do jogo no corpo do e-mail. `SITE_URL` (loterias/settings/base.py) é nova env var, default `http://www.loterias.internal` (a URL real de homologação já documentada em deploy/lab/README.md) -- decisão do Boss de usar o link de homologação em vez de esperar um domínio de produção. Adicionada em `.env.example` e nos 2 serviços de `deploy/lab/docker-compose.yml`. Testes novos: `test_email_link_uses_configured_site_url` (confirma que troca de verdade com override) + assert de link na URL default em `test_email_content_includes_...`."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-rotina-mensal-de-valores-de-premiacao.md`
  summary: "`calculate_bet_prize` consulta o banco (`_find_prize_tier` + `PrizeTier.objects.filter(game=game).exists()`) toda vez que a faixa de acertos do usuário não bate com a faixa premiada do concurso específico -- dentro de `_notify_covered_bets` (varredura de cron por bet) isso reintroduz até 2 queries por bet não pré-carregadas, o mesmo padrão de N+1 que `results_by_pair`/`preferences_by_user_id` foram escritos pra evitar nesta mesma função."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.8. Avaliado conscientemente e não corrigido agora: a tabela `PrizeTier` é pequena por natureza (6 jogos x poucas dezenas de faixas possíveis x 3 meses retidos -- no máximo algumas centenas de linhas, índice simples), então o custo por query é desprezível comparado aos N+1 anteriores (que envolviam tabelas crescendo com o número de usuários, ou I/O de rede/SMTP). Revisitar só se o volume de `GeneratedBet` por execução de cron crescer o suficiente pra tornar mensurável, ou se `PrizeTier` deixar de ser pequena (ex. se a retenção de 3 meses for aumentada).
  status: accepted
  resolution: "Finalizado 2026-09-28 -- reafirmado: PrizeTier é pequena por natureza, custo por query desprezível."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-8-rotina-mensal-de-valores-de-premiacao.md`
  summary: "3 dos 5 pontos de chamada de `calculate_bet_prize` (`check_user_results`, `save_manual_bet_view`, `check_bet_result_view`) nunca populam `official_result['captured_at']` -- sempre caem no default de `reference_month` (mês corrente local)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.8; investigado e considerado correto por design, não um bug: os 3 pontos fazem uma busca ao vivo via `fetch_cef_result` bem no momento da chamada (não leem um `LotteryResult` histórico já salvo), então tratar o mês corrente como `reference_month` é exatamente certo -- é uma captura acontecendo agora. Além disso, com a correção desta revisão que faz `calculate_bet_prize` priorizar a faixa de premiação do próprio concurso (`official_result['prizes']`, que é a fonte da verdade e nunca some) sobre o `PrizeTier` mensal, o `reference_month` só influencia o resultado no caminho de fallback (concurso sem essa faixa específica) -- risco residual baixo. Revisitar só se a CAIXA fornecer a data real de apuração do concurso (`dataApuracao` na API) e `fetch_cef_result` passar a propagá-la (ligação natural com a Story 2.11).
  status: accepted
  resolution: "Finalizado 2026-09-28 -- já investigado e concluído correto por design, não é um defeito. Nada a corrigir."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-9-tratamento-de-falha-da-captura-de-resultado.md`
  summary: "O limiar `CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS` (8 dias) mede a idade do `GeneratedBet` mais antigo do par, não a distância real até a data em que o concurso deveria ter sido sorteado -- um usuário pode criar uma aposta manual pra um concurso muito distante no futuro (nenhuma validação de teto superior existe hoje, só `_block_if_contest_already_drawn` bloqueando concurso já sorteado) e isso soaria como falha de captura passados 8 dias, mesmo sendo normal."
  evidence: Achado independentemente pelo Blind Hunter e pelo Edge Case Hunter na revisão da Story 2.9; já reconhecido na própria spec (seção Intent) como "escolha de engenharia, não constante validada contra o calendário oficial de sorteios". Corrigir de verdade exigiria ou uma validação de teto superior pro concurso digitado manualmente (`save_manual_bet_view`/`api_create_bet_view`), ou conhecer o calendário real de sorteio de cada Jogo (dado que o projeto não tem hoje e que fabricar seria arriscado) -- fora do escopo desta story (explicitamente listado em "Nunca"). Revisitar se o volume de alertas falsos-positivos no lab/produção se mostrar um problema real.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- explicitamente fora de escopo ('Nunca' na própria spec); o projeto não tem e não deve fabricar um calendário de sorteios."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-9-tratamento-de-falha-da-captura-de-resultado.md`
  summary: "As 3 execuções diárias de `fetch_daily_results` (3h/3h15/3h30) não têm nenhum lock/mutex contra sobreposição -- se o backlog de pares abertos crescer o suficiente pra uma execução ultrapassar 15 minutos, a próxima pode começar antes da anterior terminar, triplicando picos de tráfego simultâneo contra a API oficial da Caixa."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.9. Mesma causa raiz do item de modo WAL já registrado na Story 2.1 (ver acima) -- esta story amplifica o risco (3x mais execuções/dia). Não corrigido agora porque o volume real de pares abertos é baixo hoje.
  status: accepted
  resolution: "Finalizado 2026-09-28 junto com o item de WAL mode (Story 2.1, mesma causa raiz) -- coberto pela mesma story futura proposta lá se a contenção virar problema real."

## Deferred from: code review of spec-epic-3-novo-fluxo-de-cadastro (2026-09-11)

- source_spec: `_bmad-output/implementation-artifacts/spec-epic-3-novo-fluxo-de-cadastro.md`
  summary: "`createcachetable` não está documentado nos comandos de setup local do `CLAUDE.md` (só `migrate`/`runserver`), nem no runbook do lab (`deploy/lab/README.md`) -- o novo `CACHES` (`DatabaseCache`, Epic 3) exige essa tabela; um dev novo seguindo exatamente o CLAUDE.md quebra no primeiro uso de cache (ex. `ResendConfirmationEmailView`)."
  evidence: Achado pelo Blind Hunter e Edge Case Hunter, independentemente, na revisão de código do Epic 3 (2026-09-11, pedida pelo Boss antes da retrospectiva). O `Dockerfile`/deploy do lab já rodam `createcachetable` corretamente -- só o fluxo de dev local documentado no CLAUDE.md está desatualizado. Deferido porque a correção edita um arquivo de contexto de agente (CLAUDE.md), fora do escopo de patch automático desta revisão.
  status: resolved
  resolution: "CLAUDE.md já documenta `python manage.py createcachetable` no bloco de comandos de setup local (linha 26) -- confirmado na retrospectiva dos Epics 6/7, 2026-09-27. O runbook do lab não precisa mencionar, já que o `Dockerfile`/deploy rodam automaticamente."

## Deferred from: code review of spec-2-12-normalizacao-de-concurso (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-12-normalizacao-de-concurso.md`
  summary: "`contest` continua editável como texto livre no Django admin (`GeneratedBetAdmin`/`LotteryResultAdmin`, não está em `readonly_fields`) -- um operador digitando `'02500'` direto no admin recria exatamente o bug que a Story 2.12 corrigiu nos 3 pontos de entrada via views, porque o admin nunca passa por `normalize_contest`."
  evidence: Achado pelo Edge Case Hunter (confirmado lendo `apps/loterias_core/admin.py`, `contest` ausente de `readonly_fields` nas duas classes) na revisão da Story 2.12. Pré-existente (o campo sempre foi editável, não é uma regressão desta story) e fora do Given/When/Then literal da AC (que só lista `create_bet_view`/`save_manual_bet_view`/`api_create_bet_view`), mas contradiz o objetivo declarado da story ("normalizado de forma consistente em todos os pontos que o recebem"). Corrigir exigiria `save_model`/validação customizada no `ModelAdmin`, fora do escopo de patch trivial desta revisão -- decisão de produto sobre se vale a pena travar edição manual de `contest` no admin.
  status: resolved
  resolution: "Já resolvido desde a Story 2.16 (2026-09-14), não pela 2.12: `_NormalizedContestFormMixin.clean_contest()` (apps/loterias_core/admin.py) chama `normalize_contest()` no save do admin, aplicado via `form = GeneratedBetAdminForm`/etc. em `GeneratedBetAdmin`, `LotteryResultAdmin` e `CaptureFailureAlertAdmin`. Confirmado lendo admin.py na remediação pós-Epic 7, 2026-09-28 -- este item ficou órfão na lista, nunca reconciliado."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-12-normalizacao-de-concurso.md`
  summary: "`normalize_contest('0')`/`('00')` são aceitos e normalizados pra `'0'`, mas nenhum concurso real da CEF é numerado 0 -- não há validação de faixa mínima, só de formato."
  evidence: Achado independentemente pelo Blind Hunter e Edge Case Hunter na revisão da Story 2.12. Mesma categoria de lacuna já registrada como deferida na Story 2.9 (nenhuma validação de teto superior pro concurso digitado manualmente) -- a AC desta story pede só normalização de formato (zeros à esquerda) e rejeição de não numérico, nunca validação de faixa/plausibilidade contra o calendário real de sorteios. Revisitar junto com o item já deferido da Story 2.9 se isso se mostrar um problema prático.
  status: resolved
  resolution: "`normalize_contest` (apps/loterias_core/models.py) agora rejeita valores < 1 com `ValueError` -- fechado na remediação pós-Epic 7, 2026-09-28. Não afeta o item irmão da Story 2.9 (teto superior/plausibilidade contra calendário de sorteio), que continua em aberto."

## Deferred from: code review of spec-2-13-validacao-de-jogo-em-api-create-bet-view (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-13-validacao-de-jogo-em-api-create-bet-view.md`
  summary: "`api_create_bet_view` ainda pode devolver 500 não tratado pra payload JSON malformado -- `json.loads(request.body)` levanta `JSONDecodeError` sem corpo não-JSON, e `data.get('concurso', '').strip()` levanta `AttributeError` se `concurso` vier como número/objeto em vez de string."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.13. Pré-existente (linhas anteriores a esta story, não tocadas pelo diff) -- o escopo desta story era especificamente a checagem de `jogo` ausente de `GAMES_CONFIG` (já corrigida, incluindo o caso de tipo não-hasheável). Corrigir de verdade exigiria um `try/except` mais amplo envolvendo todo o parse do payload, fora do escopo de patch trivial desta revisão.
  status: resolved
  resolution: "`api_create_bet_view` (apps/loterias_core/views.py) agora envolve `json.loads` em try/except (400 em `JSONDecodeError`), valida `isinstance(data, dict)` e `isinstance(concurso, str)` antes de `.strip()` -- fechado na remediação pós-Epic 7, 2026-09-28, com 3 testes novos (`test_api_create_bet_rejects_malformed_json_body` e variantes)."

## Deferred from: code review of spec-2-14-bloqueio-real-de-concurso-duplicado (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-14-bloqueio-real-de-concurso-duplicado.md`
  summary: "`_block_if_duplicate_bet` (check-then-create) não tem `UniqueConstraint(user, game, contest)` no banco nem `transaction.atomic()`/`select_for_update` -- duas submissões quase simultâneas do mesmo usuário pro mesmo Jogo+Concurso ainda podem passar as duas pelo `.exists()` antes de qualquer uma criar, gerando 2 registros duplicados apesar da mensagem agora dizer 'não é possível'."
  evidence: Achado convergente pelo Blind Hunter e Edge Case Hunter na revisão da Story 2.14. Mesma categoria de risco de concorrência já deferida nas Stories 2.2/2.6 (mesmo padrão check-then-create, mesmo racional de baixo volume de uso concorrente esperado). Corrigir de verdade exigiria uma `UniqueConstraint`+migration e tratamento de `IntegrityError` nos 2 pontos de entrada -- mudança de schema, fora do escopo de patch trivial desta revisão.
  status: accepted
  resolution: "Risco aceito pelo Boss (2026-09-28), junto dos itens irmãos de concorrência já deferidos nas Stories 2.2/2.6/2.17 (check-then-write sem lock em `_block_if_duplicate_bet`, `NotificationPreference`, `regenerate_bet_view`) -- baixo volume de uso concorrente por usuário individual não justifica hoje a mudança de schema (`UniqueConstraint`+migration+tratamento de `IntegrityError`)."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-14-bloqueio-real-de-concurso-duplicado.md`
  summary: "**RESOLVIDO pela Story 2.17 (2026-09-14).** `regenerate_bet_view` continua criando sem checagem um segundo `GeneratedBet` pro mesmo usuário+Jogo+Concurso do jogo original (pinado pelo teste existente `test_regenerating_bet_creates_new_record_and_redirects`, que espera `count() == 2`) -- inconsistente com a garantia nova de `create_bet_view`/`save_manual_bet_view` ('não é possível gerar outro pro mesmo Jogo+Concurso')."
  evidence: Achado pelo Verification Gap Reviewer na revisão da Story 2.14. Fora do escopo desta story por decisão explícita do próprio AC em `epics.md` ("aplicado... em `create_bet_view` e `save_manual_bet_view`", sem mencionar `regenerate_bet_view`) -- mas o resultado de produto é inconsistente entre as duas telas. Decisão do Boss pendente sobre se `regenerate_bet_view` deveria seguir a mesma regra (ou se "refazer" é intencionalmente uma exceção, já que troca só os números sorteados mantendo o mesmo Jogo+Concurso do bet original).
  resolution: A Story 2.17 decidiu isso -- `regenerate_bet_view` (apps/loterias_core/views.py:320-370) agora substitui o `GeneratedBet` original in-place (`original_bet.save()`, nunca `.create()`), nunca cria um segundo registro. O teste foi renomeado/reescrito pra `test_regenerating_bet_replaces_original_in_place` (apps/loterias_core/tests.py:1062-1074), que afirma `count() == 1`. Achado (e corrigida a citação órfã deste item) na retrospectiva do Epic 2, 2026-09-16 -- ver `epic-2-retro-2026-09-16.md` achado F9.
  status: resolved

## Deferred from: code review of spec-2-15-runbook-de-backfill-inicial-de-notificacoes (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-15-runbook-de-backfill-inicial-de-notificacoes.md`
  summary: "`mark_initial_notifications_read` só ajusta `HitNotification.is_read` (badge/lista do site) -- se algum usuário já tinha `NotificationPreference.email_enabled=True` antes do primeiro ciclo real do cron, o e-mail de acerto premiado (Story 2.7) já teria sido disparado pra um acerto que o usuário já conhecia, e o backfill não desfaz isso (e-mail já enviado não pode ser recolhido)."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.15. Confirmado no lab (2026-09-14) que nenhum usuário tinha `NotificationPreference` com `email_enabled=True` até agora (todos usam o default `email_enabled=False`), então nenhum e-mail real chegou a ser disparado por esse caminho -- mas o gap é real pra quando a preferência de e-mail for ativada por algum usuário antes do próximo rollout/reset. Fora do escopo desta story: a AC pede explicitamente só ajuste do estado de leitura ("só o estado de leitura é ajustado"), nunca supressão de e-mail. Corrigir de verdade exigiria uma janela de graça (ex.: não enviar e-mail pra `HitNotification` cujo `GeneratedBet.result_checked` já era `True` antes da criação) -- decisão de produto, fora do escopo de patch trivial.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- `mark_initial_notifications_read` foi um script de backfill pontual pro rollout inicial (já executado), não uma rotina recorrente; o gap só reabre se um backfill semelhante for necessário de novo no futuro, cenário hipotético sem plano concreto hoje."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-15-runbook-de-backfill-inicial-de-notificacoes.md`
  summary: "`mark_initial_notifications_read --apply` não trata `OperationalError`/'database is locked' se rodado durante a janela em que `loterias-cron` está escrevendo no mesmo SQLite (3h/3h15/3h30)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.15. Mesma causa raiz do item de modo WAL já registrado na Story 2.1 (ver acima) -- mitigado na prática pelo runbook avisando pra não rodar durante a janela do cron, não corrigido no código.
  status: accepted
  resolution: "Finalizado 2026-09-28 junto com o item de WAL mode -- mitigado na prática pelo runbook (não rodar na janela do cron), mesma causa raiz."

- source_spec: `_bmad-output/implementation-artifacts/spec-2-15-runbook-de-backfill-inicial-de-notificacoes.md`
  summary: "Nenhum teste de comando de management neste projeto (incluindo `update_monthly_prize_values`/`fetch_daily_results`, pré-existentes) verifica o texto impresso no stdout -- convenção já estabelecida no projeto, mantida por consistência mesmo tendo sido parcialmente endereçada nesta story com um teste dedicado de lote misto."
  evidence: Achado pelo Verification Gap Reviewer na revisão da Story 2.15. Já mitigado nesta própria story via `test_dry_run_message_and_apply_count_reflect_only_unread_in_mixed_batch` (cobre o caso mais arriscado -- contagem de não-lidas em lote misto); registrado só pra nota de que os outros comandos do projeto continuam sem essa cobertura, caso vire prioridade revisitar todos de uma vez.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- convenção de projeto reafirmada, caso mais arriscado já coberto; não é um defeito, é uma nota de escopo de teste."

## Deferred from: code review of spec-2-17-refazer-segue-regra-duplicata (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-17-refazer-segue-regra-duplicata.md`
  summary: "`regenerate_bet_view` continua sendo um endpoint GET simples (sem `@require_POST`/CSRF form, sem confirmação client-side) -- antes da Story 2.17 um disparo acidental (duplo clique, replay de GET do histórico do navegador) só criava uma linha extra inofensiva; agora sobrescreve silenciosamente e sem chance de recuperação os números que o usuário tinha."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.17. Pré-existente (o endpoint já era GET sem proteção antes desta story) -- a mudança desta story aumenta a gravidade da consequência de um disparo acidental, mas corrigir exigiria mudar o método HTTP/formulário no template e adicionar confirmação, fora do escopo de patch trivial (e fora do Given/When/Then da AC, que é só sobre não duplicar).
  status: resolved
  resolution: "`regenerate_bet_view` (apps/loterias_core/views.py) agora exige `@require_POST`; os 2 pontos de entrada (bet_detail.html, history.html) viraram `<form method=\"post\">` com CSRF, e um `confirm()` de navegador (mesmo padrão já usado por `.btn-delete`) avisa antes de submeter -- fechado a pedido explícito do Boss, 2026-09-28. Teste novo `test_regenerating_via_get_is_rejected` confirma 405 em GET sem tocar no jogo."
- source_spec: `_bmad-output/implementation-artifacts/spec-2-17-refazer-segue-regra-duplicata.md`
  summary: "Sem `transaction.atomic()`/`select_for_update` -- duas requisições `regenerate_bet` quase simultâneas pro mesmo bet podem ambas ler o registro antes de qualquer uma salvar, e o segundo `save()` sobrescreve silenciosamente o primeiro (um dos 2 conjuntos de números gerados se perde)."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.17. Mesma categoria de risco de concorrência já deferida nas Stories 2.2/2.6/2.14 (check-then-write sem lock, baixo volume de uso concorrente esperado por usuário individual).
  status: accepted
  resolution: "Risco aceito pelo Boss (2026-09-28) junto com os demais itens de concorrência check-then-write (Stories 2.2/2.6/2.14). A confirmação client-side adicionada no item irmão acima (GET->POST) reduz bastante a chance prática de 2 disparos quase simultâneos, mas não elimina o risco de fato -- aceito assim mesmo."

## Deferred from: code review of spec-2-16-travar-concurso-admin (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-16-travar-concurso-admin.md`
  summary: "Um valor de Concurso com muitos zeros à esquerda (>20 caracteres antes de normalizar, ex. 20 zeros + `'5'`) é rejeitado pela validação nativa de `max_length=20` do Django ANTES de `clean_contest` rodar -- a mensagem de erro fala de tamanho, não do problema real, e um valor que normalizaria pra algo válido é recusado."
  evidence: Achado pelo Edge Case Hunter na revisão da Story 2.16, confirmado empiricamente (`'0'*20 + '5'` recusado por max_length antes de chegar em `normalize_contest`). Entrada exige um concurso digitado com 20+ caracteres, cenário sem uso prático real -- baixo impacto, não corrigido (exigiria reordenar a validação ou aumentar `max_length`, fora do escopo de patch trivial desta revisão).
  status: accepted
  resolution: "Finalizado 2026-09-28 -- cenário sem uso prático real (concurso de 20+ dígitos não existe), mantido como está."

## Deferred from: code review of spec-2-18-suporte-2o-sorteio-dupla-sena (2026-09-14)

- source_spec: `_bmad-output/implementation-artifacts/spec-2-18-suporte-2o-sorteio-dupla-sena.md`
  summary: "`update_monthly_prize_values` só promove `latest_result.prizes` (1º sorteio) pra `PrizeTier` -- nunca `prizes_second_draw`. Quando `calculate_bet_prize` cai no fallback de `PrizeTier` pro 2º sorteio (faixa específica ausente em `prizes_second_draw`), usa sem querer o valor do `PrizeTier` do 1º sorteio pra uma faixa do 2º."
  evidence: Achado pelo Blind Hunter na revisão da Story 2.18. Impacto baixo na prática: `prizes_second_draw` é extraído junto com `numbers_second_draw` sempre que a API publica o 2º sorteio, então o fallback pro `PrizeTier` só entraria em jogo se a faixa específica de acertos nunca tivesse aparecido em nenhum `listaRateioPremio` capturado (cenário raro). Corrigir de verdade exigiria uma segunda trilha de `PrizeTier` por sorteio (campo novo ou model separado), fora do escopo desta story.
  status: accepted
  resolution: "Finalizado 2026-09-28 -- cenário raro, exigiria uma segunda trilha de PrizeTier por sorteio (campo/model novo, migration). Proposto como story própria se o cenário de fallback pro 2º sorteio se mostrar real."

## Deferred from: retrospectiva do Epic 2 (2026-09-16)

Achados da revisão de fronteira entre stories (não de uma story isolada) -- ver `epic-2-retro-2026-09-16.md` pro relatório completo, incluindo os 3 achados marcados `[FIX NOW]` que viraram action items em `sprint-status.yaml` (F1, F2, F3) e não estão repetidos aqui.

- source_spec: `epic-2-retro-2026-09-16.md` (achado F5, cruzando Stories 2.7/2.9)
  summary: "`send_hit_notification_email` em `_notify_covered_bets` (jobs.py) tem seu valor de retorno descartado -- ao contrário de `_alert_operator_of_stale_capture_failures` (Story 2.9), que só persiste o dedup depois de confirmar que o e-mail foi de fato enviado, a `HitNotification` de acerto premiado é criada incondicionalmente antes do envio, então uma falha transiente de SMTP nunca é percebida nem reenviada."
  evidence: Achado pela lente adversarial na retrospectiva do Epic 2. Hoje nenhum usuário no lab tem `NotificationPreference.email_enabled=True` (confirmado na Story 2.15), então o caminho nunca disparou de verdade ainda -- risco real, mas não ativo. Corrigir exigiria um campo tipo `email_sent_at` e mudar o critério da varredura de `notification__isnull=True`, fora do escopo de um patch trivial.
  status: resolved
  resolution: "Parcialmente resolvido 2026-09-28: `send_hit_notification_email` (apps/loterias_core/emails.py) agora loga `logger.warning` quando `send_mail` não confirma entrega (retorno 0/falsy), tornando a falha visível nos logs -- antes era completamente silenciosa. O reenvio automático de verdade continua em aberto (exigiria o campo `email_sent_at` + mudar o critério de varredura, fora de escopo de um patch de última hora); revisitar se o volume de e-mails de acerto justificar a mudança de schema."

- source_spec: `epic-2-retro-2026-09-16.md` (achado F6, cruzando Stories 2.9/2.10)
  summary: "`already_alerted` (dedup de alerta de falha de captura, `CaptureFailureAlert`) nunca é limpo quando o `LotteryResult` correspondente é purgado manualmente (Story 2.10) -- se o mesmo par Jogo+Concurso voltar a falhar de captura depois de purgado, o alerta novo é silenciosamente suprimido pelo dedup antigo."
  evidence: Achado pela lente adversarial na retrospectiva do Epic 2. Cenário raro (exige purge manual + nova falha real no mesmo par), sem evidência de ter ocorrido no lab -- registrado pra não precisar reinvestigar se aparecer.
  status: resolved
  resolution: "`LotteryResultAdmin.purge_until_date` (apps/loterias_core/admin.py) agora limpa os `CaptureFailureAlert` dos pares purgados na mesma ação, via `Q()` OR por par exato (nunca `game__in`/`contest__in` cruzados, que apagariam por engano o alerta de um par não purgado) -- fechado na remediação pós-Epic 7, 2026-09-28, com 2 testes novos (`test_purge_clears_capturefailurealert_for_the_purged_pair`/`test_purge_does_not_clear_capturefailurealert_of_an_unrelated_pair`)."

- source_spec: `epic-2-retro-2026-09-16.md` (achado F7, Story 2.5/2.6)
  summary: "`NotificationPreference.site_enabled=False` só zera o badge (`context_processors.py`, Story 2.6) -- a lista completa de notificações não lidas continua renderizando normalmente se o usuário acessar `/notificacoes/` direto pela URL."
  evidence: Achado pela lente edge-case-hunter na retrospectiva do Epic 2. Inconsistência de UX entre o indicador (respeita a preferência) e a tela de destino (não respeita) -- baixo risco prático, ninguém reportou confusão até agora.
  status: resolved
  resolution: "`notifications_view` (apps/loterias_core/views.py) agora checa `NotificationPreference.site_enabled` do jeito que o context_processor do badge já fazia -- com a preferência desativada, a lista renderiza vazia com uma mensagem informativa, em vez de mostrar tudo normalmente. Fechado na remediação pós-Epic 7, 2026-09-28, com 3 testes novos (`test_site_disabled_preference_hides_the_full_list_too` e variantes)."

## Deferred from: build da Story 4.1 (2026-09-18)

- source_spec: `_bmad-output/implementation-artifacts/spec-4-1-reorganizacao-da-area-util-da-home.md`
  summary: "Os cards do `game-selector` são `div onclick` com radio `d-none required` — inacessíveis por teclado e, sem jogo selecionado, o submit falha com 'invalid form control is not focusable' sem nenhum aviso visível (agora mais exposto, já que o botão Gerar Jogo fica acima do seletor)."
  evidence: Achado pelo Blind Hunter na revisão da Story 4.1. Pré-existente (a mecânica de seleção não mudou); a Story 4.2 (UX-DR7) e o padrão `.btn-check` da EXPERIENCE.md já preveem reescrever o seletor de forma acessível — resolver lá.
  status: resolved
  resolution: "Confirmado lendo templates/loterias_core/home.html (remediação pós-Epic 7, 2026-09-28): o seletor de jogos hoje é `<input type=\"radio\" class=\"lq-tile-input\">` real com `<label for=\"jogo-{{ key }}\">`, não mais `div onclick` com radio oculto -- acessível por teclado nativamente (Tab entra/sai do grupo, setas navegam). Resolvido pela migração pro Lottiq Design System no Epic 5, não por uma story específica desta epic."

## Deferred from: build da Story 4.2 (2026-09-18)

- source_spec: `_bmad-output/implementation-artifacts/spec-4-2-icone-por-jogo-no-seletor.md`
  summary: "O comportamento JS do seletor (`selectGame`: atualizar ícone/nome/resumo da área 'jogo selecionado', sugestão de concurso, restauração via bfcache/back) não tem teste automatizado — os testes só cobrem o HTML/CSS renderizado; o projeto não tem infra de teste de frontend (Selenium/Playwright/Jest)."
  evidence: Achado pelo Blind Hunter na revisão da Story 4.2. Validado só manualmente no navegador pelo Boss. Revisitar se mais lógica de JS entrar nas Stories 4.3+ (toggle das Regras de Geração, confirmação FR-23) — aí vale montar um harness mínimo de teste de JS/E2E.
  status: accepted
  resolution: "Finalizado 2026-09-28 como lacuna de infra reconhecida, não corrigida agora -- montar um harness de teste de JS/E2E (Playwright já está disponível neste workstation pra verificação manual, mas nunca foi integrado como suite automatizada no CI) é um investimento de infra própria, não um patch pontual. Mais logica de JS realmente entrou depois (Stories 4.3, 7.1-7.5) sem harness -- proposto como story própria (setup de pytest-playwright ou similar + primeiros testes do seletor de jogo e do toggle de Regras de Geração) se a lacuna virar prioridade."

## Deferred from: build da Story 4.3 (2026-09-18)

- source_spec: `_bmad-output/implementation-artifacts/spec-4-3-model-generationrule-e-tela-de-edicao.md`
  summary: "O aviso 'sem proteção de sequência' (FR-23) só existe no navegador (modal em JS); um POST direto ou sem JavaScript salva tudo desligado sem confirmação, e nenhum teste exercita o JS da tela (switch/modais)."
  evidence: Achado pelo Blind/Edge Case Hunter na revisão da Story 4.3. Baixo risco (usuário logado editando as próprias regras), mas junto com o item da 4.2 reforça a falta de infra de teste de frontend — revisitar ao montar um harness de JS/E2E.
  status: accepted
  resolution: "Finalizado 2026-09-28 junto com o item irmão da Story 4.2 -- mesma causa raiz (falta de harness de JS/E2E), baixo risco prático (usuário logado editando as próprias regras). Coberto pela mesma story futura proposta lá."

## Deferred from: build da Story 4.4 (2026-09-19)

- source_spec: `_bmad-output/implementation-artifacts/spec-4-4-regras-de-geracao-mega-milionaria-quina-dupla.md`
  summary: "`CLAUDE.md` (seção 'Lógica de domínio das loterias') ainda descreve `generate_bet()` só com a Regra de Sequência adaptativa; deve mencionar `GenerationRule`/`bet_satisfies_rules` (modo personalizado) — atualizar quando o Epic 4 fechar."
  evidence: Achado pelo Blind Hunter na revisão da Story 4.4; adiado porque o conserto edita um arquivo de contexto de agente.
  status: resolved
  resolution: "CLAUDE.md já documenta `GenerationRule`/`bet_satisfies_rules` e o modo personalizado por completo na seção 'Lógica de domínio das loterias' (linhas 88/93) -- confirmado na retrospectiva dos Epics 6/7, 2026-09-27."
