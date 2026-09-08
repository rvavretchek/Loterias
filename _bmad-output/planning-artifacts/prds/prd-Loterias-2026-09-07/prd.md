---
title: Loterias — Verificação de Resultados e Novo Fluxo de Cadastro
status: final
created: 2026-09-07
updated: 2026-09-08
inputDocuments: ["docs/diagnostico-projeto.md"]
---

# PRD: Loterias — Verificação de Resultados e Novo Fluxo de Cadastro

## 0. Objetivo do Documento

Este PRD é dirigido ao próprio Ricardo (Boss), como PM e único desenvolvedor do projeto Loterias, e serve tanto como especificação de trabalho quanto como peça de portfólio — a documentação em si é parte do valor demonstrado. Ele cobre duas frentes de funcionalidade que se somam a um sistema já funcional de geração de apostas e autenticação por e-mail (`apps/loterias_core`, `apps/accounts`), documentado tecnicamente em `docs/diagnostico-projeto.md` (que também registra a remoção da multitenancy, uma decisão de arquitetura anterior a este PRD e fora do escopo aqui). O documento usa vocabulário fixado no Glossário (§3); termos de FRs, Jornadas de Usuário (UJs) e Métricas de Sucesso (SMs) devem ser lidos exatamente como definidos ali.

**Convenção de nomenclatura de código (decisão deste PRD, ver §3.1):** todo item de código — variáveis, constantes, classes, funções, model fields — passa a ser em inglês, inclusive o código legado hoje em português (`JogoGerado`, `ResultadoLoteria`, `capturar_resultado_cef`, etc.). Prosa deste documento, UI (labels/mensagens ao usuário) e o vocabulário de domínio do Glossário continuam em português — a convenção é só de identificador de código.

## 1. Visão

O Loterias hoje gera apostas válidas para seis loterias brasileiras e guarda o histórico de cada usuário — mas para saber se ganhou, o usuário precisa lembrar de voltar ao site e clicar manualmente em "verificar resultado", jogo por jogo. Isso é o oposto de por que alguém jogaria: a promessa de uma loteria é "e se eu tiver ganhado?", e hoje o sistema não responde essa pergunta sozinho.

As duas frentes deste PRD atacam os dois momentos em que, hoje, o sistema empurra pro usuário um trabalho que deveria ser dele: a primeira impressão (cadastro) e a primeira vitória (saber que ganhou). A primeira faz o sistema vigiar os resultados oficiais da Caixa por conta própria — todo dia — e avisar o usuário assim que ele faz login se algum dos seus jogos bateu, diferenciando claramente "acertou alguns números" de "acertou o suficiente pra ganhar prêmio". A segunda troca o cadastro genérico do django-allauth por um fluxo deliberado (e-mail → link → senha → nome) que corresponde a como o Ricardo quer que a primeira impressão do produto aconteça.

Nenhuma das duas depende de infraestrutura nova pesada: a captura de resultado já existe (`fetch_cef_result`, antes `capturar_resultado_cef` — ver §3.1), só falta rodar sozinha; o cadastro por e-mail já existe via allauth, só falta reordenar os passos.

## 2. Usuário-Alvo

### 2.1 Jobs To Be Done

- Como jogador de loteria, quero saber se ganhei sem ter que lembrar de checar manualmente — a captura de resultado deve acontecer por conta própria.
- Como jogador, quero distinguir rapidamente "acertei alguns números, mas não ganhei nada" de "acertei o suficiente pra ganhar um prêmio" — a segunda é a única que realmente importa checar com atenção.
- Como pessoa se cadastrando, quero confirmar que o e-mail é meu antes de escolher uma senha — não quero criar uma senha pra uma conta que talvez nem seja minha (e-mail digitado errado, por exemplo).
- Como Ricardo (Boss), quero que este projeto demonstre, no próprio código e na própria documentação, capacidade de diagnosticar, decidir arquitetura com critério (django-crontab em vez de Celery/Redis) e documentar como PM — isso é tão parte do "produto" quanto as funcionalidades em si, dado que o projeto é peça de portfólio.

### 2.2 Não-Usuários (v1)

- Quem quer apostar de verdade (com dinheiro) dentro do sistema — o Loterias gera números e verifica resultados, não processa apostas oficiais nem pagamentos.
- Quem precisa de notificação em tempo real (segundos após o sorteio) — a verificação é em lote, diária; não é um serviço de plantão do resultado saindo ao vivo.

### 2.3 Jornadas de Usuário Principais

