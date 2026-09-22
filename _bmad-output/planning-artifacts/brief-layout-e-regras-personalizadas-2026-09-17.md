# Brief — Redesign de UI e Regras de Geração Personalizadas por Jogo

**Origem:** ditado pelo Boss em 2026-09-17, na sequência do fechamento do Epic 2, como as "2-3 sprints" necessárias antes de entrar em homologação (ver PRD atual, `_bmad-output/planning-artifacts/prds/prd-Loterias-2026-09-07/prd.md`, que cobre só os Epics 1-3).

Este documento é uma captura fiel do que foi pedido, organizada em 3 frentes candidatas a épico/story. Ainda não passou por `bmad-prd`/`bmad-create-epics-and-stories` — é o material de entrada pra essa etapa, não um substituto dela.

## Frente 1 — Landing page (visitante não autenticado)

- Remover a mensagem "Multitenant Seguro" e os 3 cards de features (`templates/loterias_core/home.html`, bloco "Features para visitantes") — não agregam valor, e a referência a multitenant é obsoleta desde a remoção da arquitetura multitenant (ver [[project-loterias-multitenancy-removal]]).
- **Feito em 2026-09-17** (aplicado diretamente, sem passar por planejamento formal — mudança trivial e sem ambiguidade: `git log` no commit desta sessão).
- **Fora de escopo aqui:** o Boss vai criar um design system próprio e, a partir dele, uma landing page nova e mais interessante. Não inventar layout de landing page antes disso — só a limpeza acima foi pedida agora.

## Frente 2 — Home autenticada (tela "quando se entra no app")

Objetivo: eliminar a necessidade de scroll pra gerar um jogo. Reestruturar em 3 áreas, de cima pra baixo:

1. **Resumo (dashboard stats)** — hoje ocupa a área útil logo no topo (cards "Jogos Gerados"/"Tipos de Jogo"/"Jogos Recentes"). Deve encolher — não pode mais tomar a tela útil. Considerar mover pra lateral (sidebar) em vez de ficar no topo em largura total.
2. **Jogo selecionado / a realizar** — deve ficar bem no topo da área útil (onde hoje fica o resumo), pra gerar um jogo sem precisar rolar a tela.
3. **Seletor de jogos** — abaixo da área de "jogo selecionado". Cada jogo com seu próprio ícone (hoje todos usam o mesmo ícone genérico `bi-dice-5` — ver `templates/loterias_core/home.html` linha ~76, `game-selector`).

Ordem final proposta pela mensagem original: resumo (menor, lateral) → jogo selecionado/a realizar (topo da área útil) → seletor de jogos (logo abaixo).

**Pontos em aberto pra próxima etapa de planejamento:**
- Ícone por jogo: existe algum set de ícones já escolhido, ou fica a critério de quem implementar (Bootstrap Icons já é a lib em uso — ver `bi-*` no template)?
- "Resumo pode ficar de lado" — sidebar fixa, colapsável, ou só menor mas ainda no fluxo vertical? Decisão de layout, não de produto.

## Frente 3 — Regras de geração personalizadas por jogo (feature nova)

Fluxo: usuário abre o seletor de jogos → opção "editar" por jogo → tela de edição das regras de geração daquele jogo especificamente pra aquele usuário (ex.: "José seleciona editar Mega-Sena" → tela de edição das regras de geração da Mega-Sena pra José).

Implica um novo model (regras por usuário+jogo, análogo em espírito a `NotificationPreference` — único por user+game) e uma reescrita de `generate_bet()` (`apps/loterias_core/utils.py`) pra ler e aplicar essas regras em vez da regra fixa de pares sequenciais hoje hardcoded (`GAMES_WITH_SEQUENCE_RULE`/`MIN_SEQUENCE_INTERVAL`/`count_sequential_pairs()`, ver `CLAUDE.md`).

Regras por família de jogo, como ditadas (nomes e faixas de valor ainda não especificados — a especificar no planejamento formal):

