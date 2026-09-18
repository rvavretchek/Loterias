# Epic 4 Context: Home Reorganizada, Regras de Geração Personalizadas e Histórico com Filtros

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Gerar um jogo deixa de exigir scroll na home (resumo vira sidebar, jogo selecionado sobe pro topo, cada Jogo ganha ícone próprio); cada usuário pode personalizar como cada Jogo é gerado pra ele (regras de sequência/linha/coluna/distribuição, por família de Jogo); e o histórico ganha filtros cumulativos com exibição legível mesmo pra Jogos com muitos números. Depende dos Epics 1-3 concluídos.

## Stories

- Story 4.1: Reorganização da área útil da home
- Story 4.2: Ícone por Jogo no seletor
- Story 4.3: Model GenerationRule e tela de edição de Regras de Geração por Jogo
- Story 4.4: Regras de Geração — Mega-Sena, +Milionária, Quina, Dupla-Sena
- Story 4.5: Resolução de conflito entre Regras de Geração
- Story 4.6: Regras de Geração — Lotofácil
- Story 4.7: Regras de Geração — Lotomania
- Story 4.8: Filtros cumulativos e exibição legível no histórico

## Requirements & Constraints

- Meta de "sem scroll pra gerar um jogo" vale a partir de 1280×720; abaixo disso a sidebar empilha e scroll é aceitável.
- O campo Concurso (editável, aceita concursos especiais) nunca some nem é escondido pela reorganização; só muda de posição.
- Regras de Geração só valem daqui pra frente; jogos já gerados não são recalculados.
- Sem personalização, a geração mantém o comportamento adaptativo atual de sequência. Após o primeiro save de um Jogo, só os toggles explícitos valem (mesmo todos desligados). "Restaurar padrão" volta ao adaptativo.
- Conflito de regras: relaxa no máximo 1 regra por geração e avisa nomeando regra e Jogo (aviso, não erro). Se ainda falhar, cai na mensagem existente "Não foi possível gerar um jogo único".
- Valor fora da faixa: erro inline no campo, nomeando a faixa válida. A faixa por regra/Jogo é decisão do Boss por story (validação em `forms.py`).
- Desligar a última proteção de sequência exige confirmação explícita (modal Bootstrap).
- Linha/coluna: grid confirmado só pra Mega-Sena (6×10) e Lotofácil (5×5). Pra +Milionária, Quina e Dupla-Sena esses campos ficam indisponíveis até confirmação do grid (não aparecem nem geram erro).
- Conjuntos de regras por Jogo:
  - Mega-Sena: sequence_count, sequence_pairs, row, column, distribution.
  - +Milionária/Quina/Dupla-Sena: sequence_count, sequence_pairs, distribution.
  - Lotofácil: as 5 da Mega-Sena mais min_gap_between_sequences e min_sequences.
  - Lotomania: só sequence_count, min_gap_between_sequences e min_sequences.
- Distribuição: "Homogênea" sorteia um número por faixa de largura igual do intervalo. "Totalmente Aleatória" é o sorteio uniforme de hoje.
- Acessibilidade obrigatória: ícones decorativos com `aria-hidden`, região `aria-live="polite" aria-atomic="true"` na área de jogo selecionado, estado selecionado com indicador não-cromático, `:focus-visible` preservado, nenhum elemento interativo aninhado em outro.

## Technical Decisions

- `GenerationRule(user, game, rule_name, enabled, numeric_value, choice_value, updated_at)` em `apps/loterias_core/models.py`:
  - `unique_together` em (user, game, rule_name).
  - `CheckConstraint` XOR entre `numeric_value` e `choice_value` (`choice_value` só pra distribuição).
  - `updated_at` com `auto_now`.
  - Migration só cria a tabela.
- `RULE_NAMES_BY_GAME` (dict ao lado de `GAMES_CONFIG`) é a fonte única do conjunto de `rule_name` por Jogo; `choices=`, views e forms derivam dele. Valores em snake_case inglês (ex. `limit_sequence_count`, `distribution_type`).
- Ausência de linhas = estado default; sem campo `is_customized`. A view de edição nunca deleta ao desmarcar: usa `update_or_create` com `enabled=False` e grava uma linha por regra mostrada. Só "Restaurar padrão" deleta.
- `bet_satisfies_rules(numbers, clovers, game, rules) -> (ok, violated_rule_names)` é função pura em `utils.py`, sem classes/motor de regras, e retorna todas as violadas.
- `generate_bet(game, user)` usa duas queries distintas:
  - `has_customization` = exists() sem filtro de `enabled`, decide o modo.
  - `active_rules` = filtrado por `enabled=True`, alimenta a checagem.
