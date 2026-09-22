# Epic 4 Context: Home Reorganizada, Regras de Geração Personalizadas e Histórico com Filtros

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Gerar um jogo não exige mais scroll (resumo vira sidebar, jogo selecionado sobe pro topo, cada Jogo com ícone próprio); cada usuário pode personalizar como cada Jogo é gerado pra ele (regras de sequência, linha, coluna e distribuição, por família de Jogo, com resolução de conflito); e o histórico ganha filtros cumulativos com exibição legível mesmo pra Jogos com muitos números. Depende dos Epics 1-3 concluídos. Stories 4.1-4.3 já entregues (home, ícones, model `GenerationRule` + tela `/regras/<jogo>/`); restam 4.4-4.8.

## Stories

- Story 4.1: Reorganização da área útil da home (done)
- Story 4.2: Ícone por Jogo no seletor (done)
- Story 4.3: Model GenerationRule e tela de edição de Regras de Geração por Jogo (done)
- Story 4.4: Regras de Geração — Mega-Sena, +Milionária, Quina, Dupla-Sena
- Story 4.5: Resolução de conflito entre Regras de Geração
- Story 4.6: Regras de Geração — Lotofácil
- Story 4.7: Regras de Geração — Lotomania
- Story 4.8: Filtros cumulativos e exibição legível no histórico

## Requirements & Constraints

- Regras por família de Jogo, cada uma com liga/desliga + valor: limite de números em sequência, limite de sequências no jogo, limite por linha e por coluna do volante; mais Tipo de distribuição (Homogênea = um número por faixa de largura igual do intervalo; Totalmente Aleatória = sorteio uniforme de hoje).
- Mega-Sena, +Milionária, Quina e Dupla-Sena: as mesmas 5 regras. Lotofácil: 7 (as 5 + espaço mínimo entre sequências + quantidade mínima de sequências). Lotomania: só 3 (sequência, espaço mínimo, quantidade mínima), sem linha/coluna/distribuição.
- Grids dos volantes (linha/coluna) confirmados: Mega-Sena 6x10, +Milionária 5x10, Quina 8x10, Dupla-Sena 5x10, Lotofácil 5x5; já em `GAME_GRID`. Texto de ajuda de linha/coluna explica o layout do volante oficial.
- Sem personalização salva, a geração mantém a Regra de Sequência adaptativa atual; após o primeiro save de um Jogo, só os toggles explícitos valem (mesmo com todos desligados). "Restaurar padrão" é o único caminho que apaga linhas.
- Conflito: se as regras ativas são inviáveis em 10000 tentativas, relaxa no máximo 1 regra (a de maior `updated_at` entre as violadas no último candidato), só em memória; se ainda falhar, cai na mensagem existente "Não foi possível gerar um jogo único". Regra relaxada gera mensagem de aviso nomeando regra e Jogo; o jogo salva como sucesso.
- Valor fora da faixa: erro inline no campo nomeando a faixa válida (faixa por regra/Jogo ainda é decisão do Boss por story, validada em `forms.py`). Desligar a última proteção de sequência exige confirmação em modal.
- Histórico: filtros Jogo, período e só premiados, cumulativos (AND), sempre visíveis, refletidos na querystring; badges removíveis; mensagem de vazio nomeando o filtro + "Limpar filtros"; bolinhas com quebra de linha; Dupla-Sena com 2 sorteios empilhados e rotulados.

## Technical Decisions

- `GenerationRule(user, game, rule_name, enabled, numeric_value, choice_value, updated_at)`, `unique_together` user+game+rule_name; `CheckConstraint` impede numeric_value e choice_value preenchidos juntos (ambos nulos é válido). `choice_value` só pra `distribution_type` (`'homogenea'`/`'totalmente_aleatoria'`).
- `RULE_NAMES_BY_GAME` em `models.py` é a fonte única dos `rule_name` válidos por Jogo; nenhuma outra parte hardcoda o conjunto. Nomes: `limit_sequence_count`, `limit_sequence_pairs`, `limit_row_count`, `limit_column_count`, `distribution_type`, `limit_min_gap_between_sequences`, `limit_min_sequences`. Novas stories só adicionam entradas ali e campos no template.
- `bet_satisfies_rules(numbers, clovers, game, rules) -> (ok, violated_rule_names)` em `utils.py`: função pura, retorna a lista completa de violações; sem classes/motor de regras. Reusada por todas as famílias (sem lógica duplicada).
- `generate_bet(game, user)` usa duas queries distintas: `has_customization` (sem filtro de `enabled`, decide o modo) e `active_rules` (`enabled=True`, alimenta a checagem).
- `GenerationRule` só é lido/escrito pelo processo web (views/utils), nunca por `jobs.py`. Escrita só pela tela de edição, sempre `update_or_create`.
- Filtros de histórico: `filter(game=)`, `filter(prize__gt=0)` (campo-cache, sem join em HitNotification), `filter(created_at__range=)` pela data de geração, limites inclusivos início/fim do dia no `TIME_ZONE` do projeto (nunca data naive).
- Identificadores em inglês; views novas ficam em `apps/loterias_core/views.py`; sem dependência nova.

## UX & Interaction Patterns

- `rule-toggle-row`: switch habilita/desabilita o campo Valor via JS sem reload; campo nunca some, usa `disabled` nativo, com região `aria-live="polite"` anunciando a troca.
- Texto de ajuda de linha/coluna ligado ao campo via `aria-describedby`. Formulário mostra só campos aplicáveis ao Jogo.
- Indicador "Usando regras padrão do sistema" / "Personalizado por você"; salvar vale só pra jogos futuros.
- Mensagem de regra relaxada em tom de aviso (warning, não erro), direta, nomeando regra e Jogo.
- Modal Bootstrap nativo (foco preso, Esc, retorno ao botão Salvar) na confirmação de desligar sequência.
- Filtros: GET puro, sem AJAX; badges são `<button>` com `aria-label` de ação; foco pós-reload no heading da barra de filtros. Bolinhas com `role="list"/"listitem"`; sorteios da Dupla-Sena em `role="group"` com `aria-label`.
- Temas claro/escuro devem funcionar em todo componente novo. Mockups de referência em `ux-designs/ux-Loterias-2026-09-17/mockups/`.

## Cross-Story Dependencies

- 4.4 é a base: implementa `bet_satisfies_rules` e o loop de geração com regras ativas; 4.5, 4.6 e 4.7 dependem dela (4.6/4.7 só acrescentam entradas em `RULE_NAMES_BY_GAME` e campos de template, reusando a mesma checagem).
- 4.5 estende o loop de retry de `generate_bet()` da 4.4.
- 4.4-4.7 constroem sobre o model e a tela de edição da 4.3 (já entregues, incluindo `GAME_GRID`).
- 4.8 é independente das demais (só `history_view`/`historico.html`).
- Filtro "premiado" depende do campo-cache `GeneratedBet.prize` mantido pelas rotinas do Epic 2.
