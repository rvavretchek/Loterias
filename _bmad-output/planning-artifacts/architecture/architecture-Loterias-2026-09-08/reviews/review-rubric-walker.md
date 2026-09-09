# Revisão: ARCHITECTURE-SPINE.md (Loterias, 2026-09-08)

**Revisor:** rubric-walker (checklist de espinha dorsal boa)
**Alvo:** `_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md`
**Spec condutora:** `_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md` (FR-1..FR-14, rename §3.1)
**Também checado contra:** `CLAUDE.md`, `docs/diagnostico-projeto.md`, e o código real (`apps/loterias_core/models.py`, `utils.py`, `views.py`, `apps/accounts/{models,forms,adapter,views,urls}.py`, `loterias/settings/base.py`, `Dockerfile`, `deploy/lab/docker-compose.yml`, `requirements.txt`).

## Veredito

**Não está pronta como está.** A espinha dorsal é bem formada e na maior parte ratifica corretamente o código legado (mapeamento de nomenclatura/rename, caminhos de escrita atuais de `ResultadoLoteria`, formato atual do Dockerfile/compose são todos descritos com precisão), e a metade de cron/notificação (FR-1–FR-9) está arquitetada com regras reais e verificáveis (AD-5/6/7). Mas ela tem duas áreas onde uma Regra é inexequível como está escrita ou totalmente ausente pra capacidade mais nova/arriscada do PRD, mais uma necessidade de dado não modelada e uma lacuna de ambiente. Esses são exatamente o tipo de ponto de divergência que uma revisão de espinha dorsal existe pra capturar — recomendo uma passada de revisão antes de usar isso pra conduzir epics/stories.

---

## Achados

### 1. [ALTO] A regra de sidecar da AD-7 na verdade não roda o `cron` — reutiliza uma imagem que não tem o binário do cron

O próprio diagnóstico da AD-7 está correto: "a imagem atual (`python:3.12-slim`) não tem daemon de cron instalado." Verificado contra o `Dockerfile`: ele faz `pip install -r requirements.txt` e nada mais — zero passos de `apt-get`/pacote de sistema, então não há executável `cron` na imagem hoje.

Mas a *Regra* da AD-7 diz que o novo serviço `loterias-cron` usa "mesma imagem/Dockerfile do `loterias-web`" com o `CMD` mudado pra `manage.py crontab add && cron -f`. Se o Dockerfile de fato permanecer inalterado, `cron -f` não tem nada pra executar — o container sidecar vai entrar em crash-loop ou não fazer nada, e (pelo próprio propósito declarado da AD-7) "a rotina simplesmente nunca dispara em produção," que é precisamente o modo de falha que a AD afirma prevenir.

Isso falha no item de checklist "toda Regra de AD é exequível e de fato previne a divergência declarada" — é exequível (um builder consegue perfeitamente levantar um segundo serviço de compose com esse CMD) mas não previne a divergência/falha que ela nomeia, porque o ingrediente ausente (`apt-get install -y cron`, ou um `Dockerfile.cron`/estágio de build separado) nunca é declarado como parte da regra.

**Correção:** a Regra da AD-7 precisa de uma linha explícita de que o Dockerfile (ou uma variante/estágio específico do cron) instala o pacote `cron`, senão dois builders vão bater nisso de dois jeitos diferentes (um corrige o Dockerfile compartilhado, outro cria um segundo Dockerfile em fork, um descobre em produção).

### 2. [ALTO] FR-10–FR-13 (cadastro sem senha primeiro) não tem arquitetura — descartado como "só estender o formulário existente," mas o formulário e as configurações existentes fazem o oposto do que é preciso

A linha do Mapa de Capacidades pra FR-10–FR-13 diz: *"apps/accounts (views/forms existentes, estendidas) | convenção já fixada em CLAUDE.md (estender `CustomSignupForm`/`CustomAccountAdapter`)."* Isso trata como terreno rotineiro, já coberto.

Checado contra o código e as configurações reais, isso não é rotineiro:

- `loterias/settings/base.py`: `ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']` — senha é obrigatória no cadastro **hoje**. O FR-10 exige que a tela de cadastro peça **só** e-mail.
- `ACCOUNT_CONFIRM_EMAIL_ON_GET = True` + `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True` — hoje, clicar no link de confirmação confirma e **loga o usuário imediatamente**. O FR-12 exige que o link caia numa tela de criação de senha em vez disso, e o FR-10 exige que "conta pendente não permite login antes da senha ser definida" — ou seja, o login precisa ser bloqueado até um passo que, nas configurações atuais, é pulado por completo (a senha já existe) e controlado por uma flag (auto-login) que ainda não deve disparar.
- O `CustomSignupForm` de `apps/accounts/forms.py` hoje exige `first_name`/`last_name` no cadastro e herda os campos de senha do allauth — nada disso bate com "só e-mail" (FR-10) ou "nome/sobrenome só no primeiro login" (FR-14).
- `apps/accounts/models.py` não tem nenhuma noção de conta "pendente" (nenhuma flag de senha utilizável, nenhum campo de estado) que um builder pudesse usar pra bloquear o login.

