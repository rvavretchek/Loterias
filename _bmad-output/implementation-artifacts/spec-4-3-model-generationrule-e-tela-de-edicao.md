---
title: 'Story 4.3 — Model GenerationRule e tela de edição de Regras de Geração'
type: 'feature'
created: '2026-09-18'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '8affc7beb7d6d45686a26fac5e65ceb9e2952b92'
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md', '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-17/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Não existe onde o usuário personalize como cada Jogo é gerado pra ele (FR-18, FR-23, UX-DR3/8/9, AD-11/AD-13).

**Approach:** Novo model `GenerationRule` + migration, `RULE_NAMES_BY_GAME` (fonte única) e tela `/regras/<jogo>/` (`regras_geracao_view`) com formulário liga/desliga + Valor por regra, indicador default/personalizado, "Restaurar padrão" e link "editar" por Jogo na home. A geração de jogo (`generate_bet`) **não** muda nesta story — passa a honrar as regras na 4.4.

## Boundaries & Constraints

**Always:** `GenerationRule(user, game, rule_name, enabled, numeric_value, choice_value, updated_at)`, `unique_together (user, game, rule_name)`, `CheckConstraint` "nunca `numeric_value` e `choice_value` ambos preenchidos" (a versão XOR do AD-11 impediria linha desligada sem valor; AD-11 é atualizado). `RULE_NAMES_BY_GAME` em `models.py` ao lado de `GAMES_CONFIG` e nenhum outro lugar hardcoda nomes de regra. Salvar nunca deleta linha: `update_or_create` de uma linha por regra do Jogo (ligada ou desligada); desligada preserva o valor salvo. Único caminho de DELETE: "Restaurar padrão" (todas as linhas de user+game). Campo Valor desabilitado (nunca `display:none`) com região `aria-live`; texto de ajuda de linha/coluna via `aria-describedby`; modal Bootstrap (foco gerenciado) ao salvar deixando um Jogo de `GAMES_WITH_SEQUENCE_RULE` sem nenhuma regra de sequência ligada. Toda view exige login; só o próprio usuário lê/escreve suas linhas.

**Never:** mexer em `generate_bet`/`jobs.py`; avaliar regras (4.4); aplicar faixas de valor de negócio (PRD §8.6 — só inteiro ≥1 e ≤ `numbers_count` do Jogo); expor `limit_row_count`/`limit_column_count` pra +Milionária/Quina/Dupla-Sena (grid não confirmado, PRD §8.5).

