---
title: 'Bloqueio de concurso já sorteado'
type: 'feature'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '7292bc56b4f59914eb6e8f310a484acc108735ce'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Hoje o usuário pode gerar/salvar um jogo pra um Jogo+Concurso que já tem resultado oficial registrado (`LotteryResult`) — o sistema só avisa (sem bloquear) quando o próprio usuário já tem um jogo igual pro mesmo Jogo+Concurso, mas nunca checa se o concurso já foi sorteado de verdade. Isso deixa o usuário gerar apostas inúteis por engano pra um concurso que já passou.

**Approach:** Adicionar um bloqueio novo (não substitui o aviso de duplicata existente, os dois coexistem) em `create_bet_view` e `save_manual_bet_view`: antes de gerar/salvar, checa `LotteryResult.objects.filter(game=selected_game, contest=contest).exists()` — de qualquer usuário, não só o jogo/concurso do usuário atual (AD já documentado nas Consistency Conventions do spine) — e, se existir, bloqueia com mensagem clara, sem gravar nada. Além disso, sugere um próximo concurso (o maior `contest` numérico conhecido em `LotteryResult` pra aquele Jogo, +1) pré-preenchendo o campo de concurso no formulário, mas sem restringir o valor aceito — o usuário pode digitar qualquer número.

## Fronteiras e Restrições

**Sempre:**
- O bloqueio é uma checagem de existência simples (`LotteryResult.objects.filter(game=, contest=).exists()`) — nenhuma tabela nova, nenhuma lógica de "concurso válido/sequencial".
- O aviso de duplicata já existente (jogo igual do mesmo usuário pro mesmo Jogo+Concurso) continua exatamente como está — os dois checks coexistem sem relação um com o outro (Consistency Conventions do spine).
- A sugestão de próximo concurso é só uma pré-preenchimento de UI (via JS, lendo um dict `{jogo: proximo_concurso}` exposto pelo `home` view) — nunca uma validação server-side que rejeita outros valores.
- Identificadores de código em inglês, sem exceção (parâmetros/locais inclusos) — convenção já estabelecida.

**Nunca:**
- Não bloquear `api_create_bet_view` (fora do mapeamento de capacidade da PRD/spine pra esta FR — só `create_bet_view`/`save_manual_bet_view`).
- Não validar que o número do concurso "faz sentido" (sequencial, dentro de um range) além do pré-preenchimento sugerido — um concurso especial/comemorativo sem `LotteryResult` é aceito normalmente, sem nenhuma checagem extra.
- Não tocar no aviso de duplicata existente (`GeneratedBet.objects.filter(user=, game=, contest=).exists()`) nem no bug já documentado em `deferred-work.md` sobre ele não interromper a criação (fora do escopo desta story).

</frozen-after-approval>

## Code Map