- **UJ-1. Dulce gera jogos e é avisada de um acerto.**
  - **Persona + contexto:** Dulce joga Mega-Sena e Lotomania toda semana, gerando vários jogos de uma vez quando lembra. Ela não tem paciência pra voltar ao site só pra conferir resultado.
  - **Estado de entrada:** autenticada, na página inicial.
  - **Caminho:**
    1. Escolhe um jogo (ex.: Mega-Sena), o campo de concurso já vem preenchido com uma sugestão (o próximo concurso sequencial daquele jogo) — ela pode aceitar ou digitar outro número (cobre concursos especiais/comemorativos, ex. "Lotomania da Independência", que rodam em paralelo à numeração normal).
    2. Gera o jogo. Repete quantas vezes quiser, no mesmo jogo ou em jogos diferentes, na mesma sessão — sempre que o concurso digitado ainda não tiver resultado registrado.
    3. Se tentar gerar/salvar para um concurso que já tem resultado, o sistema bloqueia com mensagem clara.
    4. Pode também criar um jogo manual (digita os números em vez de gerar), sujeito à mesma regra de bloqueio.
    5. Em um login posterior, depois que a rotina diária capturou um resultado que bate com algum jogo dela, ela vê um badge no cabeçalho resumindo os acertos — diferenciando "acertos sem prêmio" de "acertos com prêmio".
  - **Clímax:** ela clica na notificação e vê a tela de detalhe do(s) acerto(s)/premiação(ões) — é o momento em que ela sabe, sem precisar caçar a informação, se ganhou e quanto.
  - **Resolução:** a partir da tela de detalhe, marca aquela notificação específica como lida. A preferência de *receber* notificação por site e/ou e-mail é uma configuração separada, ajustada uma vez, não por notificação individual.
  - **Caso de borda:** se a rotina diária falhar em capturar o resultado da Caixa (scraping quebrado, site fora do ar), Dulce simplesmente não vê notificação naquele dia — o sistema não avisa sobre a própria falha pra ela (ver FR-9).

- **UJ-2. Sônia se cadastra.**
  - **Persona + contexto:** Sônia encontrou o site e quer criar conta pela primeira vez.
  - **Estado de entrada:** não autenticada, na página inicial.
  - **Caminho:**
    1. Clica em "Crie sua conta". A tela pede só o e-mail. Ela informa e confirma.
    2. Sistema envia e-mail com link de confirmação; a UI avisa que enviou, orienta checar SPAM, e oferece um botão "reenviar e-mail de cadastro".
    3. Sônia abre o e-mail, clica no link, cai na tela de criação de senha: senha + confirmação (com ícone de "olho" pra mostrar/ocultar) + aceite dos termos de serviço (checkbox construído desde já, com o texto placeholder do Anexo A). Se as senhas não baterem, avisa inline.
    4. Confirma. É redirecionada à página inicial e faz login normalmente.
  - **Clímax:** no primeiro login, antes de liberar qualquer outra tela, o sistema pede nome e sobrenome — obrigatório, é o único passo entre o login e o uso real do sistema.
  - **Resolução:** conta completa, Sônia cai na home já com nome cadastrado.
  - **Caso de borda:** se ela demorar e o link expirar antes de criar a senha, a conta fica pendente; ao tentar usar o link vencido, vê mensagem clara e pode pedir reenvio (mesmo botão do passo 2).

## 3. Glossário

*Cada termo de domínio (em português, como sempre foi tratado neste projeto) traz entre parênteses o identificador de código correspondente, em inglês — ver mapeamento completo e regras em §3.1.*

- **Jogo** (`Game` — constante `GAMES_CONFIG`) — Um dos seis tipos de loteria suportados (Mega-Sena, +Milionária, Lotomania, Lotofácil, Quina, Dupla-Sena).
- **Concurso** (campo `contest`) — Identificador numérico de um sorteio específico de um Jogo. Não é estritamente sequencial nem exclusivo por Jogo — concursos especiais/comemorativos podem rodar em paralelo à numeração regular.
- **JogoGerado** (`GeneratedBet`) — Uma aposta salva por um usuário: um Jogo + um Concurso + um conjunto de números (e trevos, quando aplicável). Pode ser gerado automaticamente ou informado manualmente (campo `manual=True`).
- **ResultadoLoteria** (`LotteryResult`) — O resultado oficial de um Concurso, capturado da Caixa. Único por (Jogo, Concurso).
- **Acerto** (campo `hits`) — Interseção não vazia entre os números de um JogoGerado e os números de um ResultadoLoteria para o mesmo Jogo+Concurso.
- **Acerto premiado** — Acerto cuja quantidade de números atinge o mínimo que gera prêmio para aquele Jogo (ex.: 4+ na Mega-Sena). Ver `calculate_bet_prize` (antes `calcular_premiacao_jogo`).
- **Acerto não premiado** — Acerto que não atinge esse mínimo.
- **Notificação de Acerto** (`HitNotification` — nova classe) — Registro criado quando a rotina diária encontra um Acerto novo para um JogoGerado; carrega o estado lido/não-lido (`is_read`) e se é premiado ou não (`is_prize_winning`).
- **Preferência de Notificação** (`NotificationPreference` — nova classe) — Configuração por usuário de por onde deseja receber avisos de Acerto: site, e-mail, ou ambos.
- **Rotina diária de resultados** (função `fetch_daily_results` — nova) — Job agendado (django-crontab) que roda `fetch_cef_result` (antes `capturar_resultado_cef`) para os concursos em aberto de cada Jogo e cruza com os GeneratedBet dos usuários.
- **Rotina mensal de premiações** (função `update_monthly_prize_values` — nova) — Job agendado (django-crontab) que atualiza a tabela de valores de premiação vigentes.
- **Vínculo de Confirmação de Cadastro** — Token de uso único e com expiração que autentica a Sônia da UJ-2 na tela de criação de senha. Reaproveita o mecanismo já existente do django-allauth (`EmailConfirmationHMAC`) — não é uma classe nova do projeto, por isso não entra no mapeamento de renomeação de §3.1.
- **Faixa de Premiação** (`PrizeTier` — nova classe) — Valor de prêmio vigente para uma quantidade específica de acertos de um Jogo (ex.: Mega-Sena com 6 acertos = Sena; com 5 = Quina; com 4 = Quadra), capturado a cada virada de mês pela rotina mensal. É a regra de validação de quais quantidades de acertos são premiadas em cada Jogo, além de ser uma fonte oficial de valor de prêmio. Mantém histórico só dos 3 meses mais recentes por (Jogo, quantidade de acertos) — suficiente pra validar acertos retroativos dentro dessa janela.

