---
name: 'Revisão Adversarial — ARCHITECTURE-SPINE.md'
type: architecture-review
target: '_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md'
verdict: 'não-seguro-para-dividir — 7 lacunas de divergência reais, 2 delas quebram o build no primeiro dia'
created: '2026-09-08'
---

# Revisão Adversarial — Loterias ARCHITECTURE-SPINE.md

**Método:** para cada AD, construir duas unidades que obedecem ao texto literal da AD, construídas por desenvolvedores/agentes que não veem o código um do outro, e checar se o resultado compõe. Só reportando lacunas que produzem divergência real (choque de formato de dado, dupla propriedade, corrida, rota sem saída) — não implicâncias de estilo.

**Veredito:** a espinha dorsal **ainda não é segura para dividir** entre builders independentes. Duas lacunas (G1, G2) são graves o suficiente para que uma implementação literal e de boa-fé das ADs declaradas quebre o produto no primeiro dia (perda silenciosa de notificação entre usuários; bloqueio de admin/usuário existente). Mais cinco (G3–G7) são riscos reais de incompatibilidade que vão aparecer depois, sob carga ou no dia do rename.

---

## G1 — [CRÍTICO] A geração de notificação está acoplada a "quem escreveu a linha de `LotteryResult`", não ao trabalho pendente real

**ADs envolvidas:** AD-4, FR-1, FR-3, a linha de Convenções de Consistência sobre `LotteryResult`/`HitNotification`.

**A armadilha:** a espinha dorsal diz que `LotteryResult` é escrita via `update_or_create(game=, contest=)` por **dois caminhos independentes** — o caminho on-demand já existente (`check_bet_result_view`, `save_manual_bet_view`) e o novo job `fetch_daily_results` — "então não há conflito" (tabela de Convenções de Consistência). Separadamente, FR-3/AD-4 dizem que um `HitNotification` é criado **só** dentro de `fetch_daily_results`, e só "ao gravar um `LotteryResult` novo." O FR-1 ainda escopa o job pra só processar "Jogo com concursos em aberto (**sem** `LotteryResult` registrado)."

Encadeando essas três frases: se o clique on-demand de *qualquer* usuário (`check_bet_result_view`) ou o salvamento de uma aposta manual (`salvar_jogo_manual`, que já chama `fetch_cef_result`/`capturar_resultado_cef` de forma síncrona hoje — ver `apps/loterias_core/views.py` linhas 206–218) escrever o `LotteryResult` daquele Jogo+Concurso *antes* do job noturno chegar até ele, esse Jogo+Concurso deixa de estar "aberto." O job noturno nunca mais vai ver isso como um evento de "LotteryResult novo" — então **nunca** vai criar linhas de `HitNotification` para nenhum *outro* usuário que tenha um `GeneratedBet` no mesmo Jogo+Concurso. `LotteryResult` é global (único por Jogo+Concurso, não por usuário), mas o gatilho de criação de notificação é um evento único na criação da linha, pertencente a qualquer caminho de código que chegue lá primeiro.

O mesmo acoplamento também significa: se o próprio `fetch_daily_results` morrer no meio do loop (matado, OOM, exceção) depois de fazer `update_or_create` na linha de `LotteryResult` mas antes de terminar o loop de notificação/e-mail por `GeneratedBet` daquele concurso, as reexecuções de 3h15/3h30 (AD-6) também vão pular ele — não está mais "aberto" — e os usuários não processados nunca são notificados, silenciosamente. Não existe em nenhum lugar da espinha dorsal uma passada de reconciliação do tipo "garantir que todo `GeneratedBet` de todo `LotteryResult` existente tenha um `HitNotification`"; a criação de notificação é puramente orientada a evento na escrita, nunca orientada a estado na leitura.

**Duas unidades compatíveis-mas-incompatíveis:**
- **Unidade A** (implementa FR-3/AD-4 literalmente): `fetch_daily_results` checa `created=True` do próprio `update_or_create` e só então percorre `GeneratedBet` → `HitNotification`. Totalmente conforme a spec.
- **Unidade B** (mantém `check_bet_result_view`/`save_manual_bet_view` "inalterados," como o próprio `[NOTA PARA O PM]` do PRD sob FR-9 diz explicitamente que é aceitável — "continua funcionando em paralelo... não há conflito"): `update_or_create` on-demand na *mesma* linha de `LotteryResult`, sem nenhum conhecimento de `HitNotification`.