Isso não é uma lacuna estreita — é o mecanismo mais novo de todo o PRD (inverter deliberadamente a sequência nativa do allauth de cadastro/confirmação/login), e mesmo assim não recebe nenhuma AD, nenhuma decisão sobre qual hook de adapter/view muda, nenhuma decisão sobre como "pendente, ainda sem senha" é representado, e nenhuma reconciliação com as configurações `ACCOUNT_*` que atualmente a contradizem.

Revelador: a própria fonte citada pela espinha dorsal, `docs/diagnostico-projeto.md` §5.3, já sinalizava isso explicitamente: *"precisa de uma view de 'definir senha' customizada acionada pelo link de confirmação, e um passo obrigatório de completar perfil no primeiro acesso autenticado."* A espinha dorsal cita esse documento como fonte mas não carrega o próprio diagnóstico dele adiante numa AD — ela regride a tratar o trabalho como uma edição de `forms.py` no nível de template.

**Risco se não for endereçado:** dois builders vão inventar independentemente soluções incompatíveis — ex.: um adiciona uma checagem `has_usable_password()` + um override customizado de `ACCOUNT_ADAPTER.login()`, outro adiciona um novo campo booleano em `User`, um terceiro constrói uma view sob medida totalmente fora do `SignupView` do allauth — cada um com implicações diferentes pro reaproveitamento de `EmailConfirmationHMAC` (FR-11/13 dependem do mesmo mecanismo de token), pra configuração `ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION`, e pra saber se o `CustomSignupForm` continua existindo como a classe de hoje ou é substituído.

### 3. [MÉDIO-ALTO] Os horários exatos de cron da AD-6 assumem um timezone que o container não tem demonstrado ter

A AD-6 fixa a agenda de retentativa em três horários concretos de relógio: 3h00, 3h15, 3h30 "horário de Brasília." O `CRONJOBS` do `django-crontab` escreve linhas de crontab comuns, que o daemon `cron` do sistema operacional interpreta no **horário de sistema do container**, não na configuração `TIME_ZONE` do Django (`America/Sao_Paulo`, confirmado em `loterias/settings/base.py`) — `TIME_ZONE`/`USE_TZ` só afetam como o próprio Django renderiza/armazena datetimes, não em que horário de relógio o cron dispara.

Nem o `Dockerfile` nem o `deploy/lab/docker-compose.yml` define `TZ` ou instala `tzdata`. O `python:3.12-slim` do Docker usa UTC por padrão. Como especificado, "3h00" no crontab do container é 3h00 UTC = 00h00 Brasília — uma deriva de 3 horas que poderia rodar a rotina *antes* dos sorteios noturnos da Caixa terminarem, minando diretamente a justificativa declarada no FR-1 ("janela segura após os sorteios noturnos da Caixa terminarem") e a própria AD-6.

**Correção:** a AD-7 (ou a AD-6) precisa de uma linha explícita: definir `TZ=America/Sao_Paulo` (e instalar `tzdata`) no container/imagem do cron, ou expressar as entradas de `CRONJOBS` com essa restrição explicitada, pra que um builder não entregue uma rotina que dispara silenciosamente no horário errado.

### 4. [MÉDIO] A "tabela de valores de premiação vigentes" do FR-8 é uma necessidade de dado nova que nunca é modelada em nenhum lugar da espinha dorsal

O FR-8 declara que `update_monthly_prize_values` "atualiza a tabela de valores de premiação vigentes usada por `calculate_bet_prize`." Essa é uma estrutura persistente distinta de qualquer coisa no schema atual — hoje, `calcular_premiacao_jogo`/`calculate_bet_prize` lê valores de premiação embutidos no `resultado_oficial`/`LotteryResult.premiacoes` específico daquele sorteio (confirmado em `apps/loterias_core/utils.py`), não de nenhuma tabela separada de "valores vigentes da faixa."