### 3.1 Convenção de Nomenclatura de Código

**Regra:** todo identificador de código — nomes de variável, constante, classe, função e model field — é em inglês, tanto no código novo desta PRD quanto no código legado já existente. Não muda: strings de UI (labels, mensagens, `verbose_name`, texto de e-mail) e o vocabulário de domínio em português usado neste documento e em conversas — ambos continuam em português. Um model field em inglês carrega o rótulo em português explicitamente via `verbose_name` (ex.: `contest = models.CharField(..., verbose_name='Concurso')`), então a tela do usuário não muda.

**Por quê agora:** decisão do Boss durante a revisão deste PRD (2026-09-08) — o código legado em português (`JogoGerado`, `capturar_resultado_cef`, etc.) foi escrito antes dessa convenção existir; como este PRD introduz classes/campos novos, é o momento de alinhar o legado em vez de misturar as duas línguas de forma permanente no mesmo código.

**Como isso é executado:** este PRD fixa a convenção e o mapeamento de nomes (tabela abaixo); a sequência segura de execução — ordem das renomeações, geração de migrations Django (`RenameModel`/`RenameField`, preservando dados e nomes de tabela/coluna reais no SQLite de produção) e o que pode ser feito em paralelo às features FR-1 a FR-14 — é decisão de arquitetura, registrada no documento de arquitetura técnica (`/bmad-architecture`), não repetida aqui.

**Mapeamento de nomes (legado → novo, e novo código desta PRD):**