Ambas são individualmente corretas em relação à própria AD. Compostas: um único usuário que clique em "verificar" antes das 3h (ou cujo salvamento de aposta manual auto-verifique) suprime permanente e silenciosamente o SM-1 ("Todo Acerto Premiado gerado pela rotina diária resulta em uma Notificação visível") para todo outro usuário que compartilhe aquele Jogo+Concurso — um prêmio real, com um `LotteryResult` real, que nunca produz notificação para mais ninguém. Isso é exatamente o tipo de choque "dois donos diferentes escrevendo a mesma entidade" que esta revisão foi pedida para caçar.

**Direção de correção:** desacoplar a criação de notificação de "eu acabei de escrever essa linha." Ou (a) transformar a geração de notificação numa passada derivada de estado — para todo `LotteryResult` (novo ou pré-existente) sem cobertura de `HitNotification` nos `GeneratedBet` correspondentes, independente de qual caminho o criou — rodando dentro de `fetch_daily_results` (e/ou também no caminho on-demand, protegido pra nunca disparar e-mail duplicado — ver G4), ou (b) aposentar o efeito colateral de escrita de `LotteryResult` no caminho on-demand agora que o job diário existe, e fazer `check_bet_result_view` só *ler* um resultado já existente em vez de buscar/escrever um. A AD-4 precisa escolher uma opção e declará-la explicitamente; hoje ela deixa os dois caminhos escreverem e assume que isso é inofensivo, o que só é verdade pra linha em si, não pro leque de notificações amarrado a ela.

---

## G2 — [CRÍTICO] A allowlist da AD-8 não tem isenção pra `/admin/`/staff, nem cláusula de "avô" pra usuários pré-existentes

**AD envolvida:** AD-8.

**A armadilha:** a regra da AD-8 é "redireciona **qualquer** request autenticado com `first_name`/`last_name` vazio... exceto a própria tela de captura, assets estáticos e logout." Isso é uma regra geral com uma allowlist de três itens. Duas coisas que ela não considera:

1. **Toda conta que existe hoje** (isso é um app real, já em produção — ver `deploy/lab/docker-compose.yml`, commit `39b4b50 Deploy`) tem `first_name`/`last_name` em branco, porque nada antes deste PRD nunca pediu esses dados. `AbstractUser.first_name`/`last_name` têm `blank=True` por padrão, e os próprios `create_user`/`create_superuser` de `apps/accounts/models.py` nunca os preenchem. O UJ-2 do FR-14 descreve isso como um gate de **novo cadastro** ("no primeiro login... obrigatório"), mas o texto da Regra da AD-8 diz "qualquer request autenticado" sem nenhuma condição de corte/avô — nada distingue "primeiro login depois do novo fluxo FR-10–14" de "qualquer sessão pré-existente."
2. **`/admin/`** não está na allowlist. `django.contrib.admin` está instalado (`INSTALLED_APPS` em `loterias/settings/base.py`) e é como o Ricardo (o Boss/operador) administra o site hoje.

**Duas unidades compatíveis-mas-incompatíveis:**
- **Unidade A** implementa o middleware literalmente: checagem geral, allowlist = {tela de captura, estáticos, logout}. No deploy, isso trava imediatamente todo usuário existente por redirecionamento — inclusive o próprio login de admin/staff do Ricardo, porque `/admin/login/` aceita a sessão mas a *próxima* página de admin é redirecionada pra tela de captura (que por sua vez não faz parte do site de admin e não oferece caminho de volta pro `/admin/`).
- **Unidade B**, construindo o mesmo middleware a partir da leitura "obviamente isso é pra novos cadastros," adiciona uma isenção não declarada — ex.: `if user.is_staff: return None` ou `if user.date_joined < CUTOVER_DATE: return None` — nenhuma das quais aparece em nenhum lugar da espinha dorsal, então um revisor checando a Unidade B "contra a AD" a marcaria como scope creep, e um agente diferente construindo a story companheira do FR-14 não tem como saber qual isenção (se alguma) a Unidade A assumiu.

**Direção de correção:** a AD-8 precisa de uma declaração explícita sobre (a) se `/admin/` (ou `is_staff`/`is_superuser`) é isento, e (b) como contas pré-existentes são tratadas — uma migration de dados que preenche um marcador/sinaliza como "avô," ou um corte explícito por `date_joined`/flag, ou um management command único. Silêncio aqui não é um detalhe em que dois builders vão convergir independentemente; é uma moeda no ar entre "bloquear todo mundo, inclusive você mesmo, do admin" e "bloquear só usuários novos," decidida de formas diferentes por quem escreve o middleware versus quem roda o primeiro deploy de produção.

