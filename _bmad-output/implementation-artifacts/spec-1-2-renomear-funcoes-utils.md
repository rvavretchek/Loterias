---
title: 'Renomear funções de domínio em utils.py'
type: 'refactor'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '68aa088bdde2d3e072b6a3eb99a5bc6a8c193e4b'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `apps/loterias_core/utils.py` ainda usa nomes de função em português e importa de `models.py` os símbolos antigos (`JogoGerado`, `JOGOS_CONFIG` etc.) que a Story 1.1 já renomeou — hoje o módulo inteiro está com `ImportError` na linha 7, e mesmo depois de corrigir o import, o corpo das funções ainda usa os nomes de campo antigos (`usuario=`, `jogo=`, `.criado_em`, `pares_sequenciais__gt` etc.) contra o model já renomeado.

**Approach:** Renomear as 9 funções de `utils.py` para os nomes em inglês da PRD §3.1, corrigir o import de `models.py` e todo uso interno de campos/constantes pros nomes que a Story 1.1 já fixou, e atualizar as chamadas a essas 9 funções em `apps/loterias_core/tests.py` (import + call sites) — pelo mesmo motivo da Story 1.1: sem isso a suíte quebra no import assim que `views.py`/`admin.py` também forem corrigidos.

## Fronteiras e Restrições

**Sempre:**
- Usar exatamente o mapeamento de nomes já decidido (Code Map) — não inventar nomes alternativos.
- Manter a lógica de cada função idêntica — só nomes de função, o import de `models.py` e os usos internos de campo/constante do model mudam.

