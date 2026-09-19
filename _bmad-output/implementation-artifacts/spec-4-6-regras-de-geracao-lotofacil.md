---
title: 'Story 4.6 — Regras de Geração da Lotofácil (espaço mínimo, mínimo de sequências, Homogênea)'
type: 'feature'
created: '2026-09-19'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'b7cbee2cef554c46d7b65ec75c472fd794ae603d'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Na Lotofácil, `limit_min_gap_between_sequences` e `limit_min_sequences` são salvas mas ignoradas na geração, e a Distribuição Homogênea é no-op (15 de 25 não cabe em "1 número por faixa") — FR-20, AD-12.

**Approach:** Em `apps/loterias_core/utils.py`, `bet_satisfies_rules` passa a checar as duas regras, sem lógica duplicada (mesma função das demais). Sequência = run de 2+ consecutivos. **Espaço mínimo** = quantidade de números fora do jogo entre o fim de uma sequência e o início da próxima; toda dupla de sequências vizinhas precisa ter ≥ valor (com 0 ou 1 sequência a regra é satisfeita). **Mínimo de sequências** = o jogo precisa ter ≥ valor sequências. **Homogênea na Lotofácil** = volante dividido em faixas de uma linha do grid (5 faixas de 5), com exatamente `bets_count // faixas` números (3) em cada; nos demais Jogos segue "1 número por faixa". Relaxamento da 4.5 e demais regras inalteradas.

</frozen-after-approval>

## Implementation Notes

- `utils.py`: `_distribution_bands(config, game)` agora devolve `(início, fim, quota)` (Lotofácil = 5 faixas-linha de 5, quota 3); novo `_sequence_spans`; `bet_satisfies_rules` checa `limit_min_sequences` e `limit_min_gap_between_sequences` na mesma função; `_random_numbers` sorteia a quota por faixa. Suíte: 329 testes OK.
- Decisões (visíveis ao usuário): espaço mínimo = nº de números fora do jogo entre sequências vizinhas; Homogênea na Lotofácil = 3 por linha do volante.
- Sem viesamento do gerador: sorteio uniforme de 15/25 produz sequências com folga; caso extremo cai no relaxamento da 4.5.
- Revisão: autorrevisão (mudança pequena, sem subagentes). Achado: teste antigo tratava `min_*` como ignoradas — atualizado.
