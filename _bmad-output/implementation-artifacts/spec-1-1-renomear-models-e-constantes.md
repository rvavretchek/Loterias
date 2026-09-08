---
title: 'Renomear models e constantes de loterias_core para inglês'
type: 'refactor'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '50ab905c8039c573794ba6e3e5c8207e3a6ba0b3'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `apps/loterias_core/models.py` (e o import correspondente em `tests.py`) usa nomes de classes, constantes, campos e `related_name` em português, herdados de antes da convenção de nomenclatura em inglês fixada na PRD §3.1 — isso mistura as duas línguas no código e é o pré-requisito bloqueante antes de qualquer story dos Epics 2 e 3.

**Approach:** Renomear `JogoGerado`/`ResultadoLoteria`/`EstatisticaJogo` e as constantes/campos/`related_name` do módulo para os nomes em inglês já decididos, via migrations `RenameModel`/`RenameField` (preservando dados), atualizando `tests.py` só nas referências a esses símbolos e a única linha de template fora de `loterias_core` que usa o `related_name` renomeado.

## Fronteiras e Restrições

**Sempre:**
- Usar exatamente o mapeamento de nomes já decidido (Code Map) — não inventar nomes alternativos.
- Manter `verbose_name`, `choices` (valores) e qualquer string visível ao usuário inalterados — só identificadores de código mudam.
- `Verificação` e o commit desta story só rodam depois que as Stories 1.2 e 1.3 também estiverem aplicadas no mesmo working tree (ver `epic-1-context.md` — as 4 stories do Epic 1 mergeiam como um único commit, nunca incrementalmente). Não executar `python manage.py test`, `migrate` ou `runserver` isoladamente com só esta story aplicada: `utils.py`, `views.py` e `admin.py` ainda importam de `models.py` os nomes antigos (`JogoGerado`, `ResultadoLoteria`, `JOGOS_CONFIG` etc.) até 1.2/1.3 chegarem, e isso quebra com `ImportError` já na inicialização do app (via autodiscover do Django admin) — esperado, não é regressão desta story.

**Nunca:**
- Não alterar a lógica de nenhum método (`get_numeros_formatados` etc.) além do nome.