**Nunca:**
- Não tocar em `apps/loterias_core/views.py` ou `admin.py` (Story 1.3) — eles continuam quebrados com `ImportError` até lá, sequenciamento esperado, mesma lógica já documentada na Story 1.1.
- Não renomear parâmetros de função nem variáveis locais dentro dos corpos das funções (`usuario`, `jogo_nome`, `numero`, `resultado_jogo`, `pares`, `jogo_slug`, `bloco` etc.) — só os 9 nomes de função do Code Map, seguindo o mesmo precedente já usado na Story 1.1 (que também deixou variáveis locais de teste em português).
- Não renomear as chaves do dict retornado por `fetch_cef_result`/consumido por `calculate_bet_prize` (`'jogo'`, `'concurso'`, `'numeros'`, `'trevos'`, `'premiacoes'`) — não está no mapeamento oficial da PRD §3.1 (que só lista símbolos de função/model), e `views.py` (Story 1.3) já vai precisar remapear esse dict de qualquer forma por causa dos campos renomeados do model; decisão de manter ou não fica pra lá.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/utils.py` -- arquivo inteiro: import da linha 7 (`from .models import JogoGerado, JOGOS_CONFIG, JOGOS_COM_REGRA_SEQUENCIA, INTERVALO_MIN_SEQUENCIA, ResultadoLoteria` → `from .models import GeneratedBet, GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, MIN_SEQUENCE_INTERVAL, LotteryResult`); as 9 funções renomeadas: `normalizar_numeros→normalize_numbers`, `contar_pares_sequenciais→count_sequential_pairs`, `ultimos_jogos_tiveram_sequencia→recent_bets_had_sequence`, `gerar_aposta→generate_bet`, `verificar_jogo_repetido→check_duplicate_bet`, `calcular_estatisticas→calculate_statistics`, `calcular_premiacao_jogo→calculate_bet_prize`, `capturar_resultado_cef→fetch_cef_result`, `verificar_resultados_usuarios→check_user_results`; chamadas internas entre essas 9 funções também atualizadas (ex.: `gerar_aposta` chama `contar_pares_sequenciais` e `ultimos_jogos_tiveram_sequencia` — viram `generate_bet` chamando `count_sequential_pairs`/`recent_bets_had_sequence`); usos internos de campos do model renomeados na Story 1.1: `usuario=`→`user=`, `jogo=`→`game=`, `.order_by('-criado_em')`→`.order_by('-created_at')`, `pares_sequenciais__gt`→`sequential_pairs__gt`, `.numeros`→`.numbers`, `.trevos`→`.trevos`(sem uso direto aqui além de `verificar_jogo_repetido`, vira `.clovers`), `.resultado_verificado`→`.result_checked`, `.acertos`→`.hits`, `.premio`→`.prize`, `.premio_descricao`→`.prize_description`, `update_fields=[...'atualizado_em']`→`update_fields=[...'updated_at']`; `config['apostas']`/`config['numeros']`/`config['trevos']`/`config['qtd_trevos']` (chaves do dict de jogo, já renomeadas em `GAMES_CONFIG` pela Story 1.1) → `config['bets_count']`/`config['numbers_count']`/`config['clovers']`/`config['clovers_count']`.
- `apps/loterias_core/tests.py` -- import de `apps.loterias_core.utils` (linhas 10-18) atualizado pros 7 nomes novos que já são importados hoje (`calcular_estatisticas, calcular_premiacao_jogo, capturar_resultado_cef, contar_pares_sequenciais, gerar_aposta, normalizar_numeros, verificar_jogo_repetido` → `calculate_statistics, calculate_bet_prize, fetch_cef_result, count_sequential_pairs, generate_bet, normalize_numbers, check_duplicate_bet`); todos os call sites correspondentes no corpo do arquivo atualizados junto (~30 ocorrências, listadas na investigação). `ultimos_jogos_tiveram_sequencia`/`recent_bets_had_sequence` e `verificar_resultados_usuarios`/`check_user_results` não são importados em `tests.py` hoje — nada a fazer ali para essas duas.
- `apps/loterias_core/views.py` -- **fora de escopo** (Story 1.3), mas confirmado que importa e chama 6 das 9 funções (`gerar_aposta`, `verificar_jogo_repetido`, `contar_pares_sequenciais`, `calcular_estatisticas`, `normalizar_numeros`, `calcular_premiacao_jogo`) — continuará com `ImportError` até 1.3, mesmo padrão da Story 1.1.
- `apps/loterias_core/admin.py` -- confirmado que não importa nada de `utils.py`; nenhum impacto desta story.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/utils.py` -- renomear as 9 funções, corrigir o import de `models.py`, e atualizar todo uso interno de campo/constante do model pros nomes já fixados na Story 1.1 -- fecha a convenção de nomenclatura em inglês pro módulo de domínio
- [x] `apps/loterias_core/tests.py` -- import de `utils.py` e todos os call sites das 7 funções usadas nos testes atualizados -- suíte (a parte que não depende de `views.py`/`admin.py`) continua correta sem mudança de comportamento

**Critérios de Aceite:**
- Dado o mapeamento de nomes do Code Map, quando `utils.py` é renomeado, então todos os identificadores batem exatamente com o Code Map — nenhum nome alternativo inventado, nenhum parâmetro/variável local tocado
- Dado `tests.py` atualizado e a Story 1.1 já aplicada, quando as classes de teste que não dependem de `views.py` (`NormalizarNumerosTests`, `ContarParesSequenciaisTests`, `GerarApostaTests`, `VerificarJogoRepetidoTests`, `CalcularEstatisticasTests`, `CalcularPremiacaoJogoTests`, `CapturarResultadoCefTests`, `GeneratedBetModelTests`, e as de `apps/accounts/tests.py`) rodam isoladamente (ex.: `manage.py test apps.loterias_core.tests.GerarApostaTests`), então passam sem alteração de comportamento
- Dado que `views.py`/`admin.py` ainda não foram atualizados (Story 1.3 pendente), quando `python manage.py test`/`migrate`/`runserver` roda sem eles, então falha com `ImportError` neles especificamente — esperado, não regressão desta story

## Notas de Implementação