A lista de Models da espinha dorsal (Paradigma de Design + Semente Estrutural) só adiciona `HitNotification` e `NotificationPreference` (AD-3). Em nenhum lugar existe um model, campo, ou mesmo uma constante de configuração nomeada pra "tabela vigente" que o FR-8 precisa. Isso também fica em tensão com o RNF do FR-9 que a própria espinha dorsal ecoa nas Convenções de Consistência — que um prêmio exibido precisa sempre remontar a um `LotteryResult.prizes` concreto e nunca ser estimado — sem a espinha dorsal resolver se a tabela "vigente" do FR-8 é uma fonte de fallback/estimativa (que o RNF proíbe usar pra exibição) ou algo completamente diferente.

Essa é uma capacidade real (FR-8, explicitamente vinculada no frontmatter e mapeada na tabela de Capacidades) sem nenhuma arquitetura por trás do seu dado, que é exatamente o tipo de lacuna que deixa dois builders escolherem schemas incompatíveis (um model novo vs. um campo enxertado em `LotteryResult` vs. um dict de configurações/constantes).

### 5. [BAIXO] A tabela de Stack subestima materialmente o quão obsoleto está o `django-crontab`

O pin de versão em si se confirma: o último release do `django-crontab` no PyPI é de fato `0.7.1` — isso é genuinamente a versão atual/única disponível, não uma inventada. Mas a nota de risco ("não recebe release há mais de 12 meses") é uma subestimação significativa: `0.7.1` saiu em **março de 2016** — mais de uma década sem manutenção, não "12+ meses." A conclusão de "risco baixo" ainda pode estar certa (é um pacote pequeno que só invoca o `python-crontab`), mas a evidência citada pra sustentar isso subestima a obsolescência real, o que importa pra um documento de portfólio destinado a demonstrar o rigor diagnóstico do PM (conforme o item "Jobs To Be Done" do §2.1 do PRD sobre o projeto demonstrar esse rigor).

### 6. [BAIXO] Duas lacunas menores, anotadas por completude

- **A linha do mapa de capacidades do FR-2** ("bloqueio de concurso já sorteado") passa por cima do fato de que é uma mudança de comportamento em código que já está em produção: hoje `gerar_jogo`/`salvar_jogo_manual` só *avisam* (não bloqueiam) sobre um `jogo`+`concurso` duplicado pro *mesmo usuário* (ver `apps/loterias_core/views.py` linhas ~60–61 e ~192–193); o FR-2 exige um bloqueio duro baseado em existir *qualquer* `LotteryResult` pra aquele `jogo`+`concurso`, que é uma checagem totalmente diferente. Não é uma omissão que quebra a arquitetura (fica confinada a duas funções de view), mas uma entrada de uma linha nas Convenções de Consistência removeria a ambiguidade sobre "bloquear, não avisar" e "checar `LotteryResult`, não linhas irmãs de `GeneratedBet`".
- **Nenhuma política de restart declarada pra `loterias-cron`.** O serviço `loterias-web` existente tem `restart: unless-stopped`; a regra da AD-7 pro novo sidecar não diz se ele herda a mesma política. Se o container de cron morrer silenciosamente, FR-1/FR-8 simplesmente param de rodar sem nenhum sinal operacional — uma pequena lacuna de envelope operacional que vale uma linha na AD-7.

---

## O que a espinha dorsal acerta (pra balancear)

- O Paradigma (integração Shared-Database entre os processos web e cron, nunca chamadas em processo) é um invariante genuinamente útil e é imposto consistentemente através da AD-5/6/7.
- AD-1/AD-2 (convenção de rename + sequenciamento epic-de-rename-primeiro, usando `RenameModel`/`RenameField` com um passo de backup pré-migration) responde direta e corretamente à Questão Aberta §8.4 do PRD.
- A tabela de mapeamento de rename foi cruzada com precisão contra os nomes de símbolo reais de `apps/loterias_core/models.py`/`utils.py`/`views.py` — nenhum nome legado obsoleto ou inventado encontrado.
- A regra "sem segunda fonte de verdade" da AD-3/AD-4 (campos de cache em `GeneratedBet` continuam sendo autoritativos, `HitNotification` nunca os substitui) é uma regra real e exequível que capturaria uma classe comum de bug.
- A tabela de Convenções de Consistência reaproveita corretamente o histórico de `EmailConfirmation` já existente do django-allauth pro cooldown/rate-limit do FR-11 em vez de inventar um model novo — bom minimalismo, e é uma leitura precisa do que o allauth já rastreia.
- As afirmações de `requirements.txt`/`Dockerfile`/`docker-compose.yml` sobre o estado atual (celery/redis presentes mas não usados, nenhum serviço de cron hoje, processo único `gunicorn`, nenhum `django-crontab` em requirements) todas se confirmaram exatamente como descritas.
