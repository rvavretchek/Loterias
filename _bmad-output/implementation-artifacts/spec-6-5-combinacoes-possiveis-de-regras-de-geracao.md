---
title: 'Story 6.5 — Todas as combinações possíveis de Regras de Geração'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A cobertura hoje testa no máximo 2 regras ligadas ao mesmo tempo; nunca testou TODAS as combinações de quais regras ficam ligadas por Jogo (o eixo combinatório real e tratável — 2^n subconjuntos de regras, não o produto cartesiano de valores).

**Approach:** Teste novo que, pra cada Jogo, gera um jogo pra CADA subconjunto possível de regras ligadas (todas as 2^n combinações do universo de regras daquele Jogo), com um valor moderado e realista por regra, e confere que o resultado satisfaz todas as regras ligadas ou relaxa exatamente 1.

</frozen-after-approval>

## Implementation Notes

- `AllPossibleRuleCombinationsTests`: pra cada um dos 6 Jogos, itera as 2^n combinações de `RULE_NAMES_BY_GAME[game]` (32 pra Mega-Sena/+Milionária/Quina/Dupla-Sena, 128 pra Lotofácil, 8 pra Lotomania -- 264 combinações no total), com um valor moderado fixo por regra (`MODERATE_VALUE`). Pra cada combinação: se `generate_bet_with_relaxation` devolve `None`, aceita como comportamento definido (AD-12, combinação apertada demais pro orçamento de tentativas); se devolve jogo, confere que satisfaz todas as regras ligadas, ou que relaxou exatamente 1 (e que essa 1 pertence ao combo) e o resto continua satisfeito.
- Achado real durante a implementação: `limit_row_count`/`limit_column_count = 3` combinado com regras de sequência é genuinamente quase impossível pra Lotofácil por sorteio uniforme (15 de 25, grid 5×5 -- 3 por linha já é a média exata, então o limite é apertadíssimo) mesmo relaxando 1 regra -- não é bug, ficou documentado no teste como saída aceita, não forçado a sempre gerar.
- Custo: essa suíte de combinações sozinha roda em ~30s (a suíte inteira foi de ~45s pra ~86s). Aceito -- é o preço de testar a combinatória real em vez de um punhado de casos escolhidos a dedo.
- Suíte: 431 testes OK (430 + 1 novo, que cobre 264 combinações).
