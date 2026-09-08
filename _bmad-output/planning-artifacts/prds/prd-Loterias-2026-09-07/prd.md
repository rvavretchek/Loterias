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

## 1. Visão

O Loterias hoje gera apostas válidas para seis loterias brasileiras e guarda o histórico de cada usuário — mas para saber se ganhou, o usuário precisa lembrar de voltar ao site e clicar manualmente em "verificar resultado", jogo por jogo. Isso é o oposto de por que alguém jogaria: a promessa de uma loteria é "e se eu tiver ganhado?", e hoje o sistema não responde essa pergunta sozinho.

As duas frentes deste PRD atacam os dois momentos em que, hoje, o sistema empurra pro usuário um trabalho que deveria ser dele: a primeira impressão (cadastro) e a primeira vitória (saber que ganhou). A primeira faz o sistema vigiar os resultados oficiais da Caixa por conta própria — todo dia — e avisar o usuário assim que ele faz login se algum dos seus jogos bateu, diferenciando claramente "acertou alguns números" de "acertou o suficiente pra ganhar prêmio". A segunda troca o cadastro genérico do django-allauth por um fluxo deliberado (e-mail → link → senha → nome) que corresponde a como o Ricardo quer que a primeira impressão do produto aconteça.

Nenhuma das duas depende de infraestrutura nova pesada: a captura de resultado já existe (`capturar_resultado_cef`), só falta rodar sozinha; o cadastro por e-mail já existe via allauth, só falta reordenar os passos.

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
    5. Em um login posterior, depois que a rotina diária capturou um resultado que bate com algum jogo dela, ela vê uma notificação (barra/local a definir por UX) resumindo os acertos — diferenciando "acertos sem prêmio" de "acertos com prêmio".
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

- **Jogo** — Um dos seis tipos de loteria suportados (Mega-Sena, +Milionária, Lotomania, Lotofácil, Quina, Dupla-Sena). Corresponde a `JOGOS_CONFIG` no código.
- **Concurso** — Identificador numérico de um sorteio específico de um Jogo. Não é estritamente sequencial nem exclusivo por Jogo — concursos especiais/comemorativos podem rodar em paralelo à numeração regular.
- **JogoGerado** — Uma aposta salva por um usuário: um Jogo + um Concurso + um conjunto de números (e trevos, quando aplicável). Pode ser gerado automaticamente ou informado manualmente (`manual=True`).
- **ResultadoLoteria** — O resultado oficial de um Concurso, capturado da Caixa. Único por (Jogo, Concurso).
- **Acerto** — Interseção não vazia entre os números de um JogoGerado e os números de um ResultadoLoteria para o mesmo Jogo+Concurso.
- **Acerto premiado** — Acerto cuja quantidade de números atinge o mínimo que gera prêmio para aquele Jogo (ex.: 4+ na Mega-Sena). Ver `calcular_premiacao_jogo`.
- **Acerto não premiado** — Acerto que não atinge esse mínimo.
- **Notificação de Acerto** — Registro criado quando a rotina diária encontra um Acerto novo para um JogoGerado; carrega o estado lido/não-lido e se é premiado ou não.
- **Preferência de Notificação** — Configuração por usuário de por onde deseja receber avisos de Acerto: site, e-mail, ou ambos.
- **Rotina diária de resultados** — Job agendado (django-crontab) que roda `capturar_resultado_cef` para os concursos em aberto de cada Jogo e cruza com os JogoGerado dos usuários.
- **Rotina mensal de premiações** — Job agendado (django-crontab) que atualiza a tabela de valores de premiação vigentes.
- **Vínculo de Confirmação de Cadastro** — Token de uso único e com expiração que autentica a Sônia da UJ-2 na tela de criação de senha (mecanismo já existente do django-allauth).

## 4. Funcionalidades

*Convenção: um FR traz "Realiza UJ-X" quando corresponde a um passo específico de uma jornada. FRs de suporte/transversais (ex.: rotinas agendadas, preferências, envio de e-mail) não amarram a um passo específico de UJ e por isso não trazem essa tag — não é omissão.*

### 4.1 Verificação e Notificação de Resultados

**Descrição:** Realiza a UJ-1. Duas rotinas agendadas via django-crontab mantêm o sistema informado sobre resultados oficiais sem ação do usuário; o cruzamento contra os JogoGerado de cada usuário gera Notificações de Acerto, exibidas ao logar e detalhadas sob clique. Substitui a decisão de arquitetura originalmente cogitada (Celery + Redis) — ver Não-Objetivos (§5) para o porquê.

#### FR-1: Rotina diária de resultados

Diariamente às 3h (horário de Brasília — janela segura após os sorteios noturnos da Caixa terminarem), o sistema executa uma rotina que, para cada Jogo com concursos em aberto (sem ResultadoLoteria registrado), tenta capturar o resultado oficial via `capturar_resultado_cef` e grava em ResultadoLoteria.

**Consequências (testáveis):**
- A rotina não recria um ResultadoLoteria que já existe para o mesmo Jogo+Concurso (idempotente).
- Uma falha de captura para um Jogo/Concurso específico não interrompe a tentativa dos demais.
- Ver FR-9 para a política de retentativa dentro da mesma execução diária.

#### FR-2: Bloqueio de concurso já sorteado

Ao gerar (automático ou manual) um JogoGerado, o sistema pré-preenche o campo de Concurso com uma sugestão (próximo concurso sequencial daquele Jogo, com base no maior Concurso já visto), mas aceita qualquer número informado. A única validação real: rejeitar se aquele Jogo+Concurso já tiver ResultadoLoteria registrado. Realiza UJ-1, passos 1–3.

