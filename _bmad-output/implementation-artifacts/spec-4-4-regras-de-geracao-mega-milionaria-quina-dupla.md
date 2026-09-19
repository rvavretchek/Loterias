---
title: 'Story 4.4 — Regras de Geração (Mega-Sena, +Milionária, Quina, Dupla-Sena) e geração respeitando-as'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '70a7714f085b10bcb863b27e8088c30d8e9ab725'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md', '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** As Regras de Geração salvas na tela da Story 4.3 ainda não têm efeito: `generate_bet` só conhece a Regra de Sequência adaptativa (FR-19, FR-23, AD-12, AD-13, NFR-6).

**Approach:** Em `apps/loterias_core/utils.py`, nova função pura `bet_satisfies_rules(numbers, clovers, game, rules) -> (bool, list[str])` e `generate_bet` passa a decidir o modo por `has_customization` (existe linha `GenerationRule` do user+game, sem filtrar `enabled`): `False` = comportamento de hoje; `True` = só as `active_rules` (`enabled=True`) valem e a Regra de Sequência adaptativa deixa de ser consultada. Mesmo laço `max_attempts=10000`. Sem relaxamento (Story 4.5).

## Boundaries & Constraints

**Always:** `bet_satisfies_rules` é pura (sem I/O), devolve a lista **completa** de `rule_name` violadas e ignora com segurança regra desligada, sem valor ou ainda não suportada (`limit_min_gap_between_sequences`, `limit_min_sequences` — Stories 4.6/4.7). Volante por `GAME_GRID` (Mega-sena 6×10, Milionaria 5×10, Quina 8×10, Dupla-Sena 5×10): linha = `(n-1)//cols + 1`, coluna = `(n-1)%cols + 1`. Usuário anônimo/`user=None` = modo default. `create_bet_view`, `regenerate_bet_view` e `api_create_bet_view` usam `generate_bet` e ganham as regras sem mudar de contrato; o modo default não muda nada.

**Never:** relaxar regra (4.5); mexer em Lotofácil/Lotomania além de não quebrar; alterar `GenerationRule`, a tela de edição ou o PRD; devolver silenciosamente um jogo que viola regra personalizada.

**Decisões do plano (mudam o que você vê):** (1) "Limita quantidade de números em sequência" (`limit_sequence_count`) = **tamanho máximo de uma sequência** (run de números consecutivos); valor 1 = nenhum par consecutivo. (2) "Limita quantidade de sequências num jogo" (`limit_sequence_pairs`) = **máximo de sequências** (runs de 2+ consecutivos) no jogo. (3) Linha/coluna = máximo de números na mesma linha/coluna do volante. (4) Homogênea = 1 número por faixa de largura igual (`numbers_count` dividido em `bets_count` faixas; a última absorve o resto); Totalmente Aleatória = sorteio uniforme de hoje. (5) Se, com as regras personalizadas, nenhum jogo válido sai em 10000 tentativas, `generate_bet` devolve `(None, None)` e as telas mostram o aviso já existente "não foi possível gerar" (a 4.5 troca isso por relaxamento); a API responde 422. (6) A mensagem de sucesso da tela de regras volta a dizer "Valem a partir do próximo jogo gerado".

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default | sem linhas `GenerationRule` | igual a hoje (adaptativa) | N/A |
| Personalizado | ≥1 linha, adaptativa ignorada | jogo satisfaz todas as regras ligadas | N/A |
| Tudo desligado | linhas todas `enabled=False` | sorteio livre, sem regra de sequência | N/A |
| Sequência | `limit_sequence_count=1` / `limit_sequence_pairs=0`... valor ≥1 | run máx ≤ valor / nº de runs ≤ valor | N/A |
| Linha/coluna | `limit_row_count`/`limit_column_count` | máx por linha/coluna ≤ valor | N/A |
| Distribuição | `homogenea` / `totalmente_aleatoria` | 1 por faixa / uniforme | N/A |
| Impossível | regras inatingíveis | `(None, None)` | telas: aviso; API 422 |
| Regra não suportada/sem valor | `min_gap`, valor `None` | ignorada | N/A |

</frozen-after-approval>

## Code Map

