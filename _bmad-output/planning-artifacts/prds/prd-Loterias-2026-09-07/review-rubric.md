# Revisão de Qualidade do PRD — Loterias: Verificação de Resultados e Novo Fluxo de Cadastro

## Veredito geral

Este é um PRD incomumente bem trabalhado para sua escala: todo RF carrega consequências testáveis, as seções Não-Objetivos/§6.2 delimitam o escopo com honestidade em vez de por omissão, e as referências ao código legado (`capturar_resultado_cef`, `calcular_premiacao_jogo`, `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`) se confirmam contra o código real. Os pontos mais frágeis são um punhado de números não quantificados dentro de RFs por outro lado testáveis (o "ex.: 3h" do FR-1, o "2–3 tentativas... com espaçamento" do FR-9) e o agrupamento de duas áreas de funcionalidade pouco relacionadas sob uma única Visão sem nomear um tipo único de escopo de MVP. Nada aqui bloqueia o avanço para arquitetura/stories; os achados abaixo são ajustes finos, não resgate.

## Maturidade de decisão — forte

O PRD declara decisões como decisões, não como considerações em cima do muro. O §5 rejeita Celery+Redis explicitamente com um motivo declarado ("desproporcional a duas tarefas periódicas simples neste porte de projeto") em vez de apresentá-lo como opção aberta. O FR-9 nomeia um trade-off real e seu custo em linguagem direta: a falha é silenciosa para o usuário final ("não é um alerta ao usuário final... O usuário final simplesmente não vê Notificação") e só alerta o operador — o PRD não maquia isso como aceitável para todo mundo. O §6.2 explicitamente adia um painel admin de histórico de falhas para v2 em vez de fingir que o e-mail do operador do FR-9 é uma solução completa. As três Questões Abertas do §8 são genuinamente abertas (nome da env var, texto jurídico dos Termos de Uso, onde o operador vê o histórico de alertas) — nenhuma é uma pergunta retórica respondida na frase seguinte.

### Achados
- **baixo** Título provisório não resolvido (linha de título, "*Working title — confirmar.*") — uma ponta solta cosmética, mas é uma decisão deixada em aberto no primeiro lugar que um leitor olha. *Correção:* resolver antes de tratar este PRD como final, ou mover a nota para o §8.

## Substância acima de teatro — forte

Sem achados. Apenas duas Jornadas de Usuário (UJs), ambas estruturais (UJ-1 conduz FR-1–FR-9, UJ-2 conduz FR-10–FR-14) — sem enchimento de persona. Os RNFs sob §4.1 e §4.2 são específicos do produto, não clichê: "o sistema nunca estima ou arredonda um valor de prêmio na ausência de dado oficial confirmado" e "as rotinas agendadas respeitam uma cadência deliberadamente baixa... para não sobrecarregar nem ser bloqueado pelo site da Caixa" nomeiam, cada um, um modo de falha concreto sendo evitado, não um "precisa ser confiável" genérico. A Visão (§1) está fundamentada na lacuna real de UX atual ("precisa lembrar de voltar ao site e clicar manualmente em 'verificar resultado', jogo por jogo") em vez de uma declaração de propósito intercambiável.

## Coerência estratégica — adequada

A tese do §1 — o sistema deve responder "e se eu tiver ganhado?" sem ser perguntado — realmente conduz a Feature 4.1 do início ao fim: a ordem dos RFs (captura → cruzamento → notificação → detalhe → preferência → e-mail → tratamento de falha) segue a tese, não a facilidade de implementação. As Métricas de Sucesso reforçam a tese em vez de medir atividade: SM-1 é sobre confiabilidade de notificação, não volume de engajamento, e SM-C1 é uma contra-métrica real ("não otimizar" — limita o volume de e-mail contra o próprio incentivo do SM-1 de notificar demais).

A Feature 4.2 (cadastro) não está unida a essa tese, e o PRD não finge o contrário — o §1 a justifica separadamente como algo que corresponde a "como o Ricardo quer que a primeira impressão do produto aconteça," e o §0 enquadra o próprio documento como servindo a dois propósitos (spec de trabalho + peça de portfólio) em vez de uma única tese de produto. A honestidade é boa; a lacuna de coerência ainda é real para um leitor tentando extrair "no que esse PRD está apostando" numa frase só.