- Loop com `max_attempts=10000`. Ao esgotar, relaxa em memória (nunca grava no banco) a regra de maior `updated_at` entre as violadas pelo último candidato, e roda mais 10000 tentativas.
- `GenerationRule` nunca é lido nem escrito por `jobs.py`/cron, só por views/utils.
- Rota `/regras/<slug:jogo>/` (`regras_geracao_view`, GET pré-carrega, POST salva); slug é o nome do Jogo em lowercase. Views novas ficam em `views.py` (sem pacote `views/`).
- Histórico (`history_view`), filtros por querystring:
  - Jogo: `filter(game=)`.
  - Premiado: `filter(prize__gt=0)`, lendo o cache `GeneratedBet.prize`, sem join com `HitNotification`.
  - Período: `created_at__range`, com limites inclusivos convertidos pra início/fim do dia no `TIME_ZONE`, nunca data naive.
  - Os 3 combinam por AND.
- Identificadores em inglês; UI em pt-BR. Sem dependência nova (Python 3.11, Django 5.0.6).

## UX & Interaction Patterns

- Home: sidebar de resumo (3 stat-cards empilhados, só leitura) + área principal com "jogo selecionado" no topo e seletor logo abaixo. Sem jogo escolhido, mostra prompt leve.
- Seletor: `selectGame()` estendida atualiza a área de jogo selecionado sem reload. Ícones: Mega-Sena `bi-trophy`, +Milionária `bi-flower1`, Lotomania `bi-100`, Lotofácil `bi-lightning`, Quina `bi-star`, Dupla-Sena `bi-stack`.
- Ícone de editar no card leva a `/regras/<jogo>/`:
  - Usa o padrão `.btn-check` (radio escondido + `<label>` só ao redor do conteúdo, nunca cobrindo o ícone de editar).
  - Alvo mínimo de 44×44px.
- Tela de regras: indicador "Usando regras padrão do sistema" ou "Personalizado por você", com botão "Restaurar padrão". Linhas de regra (switch + campo Valor) alternam habilitação por JS; o campo fica visível e usa `disabled` nativo quando desligado.
  - Região `aria-live` anuncia a troca.
  - Texto de ajuda de linha/coluna via `aria-describedby`.
- Filtros do histórico: barra sempre visível, nunca colapsável, com badges removíveis (`<button>` com `aria-label`). Após o reload o foco vai pro heading da barra. Sem resultado: mensagem nomeando o filtro + "Limpar filtros".
- Bolinhas de número: `flex-wrap` com `role="list"`/`listitem`. Dupla-Sena mostra 2 grupos empilhados ("1º sorteio:"/"2º sorteio:"), cada um com `role="group"` e `aria-label`.
- Tom: mensagens diretas, sempre nomeando regra/Jogo/filtro, nunca genéricas.
- Mockups em `_bmad-output/planning-artifacts/ux-designs/ux-Loterias-2026-09-17/mockups/` (o mock do histórico mostra 20 números pra Lotomania; o correto é 50).

## Cross-Story Dependencies

- 4.3 entrega o model, `RULE_NAMES_BY_GAME` e a tela ponta a ponta sem regras concretas. 4.4, 4.6 e 4.7 só adicionam entradas ao dict e campos ao template.
- 4.4 introduz `bet_satisfies_rules()` e o loop de tentativas. 4.6 e 4.7 reusam essa função sem lógica duplicada.
- 4.5 estende o loop de `generate_bet()` da 4.4 com o relax de 1 regra.
- 4.1 e 4.2 compartilham o `home.html`: o ícone e o `selectGame()` da 4.2 alimentam a área de jogo selecionado da 4.1, e o ícone de editar da 4.2 é a porta de entrada da tela da 4.3.
- 4.8 é independente das demais (só `history_view`/`historico.html`).
- Depende dos Epics 1-3 concluídos, incl. Dupla-Sena com 2º sorteio (Epic 2) e o cache `GeneratedBet.prize`.