---

## G3 — [ALTO] A allowlist da AD-8 não inclui a tela de criação de senha do FR-12, e os dois gates de "usuário autenticado mas incompleto" disputam a mesma request

**ADs envolvidas:** AD-8, FR-12, FR-10, configurações já existentes do allauth (`ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True`, `ACCOUNT_CONFIRM_EMAIL_ON_GET = True` em `loterias/settings/base.py`).

**A armadilha:** hoje, clicar no link de confirmação de e-mail confirma o e-mail **e loga o usuário** (é isso que `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` faz), e então redireciona pra `LOGIN_REDIRECT_URL` ('/'). FR-10/FR-12 sobrepõem um novo estado de "conta pendente, ainda sem senha utilizável" nesse mesmo mecanismo — espera-se que o usuário caia na tela de criação de senha a seguir. Mas no momento em que ele é logado via o link de confirmação, `first_name`/`last_name` estão vazios (o FR-14 ainda não aconteceu) — então o `RequireProfileCompletionMiddleware` da AD-8, cuja allowlist é só "a própria tela de captura, assets estáticos e logout," intercepta justamente essa primeira request autenticada e redireciona pra tela de captura de nome *antes que a tela de criação de senha (FR-12) seja alcançada*. A senha nunca é definida, o usuário "completa" o formulário de captura de nome e agora está sentado dentro do app totalmente autenticado sem nunca ter escolhido uma senha — quebrando silenciosamente o contrato do FR-12.

**Duas unidades compatíveis-mas-incompatíveis:**
- **Unidade A** (middleware da AD-8, construído à letra): allowlist = {tela de captura, estáticos, logout}. Não sabe que a tela do FR-12 precisa rodar primeiro.
- **Unidade B** (fluxo de cadastro do FR-10–13, construído à letra): assume que o fluxo padrão do allauth "confirma → autenticado → cai na minha tela customizada de definição de senha" funciona como funciona hoje, sem saber que o middleware de um colega vai interceptar esse redirecionamento primeiro.

Nenhuma AD diz qual tela tem precedência quando as duas condições são verdadeiras (senha vazia *e* nome vazio), nem que a URL do FR-12 precisa ser adicionada à allowlist da AD-8.

**Direção de correção:** a allowlist da AD-8 precisa incluir explicitamente o nome de URL da tela de criação de senha, e a espinha dorsal precisa declarar diretamente o invariante de ordem: "senha-incompleta bloqueia senha-completa bloqueia nome-completo" (ou dobrar os dois gates num único middleware com uma lista de precedência explícita), em vez de deixar dois gates construídos independentemente disputarem o mesmo redirecionamento.

---

## G4 — [ALTO] Nenhuma exigência de unicidade/atomicidade pra `HitNotification`, combinada com os gatilhos cron independentes da AD-6 e o container de escrita dupla da AD-7, abre uma corrida de e-mail duplicado

**ADs envolvidas:** AD-3, AD-4, AD-6, AD-7.

**A armadilha:** a AD-6 coloca três entradas independentes de `CRONJOBS` (3h00/3h15/3h30) no mesmo job idempotente, contando com o `update_or_create` do `LotteryResult` + a filtragem de "não está mais aberto" pra tornar reexecuções seguras. Isso é sólido *pra linha de `LotteryResult` em si*. Mas nada na AD-3/AD-4/tabela de Convenções de Consistência exige uma constraint de unicidade no nível do banco (ex.: `unique_together`/`UniqueConstraint` em `(bet, result)`) sobre `HitNotification`, nem exige `get_or_create`/`update_or_create` como padrão de escrita — o "no máximo uma vez... idempotente" do FR-3 é declarado só como uma consequência testável, não como um invariante imposto. O `django-crontab` (pela seção de Stack) não garante por si só execuções sem sobreposição; se uma invocação das 3h00 ainda estiver raspando (travamentos de rede contra `loterias.caixa.gov.br` são o modo de falha normal documentado) quando a das 3h15 disparar, dois processos do sistema operacional podem — possivelmente entre o mesmo container `loterias-cron` ou, pior, sem nenhuma barreira caso o `loterias-web` também rode `check_bet_result_view` concorrentemente — avaliar "esse par `GeneratedBet`+`LotteryResult` já tem um `HitNotification`" no mesmo instante, ambos recebendo "não," e ambos criando uma linha. O FR-7 dispara um e-mail por notificação premiada criada — então isso é um bug de e-mail duplicado exatamente no caso que o PRD chama de contra-métrica inegociável (SM-C1: "nunca reenviado por reexecução da rotina").