- Verificação rodada via o mesmo truque de alias temporário da Story 1.1: `views.py`/`admin.py` receberam imports com alias pros nomes novos, suite completa rodada (venv `.venv`, Python 3.11.15, Django 5.0.6), depois revertidos via `git checkout --` (confirmado sem diff). 51/51 testes passaram, incluindo os 8 grupos de teste do Critério de Aceite mais toda `apps.accounts`.
- Diff conferido linha a linha contra o Code Map: só `utils.py` e `tests.py` tocados, nenhum nome fora do mapeamento, parâmetros/variáveis locais e as chaves do dict de `fetch_cef_result` preservados em português como as Fronteiras e Restrições pediam.

## Review Triage Log

- **`false`** — "Estilo híbrido: docstrings/parâmetros/variáveis locais em português" (Blind Hunter). Refutação: decisão deliberada e documentada nas Fronteiras e Restrições desta spec, seguindo o mesmo precedente já usado na Story 1.1.
- **`low` → patch** — Import de `LotteryResult` em `utils.py` nunca é usado no corpo do arquivo (confirmado via grep — só aparece na linha do import). Real mas trivial; já estava lá antes desta story (como `ResultadoLoteria`), e a linha já está sendo tocada pelo rename mesmo.
- **`low` → patch** — Nomes de classe de teste ficaram inconsistentes com a função renomeada que testam (`CapturarResultadoCefTests` testa `fetch_cef_result`, etc.) (Blind Hunter). Mesmo padrão de achado já corrigido como patch na Story 1.1 (lá foram nomes de método; aqui são nomes de classe) — conserto é uma correção direta de 7 nomes de `class`.
- **`false`** — "`views.py` quebra com `ImportError`, nada sinaliza que é intencional" (Blind Hunter). Refutação: a spec documenta isso explicitamente como sequenciamento esperado (Story 1.3), mesmo padrão já estabelecido na Story 1.1; Edge Case Hunter confirmou que essa quebra já existia *antes* desta story (causada pela Story 1.1), não é nova.
- **`false`** — "CLAUDE.md desatualizado" (Blind Hunter). Já é o mesmo item registrado em `deferred-work.md` pela Story 1.1 ("atualizar CLAUDE.md quando o Epic 1 inteiro fechar") — não é uma lacuna nova, não duplicar.
- **`false`** — "Inconsistência de nomenclatura dentro de `GAMES_CONFIG` (`bets_count` vs. `clovers`/`clovers_count`)" (Blind Hunter). A assimetria já existia no dicionário original em português (`apostas` vs. `trevos`/`qtd_trevos`) e o mapeamento de nomes já foi fixado e commitado pela Story 1.1 — fora do escopo desta story reabrir essa decisão por uma nitpick de estilo debatível.
- Edge Case Hunter: 0 achados. Verification Gap Reviewer: 0 achados.

## Verificação

**Nota de sequenciamento:** igual à Story 1.1 — `python manage.py test`/`migrate`/`runserver` completos só funcionam depois que a Story 1.3 também estiver aplicada (`views.py`/`admin.py` ainda importam os nomes antigos de `utils.py`/`models.py`). Rodar as classes de teste específicas listadas no Critério de Aceite acima (que não passam por `views.py`) é a forma de verificar esta story isoladamente — mesmo truque de alias temporário usado na Story 1.1 (`from .utils import X as nome_antigo` em `views.py`, revertido depois) também serve se for mais prático rodar a suíte inteira uma vez.

**Comandos:**
- `python manage.py test apps.loterias_core.tests.NormalizarNumerosTests apps.loterias_core.tests.ContarParesSequenciaisTests apps.loterias_core.tests.GerarApostaTests apps.loterias_core.tests.VerificarJogoRepetidoTests apps.loterias_core.tests.CalcularEstatisticasTests apps.loterias_core.tests.CalcularPremiacaoJogoTests apps.loterias_core.tests.CapturarResultadoCefTests apps.loterias_core.tests.GeneratedBetModelTests apps.accounts` -- esperado: 100% passando (nomes exatos das classes a confirmar contra o arquivo real; ajustar se algum nome de classe divergir)