| Português (legado)                                                                                                                                                     | Inglês (novo)                                                                                                                                                                             | Tipo                                                                                                                                                                                                          |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `JOGOS_CONFIG`                                                                                                                                                         | `GAMES_CONFIG`                                                                                                                                                                            | constante                                                                                                                                                                                                     |
| `JOGOS_COM_REGRA_SEQUENCIA`                                                                                                                                            | `GAMES_WITH_SEQUENCE_RULE`                                                                                                                                                                | constante                                                                                                                                                                                                     |
| `INTERVALO_MIN_SEQUENCIA`                                                                                                                                              | `MIN_SEQUENCE_INTERVAL`                                                                                                                                                                   | constante                                                                                                                                                                                                     |
| chaves `nome`/`apostas`/`numeros`/`trevos`/`qtd_trevos` dos dicts de jogo                                                                                              | `name`/`bets_count`/`numbers_count`/`clovers`/`clovers_count`                                                                                                                             | chaves de dict                                                                                                                                                                                                |
| `JogoGerado`                                                                                                                                                           | `GeneratedBet`                                                                                                                                                                            | classe (model)                                                                                                                                                                                                |
| `ResultadoLoteria`                                                                                                                                                     | `LotteryResult`                                                                                                                                                                           | classe (model)                                                                                                                                                                                                |
| `EstatisticaJogo`                                                                                                                                                      | `GameStatistics`                                                                                                                                                                          | classe (model)                                                                                                                                                                                                |
| `JogoGerado.JOGOS_CHOICES` (reutilizado por `ResultadoLoteria.JOGOS_CHOICES = JogoGerado.JOGOS_CHOICES` e por `EstatisticaJogo.jogo`)                                  | `GeneratedBet.GAME_CHOICES`                                                                                                                                                               | atributo de classe compartilhado entre as 3 classes acima — renomear numa só passada, nunca dividir a renomeação dessas 3 classes entre pessoas/PRs diferentes, exatamente por causa desta referência cruzada |
| `related_name='jogos'` (em `JogoGerado.usuario`)                                                                                                                       | `related_name='bets'`                                                                                                                                                                     | model field (reverse accessor `user.bets`)                                                                                                                                                                    |
| `related_name='estatisticas'` (em `EstatisticaJogo.usuario`)                                                                                                           | `related_name='statistics'`                                                                                                                                                               | model field (reverse accessor `user.statistics`)                                                                                                                                                              |
| campos `usuario`, `jogo`, `concurso`, `numeros`, `trevos`                                                                                                              | `user`, `game`, `contest`, `numbers`, `clovers`                                                                                                                                           | model field (comum às 3 classes acima)                                                                                                                                                                        |
| `pares_sequenciais`, `resultado_verificado`, `acertos`, `premio`, `premio_descricao`, `criado_em`, `atualizado_em`                                                     | `sequential_pairs`, `result_checked`, `hits`, `prize`, `prize_description`, `created_at`, `updated_at`                                                                                    | model field (`GeneratedBet`)                                                                                                                                                                                  |
| `premiacoes`, `origem`, `capturado_em`                                                                                                                                 | `prizes`, `source`, `captured_at`                                                                                                                                                         | model field (`LotteryResult`)                                                                                                                                                                                 |
| `total_jogos`, `total_com_sequencia`, `total_sem_sequencia`, `numero_mais_frequente`, `ultima_atualizacao`                                                             | `total_bets`, `total_with_sequence`, `total_without_sequence`, `most_frequent_numbers`, `last_updated`                                                                                    | model field (`GameStatistics`)                                                                                                                                                                                |
| `get_numeros_formatados`, `get_trevos_formatados`, `tem_sequencia`                                                                                                     | `get_formatted_numbers`, `get_formatted_clovers`, `has_sequence`                                                                                                                          | método                                                                                                                                                                                                        |
| `normalizar_numeros`                                                                                                                                                   | `normalize_numbers`                                                                                                                                                                       | função                                                                                                                                                                                                        |
| `contar_pares_sequenciais`                                                                                                                                             | `count_sequential_pairs`                                                                                                                                                                  | função                                                                                                                                                                                                        |
| `ultimos_jogos_tiveram_sequencia`                                                                                                                                      | `recent_bets_had_sequence`                                                                                                                                                                | função                                                                                                                                                                                                        |
| `gerar_aposta`                                                                                                                                                         | `generate_bet`                                                                                                                                                                            | função                                                                                                                                                                                                        |
| `verificar_jogo_repetido`                                                                                                                                              | `check_duplicate_bet`                                                                                                                                                                     | função                                                                                                                                                                                                        |
| `calcular_estatisticas`                                                                                                                                                | `calculate_statistics`                                                                                                                                                                    | função                                                                                                                                                                                                        |
| `calcular_premiacao_jogo`                                                                                                                                              | `calculate_bet_prize`                                                                                                                                                                     | função                                                                                                                                                                                                        |
| `capturar_resultado_cef`                                                                                                                                               | `fetch_cef_result`                                                                                                                                                                        | função                                                                                                                                                                                                        |
| `verificar_resultados_usuarios`                                                                                                                                        | `check_user_results`                                                                                                                                                                      | função                                                                                                                                                                                                        |
| `gerar_jogo`, `detalhes_jogo`, `historico`, `salvar_jogo_manual`, `verificar_resultado_jogo`, `refazer_jogo`, `estatisticas`, `excluir_jogo`, `api_gerar_jogo` (views) | `create_bet_view`, `bet_detail_view`, `history_view`, `save_manual_bet_view`, `check_bet_result_view`, `regenerate_bet_view`, `statistics_view`, `delete_bet_view`, `api_create_bet_view` | view (função)                                                                                                                                                                                                 |
| *(novo, sem equivalente legado)*                                                                                                                                       | `HitNotification`, `NotificationPreference`, `PrizeTier`, `fetch_daily_results`, `update_monthly_prize_values`                                                                            | classe/função nova desta PRD                                                                                                                                                                                  |

`apps/accounts` segue a convenção na maior parte (classes `User`, `UserManager`, `CustomSignupForm`, `CustomAccountAdapter` já em inglês), **mas dois campos do model `User` escaparam da varredura original desta PRD e continuam em português: `tema_preferido`→`preferred_theme` e `telefone`→`phone`** (usados em `apps/accounts/admin.py`, `forms.py`, `views.py`, `apps/loterias_core/context_processors.py` e nos templates `accounts/profile.html`/outros). Corrigido pela Story 1.5 do Epic 1 (achado durante a implementação, não fazia parte do mapeamento original). O novo código do fluxo de cadastro (FR-10 a FR-14) precisa nascer consistente com isso.

## 4. Funcionalidades

*Convenção: um FR traz "Realiza UJ-X" quando corresponde a um passo específico de uma jornada. FRs de suporte/transversais (ex.: rotinas agendadas, preferências, envio de e-mail) não amarram a um passo específico de UJ e por isso não trazem essa tag — não é omissão.*

### 4.1 Verificação e Notificação de Resultados

