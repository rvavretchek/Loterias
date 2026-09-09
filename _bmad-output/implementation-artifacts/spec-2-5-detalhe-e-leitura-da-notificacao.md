---
title: 'Detalhe e leitura da notificação'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '974d05b210d4612fcf651b07f32cf1c109b7959e'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A Story 2.4 entregou uma versão mínima só de leitura da tela de notificações (jogo, concurso, contagem de acertos, premiada ou não) — falta mostrar quais números bateram, o valor do prêmio quando houver, e a ação de marcar cada notificação como lida individualmente.

**Approach:** Estender a mesma tela (`notifications_view`/`notificacoes.html`, Story 2.4) em vez de criar uma nova: pra cada `HitNotification`, buscar o `LotteryResult` do Jogo+Concurso do bet (em lote, evitando N+1) e calcular a interseção com `bet.numbers` pra mostrar os números batidos; mostrar `bet.prize` formatado quando `won=True` (ou "Sem prêmio" quando não); adicionar um botão "marcar como lida" por notificação, via POST numa rota nova, que redireciona de volta pra mesma lista. Marcar como lida não afeta as demais notificações, e some do badge (FR-4) e da própria lista na próxima carga, já que ambos já filtram por `is_read=False`.

## Fronteiras e Restrições

**Sempre:**
- A ação de marcar como lida é um POST idempotente por notificação (`HitNotification.objects.filter(pk=, bet__user=request.user).update(is_read=True)`) — nunca afeta outra notificação além da que foi clicada.
- Números batidos são calculados como a interseção real entre `bet.numbers` e o `LotteryResult.numbers` do mesmo Jogo+Concurso — nunca um valor inventado ou só a contagem (`bet.hits`) sem os números em si.
- Busca de `LotteryResult` em lote (1 query pro conjunto de notificações da página, não 1 por notificação) — mesmo padrão já usado em `jobs._notify_covered_bets` (Story 2.3).
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não criar uma tela/rota nova separada — estende a mesma `notifications_view`/`notificacoes.html` da Story 2.4.
- Não mudar o comportamento do badge (`notifications_context`, Story 2.4) nem da varredura de geração (`fetch_daily_results`, Story 2.3) — essa story só consome o que já existe e adiciona a ação de leitura.
- Não implementar preferência de canal nem e-mail (Stories 2.6/2.7).

</frozen-after-approval>

## Code Map

