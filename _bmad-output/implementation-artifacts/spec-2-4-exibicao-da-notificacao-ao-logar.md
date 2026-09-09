---
title: 'Exibição da notificação ao logar (badge no cabeçalho)'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '144f97bef71d92287c75480628ceadeb4b39f4eb'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Mesmo com `HitNotification` sendo gerada (Story 2.3), o usuário não tem nenhum jeito de saber que ganhou algo sem abrir cada jogo manualmente — a notificação existe só no banco.

**Approach:** Injetar a contagem de notificações não lidas em todo template via context processor (mesmo padrão de `apps.loterias_core.context_processors.theme_context`, já registrado no settings), e mostrar um badge (ícone de sino + contador) no cabeçalho, visível em toda página enquanto autenticado. O badge diferencia visualmente se há alguma notificação premiada entre as não lidas (cor distinta) ou só acertos sem prêmio. Clicar no badge leva pra uma tela nova (`notifications`) que lista as notificações não lidas — versão mínima só de leitura nesta story; a Story 2.5 estende essa mesma tela com o detalhe completo por item e a ação de marcar como lida.

## Fronteiras e Restrições

**Sempre:**
- A contagem/flag são injetadas via context processor (`apps/loterias_core/context_processors.py`), nunca calculadas dentro de cada view individualmente — mesmo padrão já estabelecido por `theme_context`.
- O badge só aparece quando há pelo menos 1 notificação não lida (`is_read=False`) do usuário logado — nunca um sino vazio ou contador zerado.
- Sem depender de JS/tempo real — o contexto é injetado no request/response normal do Django (recarrega a página pra atualizar), conforme a PRD já fecha essa decisão.
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não implementar a ação de marcar como lida nem o detalhe completo por notificação (jogo/concurso/números batidos/valor do prêmio) — isso é Story 2.5. A tela criada nesta story é só uma lista simples de leitura.
- Não tocar em `NotificationPreference` nem em envio de e-mail (Stories 2.6/2.7).
- Não mudar o comportamento de `HitNotification`/`fetch_daily_results` (Story 2.3, já fechada) — essa story só lê o que já existe.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/context_processors.py` -- nova função `notifications_context(request)`: se `request.user.is_authenticated`, calcula `unread = HitNotification.objects.filter(bet__user=request.user, is_read=False)`, retorna `{'unread_notifications_count': unread.count(), 'has_unread_won_notification': unread.filter(won=True).exists()}`; caso contrário retorna os mesmos 2 valores zerados/`False`.
- `loterias/settings/base.py` -- adiciona `'apps.loterias_core.context_processors.notifications_context'` à lista `TEMPLATES[0]['OPTIONS']['context_processors']`.
- `templates/base/base.html` -- novo item de navbar (ícone `bi-bell`/`bi-bell-fill` + badge `<span class="badge">`) antes do dropdown do usuário, visível só quando `unread_notifications_count > 0`; classe do badge muda conforme `has_unread_won_notification` (ex. `bg-warning`/`bg-success` pra premiada, `bg-secondary` pra só acerto sem prêmio); link pra `{% url 'notifications' %}`.
- `apps/loterias_core/views.py::notifications_view` (**novo**) -- `@login_required`, lista `HitNotification.objects.filter(bet__user=request.user, is_read=False).select_related('bet')` (ordenação já vem do `Meta.ordering` do model), renderiza `loterias_core/notifications.html`. Só leitura nesta story -- nenhuma ação de marcar como lida.
- `apps/loterias_core/urls.py` -- nova rota `path('notificacoes/', notifications_view, name='notifications')`.
- `templates/loterias_core/notifications.html` (**novo**) -- lista simples: pra cada `HitNotification`, mostra `bet.game`, `bet.contest`, `bet.hits`, indicador visual de premiada (`won`) ou não; mensagem "sem notificações" quando a lista vier vazia.
- `apps/loterias_core/tests.py` -- novos testes: (1) `notifications_context` retorna contagem correta e `has_unread_won_notification` correto (com e sem notificação premiada); (2) usuário sem notificação não lida recebe contagem 0; (3) notificação já lida (`is_read=True`) não conta; (4) badge não aparece no HTML renderizado quando a contagem é 0 (`assertNotContains`); (5) badge aparece com o contador certo quando há notificação não lida; (6) `notifications_view` lista só as notificações do usuário logado, não as de outros; (7) `notifications_view` exige login.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/context_processors.py::notifications_context` -- nova função (+ falha suave e 1 query via `aggregate`, achados na revisão)
- [x] `loterias/settings/base.py` -- registrar o novo context processor
- [x] `apps/loterias_core/views.py::notifications_view` -- nova view, só leitura (+ paginação, achado na revisão)
- [x] `apps/loterias_core/urls.py` -- rota `notifications`
- [x] `templates/loterias_core/notificacoes.html` -- novo template, lista simples (nome do arquivo em português, consistente com os irmãos do diretório -- corrigido na revisão)
- [x] `templates/base/base.html` -- badge no cabeçalho, movido pra fora do `navbar-collapse` (achado crítico na revisão: ficava escondido no menu hambúrguer no mobile)
- [x] `apps/loterias_core/tests.py` -- 7 casos do Code Map + 8 casos adicionais da revisão