**Descrição:** Realiza a UJ-1. Duas rotinas agendadas via django-crontab mantêm o sistema informado sobre resultados oficiais sem ação do usuário; o cruzamento contra os GeneratedBet de cada usuário gera Notificações de Acerto (`HitNotification`), exibidas ao logar e detalhadas sob clique. Substitui a decisão de arquitetura originalmente cogitada (Celery + Redis) — ver Não-Objetivos (§5) para o porquê.

#### FR-1: Rotina diária de resultados

Diariamente às 3h (horário de Brasília — janela segura após os sorteios noturnos da Caixa terminarem), o sistema executa uma rotina (`fetch_daily_results`) que, para cada Jogo com concursos em aberto (sem LotteryResult registrado), tenta capturar o resultado oficial via `fetch_cef_result` — números sorteados e, para cada faixa premiada daquele Jogo (ex.: Mega-Sena: quadra, quina e sena), o valor do prêmio **e a quantidade de ganhadores** daquela faixa naquele concurso — e grava em LotteryResult.

**Consequências (testáveis):**
- A rotina não recria um LotteryResult que já existe para o mesmo Jogo+Concurso (idempotente).
- Uma falha de captura para um Jogo/Concurso específico não interrompe a tentativa dos demais.
- `fetch_cef_result` extrai, pra cada faixa premiada do concurso, tanto o valor do prêmio quanto a quantidade de ganhadores — não só os números sorteados. Hoje a função só extrai os números (o valor é um placeholder fixo, sem quantidade de ganhadores nenhuma); fechar essa lacuna faz parte do escopo desta FR — é o dado necessário pra informar corretamente ao usuário premiado qual foi o prêmio dele. Se a extração falhar mas os números vierem normalmente, o resultado é salvo sem prêmio populado e `calculate_bet_prize` usa a Faixa de Premiação (`PrizeTier`, FR-8) vigente como fonte. Uma faixa premiada nunca é gravada com quantidade de ganhadores zerada ou ausente — isso é tratado como falha de extração daquela faixa, não como "zero ganhadores".
- Ver FR-9 para a política de retentativa dentro da mesma execução diária.

#### FR-2: Bloqueio de concurso já sorteado

Ao gerar (automático ou manual) um GeneratedBet, o sistema pré-preenche o campo de Concurso com uma sugestão (próximo concurso sequencial daquele Jogo, com base no maior Concurso já visto), mas aceita qualquer número informado. A única validação real: rejeitar se aquele Jogo+Concurso já tiver LotteryResult registrado. Realiza UJ-1, passos 1–3.

**Consequências (testáveis):**
- Tentar gerar/salvar um GeneratedBet para um Jogo+Concurso com LotteryResult existente retorna erro claro, sem gravar o registro.
- Um Concurso fora da sequência normal (especial/comemorativo) sem LotteryResult é aceito normalmente.

#### FR-3: Geração de Notificação de Acerto

Sempre que a rotina diária grava um LotteryResult novo, o sistema compara com todos os GeneratedBet existentes daquele Jogo+Concurso e cria uma Notificação de Acerto (`HitNotification`) para cada GeneratedBet com interseção não vazia — marcada como premiada ou não, conforme `calculate_bet_prize`. Realiza UJ-1, passo 5.

**Consequências (testáveis):**
- GeneratedBet sem interseção nenhuma não gera Notificação.
- Uma Notificação de Acerto é criada no máximo uma vez por GeneratedBet+LotteryResult (idempotente — reexecutar a rotina não duplica).

#### FR-4: Exibição da notificação ao logar

Ao autenticar, o usuário com Notificação(ões) de Acerto não lida(s) vê um badge numérico no cabeçalho (ícone de sino + contador, junto do nome/avatar do usuário) resumindo a quantidade, diferenciando visualmente acertos premiados de não premiados. Visível em toda página enquanto autenticado, sem depender de JS/tempo real — decisão fechada nesta PRD, não fica mais pendente de UX.

**Consequências (testáveis):**
- Usuário sem Notificação pendente não vê o badge (sem sino vazio, sem contador zerado).
- Um acerto premiado é visualmente distinguível de um não premiado no resumo (não apenas no detalhe).
- Clicar no badge leva direto à tela de detalhe (FR-5).

#### FR-5: Detalhe e leitura da notificação

Clicar no indicador leva a uma tela listando as Notificações de Acerto pendentes, identificando pra cada uma o tipo de Jogo (ex.: Mega-Sena) e o número do Concurso, além do detalhe de números batidos e valor do prêmio (se houver). Cada Notificação pode ser marcada como lida individualmente a partir dessa tela. Realiza UJ-1, clímax e resolução.

**Consequências (testáveis):**
- Cada item da lista identifica claramente qual Jogo e qual Concurso geraram aquele acerto — o usuário nunca precisa adivinhar a qual jogo uma notificação se refere.
- Marcar uma Notificação como lida não afeta o estado das demais.
- Notificação marcada como lida não volta a aparecer no indicador de FR-4.

#### FR-6: Preferência de canal de notificação