**Duas unidades compatíveis-mas-incompatíveis:**
- O modelo de `HitNotification` da **Unidade A** não tem constraint de unicidade (a espinha dorsal não exige uma); a lógica do job faz um `.exists()` simples e depois `.create()` — correto sob execução sequencial, sujeito a corrida sob sobreposição.
- A **Unidade B** independentemente adiciona `unique_together = ('bet', 'result')` como escolha defensiva de modelagem (também não proibida) e escreve via `.create()` dentro de um `try/except IntegrityError` — modo de falha diferente (violação de constraint engolida) do da Unidade A (linha duplicada silenciosa + e-mail duplicado).

Ambas "obedecem" ao texto da AD-3/AD-4; o comportamento real sob uma sobreposição de fato é diferente dependendo puramente de qual desenvolvedor calhou de adicionar a constraint.

**Direção de correção:** a AD-3 ou a AD-4 deveria exigir uma `UniqueConstraint`/`unique_together` no nível do banco em `(bet, result)` pra `HitNotification` (batendo com a cardinalidade "gera no máximo 1" do próprio diagrama ER, que hoje é só uma anotação de diagrama, não uma regra imposta) e exigir `get_or_create`/`update_or_create` como caminho de escrita — transformando uma possível corrida num no-op garantidamente idempotente em vez de deixar o resultado pra quem calhar de pensar nisso.

---

## G5 — [MÉDIO-ALTO] Nada especifica como `fetch_daily_results()` sabe que é a execução "3h30 = tentativa final" que deveria alertar o operador

**ADs envolvidas:** AD-5, AD-6, FR-9.

**A armadilha:** a AD-5 exige que jobs sejam funções puras com um management command que "só chama a função," e o `CRONJOBS` apontando pra `call_command` com o nome do comando — "nunca a função direta." A AD-6 então exige que **só** a invocação das 3h30 envie o alerta por e-mail ao operador (FR-9), e só pra Jogo/Concurso ainda sem `LotteryResult` depois das três tentativas. Mas `fetch_daily_results()` é especificada como uma única função de aparência sem parâmetros, invocada de forma idêntica pelas três entradas de `CRONJOBS` — nada diz como a função (ou seu wrapper de management command) distingue "eu sou a 3ª invocação do dia" de "eu sou a 1ª."

**Duas unidades compatíveis-mas-incompatíveis:**
- A **Unidade A** (autor de jobs.py) implementa introspecção de relógio dentro da função: `if timezone.localtime().minute >= 30: send_alerts()`. Frágil (um cron que dispara um minuto atrasado por contenção de CPU do container pula o alerta silenciosamente, ou dispara duas vezes se a execução anterior passar das :30), mas bate com "a função não precisa de nenhum sinal externo."
- A **Unidade B** (autor de settings/CRONJOBS) assume em vez disso o idioma natural do Django: três entradas de `CRONJOBS` chamando o *mesmo* management command com um argumento `--attempt=1/2/3` diferente, que o comando passa pra `fetch_daily_results(attempt=N)`.

Se a Unidade A entregar `fetch_daily_results()` sem parâmetro `attempt` e o wrapper de comando/`CRONJOBS` da Unidade B passar um, isso é um `TypeError` em toda execução noturna. Se a Unidade A entregar detecção baseada em relógio e a Unidade B nunca conectar um argumento, isso "funciona" por acidente mas é exatamente o tipo de acoplamento implícito que uma espinha dorsal deveria ter eliminado.

**Direção de correção:** a AD-6 (ou a AD-5) deveria fixar a interface real: ou o management command aceita uma flag explícita `--attempt`/`--final` e a espinha dorsal declara isso na Semente Estrutural, ou a espinha dorsal declara que detecção baseada em relógio é o mecanismo pretendido e especifica o limite exato (ex.: "a invocação é final se e somente se `>= 03:25` no horário local," com uma justificativa de por que isso é robusto a alguns minutos de variação do agendador).

---

## G6 — [MÉDIO] O mapeamento de rename da AD-2 (PRD §3.1) é silencioso sobre identificadores compartilhados *entre* os três models renomeados, convidando a traduções divergentes no meio do rename

**ADs envolvidas:** AD-2, AD-1, PRD §3.1.