**Critérios de Aceite:**
- Dado que o usuário tem Notificação(ões) de Acerto não lida(s), quando ele autentica no sistema, então vê um badge numérico no cabeçalho (ícone de sino + contador, junto do nome/avatar do usuário), resumindo a quantidade de notificações não lidas — visível em toda página enquanto estiver logado, sem depender de JS/tempo real
- E o badge diferencia visualmente acertos premiados de não premiados no resumo
- E clicar no badge leva direto à tela de detalhe (versão mínima nesta story; Story 2.5 completa)
- E se o usuário não tem notificação pendente, o badge não aparece

## Notas de Implementação

A revisão em 3 camadas achou um problema real contra o próprio Critério de Aceite: o sino ficava dentro do `<div class="collapse navbar-collapse">`, que o Bootstrap esconde por padrão em telas menores que 992px até o usuário abrir o menu hambúrguer -- ou seja, no celular o usuário não via nenhum sinal de notificação nova ao carregar a página, contrariando "visível em toda página enquanto estiver logado". Corrigido movendo o link do sino pra fora do `navbar-collapse`, entre a marca e o botão hambúrguer -- fica sempre visível, em qualquer largura de tela.

Também corrigido: `notifications_context` não tinha `try/except` -- como roda em **todo** request autenticado (context processor global), uma exceção ali derrubaria o site inteiro com 500, não só o badge. Agora falha suave (conta zerada), e usa `aggregate()` (1 query) em vez de `count()`+`filter().exists()` (2 queries) -- reduz o custo fixo pago em cada página. `notifications_view` ganhou paginação (`Paginator`, mesmo padrão de `history_view`, que já a usava), já que nada nesta story marca notificação como lida ainda -- a lista só cresceria sem limite até a Story 2.5. O template novo foi renomeado de `notifications.html` pra `notificacoes.html`, consistente com os nomes em português dos templates irmãos (`historico.html`, `estatisticas.html`) -- mesma tensão já registrada em `deferred-work.md` desde a Story 1.3, evitada aqui por já nascer certa.

Suíte final: 134 testes no projeto inteiro (era 129 no fim da Story 2.3, que por sua vez ganhou +1 teste na correção da regra da Lotomania) -- 100% passando.

## Log de Triagem da Revisão

**Patches aplicados:**
1. Badge escondido no mobile (dentro do `navbar-collapse`) -- contrariava o próprio Critério de Aceite. *(Edge Case Hunter)*
2. `notifications_context` sem `try/except` -- uma falha ali derruba o site inteiro (500 geral), não só o badge. *(Edge Case Hunter)*
3. 2 queries reduzidas a 1 via `aggregate()`. *(Blind Hunter + Edge Case Hunter, achado independente)*
4. `notifications_view` sem paginação -- corrigido com o mesmo `Paginator` já usado em `history_view`. *(Blind Hunter + Edge Case Hunter, achado independente)*
5. Template `notifications.html` (inglês) renomeado pra `notificacoes.html`, consistente com os irmãos do diretório. *(Blind Hunter)*
6. `aria-label`/`visually-hidden` adicionados ao badge pra acessibilidade. *(Edge Case Hunter)*
7. Link "ver jogo" (`bet_detail`) adicionado a cada linha da lista -- a tela não tinha nenhuma ação possível antes. *(Blind Hunter)*
8. 8 testes novos cobrindo os gaps achados pela Verification Gap Reviewer: classe CSS do badge pra `won=True`/`won=False`, badge aparecendo em outra página além da home, múltiplas notificações com ordenação e conteúdo renderizado (jogo/concurso/status), mensagem de estado vazio, visualizar a lista não marca como lida, e `assertRedirects` de verdade pro teste de login (em vez de só `assertNotEqual(200)`).

**Adiado (`deferred-work.md`, 3 itens):** sem link permanente na navbar pra revisitar notificações já lidas (só faz sentido decidir junto da Story 2.5); contador do badge sem teto visual tipo "99+"; sem índice composto `bet__user`+`is_read` (baixo volume hoje).

**Falso positivo (sem ação):** inconsistência de nomenclatura apontada entre as chaves do context processor (`unread_notifications_count`, inglês) e as chaves de contexto de view (`notificacoes`, português) -- na verdade consistente com o precedente já estabelecido por `theme_context` (`theme`, `is_dark`, também inglês), que é a mesma categoria de coisa (saída de context processor global, não contexto de view). Reafirmado, sem mudança.

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 114 testes, 100% passando
- `python manage.py test` (suíte completa) -- 134 testes, 100% passando
- `python manage.py check` -- sem erro novo
