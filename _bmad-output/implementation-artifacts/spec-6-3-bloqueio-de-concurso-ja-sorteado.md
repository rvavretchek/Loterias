---
title: 'Story 6.3 — Bloqueio de concurso já sorteado nos 3 pontos de entrada'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Os 3 pontos de entrada (`create_bet_view`, `regenerate_bet_view`, `save_manual_bet_view`) já têm teste do bloqueio de concurso já sorteado, mas com rigor desigual: `regenerate_bet_view` não verifica a mensagem de erro nem que o jogo original ficou intocado (só que a contagem de linhas não mudou) — um bug que trocasse os números da mesma linha em vez de criar uma segunda passaria despercebido.

**Approach:** Igualar o rigor dos 3: cada um verifica a mensagem de erro exata, e `regenerate_bet_view` passa a verificar também que `numbers`/`clovers` do jogo original não mudaram.

</frozen-after-approval>

## Implementation Notes

- Achado real na investigação: os 3 pontos de entrada JÁ tinham teste do bloqueio (`create_bet_view`, `regenerate_bet_view`, `save_manual_bet_view`) -- a suposição no épico ("hoje só parte deles tem") estava desatualizada. O gap real era rigor desigual, não ausência.
- `create_bet_view`/`save_manual_bet_view`: passaram a checar o texto exato da mensagem de erro (antes só checavam o nível `error`, ou nem isso).
- `regenerate_bet_view`: ganhou a checagem que faltava de verdade -- `original_bet.numbers` inalterado após o bloqueio, além da mensagem exata. Sem essa checagem, um bug que trocasse os números da mesma linha em vez de bloquear passaria despercebido (a contagem de `GeneratedBet` continuaria 1 do mesmo jeito).
- Suíte: 428 testes OK (nenhum teste novo, 3 fortalecidos).