**Consequências (testáveis):**
- Tentar gerar/salvar um JogoGerado para um Jogo+Concurso com ResultadoLoteria existente retorna erro claro, sem gravar o registro.
- Um Concurso fora da sequência normal (especial/comemorativo) sem ResultadoLoteria é aceito normalmente.

#### FR-3: Geração de Notificação de Acerto

Sempre que a rotina diária grava um ResultadoLoteria novo, o sistema compara com todos os JogoGerado existentes daquele Jogo+Concurso e cria uma Notificação de Acerto para cada JogoGerado com interseção não vazia — marcada como premiada ou não, conforme `calcular_premiacao_jogo`. Realiza UJ-1, passo 5.

**Consequências (testáveis):**
- JogoGerado sem interseção nenhuma não gera Notificação.
- Uma Notificação de Acerto é criada no máximo uma vez por JogoGerado+ResultadoLoteria (idempotente — reexecutar a rotina não duplica).

#### FR-4: Exibição da notificação ao logar

Ao autenticar, o usuário com Notificação(ões) de Acerto não lida(s) vê um indicador (local exato definido por UX) resumindo a quantidade, diferenciando visualmente acertos premiados de não premiados.

**Consequências (testáveis):**
- Usuário sem Notificação pendente não vê indicador algum.
- Um acerto premiado é visualmente distinguível de um não premiado no resumo (não apenas no detalhe).

#### FR-5: Detalhe e leitura da notificação

Clicar no indicador leva a uma tela listando as Notificações de Acerto pendentes, com o detalhe de números batidos e valor do prêmio (se houver). Cada Notificação pode ser marcada como lida individualmente a partir dessa tela. Realiza UJ-1, clímax e resolução.

**Consequências (testáveis):**
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

No primeiro dia de cada mês, o sistema atualiza a tabela de valores de premiação vigentes usada por `calcular_premiacao_jogo`, para que o valor exibido numa Notificação premiada reflita a faixa de prêmio corrente.

**Consequências (testáveis):**
- Uma Notificação de Acerto premiada criada após a rotina mensal usa os valores atualizados, não os anteriores.

#### FR-9: Tratamento de falha da captura de resultado

Dentro de uma mesma execução da rotina diária, se `capturar_resultado_cef` falhar para um Jogo/Concurso, o sistema tenta novamente até 3 vezes, com 15 minutos de intervalo entre tentativas, antes de desistir daquele Jogo/Concurso para o dia — as 3 tentativas terminam bem antes do horário em que usuários costumam abrir o sistema pela manhã. Se todas as tentativas falharem, o sistema envia um e-mail de alerta ao operador (Boss) — não é um alerta ao usuário final, e não depende de múltiplos dias de falha. O usuário final simplesmente não vê Notificação naquele Jogo/Concurso até a captura funcionar em um dia seguinte. Realiza UJ-1, caso de borda.

**Consequências (testáveis):**
- Falha de captura não gera Notificação de Acerto incorreta nem falsa (nunca inventa resultado).
- Falha de captura não bloqueia a rotina diária dos demais Jogos.
- Esgotadas as 3 tentativas do dia, exatamente um e-mail de alerta é enviado ao operador por Jogo/Concurso falho — não um por tentativa.
- O e-mail de alerta vai para um endereço de operador configurável via variável de ambiente (`[ASSUMPTION]` nome da variável e endereço exatos ficam para a implementação — ver §8).

**NFRs específicas desta funcionalidade:**
- Um valor de prêmio exibido numa Notificação sempre rastreia a um ResultadoLoteria.premiacoes concreto — o sistema nunca estima ou arredonda um valor de prêmio na ausência de dado oficial confirmado (falha = sem Notificação, não Notificação com valor incerto).
- As rotinas agendadas respeitam uma cadência deliberadamente baixa (diária para resultado, mensal para valores) para não sobrecarregar nem ser bloqueado pelo site da Caixa, que não oferece API oficial.

**Notas:** `[NOTE FOR PM]` A view `verificar_resultado_jogo` já existente (verificação sob demanda, por clique) continua funcionando em paralelo à rotina diária — ambas escrevem no mesmo ResultadoLoteria via `update_or_create`, então não há conflito, mas vale revisitar se a verificação manual ainda faz sentido depois que a rotina automática cobre o caso comum.

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
- Novo fluxo de cadastro completo: e-mail → link → senha → nome/sobrenome no primeiro login (FR-10 a FR-14).

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
- **SM-3**: Zero falso-positivo de premiação — nenhuma Notificação Premiada é criada sem um ResultadoLoteria oficial confirmado por trás. Valida FR-9 e a NFR de rastreabilidade de valor de prêmio (§4.1).

**Contra-métricas (não otimizar)**
- **SM-C1**: Volume de e-mails de acerto por usuário permanece baixo (um e-mail por Acerto Premiado real, nunca reenviado por reexecução da rotina) — contrabalança SM-1: o objetivo é notificar corretamente, não notificar com frequência.

## 8. Questões em Aberto

1. Nome exato da variável de ambiente e endereço de e-mail do operador para o alerta de FR-9 (ex.: `OPERATOR_ALERT_EMAIL`) — decisão de implementação, não de produto.
2. Texto definitivo (jurídico) dos termos de serviço, para quando o projeto for publicado de verdade — o Anexo A é só placeholder até lá.
3. Onde/como o operador (Boss) acompanha o histórico de alertas de FR-9 além do e-mail avulso — um painel dedicado ficou fora do MVP (§6.2); por ora, o e-mail é o único registro.

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
