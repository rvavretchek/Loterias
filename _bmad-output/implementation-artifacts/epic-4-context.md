# Epic 4 Context: Home Reorganizada, Regras de Geração Personalizadas e Histórico com Filtros

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Gerar um jogo não exige mais scroll (resumo vira sidebar, jogo selecionado sobe pro topo, cada Jogo tem ícone próprio); cada usuário pode personalizar como cada Jogo é gerado pra ele (regras de sequência, linha, coluna e distribuição, por família de Jogo); e o histórico ganha filtros cumulativos com exibição legível mesmo pra Jogos com muitos números. Depende dos Epics 1-3 concluídos. As Stories 4.1 e 4.2 já estão entregues; a Story 2.20 reverteu o bloqueio de jogo duplicado (vários jogos por Jogo+Concurso são permitidos).

## Stories

- Story 4.1: Reorganização da área útil da home (done)
- Story 4.2: Ícone por Jogo no seletor (done)
- Story 4.3: Model GenerationRule e tela de edição de Regras de Geração por Jogo
- Story 4.4: Regras de Geração — Mega-Sena, +Milionária, Quina, Dupla-Sena
- Story 4.5: Resolução de conflito entre Regras de Geração
- Story 4.6: Regras de Geração — Lotofácil
- Story 4.7: Regras de Geração — Lotomania
- Story 4.8: Filtros cumulativos e exibição legível no histórico

## Requirements & Constraints

- A personalização vale só daqui pra frente: jogos já gerados nunca são recalculados nem mudam de números.
- Sem personalização salva, a geração mantém o comportamento adaptativo atual da Regra de Sequência. Depois do primeiro save de um Jogo, só os toggles explícitos valem, inclusive com todos desligados.
- Conflito de regras: nunca deixar o usuário sem gerar. Relaxa no máximo uma regra por chamada; o aviso nomeia a regra e o Jogo, e o jogo é salvo como sucesso, não como erro.
- Valor numérico fora da faixa: erro inline no campo, nomeando a faixa válida. A faixa por regra/Jogo é decisão de produto por story (validada em `forms.py`).
- Histórico: filtros de Jogo, período e só premiados, sempre visíveis e cumulativos (AND). Mensagem de vazio nomeia o que foi filtrado.
- Acessibilidade: ícones decorativos com `aria-hidden`, estado nunca só por cor, elementos interativos nunca aninhados, foco visível preservado (sem `outline: none`), modais Bootstrap com foco gerenciado.
- Tom das mensagens: direto, em pt-BR, sem jargão. Identificadores de código em inglês.

## Technical Decisions

- `GenerationRule` fica em `apps/loterias_core/models.py`: uma linha por (user, game, rule_name), com `enabled`, `numeric_value` (int, nulo), `choice_value` (char, nulo) e `updated_at` (`auto_now`). Tem `unique_together` e `CheckConstraint` de XOR entre os dois valores. Não usa JSONField, porque cada regra precisa de `updated_at` próprio.
- `RULE_NAMES_BY_GAME` (dict ao lado de `GAMES_CONFIG`) é a fonte única do conjunto de `rule_name` por Jogo; `choices=`, views e forms derivam dele.
  - Mega-Sena, +Milionária, Quina e Dupla-Sena: `limit_sequence_count`, `limit_sequence_pairs`, `distribution_type`. Só a Mega-Sena tem também `limit_row_count` e `limit_column_count` (grid 6×10).
  - Lotofácil: as 5 acima (com linha/coluna em grid 5×5) mais `limit_min_gap_between_sequences` e `limit_min_sequences`.
  - Lotomania: só `limit_sequence_count`, `limit_min_gap_between_sequences` e `limit_min_sequences`.
  - Linha/coluna de +Milionária, Quina e Dupla-Sena ficam indisponíveis até o grid oficial ser confirmado.
- `distribution_type` usa `choice_value` `homogenea` ou `totalmente_aleatoria`. Homogênea sorteia um número por faixa de largura igual do intervalo do Jogo.
- `bet_satisfies_rules(numbers, clovers, game, rules) -> (ok, lista_de_rule_name_violadas)` é função pura em `utils.py`, sem classes nem "motor de regras". As Stories 4.6 e 4.7 reusam a mesma função, só acrescentando entradas no dict.
- `generate_bet(game, user)` usa duas queries distintas:
  - `has_customization`: `filter(user, game).exists()`, sem filtro de `enabled`, decide o modo.
  - `active_rules`: `filter(..., enabled=True)`, alimenta a checagem.