**Decisões do plano (mudam o que você vê):** (1) `RULE_NAMES_BY_GAME` já nasce completo (5/5/5/5+7/3 regras conforme Capability Map do spine) e a tela mostra todos os campos de cada Jogo já agora — 4.4/4.6/4.7 só implementam a checagem. (2) Como `generate_bet` não muda, regras salvas **ainda não têm efeito** na geração e a Regra de Sequência adaptativa segue valendo até a 4.4 (o AC da 4.3 "adaptativa deixa de ser consultada após salvar" passa a ser entregue na 4.4, junto da geração).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Primeira visita | GET jogo sem linhas | "Usando regras padrão do sistema", toggles NÃO, Valor visível desabilitado | N/A |
| Salvar | POST com regra ligada + valor válido | uma linha por regra do Jogo gravada; "Personalizado por você" | N/A |
| Desmarcar | POST sem o toggle de regra já salva | linha atualizada `enabled=False`, valor preservado, nunca deletada | N/A |
| Valor inválido | ligada com valor vazio/0/> `numbers_count`/não inteiro | nada gravado, página reexibida com erro no campo | mensagem nomeando a faixa |
| Restaurar padrão | POST `restaurar` | apaga só as linhas de user+game; volta ao default | N/A |
| Jogo inexistente / anônimo | `/regras/xpto/` / sem login | 404 / redirect ao login | N/A |
| Sem proteção de sequência | Jogo com regra adaptativa, salvar tudo de sequência desligado | modal de confirmação antes de enviar | cancelar não envia |

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py` -- `GAMES_CONFIG`/`GAMES_WITH_SEQUENCE_RULE`; acrescentar `RULE_DEFINITIONS`, `RULE_NAMES_BY_GAME`, `GenerationRule` (+ migration `0007`).
- `apps/loterias_core/views.py`, `urls.py` -- `regras_geracao_view`, `path('regras/<slug:jogo>/', name='generation_rules')`; padrão `messages`/`login_required` das views vizinhas.
- `templates/loterias_core/regras_geracao.html` (novo) -- estende `base/base.html`; mock `ux-designs/.../mockups/regras-geracao.html`.
- `templates/loterias_core/home.html` -- link "editar" por Jogo, irmão do `<label>` (não dentro), alvo ≥44×44, sem disparar seleção.
- `apps/loterias_core/tests.py` -- novas classes de teste; `_bmad-output/.../ARCHITECTURE-SPINE.md` AD-11 -- ajustar constraint.

## Tasks & Acceptance

**Execution:**
- [x] `apps/loterias_core/models.py` -- `RULE_DEFINITIONS`/`RULE_NAMES_BY_GAME`/`GenerationRule` + `clean()` validando `rule_name` do Jogo -- fonte única
- [x] `apps/loterias_core/migrations/0007_generationrule.py` -- gerar com `makemigrations` -- tabela nova aditiva
- [x] `apps/loterias_core/views.py`, `urls.py` -- view GET/POST (salvar/restaurar), slug→Jogo, validação de Valor
- [x] `templates/loterias_core/regras_geracao.html` -- formulário, indicador, aria-live, ajuda linha/coluna, modais (sequência e restaurar)
- [x] `templates/loterias_core/home.html` -- link "editar" por card
- [x] `apps/loterias_core/tests.py` -- model, view (matriz acima), isolamento entre usuários, `RULE_NAMES_BY_GAME` × `GAMES_CONFIG`, links da home
- [x] spine AD-11 -- trocar XOR por "nunca ambos"

**Acceptance Criteria:**
- Given um usuário sem linhas, when abre `/regras/mega-sena/`, then vê o indicador de default e os campos da Mega-Sena com Valor desabilitado.
- Given ele liga uma regra e salva, when reabre, then vê "Personalizado por você" e o valor salvo; desmarcar e salvar mantém a linha com `enabled=False`.
- Given "Restaurar padrão", when confirmado, then as linhas de user+game somem e outros Jogos/usuários ficam intactos.

## Implementation Notes

_(preenchido durante a implementação)_

- Implementação via subagente; suíte completa 352+ testes OK, `makemigrations --check` sem pendências. Arquivos: `models.py` (+`0007_generationrule.py`), `views.py`, `urls.py`, `regras_geracao.html`, `home.html` (link "editar" por card), `tests.py`, AD-11 do spine (constraint "nunca ambos").
- Contagem real de regras (segue o Capability Map e o "Never", não a frase "5/5/5/5+7/3" da decisão 1): Mega-Sena 5; +Milionária/Quina/Dupla-Sena 3 cada; Lotofácil 7; Lotomania 3.
- Rótulos de `limit_min_gap_between_sequences` ("Distância mínima entre sequências") e `limit_min_sequences` ("Quantidade mínima de sequências") são redação do implementador.
- A mensagem de sucesso não promete "vale no próximo jogo" (regras só têm efeito na geração a partir da Story 4.4).
- JS (switch habilita/desabilita, modais) não verificado em navegador — só HTML renderizado nos testes.

## Review Triage Log

- `int()` de string de dígitos gigante levantava `ValueError` (500) na validação: **medium, corrigido** (`[0-9]{1,6}` + teste).
- Salvamento não atômico (`update_or_create` em laço): **medium, corrigido** (`transaction.atomic()`).
- Atributo `disabled` do campo Valor não assertado em nenhum teste (gap): **medium, corrigido** (testes de first visit e de regra ligada).
- Modal "Restaurar padrão" só verificado por ausência; valores digitados preservados em POST inválido sem teste: **low/medium, corrigido** (novos testes).
- Modal de sequência só no cliente / sem JS burla: **low, rejeitado** — a spec define confirmação via modal Bootstrap; enforcement server-side exigiria novo fluxo de POST.
- Linhas órfãs de `rule_name` removido de `RULE_NAMES_BY_GAME`: **low, rejeitado** — hipotético, sem caminho que o produza hoje.
- Máximo `numbers_count` genérico pra todas as regras / consistência entre regras (pairs × count, gap × min): **false** (previsto) — faixas por regra são PRD §8.6 (adiado) e conflitos são resolvidos por FR-22 na geração.
- `clean()` sem checar `kind`/choice válida; `clean()` não chamado no save: **low, rejeitado** — a view é o único caminho de escrita (AD-13) e valida antes; sem admin registrado.
- Slug/`key|lower` duplicado, acentos em strings, `--text-muted`, foco no primeiro erro, `aria-describedby` no toggle: **low, rejeitado** — cosméticos/consistentes com o app; refeitos na migração pro design system.
- "Modal devolve foco ao Salvar em vez do switch": **false** — a spec manda devolver ao botão "Salvar".
- Migration com `choices` fixos: **false** — comportamento normal do Django.