O usuário configura, em um único lugar (fora do fluxo de notificação individual), se deseja receber avisos de Acerto no site, por e-mail, ou ambos.

**Consequências (testáveis):**
- Alterar a preferência não recria Notificações passadas.
- Preferência default no cadastro: notificação no site **ativa**, e-mail **desativado** — usuário precisa ligar e-mail manualmente se quiser.

#### FR-7: Envio de e-mail de acerto

Quando a Preferência de Notificação do usuário inclui e-mail, o sistema envia um e-mail (via backend SMTP já configurado — Brevo) para cada Notificação de Acerto **premiada** criada.

**Consequências (testáveis):**
- Acerto não premiado nunca dispara e-mail, independentemente da preferência — apenas o indicador de site (FR-4) cobre esse caso.
- Falha no envio de e-mail não impede a criação/exibição da Notificação no site.

**Out of Scope:** notificação por SMS ou push mobile.

#### FR-8: Rotina mensal de valores de premiação

No primeiro dia de cada mês, o sistema (`update_monthly_prize_values`) captura, para cada tipo de Jogo, as Faixas de Premiação vigentes (`PrizeTier`) — o valor de prêmio oficial pra cada quantidade de acertos que dá prêmio naquele Jogo (ex.: Mega-Sena: 4, 5 e 6 acertos, cada um com seu valor; o mesmo padrão vale pra todos os 6 Jogos). Essas faixas são a regra de validação que `calculate_bet_prize` usa pra decidir se uma quantidade de acertos é premiada — substituem a lista fixa de faixas hoje hardcoded por Jogo dentro da função. O sistema mantém histórico só dos **3 meses mais recentes** por (Jogo, quantidade de acertos) — suficiente pra validar acertos retroativos dentro dessa janela; capturar um mês novo remove automaticamente o mês mais antigo além dos 3 retidos.

**Consequências (testáveis):**
- Uma Notificação de Acerto premiada criada após a rotina mensal usa os valores atualizados, não os anteriores.
- Para cada Jogo, todas as quantidades de acertos que dão prêmio naquele Jogo têm uma Faixa de Premiação capturada — nenhuma fica de fora da validação.
- Apagar o mês mais antigo ao capturar um novo nunca deixa menos de 1 nem mais de 3 meses retidos por (Jogo, quantidade de acertos).

#### FR-9: Tratamento de falha da captura de resultado

Dentro de uma mesma execução da rotina diária, se `fetch_cef_result` falhar para um Jogo/Concurso, o sistema tenta novamente até 3 vezes, com 15 minutos de intervalo entre tentativas, antes de desistir daquele Jogo/Concurso para o dia — as 3 tentativas terminam bem antes do horário em que usuários costumam abrir o sistema pela manhã. Se todas as tentativas falharem, o sistema envia um e-mail de alerta ao operador (Boss) — não é um alerta ao usuário final, e não depende de múltiplos dias de falha. O usuário final simplesmente não vê Notificação naquele Jogo/Concurso até a captura funcionar em um dia seguinte. Realiza UJ-1, caso de borda.

**Consequências (testáveis):**
- Falha de captura não gera Notificação de Acerto incorreta nem falsa (nunca inventa resultado).
- Falha de captura não bloqueia a rotina diária dos demais Jogos.
- Esgotadas as 3 tentativas do dia, exatamente um e-mail de alerta é enviado ao operador por Jogo/Concurso falho — não um por tentativa.
- O e-mail de alerta vai para um endereço de operador configurável via variável de ambiente (`[ASSUMPTION]` nome da variável e endereço exatos ficam para a implementação — ver §8).

**NFRs específicas desta funcionalidade:**
- Um valor de prêmio exibido numa Notificação sempre rastreia a um `LotteryResult.prizes` (antes `ResultadoLoteria.premiacoes`) concreto **ou a uma Faixa de Premiação (`PrizeTier`) oficial vigente pra aquela quantidade de acertos (FR-8)** — o sistema nunca estima ou arredonda um valor de prêmio na ausência de um desses dois dados oficiais confirmados (falha = sem Notificação, não Notificação com valor incerto).
- As rotinas agendadas respeitam uma cadência deliberadamente baixa (diária para resultado, mensal para valores) para não sobrecarregar nem ser bloqueado pelo site da Caixa, que não oferece API oficial.

**Notas:** `[NOTE FOR PM]` A view `check_bet_result_view` (antes `verificar_resultado_jogo`) já existente (verificação sob demanda, por clique) continua funcionando em paralelo à rotina diária — ambas escrevem no mesmo LotteryResult via `update_or_create`, então não há conflito, mas vale revisitar se a verificação manual ainda faz sentido depois que a rotina automática cobre o caso comum.

#### FR-15: Retenção e purge manual de resultados oficiais antigos