**Mega-Sena, Dupla-Sena, Quina, Milionária** (mesmo conjunto de regras pras 4):
- Limita quantidade de número em sequência — [SIM/NÃO] + [Valor]
- Limita quantidade de sequências num jogo — [SIM/NÃO] + [Valor]
- Limita quantidade de números na mesma linha — [SIM/NÃO] + [Valor]
- Limita quantidade de números na mesma coluna — [SIM/NÃO] + [Valor]
- Tipo de distribuição — [Homogênea / Totalmente Aleatória]

**Lotofácil** (conjunto próprio, mais regras que o grupo acima):
- Limita quantidade de número em sequência — [SIM/NÃO] + [Valor]
- Limita quantidade de sequências num jogo — [SIM/NÃO] + [Valor]
- Limita espaço mínimo entre sequências — [SIM/NÃO] + [Valor]
- Limita quantidade mínima de sequências num jogo — [SIM/NÃO] + [Valor]
- Limita quantidade de números na mesma linha — [SIM/NÃO] + [Valor]
- Limita quantidade de números na mesma coluna — [SIM/NÃO] + [Valor]
- Tipo de distribuição — [Homogênea / Totalmente Aleatória]

**Lotomania** (conjunto reduzido):
- Limita quantidade de número em sequência — [SIM/NÃO] + [Valor]
- Limita espaço mínimo entre sequências — [SIM/NÃO] + [Valor]
- Limita quantidade mínima de sequências num jogo — [SIM/NÃO] + [Valor]

**Perguntas em aberto pra próxima etapa (não respondidas na mensagem original):**
- "Linha"/"coluna" pressupõe um layout em grade pro volante de cada jogo (como o volante físico da Caixa) — precisa confirmar o grid exato por jogo (quantas colunas, numeração) antes de implementar as regras de linha/coluna.
- O que acontece com a regra de pares sequenciais já existente (`GAMES_WITH_SEQUENCE_RULE`, olha os últimos 5 jogos do usuário) — é substituída por essas regras configuráveis, ou convive com elas como default quando o usuário nunca personalizou?
- "Valor" de cada regra — faixa válida, e o que a regra faz exatamente quando o valor não é atingível (ex. pedir 0 sequências num jogo que estruturalmente sempre tem pelo menos 1 par, dependendo da faixa numérica)?
- Regras conflitantes entre si (ex. limite de sequência muito restritivo + distribuição "Totalmente Aleatória") — como resolver sem loop infinito de geração (o código já tem um padrão de `max_attempts` em `regenerate_bet_view`, algo parecido provavelmente serve aqui)?
- Lotomania e Lotofácil não tiveram "número em sequência"/"distribuição" explicitados com os mesmos rótulos do grupo principal — confirmar se são os mesmos conceitos ou algo específico de cada jogo.

## Frente 4 — Tela de resultados/histórico separada

Hoje `history_view`/`historico.html` existe mas sem filtros. Pedido:
- Tela própria (já existe como tela separada — `/historico/` — mas precisa dos filtros abaixo).
- Filtros **cumulativos** (aplicáveis em conjunto, não mutuamente exclusivos): por jogo, por data/período, por "quem ganhou" (só jogos premiados).
- Exibição legível apesar do volume/formato de números por jogo: Lotomania e Lotofácil têm muitos números (50 e 15, respectivamente — ver `GAMES_CONFIG` em `apps/loterias_core/models.py`), Dupla-Sena tem 2 sorteios (`numbers`/`numbers_second_draw`, Story 2.18) — o layout atual de "bolinhas em linha" (`numero-bola`, ver `home.html`/`historico.html`) pode não escalar bem pra 50 números por jogo × todos os jogos guardados de um usuário ativo.

## Próximo passo

Este brief ainda não tem FRs formais, critérios de aceite, nem story breakdown — só a intenção capturada fielmente. Antes de qualquer implementação de Frentes 2-4 (a 1 já foi feita), decidir com o Boss: rodar `bmad-prd` (adicionar FRs a um novo épico no PRD existente) e depois `bmad-create-epics-and-stories`, ou ir direto pra `bmad-create-epics-and-stories`/`bmad-spec` já que o escopo já está bem descrito aqui.
