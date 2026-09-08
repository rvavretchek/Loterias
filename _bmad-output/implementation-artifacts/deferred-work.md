- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-renomear-models-e-constantes.md`
  summary: Confirmar se o deploy do lab (`deploy/lab/docker-compose.yml`) já aplicou a migration `0001_initial` de `loterias_core` com o schema antigo (português) antes desta renomeação.
  evidence: A Story 1.1 editou `0001_initial.py` no lugar (nomes novos direto na `CreateModel`) em vez de gerar uma `0002` com `RenameModel`/`RenameField`, sancionado pela spec só para bancos de dev sem essa migration ainda aplicada. Se o ambiente do lab já rodou `migrate` com o schema antigo, aplicar essa mesma migration lá seria um no-op do Django (mesmo nome de migration), deixando as colunas reais divergentes dos nomes que o código agora espera — um `OperationalError: no such column` em produção. Não dá pra confirmar isso só pelo repo local; precisa de uma decisão/checagem do Boss antes do deploy do Epic 1 completo.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-1-renomear-models-e-constantes.md`
  summary: Atualizar a seção "Lottery domain logic" do CLAUDE.md pros nomes novos em inglês, depois que as 4 stories do Epic 1 estiverem todas aplicadas.
  evidence: CLAUDE.md hoje documenta `JogoGerado`, `ResultadoLoteria`, `EstatisticaJogo`, `JOGOS_CONFIG`, `gerar_aposta()` etc. como a arquitetura atual — desatualizado assim que Story 1.1 renomeia `models.py`. Atualizar agora seria documentar um estado transitório pela metade (já que `utils.py`/`views.py` ainda estão em português até 1.2/1.3); faz mais sentido corrigir de uma vez quando o Epic 1 inteiro fechar (natural pra Story 1.4, que já é a story de fechamento/validação do épico).

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "`api_create_bet_view` não valida `selected_game not in GAMES_CONFIG` antes de gerar o jogo — diferente de `create_bet_view`, que valida."
  evidence: Com um `jogo` inválido no payload JSON, `generate_bet()` retorna `(None, None)` e a chamada seguinte (`count_sequential_pairs(nums)`) faz `len(None)`, levantando `TypeError` não tratado (500) em vez do 400 limpo que o form HTML equivalente devolve. Bug pré-existente (mesma assinatura já existia antes do rename, achado pela Verification Gap Reviewer/Blind Hunter na Story 1.3), fora do escopo de uma story de renomeação — precisa de uma story própria de correção de bug.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "`create_bet_view`/`save_manual_bet_view` avisam sobre concurso duplicado mas criam o registro duplicado mesmo assim (falta `return`/interrupção após o `messages.warning()`)."
  evidence: Bug pré-existente, comportamento idêntico antes e depois do rename (achado pelo Blind Hunter na Story 1.3). Corrigir exigiria decidir o comportamento correto (bloquear totalmente vs. permitir duplicata com aviso) — decisão de produto, não só código.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: Nomes de arquivo de template (`historico.html`, `detalhes_jogo.html`, `estatisticas.html`) continuam em português; considerar renomear pro inglês (`history.html`, `bet_detail.html`, `statistics.html`) numa story futura.
  evidence: Não são identificador de código Python (são string literal de caminho passada pra `render()`, análogo a uma rota) — por isso ficaram fora do mapeamento oficial da Story 1.3, mas o Blind Hunter apontou a inconsistência de views/rotas em inglês apontando pra arquivos com nome em português. Decisão do Boss pendente sobre se vale ampliar o escopo do rename até esse nível.

- source_spec: `_bmad-output/implementation-artifacts/spec-1-3-renomear-views-admin-templates.md`
  summary: "`config.clovers` (o jogo usa trevo?) e `config.clovers_count` (quantos trevos sortear) em `GAMES_CONFIG` têm nomes muito parecidos e nenhum comentário os distingue — risco de confusão futura em `home.html` e em qualquer código novo que leia esse dict."
  evidence: Achado pelo Blind Hunter na Story 1.3; não é um bug hoje (o uso atual está correto), só um risco de manutenção. Bastaria um comentário no dict `GAMES_CONFIG` em `models.py` explicando a diferença.