**A armadilha:** a tabela de mapeamento (PRD §3.1) é minuciosa pra nomes de campo e de função, mas deixa passar pelo menos dois símbolos referenciados *entre* as fronteiras de classe em `apps/loterias_core/models.py` hoje:
- `related_name='jogos'` (em `JogoGerado.usuario`) e `related_name='estatisticas'` (em `EstatisticaJogo.usuario`) — são identificadores de código sob a própria regra da AD-1 ("todo identificador de código... é em inglês"), usados como reverse accessors `user.jogos`/`user.estatisticas`, mas não aparecem em nenhum lugar da tabela do §3.1.
- `ResultadoLoteria.JOGOS_CHOICES = JogoGerado.JOGOS_CHOICES` e `EstatisticaJogo.jogo = models.CharField(..., choices=JogoGerado.JOGOS_CHOICES, ...)` — `LotteryResult` e `GameStatistics` referenciam diretamente o atributo de classe `JOGOS_CHOICES` de `GeneratedBet`, mas esse nome de atributo também está ausente da tabela do §3.1 (só as constantes de módulo `JOGOS_CONFIG`/`JOGOS_COM_REGRA_SEQUENCIA`/`INTERVALO_MIN_SEQUENCIA` estão listadas).

**Duas unidades compatíveis-mas-incompatíveis:** a AD-2 diz que o rename é "um epic isolado," não necessariamente um único PR atômico — nada impede que seja dividido model-por-model entre dois desenvolvedores/agentes (ex.: um fazendo `GeneratedBet`, outro fazendo `LotteryResult`/`GameStatistics`, ambos "renomeando conforme o §3.1"). Se quem renomeia `GeneratedBet` escolher `GAME_CHOICES` pro antigo `JOGOS_CHOICES` (um nome em inglês razoável, não contrariado pelo §3.1) enquanto quem renomeia `LotteryResult`/`GameStatistics` — trabalhando a partir da mesma tabela, sem ver nenhuma entrada pra isso — independentemente escrever `GamesChoices` ou continuar referenciando `GeneratedBet.JOGOS_CHOICES` (ainda não renomeado no branch dele), o arquivo falha ao importar. Mesmo risco pro `related_name`: um escolhe `generated_bets`, o código não relacionado de admin/template (ou um teste) esperando o antigo accessor `jogos` quebra sem nenhum sinal em tempo de compilação — só um `AttributeError` em tempo de execução, fácil de passar batido se o gate "passa 100% na suíte de testes" da AD-2 não cobrir por acaso todo uso de reverse accessor (o `tests.py` atual não exercita `user.jogos`/`user.estatisticas` diretamente).

**Direção de correção:** ou estender a tabela do PRD §3.1 (de propriedade do PRD, mas a AD-2 da espinha dorsal é a coisa que deveria marcar isso como um requisito de completude antes do epic de rename ser considerado "concluído") pra incluir valores de `related_name` e atributos de classe referenciados entre models, ou fazer a AD-2 declarar uma regra mais forte: "o epic de rename é um único PR/commit entre os três models, revisado como uma unidade, especificamente porque referências entre models (`choices=` compartilhado, `related_name`) não podem ser divididas com segurança entre renomeadores independentes."

---

## G7 — [MÉDIO] A AD-7 coloca dois containers num único arquivo SQLite sem exigir nenhuma configuração de concorrência

**ADs envolvidas:** AD-7, seção de Stack.

**A armadilha:** antes desta espinha dorsal, `loterias-web` era o único escritor de `db.sqlite3`. A AD-7 adiciona `loterias-cron` como um segundo processo, escrevendo rotineiramente no mesmo arquivo via o volume compartilhado `loterias_data` — explicitamente por design ("os dois containers só se comunicam através do arquivo SQLite... nunca por HTTP"). O backend sqlite3 do Django, por padrão, não define `timeout` em `DATABASES[...]['OPTIONS']` (ou seja, o padrão do próprio `sqlite3`, efetivamente falha imediata sob contenção de lock) e o `loterias/settings/base.py` do repositório não define nenhum `OPTIONS`. Nada na tabela de Stack ou na AD-7 exige o modo de journal WAL ou um busy-timeout, mesmo a AD-7 sendo precisamente a mudança que torna rotina escritores concorrentes sustentados (um job noturno fazendo potencialmente dezenas de chamadas `update_or_create`/`create` em vários Jogos ao longo de vários minutos, pelo FR-1/FR-3), ao mesmo tempo em que usuários reais geram/verificam apostas durante o horário comercial (menos provável especificamente às 3h, mas as retentativas do job sob a AD-6 podem se estender de 3h00 a 3h30+, e nada restringe o `update_monthly_prize_values` — FR-8 — a um horário específico de baixo movimento).