Diferente das Faixas de Premiação (FR-8, retidas só 3 meses), os `LotteryResult` (resultados oficiais capturados por Jogo+Concurso) são retidos **integralmente e por padrão indefinidamente** — nenhuma exclusão automática. O painel de administração ganha uma ação de "purge até uma data": o operador (Boss) informa uma data de corte e o sistema apaga os `LotteryResult` capturados antes dela, sob demanda.

**Consequências (testáveis):**
- Nenhum `LotteryResult` é apagado automaticamente por rotina alguma — só uma ação manual do operador no admin apaga.
- A ação de purge aceita uma data de corte e afeta somente `LotteryResult` capturados antes dela; `GeneratedBet` dos usuários e `PrizeTier` não são afetados por essa ação.

### 4.2 Novo Fluxo de Cadastro

**Descrição:** Realiza a UJ-2. Substitui o signup padrão do django-allauth (e-mail + senha de uma vez, confirmação depois) por uma sequência de confirmação-primeiro: e-mail → link → senha → (no primeiro login) nome e sobrenome.

#### FR-10: Cadastro inicial só com e-mail

A tela de "Criar conta" pede apenas e-mail. Ao confirmar, o sistema cria uma conta pendente (sem senha utilizável ainda) e envia o Vínculo de Confirmação de Cadastro por e-mail. Realiza UJ-2, passos 1–2.

**Consequências (testáveis):**
- Conta pendente não permite login antes da senha ser definida.
- Tela pós-envio informa claramente para checar e-mail (incluindo SPAM) e oferece reenvio.

#### FR-11: Reenvio do e-mail de confirmação

Um botão "reenviar e-mail de cadastro" gera um novo Vínculo e invalida o anterior, reenviando para o mesmo e-mail.

**Consequências (testáveis):**
- Um Vínculo antigo invalidado não autentica mais na tela de criação de senha.
- Botão de reenvio fica desabilitado por 60 segundos após cada envio (padrão comum contra clique duplo/abuso leve, ex.: GitHub e Slack usam janelas semelhantes).
- Limite de 5 reenvios por conta por dia — esgotado o limite, a tela orienta a checar SPAM e tentar novamente no dia seguinte, sem travar a conta.

#### FR-12: Definição de senha via link

Clicar no Vínculo válido leva a uma tela que pede senha + confirmação (com alternância mostrar/ocultar) e o aceite dos termos de serviço (`[ASSUMPTION]` texto placeholder no Anexo A até a publicação real — ver §8.2). Realiza UJ-2, passo 3.

**Consequências (testáveis):**
- Senhas divergentes entre os dois campos são sinalizadas inline, sem submeter o formulário.
- Confirmar sem marcar o aceite dos termos não conclui o cadastro.
- Ao confirmar, a conta passa a permitir login e o usuário é redirecionado à página inicial.

#### FR-13: Vínculo expirado

Se o Vínculo expirar antes da senha ser definida, a conta permanece pendente. Acessar o link vencido mostra mensagem clara e oferece o mesmo reenvio de FR-11. Realiza UJ-2, caso de borda.

**Consequências (testáveis):**
- Link expirado nunca autentica na tela de criação de senha.
- Não existe estado "conta perdida para sempre" — reenvio sempre disponível a partir do e-mail já cadastrado.

#### FR-14: Nome e sobrenome obrigatórios no primeiro login

No primeiro login bem-sucedido após FR-12, antes de qualquer outra tela do sistema, o usuário é obrigado a informar nome e sobrenome. Realiza UJ-2, clímax e resolução.

**Consequências (testáveis):**
- Tentar acessar qualquer outra rota do sistema nesse estado redireciona para essa tela até nome e sobrenome serem salvos.
- Em logins subsequentes (nome já preenchido), essa tela não aparece mais.

**Out of Scope:** login social (Google, etc.) — fora do escopo deste PRD.

**NFRs específicas desta funcionalidade:**
- O Vínculo de Confirmação de Cadastro é de uso único e expira (mecanismo padrão do django-allauth já em uso — `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`).
- Nenhuma senha é solicitada antes da confirmação do e-mail (elimina o caso de alguém criar senha para um e-mail que não controla).

## 5. Não-Objetivos (Explícitos)

- **Multitenancy** — decisão de arquitetura já tomada e revertida antes deste PRD (ver `docs/diagnostico-projeto.md`); o sistema é e continua multi-user simples.
- **Celery + Redis** — avaliado e rejeitado para as rotinas agendadas deste PRD; desproporcional a duas tarefas periódicas simples neste porte de projeto. `django-crontab` é a escolha. `celery`/`redis` serão removidos do `requirements.txt`.
- **Monetização / anúncios** — mencionada como possibilidade futura pelo Boss, mas não faz parte deste PRD.
- **Login social** — fora de escopo (ver FR-14).
- **Notificação em tempo real / push mobile / SMS** — a verificação é em lote diário; nenhum canal além de site e e-mail está no escopo.
- **Processamento real de apostas/pagamentos** — o sistema gera números e informa resultado; não é um canal oficial de aposta.

## 6. Escopo do MVP