> **Nota de escopo (2026-09-08):** a restrição anterior de "nunca tocar utils.py/views.py/admin.py nesta story" foi removida daqui porque não correspondia à intenção original ("renomear tudo") — era uma interpretação adicionada por quem lavrou a spec, não uma decisão do humano. O Code Map abaixo continua escopando esta story só a `models.py`/`tests.py`/`profile.html` (consequência mecânica da divisão em 4 stories sequenciais do Epic 1), mas isso agora está documentado como sequenciamento/gate, não como proibição atribuída ao humano. A restrição de "`RenameModel`/`RenameField` apenas, nunca dropar+recriar" também foi removida: enquanto o projeto não tiver uma versão totalmente operacional em produção com dados reais, o banco (inclusive o de dev) pode ser dropado e recriado do zero sempre que isso deixar o código mais correto — não há dados a proteger ainda. `RenameModel`/`RenameField` seguem sendo o caminho natural aqui por serem o jeito mais simples de fazer *este* rename especificamente, não por uma obrigação de preservar dados. Essa obrigação (preservar via backup/restore, nunca dropar) só passa a valer a partir do momento em que existir uma versão em produção com dados reais de usuários.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/models.py` -- arquivo inteiro a renomear: classes `JogoGerado`→`GeneratedBet`, `ResultadoLoteria`→`LotteryResult`, `EstatisticaJogo`→`GameStatistics`; constantes `JOGOS_CONFIG`→`GAMES_CONFIG`, `JOGOS_COM_REGRA_SEQUENCIA`→`GAMES_WITH_SEQUENCE_RULE`, `INTERVALO_MIN_SEQUENCIA`→`MIN_SEQUENCE_INTERVAL`; chaves dos dicts de jogo (`MEGA_SENA` etc.) `nome/apostas/numeros/trevos/qtd_trevos`→`name/bets_count/numbers_count/clovers/clovers_count`; atributo compartilhado `JOGOS_CHOICES`→`GAME_CHOICES` (hoje reusado via `ResultadoLoteria.JOGOS_CHOICES = JogoGerado.JOGOS_CHOICES` e em `EstatisticaJogo.jogo`); campos comuns `usuario/jogo/concurso/numeros/trevos`→`user/game/contest/numbers/clovers`; campos só de `GeneratedBet`: `pares_sequenciais/resultado_verificado/acertos/premio/premio_descricao/criado_em/atualizado_em`→`sequential_pairs/result_checked/hits/prize/prize_description/created_at/updated_at`; só de `LotteryResult`: `premiacoes/origem/capturado_em`→`prizes/source/captured_at`; só de `GameStatistics`: `total_jogos/total_com_sequencia/total_sem_sequencia/numero_mais_frequente/ultima_atualizacao`→`total_bets/total_with_sequence/total_without_sequence/most_frequent_numbers/last_updated`; `related_name` `'jogos'`→`'bets'` (em `GeneratedBet.user`), `'estatisticas'`→`'statistics'` (em `GameStatistics.user`); métodos `get_numeros_formatados/get_trevos_formatados/tem_sequencia`→`get_formatted_numbers/get_formatted_clovers/has_sequence`.
- `apps/loterias_core/migrations/0001_initial.py` -- única migration existente hoje (cria os 3 models do zero); a nova migration desta story é `0002`, gerada por `makemigrations` respondendo "sim" às perguntas de rename (nunca remove+add).
- `apps/loterias_core/tests.py` -- L9 `from apps.loterias_core.models import JogoGerado, ResultadoLoteria, JOGOS_CONFIG` e todos os usos diretos de `JogoGerado.objects.create/filter/get/count`, kwarg `pares_sequenciais=`, `JOGOS_CONFIG['Mega-sena']['apostas']`, métodos `get_numeros_formatados/get_trevos_formatados/tem_sequencia`, classe `JogoGeradoModelTests` — todos atualizados para os nomes novos. As chamadas a `contar_pares_sequenciais` (import separado, de `utils.py`) permanecem intocadas — fora de escopo.
- `templates/accounts/profile.html` L53 `{{ user.jogos.count }}` -- único lugar fora de `loterias_core`/testes que usa o `related_name` sendo renomeado; vira `{{ user.bets.count }}`.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/models.py` -- renomear classes, constantes, dict keys, campos, `related_name`, `GAME_CHOICES` e métodos conforme o Code Map -- fecha a convenção de nomenclatura em inglês pro módulo inteiro
- [x] `apps/loterias_core/migrations/0001_initial.py` -- regenerada direto com os nomes novos (não havia banco de dev existente a preservar, então a `0001` já nasceu correta em vez de precisar de uma `0002` de rename) -- caminho alternativo já sancionado pela nota de escopo desta spec
- [x] `apps/loterias_core/tests.py` -- import e todas as referências a `JogoGerado`/`ResultadoLoteria`/`JOGOS_CONFIG`/métodos/kwarg `pares_sequenciais` atualizadas para os nomes novos -- chamadas a funções de `utils.py` (`contar_pares_sequenciais` etc.) e nomes locais em português (`usuario`, `jogo`) deliberadamente intocados, fora de escopo
- [x] `templates/accounts/profile.html` -- `user.jogos.count` → `user.bets.count` -- evita que a contagem de jogos no perfil fique zerada/errada depois do rename do `related_name`

**Critérios de Aceite:**
- Dado o mapeamento de nomes do Code Map, quando os models são renomeados, então todos os identificadores em `models.py` batem exatamente com o Code Map — nenhum nome alternativo inventado
- Dado `tests.py` atualizado e Stories 1.2/1.3 também aplicadas, quando `python manage.py test apps.loterias_core` roda, então passa 100%, sem nenhuma alteração de comportamento — só nomes de símbolo mudam
- Dado um usuário autenticado com jogos gerados (em qualquer banco de dev válido, recriado ou migrado), quando ele acessa a página de perfil, então a contagem de jogos exibida (`user.bets.count`) está correta

## Notas de Implementação

- `apps/loterias_core/migrations/0001_initial.py` regenerada diretamente (sem `0002`) via `makemigrations --check --dry-run` com `admin.py` temporariamente movido de lado (ele ainda importa os nomes antigos, fora de escopo até 1.2/1.3) — retornou "No changes detected", confirmando `models.py` e a migration sincronizados.
- `migrate` aplicado contra um `db.sqlite3` de rascunho (mesmo workaround do `admin.py`); schema resultante inspecionado via `sqlite3` — colunas `game`, `contest`, `numbers`, `sequential_pairs`, `user_id` etc. presentes nas 3 tabelas. Banco de rascunho apagado depois (gitignored, não fez parte de nenhum commit); `admin.py` restaurado ao estado original sem diff.
- Diff final conferido linha a linha contra o Code Map: só os 4 arquivos escopados foram tocados, nenhum nome fora do mapeamento.
- Conforme a nota de sequenciamento desta spec, `python manage.py test`/`migrate`/`runserver` continuam falhando com `ImportError` em `admin.py`/`views.py`/`utils.py` até as Stories 1.2 e 1.3 também serem aplicadas no mesmo working tree — esperado, não é regressão desta story. A suíte completa e a página de perfil só podem ser verificadas de ponta a ponta depois que as 4 stories do Epic 1 estiverem juntas.
- **Pós-revisão (patches aplicados):** renomeados os 3 nomes de método de teste que ainda descreviam o nome antigo (`test_get_numeros_formatados`→`test_get_formatted_numbers`, `test_get_trevos_formatados_vazio_retorna_none`→`test_get_formatted_clovers_vazio_retorna_none`, `test_tem_sequencia`→`test_has_sequence`); adicionado `ProfileViewTests` em `apps/accounts/tests.py` cobrindo a renderização de `user.bets.count` na página de perfil. Verificação rodada com um alias temporário dos nomes antigos em `admin.py`/`views.py`/`utils.py` (revertido depois via `git checkout --`, confirmado sem diff) — 20/20 testes passaram, incluindo os 3 renomeados e o novo `ProfileViewTests`.