**Duas unidades compatíveis-mas-incompatíveis:** o desenvolvedor conectando o `loterias-cron` (AD-7) e o desenvolvedor tocando `loterias/settings/base.py` por um motivo não relacionado (ex.: mudanças do FR-6/FR-14) ambos deixam `DATABASES[...]['OPTIONS']` intocado — nenhuma AD exige que qualquer um dos dois adicione isso, então é igualmente provável que ninguém faça, e igualmente possível que um deles "conserte" localmente de um jeito que o outro não saiba (ex.: adicionando `'timeout': 20` só ao debugar um erro de `database is locked` que ele mesmo bateu, sem isso ser registrado como convenção do projeto).

**Direção de correção:** a AD-7 (ou uma nova AD pequena) deveria exigir `DATABASES['default']['OPTIONS'] = {'timeout': N}` (e/ou modo WAL via um `PRAGMA` de inicialização) como parte de introduzir o segundo escritor, declarado uma vez na espinha dorsal pra não ficar dependendo de qual desenvolvedor bater no erro de lock primeiro em produção.

---

## Confiança mais baixa / vale um olhar mas não escrito por completo

- **Propriedade da linha padrão de `NotificationPreference` (AD-3):** "`NotificationPreference` só é escrita pela própria tela de preferências" lê como proibindo qualquer outro caminho de escrita, mas a checagem de bloqueio de e-mail do FR-7 em `fetch_daily_results` precisa de *alguma* resposta pra usuários que nunca visitaram a tela de preferências (nenhuma linha existe ainda). Um fallback padrão do lado da leitura (`site_enabled=True, email_enabled=False` quando não há linha) é consistente com a AD; uma chamada `get_or_create` a partir do job é uma implementação plausível e idiomática que tecnicamente viola o texto literal da AD. Vale a AD-3 declarar explicitamente qual das duas é a pretendida, e se `user` é exigido único (`OneToOneField`), já que isso também não está declarado.
- **Granularidade da allowlist do middleware vs. endpoints auxiliares da mesma página:** a tela de completar perfil quase certamente renderiza o chrome de template compartilhado do site (alternador de tema, etc.); `accounts/theme/toggle/` não está na allowlist declarada da AD-8 ("captura, estáticos, logout"), então uma ação legítima dentro da própria página, a partir da tela de captura, é redirecionada de volta pra mesma tela em vez de executar. Menor (sem loop infinito, só um alternador silenciosamente quebrado), mas é a mesma causa raiz de G2/G3 — a allowlist é enumerada chutando no que um usuário autenticado-incompleto poderia clicar, não derivada de uma lista real de nomes de URL isentos fixada na espinha dorsal.

---

## Tabela-Resumo

| ID | Severidade | AD(s) a reforçar | Lacuna em uma linha |
|----|----------|-------------------|---------------|
| G1 | Crítica | AD-4 (gatilho do FR-3) | Criação de notificação dispara em "eu escrevi essa linha," não em "essa linha precisa de cobertura" — escritas on-demand suprimem silenciosamente notificações de outros usuários |
| G2 | Crítica | AD-8 | Allowlist sem isenção pra `/admin/`/staff e sem cláusula de avô — regra geral bloqueia toda conta pré-existente, inclusive o operador, no deploy |
| G3 | Alta | AD-8 (+ FR-12) | Tela de criação de senha fora da allowlist — o gate de completar perfil ganha a corrida e a senha nunca é definida |
| G4 | Alta | AD-3 / AD-4 | Nenhuma constraint de unicidade exigida em `HitNotification` — execuções de cron sobrepostas (AD-6) podem criar notificações em duplicidade e e-mails duplicados (viola SM-C1) |
| G5 | Média-Alta | AD-5 / AD-6 | Nenhum mecanismo especificado pra `fetch_daily_results()` saber que é a invocação "final" (3h30) que deveria alertar o operador |
| G6 | Média | AD-2 / PRD §3.1 | Mapeamento de rename omite identificadores entre models (`related_name`, `JOGOS_CHOICES` compartilhado) — dividir o rename por model arrisca divergência que quebra import |
| G7 | Média | AD-7 | Dois containers agora escrevem num único arquivo SQLite sem timeout/WAL exigido |
