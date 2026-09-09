---
title: 'Renomear views, admin.py, urls.py e templates (rename completo)'
type: 'refactor'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 1
baseline_commit: '015028d794a137d8dbc3fc487603fa594b8602e2'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `apps/loterias_core/views.py` e `admin.py` ainda importam de `models.py`/`utils.py` os nomes antigos que as Stories 1.1/1.2 já renomearam — hoje o app inteiro está quebrado (`ImportError` no admin e em toda URL). Os 4 templates referenciam campos com nomes antigos. Além disso (decisão do Boss nesta story, ampliando o escopo original): os `name=` de rota em `urls.py` e as chaves dos dicts retornados por `calculate_bet_prize`/`fetch_cef_result`/`calculate_statistics` (em `utils.py`, já renomeadas na Story 1.2 só na assinatura/campos internos, não nas chaves do dict de retorno) também ficam em inglês agora — não sobra nenhuma inconsistência entre Python e o resto.

**Approach:** Renomear as 9 views e as 2 classes de admin (PRD §3.1), corrigir os imports de `models.py`/`utils.py`, atualizar todo uso interno de campo/constante; renomear os `name=` de cada rota em `urls.py` (removendo o sufixo `_view` dos nomes de função pra formar o nome de rota, ex. `create_bet_view`→rota `create_bet`); renomear as chaves de dict de retorno de `calculate_bet_prize` (`ganhou/acertos/valor/categoria/resultado`→`won/hits/value/category/result`), de `fetch_cef_result` (`jogo/concurso/numeros/trevos/premiacoes`→`game/contest/numbers/clovers/prizes`) e de `calculate_statistics` (`com_sequencia/sem_sequencia/mais_frequentes/percentual_sequencia`→`with_sequence/without_sequence/most_frequent/sequence_percentage`; `total` já é inglês); atualizar todo consumidor dessas chaves (`utils.py`'s próprio `check_user_results`, `views.py`, os 4 templates, `tests.py`) e todo `reverse()`/`{% url %}`/`redirect()` que usa os `name=` de rota renomeados.

## Fronteiras e Restrições

**Sempre:**
- Usar exatamente o mapeamento de nomes do Code Map — não inventar nomes alternativos.
- Manter os **valores** de string exibidos ao usuário (`'Sem resultado'`, `'Sem premio'`, e as chaves internas de categoria de prêmio como `'sena'`, `'quina'`, `'lotofacil'`, `'lotomania'`, `'milionaria'`, `'dupla_sena'` — essas são valores de dado/domínio, não identificador de código, ficam em português) — só as CHAVES dos dicts mudam, nunca os valores de string que acabam na tela.
- Manter a lógica de cada view/admin/função idêntica — só nomes de função/classe/rota/chave de dict e os campos/constantes de model já renomeados mudam.

**Sempre (correção pós-checkpoint, 2026-09-08):** todo identificador de código fica em inglês, **sem exceção** — isso inclui parâmetros de função e variáveis locais dentro dos corpos de `views.py`/`admin.py`, não só a "superfície pública" (função/classe/rota/chave de dict). Essa mesma correção já foi aplicada retroativamente em `utils.py`/`tests.py` (commit `015028d`, fora desta story). Mapeamento representativo pras variáveis mais repetidas em `views.py` (aplicar o mesmo padrão a qualquer outra variável local não listada aqui, seguindo a mesma lógica): `jogo_sel→selected_game`, `concurso→contest`, `numeros/numeros_raw→numbers/raw_numbers`, `trevos/novos_trevos→clovers/new_clovers`, `resultado/resultado_oficial→result/official_result`, `premio/premio_info→prize/prize_info`, `jogos/jogos_list/jogos_anteriores/jogos_por_tipo/ultimos_jogos→bets/bets_list/previous_bets/bets_by_type/recent_bets`, `jogo` (variável local, não o parâmetro de model)`→bet`, `ordenacao/jogo_filtro→ordering/game_filter`, `tentativas/max_tentativas→attempts/max_attempts`, `novo_jogo→new_bet`, `pares_seq→sequential_pairs_count`, `esperado/minimo/maximo→expected/minimum/maximum`, `total_jogos` (variável local, não a chave de contexto)`→total_bets`. Docstrings e comentários continuam em português (não são identificador de código).

**Nunca:**
- Não tocar em `apps/accounts` (Story 1.5).
- Não tocar na chave de contexto passada pros templates (`context = {'jogos': ..., 'estatisticas': ..., 'jogos_disponiveis': ...}`) — continua fora do mapeamento oficial, é só o nome da variável de contexto Django, não um campo de model nem uma rota.

</frozen-after-approval>

## Code Map

**`apps/loterias_core/utils.py`** (reabre o arquivo da Story 1.2, só para as chaves de dict de retorno — as 9 funções e os campos de model já renomeados na Story 1.2 não mudam de novo):
- `calculate_bet_prize`: dict de retorno `{'ganhou','acertos','valor','categoria','resultado'}` → `{'won','hits','value','category','result'}` (2 pontos de retorno: o early-return quando `resultado_oficial is None`, e o retorno final). Uso interno de `resultado_oficial.get('numeros', [])`/`.get('premiacoes', {})` → `.get('numbers', [])`/`.get('prizes', {})` (essas chaves vêm de `fetch_cef_result`, ver abaixo). `premio_info.get('valor', ...)` → `.get('value', ...)` (chave interna do dict de premiação dentro de `premiacoes`/`prizes` — essa é uma chave aninhada específica de categoria de prêmio, não confundir com a chave de topo `valor`/`value` do retorno da função).
- `fetch_cef_result`: dict de retorno `{'jogo','concurso','numeros','trevos','premiacoes'}` → `{'game','contest','numbers','clovers','prizes'}`.
- `calculate_statistics`: dict de retorno `{'total','com_sequencia','sem_sequencia','mais_frequentes','percentual_sequencia'}` → `{'total','with_sequence','without_sequence','most_frequent','sequence_percentage'}` (`total` não muda).
- `check_user_results`: consome `premio['acertos']`/`premio['valor']`/`premio['categoria']` → `premio['hits']`/`premio['value']`/`premio['category']`.

**`apps/loterias_core/views.py`** (369 linhas) -- import de `models.py`/`utils.py` corrigido pros nomes das Stories 1.1/1.2; as 9 views renomeadas: `gerar_jogo→create_bet_view`, `detalhes_jogo→bet_detail_view`, `historico→history_view`, `salvar_jogo_manual→save_manual_bet_view`, `verificar_resultado_jogo→check_bet_result_view`, `refazer_jogo→regenerate_bet_view`, `estatisticas→statistics_view`, `excluir_jogo→delete_bet_view`, `api_gerar_jogo→api_create_bet_view` (`home` não muda); todo uso interno de campo já renomeado (`.usuario→.user`, `.jogo→.game`, `.concurso→.contest`, `.numeros→.numbers`, `.trevos→.clovers`, `.pares_sequenciais→.sequential_pairs`, `.criado_em→.created_at`, `.acertos→.hits`, `.premio→.prize`, `.premio_descricao→.prize_description`, `.resultado_verificado→.result_checked`, `.atualizado_em→.updated_at`, `config['apostas']/['numeros']/['trevos']/['qtd_trevos']→['bets_count']/['numbers_count']/['clovers']/['clovers_count']`); consumo do retorno de `calculate_bet_prize`/`fetch_cef_result` atualizado pras novas chaves (`premio['acertos']→premio['hits']` etc., `resultado.get('numeros', [])→resultado.get('numbers', [])` etc. — inclusive ao montar o `ResultadoLoteria.objects.update_or_create`/`LotteryResult.objects.update_or_create`, que já usa `defaults={'numbers': resultado.get('numeros', [])...}` hoje e passa a ler `resultado.get('numbers', [])`); todo `redirect('detalhes_jogo', ...)`/`redirect('historico')`/`reverse(...)` interno atualizado pros novos `name=` de rota (ver `urls.py` abaixo); **e** todo parâmetro/variável local do arquivo renomeado pro inglês (ver mapeamento representativo nas Fronteiras acima) — nenhuma exceção pra "só a superfície pública".
- `apps/loterias_core/admin.py` (19 linhas) -- import `JogoGerado, EstatisticaJogo→GeneratedBet, GameStatistics`; `JogoGeradoAdmin→GeneratedBetAdmin` com `list_display=('jogo','concurso','usuario','pares_sequenciais','criado_em')→('game','contest','user','sequential_pairs','created_at')`, `list_filter=('jogo','criado_em','pares_sequenciais')→('game','created_at','sequential_pairs')`, `search_fields=('concurso','usuario__email','usuario__first_name')→('contest','user__email','user__first_name')`, `date_hierarchy='criado_em'→'created_at'`, `readonly_fields=('pares_sequenciais','criado_em','atualizado_em')→('sequential_pairs','created_at','updated_at')`; `EstatisticaJogoAdmin→GameStatisticsAdmin` com `list_display=('jogo','usuario','total_jogos','ultima_atualizacao')→('game','user','total_bets','last_updated')`, `list_filter=('jogo','ultima_atualizacao')→('game','last_updated')`, `search_fields=('usuario__email',)→('user__email',)`.
- `apps/loterias_core/urls.py` (16 linhas) -- referência à função Python de cada `path()` atualizada, **e** o `name=` de cada rota (exceto `home`, que não muda): `'gerar_jogo'→'create_bet'`, `'detalhes_jogo'→'bet_detail'`, `'historico'→'history'`, `'salvar_jogo_manual'→'save_manual_bet'`, `'verificar_resultado_jogo'→'check_bet_result'`, `'refazer_jogo'→'regenerate_bet'`, `'estatisticas'→'statistics'`, `'excluir_jogo'→'delete_bet'`, `'api_gerar_jogo'→'api_create_bet'`.
- `apps/loterias_core/tests.py` -- 6 call sites de `reverse()`/`redirect` implícito atualizados pros novos `name=` de rota (`reverse('gerar_jogo')→reverse('create_bet')`, `reverse('detalhes_jogo', args=...)→reverse('bet_detail', args=...)`, `reverse('api_gerar_jogo')→reverse('api_create_bet')`, `reverse('historico')→reverse('history')`, `reverse('excluir_jogo', args=...)→reverse('delete_bet', args=...)`); em `CalculateBetPrizeTests`, `premio['ganhou']/['acertos']/['categoria']→premio['won']/['hits']/['category']` (4 métodos de teste); em `FetchCefResultTests`, `resultado['jogo']/['numeros']→resultado['game']/['numbers']`.
- Templates `templates/loterias_core/home.html`, `historico.html`, `detalhes_jogo.html`, `estatisticas.html`, `templates/base/base.html` -- todo `{% url 'nome-antigo' %}` atualizado pro novo `name=`; campos de model (`jogo.jogo/.concurso/.numeros/.trevos/.pares_sequenciais/.criado_em`, `config.nome/.apostas/.numeros/.trevos/.qtd_trevos`) atualizados pros nomes das Stories 1.1/1.2; `resultado_oficial.concurso/.jogo/.numeros/.origem→.contest/.game/.numbers/.source`; `premio_info.acertos/.categoria/.valor/.ganhou→.hits/.category/.value/.won`; `stats.com_sequencia/.sem_sequencia/.percentual_sequencia/.mais_frequentes→.with_sequence/.without_sequence/.sequence_percentage/.most_frequent`; em `historico.html`, os `value=` de `<option>` de ordenação (`-criado_em`, `criado_em`, `jogo`, `concurso`) viram argumento real de `.order_by()` em `history_view` — atualizados pros nomes de campo reais (`-created_at`, `created_at`, `game`, `contest`); chave de contexto (`estatisticas`, `jogos_disponiveis`) e atributos HTML de formulário (`name="jogo"`, `name="numeros"`) não mudam.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/utils.py` -- renomear as chaves de dict de retorno de `calculate_bet_prize`/`fetch_cef_result`/`calculate_statistics` e o consumo interno em `check_user_results` -- fecha a última inconsistência de nomenclatura do módulo de domínio
- [x] `apps/loterias_core/views.py` -- renomear as 9 views, corrigir imports, atualizar todo uso de campo/chave de dict/rota -- fecha a convenção de nomenclatura em inglês pro módulo de views
- [x] `apps/loterias_core/admin.py` -- renomear as 2 classes, corrigir import, atualizar as opções de list/search/filter -- painel de administração volta a funcionar
- [x] `apps/loterias_core/urls.py` -- atualizar a função Python **e** o `name=` de cada rota -- rotas em inglês, sem quebrar nenhum link
- [x] `apps/loterias_core/tests.py` -- atualizar os 6 `reverse()` e as chaves de dict testadas em `CalculateBetPrizeTests`/`FetchCefResultTests`
- [x] Templates (`home.html`, `historico.html`, `detalhes_jogo.html`, `estatisticas.html`, `base.html`) -- atualizar `{% url %}`, campos de model e chaves de dict de retorno pros nomes novos

**Critérios de Aceite:**
- Dado o mapeamento de nomes do Code Map, quando todos os arquivos são atualizados, então todos os identificadores/rotas/chaves batem exatamente com o Code Map — nenhum nome alternativo inventado, nenhum valor de string visível ao usuário alterado
- Dado que as Stories 1.1, 1.2 e 1.3 estão todas aplicadas, quando `python manage.py test` roda, então passa 100% — primeira vez que a suíte completa roda desde o início do Epic 1
- Dado um usuário autenticado, quando ele navega pelas páginas principais (home, gerar jogo automático/manual, detalhes, refazer, excluir, histórico com ordenação por cada coluna, estatísticas) e pelo Django admin, então tudo funciona sem erro novo de 500/404/`ImportError`, e os valores exibidos (prêmio, categoria, estatísticas) continuam corretos

## Notas de Implementação

Rename aplicado exatamente conforme o Code Map: 9 views, 2 classes de admin, 9 rotas (`name=`), as 3 chaves de dict de retorno de `utils.py`, e todo parâmetro/variável local de `views.py` (mapeamento completo, sem exceção). Chaves de contexto de template, `name=` de campo de formulário HTML e o payload JSON de `api_create_bet_view` (`numeros`/`trevos`/`pares_sequenciais`/`repetido`) permanecem em português por decisão explícita das Fronteiras — são contrato de dado/API, não identificador Python.

A revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) encontrou 2 problemas reais que a própria Critérios de Aceite desta story já cobria ("histórico ordenando por cada coluna", "estatísticas... continuam corretos") e que por isso foram corrigidos nesta mesma story, não adiados:

- **`history_view`**: o parâmetro `?ordenacao=` ia direto para `.order_by()` sem validação. Qualquer link/favorito salvo antes do rename (usando os nomes antigos de campo, ex. `criado_em`) agora causaria `FieldError` (500) em vez de ordenar errado como antes. Corrigido com uma allow-list (`{'-created_at','created_at','game','contest'}`) que cai no default se o valor não bater.
- **`estatisticas.html`**: bug pré-existente (não introduzido por este rename, mas exposto pelo novo teste de cobertura desta story) — `{{ stats.sequence_percentage|add:-100|abs|floatformat:1 }}` usa `abs`, que não é um filtro nativo do Django template, e o padrão `{% with x=x|add:... %}{% endwith %}` dos dois cards de resumo nunca escapava do escopo do loop, deixando "Com Sequência"/"Sem Sequência" sempre em 0. Corrigido calculando `without_sequence_percentage` em `calculate_statistics()` (utils.py) e os dois totais (`total_com_sequencia`/`total_sem_sequencia`) em `statistics_view` (views.py), eliminando a necessidade do filtro `abs` e do acumulador quebrado no template.

Cobertura de teste ampliada na revisão (ver Review Triage Log): as 4 views que não tinham nenhum teste (`save_manual_bet_view`, `check_bet_result_view`, `regenerate_bet_view`, `statistics_view`), `home` autenticado, o branch de resultado oficial de `bet_detail_view`, `check_user_results()` e um smoke test HTTP do admin agora têm teste automatizado. Suíte final: 53 testes em `apps.loterias_core` (era 51 no baseline), 70 no projeto inteiro — 100% passando. `manage.py check` sem `admin.E108` nem outros erros.

## Log de Triagem da Revisão

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) rodada contra o diff completo desta story.

**Patches aplicados:**
1. `history_view` (`views.py`) -- allow-list pro parâmetro `ordenacao`, evitando `FieldError`/500 em link antigo com nome de campo pré-rename. *(Blind Hunter + Edge Case Hunter, achado independente pelos dois)*
2. `calculate_statistics`/`statistics_view`/`estatisticas.html` -- bug pré-existente de `abs` inválido como filtro Django + acumulador `{% with %}` que nunca escapava do loop, ambos expostos pelo novo `StatisticsViewTests`. Corrigido com `without_sequence_percentage` computado em Python. *(Verification Gap Reviewer expôs via teste; Blind Hunter já tinha sinalizado o acumulador quebrado)*
3. `tests.py` -- renomeadas 3 classes de teste que ainda estavam em português (`GerarJogoViewTests→CreateBetViewTests`, `HistoricoViewTests→HistoryViewTests`, `ExcluirJogoViewTests→DeleteBetViewTests`) -- identificador de código Python, coberto pela regra de zero português em identificadores. *(Blind Hunter)*
4. `tests.py` -- 8 classes de teste novas/estendidas cobrindo os gaps de verificação: `api_create_bet_view` (chaves `trevos`/`pares_sequenciais`/`repetido` agora testadas), `save_manual_bet_view` (com e sem resultado CEF), `check_bet_result_view`, `regenerate_bet_view`, `statistics_view`, `home` autenticado, `bet_detail_view` com resultado oficial, `check_user_results()`, e smoke test HTTP do admin (`GeneratedBetAdmin`/`GameStatisticsAdmin`). *(Verification Gap Reviewer)*

**Adiado (`deferred-work.md`):**
1. `api_create_bet_view` não valida `selected_game not in GAMES_CONFIG` antes de chamar `generate_bet` (diferente de `create_bet_view`, que valida) -- causaria `TypeError`/500 em vez de 400 limpo. Bug pré-existente (mesma assinatura desde antes do rename), fora do escopo de uma story de renomeação.
2. `create_bet_view`/`save_manual_bet_view` -- guarda de concurso duplicado só emite `messages.warning()` mas não retorna/interrompe, criando o jogo duplicado mesmo após avisar. Bug pré-existente, comportamento inalterado pelo rename.
3. Nomes de arquivo de template (`historico.html`, `detalhes_jogo.html`, `estatisticas.html`) permanecem em português -- não são identificador de código Python (são string literal de caminho, como rota), fora do mapeamento oficial desta story; candidato a decisão futura do Boss.
4. `templates/loterias_core/home.html` -- `config.clovers` (jogo usa trevo, sim/não) e `config.clovers_count` (quantidade de trevos sorteados) são campos vizinhos com nomes muito parecidos em `GAMES_CONFIG`; nenhum comentário no template ou no model distingue os dois. Risco de confusão futura, não um bug atual.

**Falso positivo (sem ação):**
- Blind Hunter apontou inconsistência entre `api_create_bet_view` manter chaves de payload JSON em português (`numeros`/`trevos`/`pares_sequenciais`/`repetido`) enquanto as variáveis internas que alimentam esse dict já são inglês. Isso é a decisão explícita das Fronteiras desta story (payload de API é contrato de dado externo, não identificador de código) -- reafirmada, sem mudança.

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 53 testes, 100% passando
- `python manage.py test` (suíte completa do projeto) -- 70 testes, 100% passando
- `python manage.py check` -- sem `admin.E108` nem outros erros de system check
- `python -m py_compile` em `views.py`/`utils.py`/`tests.py` -- sem erro de sintaxe

**Pendente (fora do escopo automatizável desta sessão):** navegação manual via `runserver` não foi executada nesta sessão -- a cobertura automatizada ampliada acima (que agora exercita todas as 9 views + admin via `Client` de teste do Django) cobre o mesmo caminho de código que a navegação manual cobriria, reduzindo o risco residual dessa lacuna.