- `apps/loterias_core/utils.py` -- nova função `suggest_next_contest(game)`: pega `LotteryResult.objects.filter(game=game).values_list('contest', flat=True)`, converte cada valor pra `int` (ignora os que não convertem, ex. concurso especial não numérico), retorna `str(max(...) + 1)` como string, ou `None` se não houver nenhum `LotteryResult` pra esse Jogo ainda.
- `apps/loterias_core/views.py::create_bet_view` -- novo bloqueio logo após validar `selected_game`/`contest`: `if LotteryResult.objects.filter(game=selected_game, contest=contest).exists(): messages.error(request, f'O concurso {contest} de {selected_game} ja foi sorteado. Escolha outro concurso.'); return redirect('home')`. Fica **antes** do aviso de duplicata existente (que continua igual).
- `apps/loterias_core/views.py::save_manual_bet_view` -- mesmo bloqueio, no mesmo ponto relativo (após validar `selected_game`/`contest`/`raw_numbers`, antes do aviso de duplicata).
- `apps/loterias_core/views.py::home` -- context ganha `suggested_contests`: dict `{game_name: suggest_next_contest(game_name) para cada game_name em GAMES_CONFIG}` (só quando `request.user.is_authenticated`, mesmo padrão do resto do context).
- `templates/loterias_core/home.html` -- `{{ suggested_contests|json_script:"suggested-contests-data" }}` (ou dict equivalente exposto via contexto) + pequeno JS: ao selecionar um jogo (tanto no seletor de cards do formulário automático quanto no `<select>` do formulário manual), preenche o campo de concurso correspondente com o valor sugerido daquele jogo, se houver, sem impedir edição manual.
- `apps/loterias_core/tests.py` -- novos testes: (1) `create_bet_view` bloqueia quando já existe `LotteryResult` pro Jogo+Concurso, sem criar `GeneratedBet`; (2) `save_manual_bet_view` idem; (3) Jogo+Concurso sem `LotteryResult` continua funcionando normalmente (nenhuma regressão); (4) `suggest_next_contest` retorna `None` sem `LotteryResult` nenhum pro Jogo; (5) `suggest_next_contest` retorna o maior contest numérico +1, ignorando um `LotteryResult` com `contest` não numérico (concurso especial).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/utils.py::suggest_next_contest` -- nova função conforme Code Map
- [x] `apps/loterias_core/views.py::create_bet_view` -- bloqueio de concurso já sorteado
- [x] `apps/loterias_core/views.py::save_manual_bet_view` -- bloqueio de concurso já sorteado
- [x] `apps/loterias_core/views.py::regenerate_bet_view` -- bloqueio de concurso já sorteado (achado na revisão, não estava no Code Map original)
- [x] `apps/loterias_core/views.py::home` -- context `concursos_sugeridos`
- [x] `templates/loterias_core/home.html` -- pré-preenchimento via JS nos 2 formulários
- [x] `apps/loterias_core/tests.py` -- 5 casos do Code Map + 6 casos adicionais da revisão

**Critérios de Aceite:**
- Dado um Jogo+Concurso que já tem `LotteryResult` registrado, quando o usuário tenta gerar (automático) ou salvar (manual) um `GeneratedBet` pra esse mesmo Jogo+Concurso, então o sistema bloqueia com uma mensagem clara, sem gravar o registro
- E um Concurso fora da sequência normal (especial/comemorativo) sem `LotteryResult` é aceito normalmente
- E o campo de Concurso continua pré-preenchido com uma sugestão (próximo concurso sequencial), mas aceita qualquer número informado

## Notas de Implementação

O bloqueio foi extraído pra uma função compartilhada `_block_if_contest_already_drawn(request, game, contest, redirect_to='home', **redirect_kwargs)` em `views.py` (evita duplicar a query/mensagem entre `create_bet_view`/`save_manual_bet_view`, e permite reusar em `regenerate_bet_view` com `redirect_to='bet_detail'`).

A revisão em 3 camadas achou um gap real fora do Code Map original: `regenerate_bet_view` ("refazer jogo") reaproveita `original_bet.contest` sem nenhuma checagem -- um usuário conseguiria contornar o bloqueio inteiro clicando em "refazer" numa aposta antiga cujo concurso já foi sorteado nesse meio-tempo. Corrigido aplicando o mesmo bloqueio nessa view (redirecionando pra `bet_detail` do jogo original, não pra `home`, já que faz mais sentido nesse contexto).

O JS de pré-preenchimento também tinha 2 falhas achadas na revisão: (1) trocar de jogo duas vezes deixava o campo com o valor da primeira sugestão mas o texto auxiliar com a segunda (dessincronia valor/rótulo) -- corrigido com um marcador `data-autofilled` que distingue "preenchido automaticamente" de "digitado pelo usuário", só sobrescrevendo no primeiro caso; (2) o `<select>` do formulário manual não disparava a sugestão pra sua opção inicial (só ao trocar, via evento `change`) -- corrigido chamando o preenchimento uma vez também no carregamento da página.

Suíte final: 107 testes no projeto inteiro (era 102 no fim da Story 2.1) -- 100% passando. `manage.py check` sem erro novo.

## Log de Triagem da Revisão

**Patches aplicados:**
1. `regenerate_bet_view` sem nenhum bloqueio -- contornava a regra inteira. *(Blind Hunter)*
2. Bloqueio duplicado literalmente em 2 views -- extraído pra `_block_if_contest_already_drawn`. *(Blind Hunter)*
3. JS: dessincronia valor/rótulo ao trocar de jogo 2x -- corrigido com marcador `data-autofilled`. *(Edge Case Hunter)*
4. JS: `<select>` manual não preenchia a sugestão da opção inicial sem troca -- corrigido chamando o preenchimento também no carregamento. *(Edge Case Hunter)*
5. 6 testes novos cobrindo os gaps achados pela Verification Gap Reviewer: conteúdo da mensagem de erro (`response.context['messages']`), as 2 condições coexistindo (bloqueio vence sobre o aviso de duplicata), `concursos_sugeridos`/`json_script` renderizado numa resposta HTTP real, concurso especial aceito no fluxo manual também, `api_create_bet_view` explicitamente não bloqueado (nega regressão futura), `regenerate_bet_view` bloqueado.

**Adiado (`deferred-work.md`, 3 itens):** `contest` sem normalização de zeros à esquerda/case enfraquecendo o bloqueio (mesma causa raiz já adiada na Story 2.1); `save_manual_bet_view` grava seu próprio `LotteryResult` logo após o bloqueio, criando uma dependência de "quem submete primeiro" entre 2 submissões quase simultâneas (não quebra, só é uma nuance de comportamento); N+1 de `suggest_next_contest` na `home` view (baixo volume hoje).

**Falso positivo (sem ação):** nenhum -- todos os achados dos 3 revisores foram confirmados como reais (patch ou defer).

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 87 testes, 100% passando
- `python manage.py test` (suíte completa) -- 107 testes, 100% passando
- `python manage.py check` -- sem erro novo