### Achados
- **médio** Duas áreas de funcionalidade, nenhuma tese única (§1, §0) — o parágrafo de Visão argumenta a favor da 4.1 a partir da tese de notificação e depois encaixa a 4.2 via uma justificativa diferente ("corresponde a como o Ricardo quer que a primeira impressão... aconteça"). Um leitor construindo um slide a partir deste PRD precisaria de duas frases, não uma. *Correção:* ou dividir em dois PRDs, ou adicionar uma frase no §1 nomeando a lógica guarda-chuva (ex.: "esta versão resolve os dois momentos — primeira impressão, primeira vitória — em que o produto hoje exige que o usuário faça o trabalho do sistema").
- **baixo** Tipo de escopo do MVP não nomeado — o §6 não declara se este MVP é orientado a resolver problema, a experiência, a plataforma ou a receita (rubrica §3). É inferível (4.1 lê como resolver-problema, 4.2 como experiência), mas fica implícito.

## Clareza de "pronto" — forte

Esta é a melhor dimensão do PRD. Todo RF (FR-1 a FR-14) carrega um bloco "Consequências (testáveis)" com condições verificáveis — ex.: o "retorna erro claro, sem gravar o registro" do FR-2 vem acompanhado de um caso negativo concreto ("Concurso fora da sequência normal... é aceito normalmente"), e o FR-11 dá números concretos ("desabilitado por 60 segundos," "Limite de 5 reenvios por conta por dia") em vez de adjetivos. O posicionamento de UX do FR-4 é explicitamente adiado ("local exato definido por UX") em vez de deixado ambíguo por omissão — isso é um adiamento legítimo, não uma lacuna de "pronto".

### Achados
- **médio** A política de retentativa do FR-9 é subespecificada para algo que o próprio RF chama de testável — "tenta novamente 2–3 vezes (com espaçamento entre tentativas)" não diz se é 2 ou 3, e "espaçamento" não tem duração. A consequência "Esgotadas as 2–3 tentativas do dia, exatamente um e-mail..." não pode ser testada sem escolher um número. *Correção:* comprometer-se com um número e um valor de espaçamento (ou marcar ambos explicitamente como `[ASSUNÇÃO]` adiada para a implementação, do mesmo jeito que o endereço de e-mail do operador do FR-9 já está marcado).
- **baixo** O horário do FR-1 é ilustrativo, não comprometido — "de madrugada (ex.: 3h, horário de Brasília)" — o "ex.:" sinaliza que isso é um exemplo, então um engenheiro não sabe se 3h é o requisito ou um placeholder. *Correção:* ou se comprometer com um horário, ou marcar como `[ASSUNÇÃO]` como a variável de e-mail do FR-9 já está.
- **baixo** A cadência mensal do FR-8 não tem dia/horário especificado (diferente do "ex.: 3h" do FR-1, que ao menos aponta um) — "Mensalmente, o sistema atualiza..." não diz em que dia do mês. Severidade baixa porque a própria consequência testável do RF não depende do dia exato.

## Honestidade de escopo — forte

O §5 (Não-Objetivos) e o §6.2 (Fora de Escopo do MVP) fazem trabalho real em vez de gesticular — o §6.2 nomeia quatro omissões concretas, uma marcada `[NOTA PARA O PM]` para revisitar antes do lançamento (texto dos Termos de Uso) e uma explicitamente adiada para v2 com o motivo pelo qual é seguro adiar (FR-9 "registra o problema, mas não define onde/como o operador vê isso"). A densidade de itens abertos (3 Questões Abertas, 1 `[ASSUNÇÃO]` inline, 2 `[NOTA PARA O PM]`) é adequadamente leve para um PRD de projeto solo/portfólio — a orientação da rubrica de que contagens altas são aceitáveis em baixo risco também vale ao contrário: essa contagem é proporcional, não rala.