- Loop de tentativas: `max_attempts=10000`. Ao esgotar, relaxa em memória (nunca grava no banco) a regra de maior `updated_at` entre as violadas pelo último candidato, e roda mais 10000 tentativas. Se falhar de novo, cai na mensagem existente "Não foi possível gerar um jogo único".
- Salvar o formulário faz `update_or_create` de uma linha por `rule_name` mostrado (ligadas e desligadas), nunca `DELETE` ao desmarcar. Só "Restaurar padrão" apaga linhas do (user, game).
- `GenerationRule` é lido e escrito só pelo processo web, nunca por `jobs.py`/cron. Nenhuma dependência nova.
- Filtros do histórico são `.filter()` encadeados em `GeneratedBet`, sem join novo:
  - Jogo: `game=`.
  - Premiado: `prize__gt=0`, lendo o campo-cache, sem reconsultar `HitNotification`.
  - Período: `created_at__range`, limites inclusivos convertidos pro início e fim do dia no `TIME_ZONE` do projeto (nunca data naive). É a data de geração, não a de captura do resultado.
- Novos: `regras_geracao_view` e a rota `regras/<slug:jogo>/` (slug = nome do Jogo em lowercase, sem tabela de mapeamento) em `apps/loterias_core/views.py`/`urls.py`; template `regras_geracao.html`; `history_view` estendida. A migration só cria a tabela.

## UX & Interaction Patterns

- Cada Jogo tem uma URL própria de regras, alcançada por um ícone de editar no card do seletor. Esse ícone não pode ficar dentro do `<label>` do radio (padrão `.btn-check`) e precisa de pelo menos 44×44px de área clicável.
- Linha do formulário de regra (`rule-toggle-row`): label + switch SIM/NÃO + campo Valor. O switch habilita/desabilita o campo via JS, sem reload; o campo nunca some, usa o atributo `disabled` nativo e mantém estilo de desabilitado. Uma região `aria-live="polite"` anuncia a troca.
- Só aparecem campos que se aplicam ao Jogo. O texto de ajuda de linha/coluna (layout do volante oficial) é ligado ao campo via `aria-describedby`.
- Indicador no topo da tela: "Usando regras padrão do sistema" ou "Personalizado por você". Botão "Restaurar padrão" só quando personalizado.
- Modal Bootstrap de confirmação ao salvar sem nenhuma proteção de sequência ativa (foco preso, volta ao botão Salvar, fecha com Esc).
- Aviso de regra relaxada usa cor de warning e aparece junto da confirmação de sucesso.
- Barra de filtros do histórico: `.form-select` de Jogo, dois `<input type="date">`, checkbox de premiados. Estado na querystring (GET, sem AJAX). Badges removíveis são `<button>` reais com `aria-label`, e o foco pós-reload vai pro heading da barra.
- Números no histórico: bolinhas com `flex-wrap` e `role="list"`/`listitem`. Dupla-Sena mostra "1º sorteio:" e "2º sorteio:" empilhados, cada um num `role="group"` com `aria-label`.
- Bootstrap 5.3.2 + Bootstrap Icons, tema claro/escuro em todo componente novo. Mockups de referência estão em `ux-designs/ux-Loterias-2026-09-17/mockups/`. O mock do histórico mostra 20 bolinhas na Lotomania; o correto é 50.

## Cross-Story Dependencies

- A Story 4.3 entrega o model, a tela e o fluxo ponta a ponta sem nenhuma regra concreta; as Stories 4.4, 4.6 e 4.7 só adicionam entradas em `RULE_NAMES_BY_GAME` e campos no template.
- A Story 4.4 introduz `bet_satisfies_rules` e o loop de tentativas; as Stories 4.5, 4.6 e 4.7 dependem dela. A 4.5 estende o loop com o relax de uma regra.
- A Story 4.8 é independente da geração de regras e só depende do `history_view` existente e do campo `GeneratedBet.prize`.
- A Story 2.20 permite vários jogos por Jogo+Concurso, então o filtro e a geração não devem assumir unicidade.