### 6.1 Em Escopo
- Rotina diária de captura de resultado + bloqueio de concurso já sorteado (FR-1, FR-2).
- Geração e exibição de Notificação de Acerto, com distinção premiado/não-premiado (FR-3, FR-4, FR-5).
- Preferência de canal (site/e-mail) e envio de e-mail para acerto premiado (FR-6, FR-7).
- Rotina mensal de valores de premiação (FR-8).
- Tratamento silencioso de falha de captura, sem notificar o usuário sobre a falha (FR-9).
- Purge manual de resultados oficiais antigos pelo operador, via admin (FR-15).
- Novo fluxo de cadastro completo: e-mail → link → senha → nome/sobrenome no primeiro login (FR-10 a FR-14).
- Renomeação dos identificadores de código legados do português para o inglês, conforme mapeamento de §3.1 (débito técnico transversal, não é um FR numerado nem visível ao usuário final — UI e dados não mudam).

### 6.2 Fora de Escopo do MVP
- Texto definitivo (jurídico) dos termos de serviço — usa placeholder até a publicação real do projeto. `[NOTE FOR PM]` revisitar antes de qualquer publicação pública.
- Cadência configurável por usuário para as rotinas — fixa (diária/mensal) para todos nesta versão.
- Histórico paginado/arquivamento de Notificações antigas além da listagem simples de FR-5.
- Painel de administração dedicado para acompanhar falhas da rotina diária (FR-9 registra o problema, mas não define onde/como o operador vê isso) — deferido a v2.

## 7. Métricas de Sucesso

**Primária**
- **SM-1**: Todo Acerto Premiado gerado pela rotina diária resulta em uma Notificação visível no próximo login do usuário, sem intervenção manual. Valida FR-1, FR-2, FR-3, FR-4.
- **SM-2**: Uma pessoa consegue completar o cadastro (e-mail → senha → nome/sobrenome) sem precisar de ajuda ou reenvio de link na maioria das tentativas. Valida FR-10 a FR-14.

**Secundária**
- **SM-3**: Zero falso-positivo de premiação — nenhuma Notificação Premiada é criada sem um LotteryResult oficial confirmado por trás. Valida FR-9 e a NFR de rastreabilidade de valor de prêmio (§4.1).

**Contra-métricas (não otimizar)**
- **SM-C1**: Volume de e-mails de acerto por usuário permanece baixo (um e-mail por Acerto Premiado real, nunca reenviado por reexecução da rotina) — contrabalança SM-1: o objetivo é notificar corretamente, não notificar com frequência.

## 8. Questões em Aberto

1. Nome exato da variável de ambiente e endereço de e-mail do operador para o alerta de FR-9 (ex.: `OPERATOR_ALERT_EMAIL`) — decisão de implementação, não de produto.
2. Texto definitivo (jurídico) dos termos de serviço, para quando o projeto for publicado de verdade — o Anexo A é só placeholder até lá.
3. Onde/como o operador (Boss) acompanha o histórico de alertas de FR-9 além do e-mail avulso — um painel dedicado ficou fora do MVP (§6.2); por ora, o e-mail é o único registro.
4. Sequenciamento da renomeação de código legado (§3.1): se acontece antes, em paralelo ou depois das features FR-1 a FR-14, e como as migrations Django (`RenameModel`/`RenameField`) são geradas e aplicadas sem perda de dados no SQLite de produção — decisão de arquitetura, não de produto.

## 9. Índice de Suposições

- §4.1, FR-9 — o alerta de falha ao operador é enviado por e-mail (reaproveitando o SMTP já configurado); o endereço exato de destino é uma variável de ambiente a definir na implementação (questão em aberto §8.1).
- §4.2, FR-12 — texto dos termos de serviço é o placeholder do Anexo A até a publicação real do projeto (questão em aberto §8.2).

## Anexo A — Termos de Serviço (placeholder)

*Texto de rascunho, sem validade jurídica, para preencher o fluxo de cadastro até a publicação real do projeto — ver Questão em Aberto §8.2.*

> **Termos de Serviço — Loterias**
>
> Este é um projeto pessoal, sem fins comerciais, criado para fins de portfólio e estudo. Ao criar uma conta, você concorda que:
>
> 1. O sistema gera combinações de números para loterias brasileiras e informa resultados oficiais de forma automatizada, mas **não** processa apostas reais nem qualquer pagamento — ele não é um canal oficial de aposta.
> 2. As informações de resultado e premiação são obtidas de fontes públicas da Caixa Econômica Federal de forma automatizada e podem, eventualmente, estar desatualizadas ou incorretas; sempre confirme resultados importantes diretamente com a fonte oficial.
> 3. Seus dados (e-mail, nome) são usados apenas para autenticação e envio das notificações que você configurar, e não são compartilhados com terceiros.
> 4. Este serviço é fornecido "como está", sem garantias, podendo ser alterado ou descontinuado a qualquer momento.
>
> Última atualização: {{data}}.
