# Addendum — Loterias PRD

Conteúdo técnico/de implementação que não pertence ao corpo do PRD (capacidades, não implementação), mas que veio junto do input do usuário e merece registro pra quem for desenhar a arquitetura.

## Adendo 2026-09-17 — Regras de Geração Personalizadas (FR-18 a FR-23)

**Ponto de integração no código:** o pedido original do Boss (`_bmad-output/planning-artifacts/brief-layout-e-regras-personalizadas-2026-09-17.md`) nomeia explicitamente `generate_bet()` (`apps/loterias_core/utils.py`) como a função que precisa ser reescrita pra ler e aplicar as novas Regras de Geração (`GenerationRule`, §3 do PRD) em vez de só a regra fixa hoje hardcoded (`GAMES_WITH_SEQUENCE_RULE`/`MIN_SEQUENCE_INTERVAL`/`count_sequential_pairs()`). O PRD (§4.4) descreve o comportamento observável esperado (FR-19 a FR-23) sem nomear a função — fica registrado aqui como o ponto de entrada real pra arquitetura partir dele.

**Padrão de retry já existente reaproveitável:** `regenerate_bet_view` (`apps/loterias_core/views.py`) já implementa um loop de tentativas (`max_attempts = 1000`) pra gerar um jogo que não colida com um duplicate-check. FR-22 (resolução de conflito entre Regras de Geração) pode reaproveitar o mesmo padrão em vez de inventar um novo mecanismo de retry.

**Model novo sugerido:** `GenerationRule`, único por (`user`, `game`) — mesmo padrão de unicidade já usado por `NotificationPreference` (único por `user`) e `LotteryResult` (único por `game`+`contest`). Os campos concretos (liga/desliga + valor por regra, tipo de distribuição) variam por família de Jogo (FR-19/FR-20/FR-21 descrevem 3 conjuntos diferentes) — decisão de arquitetura se isso é um único model com campos nulos por família, um JSON schema-less por Jogo, ou 3 models separados.
