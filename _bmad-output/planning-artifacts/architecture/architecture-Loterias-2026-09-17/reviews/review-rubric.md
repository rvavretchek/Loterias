---
name: 'Revisão de rubrica (good-spine checklist) — Architecture Spine (adendo 2026-09-17)'
type: review
altitude: epic
target: '_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md'
method: 'checklist walk, feito inline pelo parent (subagente falhou por rate limit de sessão) DEPOIS de aplicar os achados da revisão adversarial e web-verification'
created: '2026-09-17'
---

# Revisão de rubrica — Architecture Spine (adendo 2026-09-17)

*Nota de processo: o subagente da rubric walker falhou por rate limit da sessão antes de escrever este arquivo. Esta revisão foi refeita inline pelo parent, sobre a versão do spine já corrigida pelos achados críticos da revisão adversarial (F1-F8) e da web-verification — não é uma revisão "antes dos fixes", é a checagem final.*

## Veredito geral

Spine sólido depois das correções. Os 3 achados críticos e 2 altos da revisão adversarial (assinatura de `bet_satisfies_rules`, caminho de escrita upsert-never-delete, duas queries distintas, listas de `rule_name` fechadas) foram todos fechados diretamente no texto dos ADs, não só anotados. Cobre as 9 FRs do escopo (FR-16 a FR-24) sem lacuna. Um erro de auto-correção (removi `distribution_type` de Lotofácil por engano ao aplicar o achado F5, contradizendo o PRD FR-20) foi pego e corrigido antes deste review final.

## 1. Fixa os divergence points reais pro nível abaixo (stories) — forte

`RULE_NAMES_BY_GAME` como fonte única (AD-11) fecha exatamente o tipo de "dois builders hardcodando conjuntos diferentes" que a Capability Map sozinha não fechava antes da revisão adversarial. AD-12's duas queries nomeadas (`has_customization`/`active_rules`) fecham a ambiguidade que permitiria um builder desligar um toggle sem efeito real na geração. Nenhum achado novo.

## 2. Toda Rule de AD é enforceable e previne a divergência declarada — forte

`CheckConstraint` (AD-11) é enforcement de banco, não só prosa — item que a revisão adversarial (F6) pediu explicitamente e que agora está no texto. AD-13's "nunca deleta, só `enabled=False`" é uma regra de código verificável em review (não uma convenção implícita). Sem achados novos.

## 3. Nada em Deferred permite divergência incompatível — adequado

O item de Deferred sobre o grid não confirmado (Quina/+Milionária/Dupla-Sena) **não** deixa a porta aberta pra divergência, porque a Capability Map já faz o carve-out explícito (essas 3 simplesmente não têm `limit_row_count`/`limit_column_count` no `RULE_NAMES_BY_GAME` até resolver) — a Deferred registra o *porquê*, a Rule em si já fecha o comportamento. §8.6 (faixa de valores) é legitimamente adiável — `numeric_value` sendo um `IntegerField` genérico não cria inconsistência entre builders, só falta a validação de negócio (forms.py), que é per-story por natureza.

## 4. Tecnologia nomeada é verificada-atual — forte

Nenhuma dependência nova (confirmado pela revisão de web-verification). O único claim técnico que precisou de correção (JSONField "sem precedente") já foi corrigido com a contagem real (7 campos) e a razão real (timestamp por linha) no lugar da alegação falsa.

## 5. Ratifica o código brownfield em vez de contradizer — forte

Spot-checks confirmados nesta sessão: `max_attempts=10000` em `generate_bet()` (não 1000 — corrigido depois do achado da web-verification), `JSONField` em 7 campos reais (`grep` direto no `models.py`), `views.py` sem pacote `views/` (convenção real). Nenhuma alegação não verificada permanece no texto final.

## 6. Cobre as capacidades do PRD que dirigiu o spine — forte

Todas as 9 FRs do `binds` (FR-16 a FR-24) têm linha na Capability Map. UJ-3 (José) está coberta indiretamente via FR-18/22/23 (a UJ em si é um artefato do PRD/UX, não repetida aqui).

## 7. Nenhum AD novo enfraquece/contradiz um AD herdado — forte

AD-11/12/13/14 reforçam os ADs herdados (AD-3, AD-4, AD-7, AD-9) em vez de tensioná-los — checado explicitamente na tabela de Inherited Invariants, com a coluna "Binds here" nomeando a ligação concreta pra cada um, não só citando o ID.

## 8. Toda dimensão que esta altitude possui está decidida, adiada ou é pergunta aberta — adequado

O envelope operacional/de deploy é tratado explicitamente como "sem mudança" na seção Stack (não fica em silêncio) — correto, já que este adendo não adiciona serviço/dependência/container novo. Único ponto de atenção: a seção Stack é uma frase só ("sem mudança"); pra um spine desta escala isso é proporcional, mas registro aqui que se um reviewer mais rigoroso quisesse, poderia pedir uma frase confirmando explicitamente "nenhuma migration de dados além de `CREATE TABLE GenerationRule`" — baixo valor de adicionar agora, não bloqueia.

## Achados

Nenhum achado novo além do que já foi identificado e corrigido pelas revisões adversarial e de web-verification (ver `reviews/review-adversarial.md` e `reviews/review-web-verification.md`) — este pass é confirmatório.

## Notas mecânicas

- `lint_spine.py` roda limpo (0 findings) na versão final.
- IDs de AD contíguos com o spine pai: AD-11 a AD-14 (pai termina em AD-10) — sem colisão, sem lacuna.