- `apps/loterias_core/utils.py` -- `generate_bet` (laço 10000, sequência adaptativa), `count_sequential_pairs`, `recent_bets_had_sequence`; adicionar `bet_satisfies_rules` e helpers de runs/linha/coluna/faixas.
- `apps/loterias_core/models.py` -- `GenerationRule`, `GAME_GRID`, `RULE_NAMES_BY_GAME` (só ler).
- `apps/loterias_core/views.py` -- `create_bet_view`/`regenerate_bet_view` (já tratam jogo nulo com aviso), `api_create_bet_view` (hoje quebra com `None`: tratar → 422), mensagem de `regras_geracao_view`.
- `apps/loterias_core/tests.py` -- testes de `generate_bet` existentes (não podem quebrar) e novos.

## Tasks & Acceptance

**Execution:**
- [x] `apps/loterias_core/utils.py` -- `bet_satisfies_rules` + `generate_bet` com `has_customization`/`active_rules` e geração homogênea
- [x] `apps/loterias_core/views.py` -- `api_create_bet_view` trata `(None, None)` (422); mensagem de sucesso da tela de regras
- [x] `apps/loterias_core/tests.py` -- função pura (cada regra, lista completa de violações, ignoradas), `generate_bet` nos modos default/personalizado/tudo desligado/impossível, homogênea, views e API

**Acceptance Criteria:**
- Given regras ligadas pra um Jogo, when gera jogos várias vezes, then todos satisfazem as regras.
- Given o usuário salvou regras (mesmo todas desligadas), when gera, then a Regra de Sequência adaptativa não é consultada; sem linhas, segue como hoje.
- Given regras impossíveis, when gera, then nenhum jogo inválido é gravado e o usuário vê o aviso.

## Implementation Notes

_(preenchido durante a implementação)_

- Implementação via subagente; suíte completa OK. Arquivos: `utils.py` (`bet_satisfies_rules`, helpers, `generate_bet` com `has_customization`/`active_rules`, geração Homogênea), `views.py` (break em `None`, 422 na API, mensagens), `tests.py`.
- Semântica adotada (aprovada): sequência = tamanho máximo de run; "sequências no jogo" = nº máximo de runs de 2+; linha/coluna via `GAME_GRID`; Homogênea = 1 número por faixa (a última absorve o resto).
- Ajuste da revisão: Homogênea é no-op quando a faixa teria largura < 2 (Lotofácil 15/25) — a semântica dela fica pra Story 4.6.
- Mensagem específica quando as regras do usuário são inatingíveis (create/regenerate/API), em vez de "após muitas tentativas".
- `generate_bet` com `AnonymousUser` no modo default quebra em `recent_bets_had_sequence` — pré-existente e inalcançável (todas as views são `login_required`); não tratado.

## Review Triage Log

- Homogênea degenerada em Lotofácil (faixas de 1 número): **medium, corrigido** (no-op; 4.6 define) + testes pra Milionária/Dupla-Sena.
- Mensagem "após muitas tentativas" enganosa com regras inatingíveis: **medium, corrigido** (mensagens dedicadas + testes do corpo da API/regenerate).
- Testes de homogênea só em Mega-Sena/Quina; regenerate/API sem asserção de mensagem: **medium, corrigido**.
- 10000 iterações por requisição com regras impossíveis (sem pré-checagem de viabilidade): **low, rejeitado** — trabalho em memória (~ms), viabilidade/relaxamento é a Story 4.5.
- `limit_sequence_count`≤0, duplicatas no input, `bets_count`=0, `choice_value` desconhecido: **low, rejeitado** — inalcançáveis (form exige ≥1, config fixa, escolhas validadas).
- `clovers` sem uso em `bet_satisfies_rules`; duas queries em `generate_bet`: **false** — assinatura e duas queries são exigência do AD-12.
- Semântica "pairs" ≠ `count_sequential_pairs`: **low, rejeitado** — nomes vêm do PRD; rótulo da UI ("sequências num jogo") é claro.
- Jogo desconhecido na API devolveria 422: **false** — jogo é validado antes (400).
- `CLAUDE.md` ainda descreve só a regra adaptativa: **defer** (arquivo de contexto de agente).
- Sem teste de `AnonymousUser`: **false** — caminho inalcançável (ver notas).