- `apps/loterias_core/views.py::notifications_view` -- busca `LotteryResult` em lote pro conjunto de (game, contest) das notificações da página atual (mesmo padrão de dict `{(game,contest): LotteryResult}` de `jobs._notify_covered_bets`); anexa a cada notificação (via atributo dinâmico, ex. `notification.matched_numbers`) a lista ordenada de números batidos (interseção `bet.numbers`/`LotteryResult.numbers`), ou lista vazia se o `LotteryResult` não for encontrado (não deveria acontecer na prática, mas falha soft).
- `apps/loterias_core/views.py::mark_notification_read_view` (**novo**) -- `@login_required`, `@require_POST`, recebe `pk`; `HitNotification.objects.filter(pk=pk, bet__user=request.user).update(is_read=True)` (não usa `get_object_or_404`+`save()` pra já garantir no filtro que só o dono pode marcar a própria notificação — um `pk` de outro usuário simplesmente não casa com o filtro e não faz nada, sem vazar erro 404 revelando existência); redireciona pra `notifications`.
- `apps/loterias_core/urls.py` -- nova rota `path('notificacoes/<int:pk>/lida/', views.mark_notification_read_view, name='mark_notification_read')`.
- `templates/loterias_core/notificacoes.html` -- por notificação: nova célula com os números batidos (estilo `numero-bola`, igual ao usado em `historico.html`/`home.html`), nova célula com o valor do prêmio formatado (`bet.prize` quando `won`, ou "Sem premio"); novo botão/form POST "marcar como lida" na coluna de ações, ao lado do link "ver jogo" já existente.
- `apps/loterias_core/tests.py` -- novos testes: (1) números batidos calculados corretamente e exibidos na tela; (2) valor do prêmio exibido quando `won=True`, "Sem premio" quando `won=False`; (3) marcar como lida via POST atualiza só a notificação clicada, sem afetar outras do mesmo usuário; (4) marcar como lida de uma notificação de outro usuário não tem efeito (403 implícito via filtro, sem erro); (5) notificação marcada como lida some da lista na carga seguinte e do badge (`unread_notifications_count`); (6) rota de marcar como lida exige login e só aceita POST (`GET` não marca nada).

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/views.py::notifications_view` -- números batidos calculados em lote conforme Code Map, com `normalize_numbers()` (achado na revisão)
- [x] `apps/loterias_core/views.py::mark_notification_read_view` -- nova view (+ preserva `?page=N` via campo `next`, mensagem de confirmação, achados na revisão)
- [x] `apps/loterias_core/urls.py` -- rota `mark_notification_read`
- [x] `templates/loterias_core/notificacoes.html` -- números batidos, valor do prêmio, botão marcar como lida (+ `aria-label`, nota pro caso Lotomania 0 acertos premiado, achados na revisão)
- [x] `apps/loterias_core/tests.py` -- 6 casos do Code Map + 11 casos adicionais da revisão

**Critérios de Aceite:**
- Dado que cliquei no indicador de notificações, quando a tela de detalhe abre, então vejo a lista de Notificações de Acerto pendentes, cada uma identificando claramente o tipo de Jogo e o número do Concurso
- E cada item mostra os números batidos e o valor do prêmio (se houver)
- E posso marcar cada notificação como lida individualmente, sem afetar as demais
- E uma notificação marcada como lida não volta a aparecer no indicador de FR-4

## Notas de Implementação

A revisão em 3 camadas achou uma inconsistência de domínio real: os números batidos eram calculados por interseção crua (`set(bet.numbers) & set(result.numbers)`), diferente de `calculate_bet_prize` (que gerou `bet.hits`), que passa os dois lados por `normalize_numbers()` antes de comparar. Como `numbers` é `JSONField` sem validação de tipo, um dado legado com strings numéricas (`'1'` em vez de `1`) faria a tela mostrar uma quantidade de bolinhas diferente da contagem `bet.hits` ao lado. Corrigido usando `normalize_numbers()` nos dois lados, igual ao domínio já estabelecido.

Outros ajustes da revisão: `mark_notification_read_view` agora preserva a página de origem (campo oculto `next` no form, validado como caminho relativo antes de redirecionar — proteção simples contra open redirect) e sempre mostra a mensagem de confirmação **independente** de a notificação realmente existir/pertencer ao usuário (do contrário, a ausência da mensagem vazaria essa informação, contradizendo o próprio design de `.filter().update()` sem `get_object_or_404`). Adicionado log de aviso quando um `LotteryResult` esperado não é encontrado (não deveria acontecer, mas antes falhava em silêncio total). Célula de "números batidos" ganhou uma nota específica pro caso Lotomania premiada com 0 acertos (sem isso, a combinação "prêmio em R$" + "nenhuma bolinha destacada" podia parecer inconsistência de dado pro usuário).

Suíte final: 150 testes no projeto inteiro (era 141 no fim da Story 2.4) -- 100% passando.

## Log de Triagem da Revisão

**Patches aplicados:**
1. `matched_numbers` calculado sem `normalize_numbers()` -- podia divergir silenciosamente de `bet.hits`. *(Edge Case Hunter)*
2. `mark_notification_read_view` não preservava a página de origem -- usuário na página 2+ sempre voltava pra página 1 depois de marcar como lida. *(Edge Case Hunter)*
3. Nenhuma mensagem de confirmação após marcar como lida -- adicionada, e deliberadamente incondicional (não checa se a notificação existia) pra não vazar essa informação via ausência da mensagem. *(Blind Hunter, ajustado pra preservar a garantia de não-vazamento já intencional na view)*
4. `LotteryResult` ausente pra uma notificação caía em lista vazia sem nenhum log -- adicionado `logger.warning`. *(Edge Case Hunter)*
5. `aria-label` adicionado aos botões de ação (antes só `title`). *(Edge Case Hunter)*
6. `btn-group` não funcionava visualmente com um `<form>` no meio (Bootstrap só estiliza filhos diretos) -- trocado por um container flex simples com gap. *(Blind Hunter)*
7. Nota "Prêmio por 0 acertos" adicionada pro caso Lotomania, evitando a aparência de inconsistência (prêmio em R$ sem nenhum número destacado). *(Edge Case Hunter)*
8. 11 testes novos cobrindo os gaps achados pela Verification Gap Reviewer: 2 notificações compartilhando o mesmo `LotteryResult`, 2 notificações com `LotteryResult`s diferentes na mesma página (busca em lote de verdade), texto exato dos números renderizados (não só a contagem), placeholder "sem resultado" exibido, formulário/botão de marcar como lida presente no HTML renderizado, pk inexistente não gera erro, equivalência de resposta entre notificação própria/de outro usuário/inexistente (garantia de não-vazamento), preservação de página via `next`, e rejeição de `next` apontando pra fora do site.

**Adiado (`deferred-work.md`, 2 itens):** busca em lote de `LotteryResult` com produto cartesiano (mesmo padrão de `jobs.py`, sem bug de correção, só ineficiência); marcar como lida sem confirmação/desfazer (decisão de produto, não bug).

**Falso positivo (sem ação):** nenhum -- todos os achados dos 3 revisores foram confirmados como reais (patch ou defer).

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 130 testes, 100% passando
- `python manage.py test` (suíte completa) -- 150 testes, 100% passando
- `python manage.py check` -- sem erro novo
