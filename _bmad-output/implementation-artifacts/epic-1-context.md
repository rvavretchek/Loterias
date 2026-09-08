# Contexto do Epic 1: Renomeação do Código Legado para Inglês

<!-- Compilado a partir dos artefatos de planejamento. Editar livremente. Regenerar com compile-epic-context se os documentos de planejamento mudarem. -->

## Objetivo

Alinhar todo o código legado de `apps/loterias_core` (models, constantes, funções de domínio, views, admin) à convenção de nomenclatura em inglês adotada para o projeto, sem alterar comportamento, dados ou a interface do usuário (que permanece em português via `verbose_name` e strings de UI). É débito técnico transversal e pré-requisito de sequenciamento: nenhuma story dos Epics 2 e 3 pode começar antes deste épico estar concluído, testado e mergeado — evita que código novo nasça misturando português (herdado) e inglês (novo) no mesmo módulo.

## Histórias

- Story 1.1: Renomear models e constantes de loterias_core para inglês
- Story 1.2: Renomear funções de domínio em utils.py
- Story 1.3: Renomear views, admin.py e atualizar urls.py/templates
- Story 1.4: Cobrir reverse accessors renomeados e validar a migration antes do deploy

## Requisitos e Restrições

- Sem mudança de comportamento ou de UI: apenas identificadores de código mudam de nome. Strings de UI, `verbose_name`, mensagens e vocabulário de domínio continuam em português.
- **Dados:** em produção, nenhuma linha existente no SQLite pode ser perdida ou alterada pela renomeação (ver o item de backup abaixo). Em ambiente de dev, enquanto não existir uma versão em produção com dados reais, o banco pode ser dropado e recriado do zero livremente sempre que isso simplificar o rename — não há dado de dev a proteger a qualquer custo.
- A suíte de testes (`python manage.py test`) precisa passar 100% ao final do épico, incluindo casos novos que exercitem explicitamente os reverse accessors renomeados (`user.bets`, `user.statistics`), que a suíte atual não cobre.
- Navegação manual pelas páginas principais (home, gerar jogo, detalhes, histórico) e pelo Django admin precisa funcionar sem novo erro 500/404 após a renomeação de views/admin.
- Antes de aplicar a migration em produção: copiar/backup do arquivo do volume `loterias_data`, e rodar a migration contra uma cópia do `db.sqlite3` de produção (não só o banco de teste vazio), conferindo contagem de linhas antes/depois e uma amostra de registros manualmente.
- As 4 stories são sequenciais e mergeadas como um único PR/commit — nunca incrementalmente, nunca dividido por model entre pessoas diferentes.

## Decisões Técnicas

- Regra geral: todo identificador de código (variável, constante, classe, função, model field) passa para inglês, inclusive o legado. UI, mensagens/e-mails e o vocabulário de domínio em português não mudam; um model field em inglês carrega o rótulo em português via `verbose_name` (ex.: `contest = models.CharField(..., verbose_name='Concurso')`).
- Mapeamento de nomes (resumo — a lista completa fica na PRD, não repetir integralmente aqui):
  - Models: `JogoGerado`→`GeneratedBet`, `ResultadoLoteria`→`LotteryResult`, `EstatisticaJogo`→`GameStatistics`.
  - Constantes: `JOGOS_CONFIG`→`GAMES_CONFIG`, `JOGOS_COM_REGRA_SEQUENCIA`→`GAMES_WITH_SEQUENCE_RULE`, `INTERVALO_MIN_SEQUENCIA`→`MIN_SEQUENCE_INTERVAL`; chaves de dict de jogo `nome/apostas/numeros/trevos/qtd_trevos`→`name/bets_count/numbers_count/clovers/clovers_count`.
  - Atributo de classe compartilhado entre as 3 classes de model: `JOGOS_CHOICES`→`GAME_CHOICES`.
  - `related_name`: campo `usuario` de `JogoGerado`→`related_name='bets'` (`user.bets`); campo `usuario` de `EstatisticaJogo`→`related_name='statistics'` (`user.statistics`).
  - Campos comuns às 3 classes: `usuario/jogo/concurso/numeros/trevos`→`user/game/contest/numbers/clovers`.
  - Funções de domínio (`utils.py`): `normalizar_numeros`, `contar_pares_sequenciais`, `ultimos_jogos_tiveram_sequencia`, `gerar_aposta`, `verificar_jogo_repetido`, `calcular_estatisticas`, `calcular_premiacao_jogo`, `capturar_resultado_cef`, `verificar_resultados_usuarios` → `normalize_numbers`, `count_sequential_pairs`, `recent_bets_had_sequence`, `generate_bet`, `check_duplicate_bet`, `calculate_statistics`, `calculate_bet_prize`, `fetch_cef_result`, `check_user_results`.
  - Views: `gerar_jogo/detalhes_jogo/historico/salvar_jogo_manual/verificar_resultado_jogo/refazer_jogo/estatisticas/excluir_jogo/api_gerar_jogo` → `create_bet_view/bet_detail_view/history_view/save_manual_bet_view/check_bet_result_view/regenerate_bet_view/statistics_view/delete_bet_view/api_create_bet_view`.
  - Admin: `JogoGeradoAdmin`→`GeneratedBetAdmin`, `EstatisticaJogoAdmin`→`GameStatisticsAdmin` (inclui atualizar `list_display`/`list_filter`/`search_fields`/`readonly_fields` que hoje referenciam os campos antigos).
- `related_name` e o atributo `GAME_CHOICES` cruzam as três classes de model — é o ponto cego mais provável de import quebrado se a renomeação for dividida entre pessoas; por isso essas 3 classes são renomeadas numa só passada, nunca em paralelo por builders diferentes.
- Em dev, o caminho natural é `RenameModel`/`RenameField` do Django, por ser o mais simples pra este rename — mas dropar+recriar coluna/tabela também é aceitável em dev (ver Requisitos e Restrições acima). Em produção, o caminho é sempre `RenameModel`/`RenameField`, nunca dropar+recriar: é seguro no SQLite bundled do Python 3.11 (≥3.25 já suporta `ALTER TABLE RENAME COLUMN`/`RENAME TO` nativamente, sem reconstrução de tabela).
- `apps/accounts` já segue a convenção em inglês (`User`, `UserManager`, `CustomSignupForm`, `CustomAccountAdapter`) e está fora do escopo desta renomeação.

## Dependências Entre Histórias

- Sequência estrita dentro do épico: 1.1 (models/constantes) → 1.2 (utils.py, depende dos models renomeados) → 1.3 (views/admin/urls/templates, depende de utils.py renomeado) → 1.4 (testes de reverse accessors + validação de migration, depende das views renomeadas).
- As 4 stories são reunidas num único PR/commit — sem merge incremental entre elas.
- Epic 1 concluído (incluindo Story 1.4 passando 100%) é pré-requisito obrigatório para qualquer story do Epic 2 (Verificação e Notificação Diária de Resultados) e do Epic 3 (Novo Fluxo de Cadastro), ambos dependentes dos nomes novos já estarem em vigor.