### Achados
- **baixo** O ida-e-volta do Índice de Assunções está incompleto — a segunda entrada do §9 ("§4.2, FR-12 — texto dos termos de serviço é o placeholder...") não tem a marcação inline `[ASSUNÇÃO]` correspondente no próprio FR-12 (§4.2, FR-12 só diz "texto placeholder no Anexo A" sem o marcador entre colchetes), diferente da primeira entrada, cuja marcação inline está presente nas consequências do FR-9. Ver também Notas mecânicas.

## Utilidade a jusante — forte

O Glossário (§3) é genuinamente estrutural — dez termos definidos uma vez e usados de forma idêntica em todos os lugares verificados (ex.: "Notificação de Acerto" aparece consistentemente na UJ-1, FR-3–FR-7 com a mesma capitalização). O §0 instrui explicitamente os leitores a jusante a tratar o Glossário como canônico. Os IDs de RF (FR-1–FR-14), UJ (UJ-1, UJ-2) e SM (SM-1–SM-3, SM-C1) são contíguos, sem lacunas ou duplicatas. Cada UJ tem um protagonista nomeado e contextualizado (Dulce, Sônia) em vez de texto de cenário flutuante.

### Achados
- **baixo** Marcação "Realiza UJ-X" inconsistente — FR-2, FR-3, FR-5, FR-9, FR-10, FR-12, FR-13, FR-14 declaram, cada um, qual passo de UJ realizam; FR-1, FR-6, FR-7, FR-8, FR-11 não. Isso é defensável (esses cinco são RFs de suporte/transversais não ligados a um passo de UJ específico), mas não está declarado como convenção, então um leitor a jusante não consegue distinguir "omitido por ser transversal" de "omitido por descuido". *Correção:* uma linha na introdução do §4 esclarecendo a convenção.

## Adequação de forma — forte

O PRD fica entre duas formas e nomeia a própria tensão: o §0 declara que serve tanto como spec de trabalho quanto como peça de portfólio ("a documentação em si é parte do valor demonstrado"), o que explica e justifica um rigor bem além do que um projeto hobby/solo puro exigiria (rubrica: "Hobby/solo → rigor leve, a régua de substância ainda se aplica"). Como o rigor elevado é um objetivo declarado, e não um acidente, isso não é over-formalização. UJs com protagonistas nomeados são adequadamente estruturais dado que este é um fluxo real voltado ao consumidor (Dulce, Sônia), não uma ferramenta interna de operador único. As referências ao código legado foram verificadas pontualmente contra o repositório real e estão corretas: `capturar_resultado_cef`, `calcular_premiacao_jogo` e `verificar_resultado_jogo` existem em `apps/loterias_core` (views.py/utils.py/models.py), `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS` existe em `loterias/settings/base.py`, e `celery`/`redis` de fato ainda estão presentes em `requirements.txt`, confirmando a afirmação do §5 de que precisam ser removidos.

Sem achados.

## Notas mecânicas

- **Ida-e-volta do Índice de Assunções — uma entrada sem par.** A primeira entrada do §9 (e-mail do operador do FR-9) tem a marcação inline `` `[ASSUNÇÃO]` `` correspondente no §4.1 FR-9. A segunda entrada do §9 (placeholder de Termos de Uso do FR-12) não tem marcação inline correspondente no §4.2 FR-12 — o texto do RF só diz "texto placeholder no Anexo A" sem o marcador entre colchetes. Pequeno, mas quebra a convenção de ida-e-volta declarada.
- **Consistência do glossário** — termos verificados pontualmente ("Jogo," "Concurso," "JogoGerado," "ResultadoLoteria," "Acerto," "Notificação de Acerto") são usados com capitalização e forma singular/plural consistentes em RFs e UJs. Nenhum desvio encontrado.
- **Continuidade de IDs** — FR-1 a FR-14 contíguos; UJ-1/UJ-2 contíguos; SM-1/SM-2/SM-3 mais a contra-métrica SM-C1, sem lacunas ou duplicatas. Referências cruzadas (ex.: "Realiza UJ-1, passos 1–3," "Ver FR-9") todas resolvem para seções existentes.
- **Nomeação de protagonistas de UJ** — ambas as UJs têm um protagonista nomeado com detalhe contextual (os jogos e a impaciência da Dulce; o primeiro cadastro da Sônia), satisfazendo diretamente a exigência da rubrica.