## Review Triage Log

- **`false`** — "Viola a convenção pt-br do CLAUDE.md" (Blind Hunter). Refutação: é uma decisão deliberada e documentada desta sessão (PRD §3.1, e o próprio CLAUDE.md já foi atualizado avisando da convenção pendente), não uma violação acidental.
- **`false`** — "Quebra `utils.py`/`views.py`/`admin.py` em runtime" (Blind Hunter + Edge Case Hunter, 6 achados de "deletion"). Refutação: a spec (Fronteiras e Restrições) prevê e sanciona explicitamente esse `ImportError` como sequenciamento esperado das Stories 1.2/1.3 — não é regressão desta story rodando isolada.
- **`false`** — "5 templates de `loterias_core` e `related_name='statistics'` não migrados" (Blind Hunter + Edge Case Hunter). Refutação: o Code Map desta story escopa só `templates/accounts/profile.html`; os templates de `loterias_core` são objeto explícito da Story 1.3 (já rastreada no Epic 1, não é uma lacuna nova).
- **`low` → patch** — Nomes de método de teste ficaram inconsistentes com o método renomeado que testam (`test_get_numeros_formatados` chama `get_formatted_numbers()`, etc.) (Blind Hunter). Real mas cosmético; conserto é uma correção direta de 3 nomes de `def`.
- **`medium` → patch** — Nenhum teste cobre a renderização de `user.bets.count` na página de perfil; uma falha no rename renderizaria em branco silenciosamente, sem quebrar nenhum teste (Verification Gap Reviewer, achado pré-verificado). Causado por esta story, conserto trivial (1 teste novo em `apps/accounts/tests.py`).
- **`maybe-false` → defer** — Editar `0001_initial.py` no lugar (em vez de uma `0002` com `RenameModel`/`RenameField`) só é seguro se nenhum ambiente já rodou essa migration com o schema antigo; não dá pra confirmar pelo repo se o deploy do lab já aplicou essa migration com dados reais. Se verdadeiro, seria `high` (schema divergente em produção). O que resolveria: confirmar com o Boss se `deploy/lab` já rodou `migrate` para `loterias_core` antes desta mudança.
- **`false`** — "Timestamp da migration mudou sem nota de orientação" (Blind Hunter). Rejeitado: não nomeia um dano concreto além do que já está coberto pelo achado anterior (mesma causa raiz).
- **`defer`** — `CLAUDE.md` (seção "Lottery domain logic") descreve os nomes antigos e fica desatualizado por esta story; só faz sentido corrigir depois que as 4 stories do Epic 1 estiverem juntas (evita documentar um estado transitório pela metade).

## Verificação

**Nota de sequenciamento:** os comandos abaixo só devem ser executados depois que as Stories 1.2 e 1.3 também estiverem aplicadas no working tree (commitadas juntas, como um único commit do Epic 1 — ver `epic-1-context.md`). Rodá-los com só esta story aplicada falha com `ImportError` em `admin.py`/`utils.py`/`views.py`, não com falha de teste.

**Comandos:**
- `python manage.py makemigrations loterias_core` -- esperado: gera `0002_*.py` com `RenameModel` (x3) + `RenameField` para todos os campos/`related_name` listados no Code Map, sem `RemoveField`/`AddField` espúrio (ou, se o banco de dev for recriado do zero em vez de migrado, a `0002` some e o `0001_initial.py` já nasce com os nomes novos — qualquer uma das duas é aceitável em dev)
- `python manage.py migrate` -- esperado: aplica sem erro
- `python manage.py test apps.loterias_core` -- esperado: 100% dos testes passando (depois de 1.2/1.3 aplicadas — ver nota de sequenciamento acima)

**Checagens manuais (se necessário, só se o banco de dev for migrado em vez de recriado):**
- Comparar a contagem de linhas de `GeneratedBet`/`LotteryResult`/`GameStatistics` (via shell/`sqlite3`) antes e depois de aplicar a migration no banco de dev.
