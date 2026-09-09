---
title: 'Envio de e-mail de acerto premiado'
type: 'feature'
created: '2026-09-09'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '5d21d7dbd37cdd3e54b212e6afdd8f5b427f551b'
context: ['_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `NotificationPreference.email_enabled` existe desde a Story 2.6, mas nada ainda lê esse campo — habilitar e-mail hoje não tem nenhum efeito. O usuário que ganha um prêmio só fica sabendo se abrir o site.

**Approach:** Estender `jobs._notify_covered_bets` (Story 2.3): no exato ponto em que `HitNotification.objects.get_or_create(...)` retorna `created=True` **e** a notificação é premiada (`prize['won']`), consulta `NotificationPreference` do usuário (ausência de linha = `email_enabled=False`, default já estabelecido na Story 2.6) e, se `email_enabled=True`, envia um e-mail via `send_mail` (mesmo padrão já usado em `apps/accounts/signals.py::send_welcome_email` — plain text, `fail_silently=True`, `try/except` isolado). Falha no envio nunca afeta a criação/exibição da notificação (o e-mail é disparado depois que a notificação já foi persistida com sucesso).

## Fronteiras e Restrições

**Sempre:**
- E-mail só é disparado quando `HitNotification.objects.get_or_create(...)` retorna `created=True` (AD-4) — uma reexecução da rotina que encontra a notificação já existente nunca reenvia.
- E-mail só é disparado quando `prize['won'] is True` — um acerto não premiado nunca dispara e-mail, independente da preferência do usuário.
- Ausência de `NotificationPreference` pro usuário é lida como `email_enabled=False` (default já estabelecido, Story 2.6/AD-3) — sem preferência configurada, sem e-mail.
- Falha ao enviar e-mail (SMTP Brevo fora do ar, credencial inválida, etc.) é isolada num `try/except` dedicado — nunca interrompe o resto da varredura de notificação nem desfaz a criação da `HitNotification` (que já aconteceu antes da tentativa de envio).
- Mesmo padrão de envio já estabelecido em `apps/accounts/signals.py::send_welcome_email` (`send_mail` puro, texto simples, `fail_silently=True`, `settings.DEFAULT_FROM_EMAIL`) — sem introduzir um segundo mecanismo de e-mail (ex. templates HTML, fila assíncrona) nesta story.
- Identificadores de código em inglês, sem exceção — convenção já estabelecida.

**Nunca:**
- Não checar se o e-mail do usuário está verificado (allauth) antes de enviar — fora do escopo desta story (nenhuma FR pede isso).
- Não mudar o gatilho de geração de `HitNotification` em si (Story 2.3) — só adiciona o envio de e-mail no ramo `created=True` e `won=True`.
- Não implementar e-mail HTML/template rico nem fila assíncrona (Celery já foi removido do projeto, Story 2.1) — plain text síncrono, mesmo padrão do welcome e-mail.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/emails.py` (**novo arquivo**) -- `send_hit_notification_email(notification)`: monta assunto/corpo (jogo, concurso, acertos, categoria, valor do prêmio formatado via `django.utils.formats.number_format(bet.prize, decimal_pos=2)` -- mesma formatação pt-br já usada nos templates) e chama `send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [bet.user.email], fail_silently=True)` dentro de um `try/except Exception` com `logger.exception` (mesmo padrão de log já estabelecido em `jobs.py`).
- `apps/loterias_core/jobs.py::_notify_covered_bets` -- após `HitNotification.objects.get_or_create(bet=bet, defaults={'won': prize['won']})`: se `created` e `prize['won']`, consulta `NotificationPreference.objects.filter(user=bet.user).first()` e, se existir e `email_enabled=True`, chama `send_hit_notification_email(notification)`.
- `apps/loterias_core/tests.py` -- novos testes: (1) notificação nova e premiada com `email_enabled=True` dispara e-mail (`django.core.mail.outbox`); (2) notificação nova e premiada sem `NotificationPreference` (default `email_enabled=False`) não dispara e-mail; (3) notificação nova e premiada com `email_enabled=False` explícito não dispara e-mail; (4) notificação nova mas **não premiada** (`won=False`) nunca dispara e-mail, mesmo com `email_enabled=True`; (5) reexecução da rotina pro mesmo bet (notificação já existente, `created=False`) não reenvia e-mail; (6) falha no `send_mail` (mockado levantando exceção) não impede a criação da `HitNotification` nem interrompe o processamento de outros bets na mesma execução; (7) conteúdo do e-mail inclui jogo, concurso, acertos e valor do prêmio formatado em pt-br.

## Tarefas e Aceite

**Execução:**
- [x] `apps/loterias_core/emails.py::send_hit_notification_email` -- novo arquivo/função (função inteira dentro do try/except, não só o `send_mail` -- achado na revisão; + guarda contra e-mail vazio, igual ao `send_welcome_email`)
- [x] `apps/loterias_core/jobs.py::_notify_covered_bets` -- chama o envio de e-mail conforme Code Map (+ preferências buscadas em lote, evitando N+1 -- achado na revisão)
- [x] `apps/loterias_core/tests.py` -- 7 casos do Code Map + 6 casos adicionais da revisão

**Critérios de Aceite:**
- Dado que a preferência de notificação do usuário inclui e-mail, quando uma Notificação de Acerto premiada é criada pra ele, então ele recebe um e-mail via SMTP Brevo já configurado
- E um acerto não premiado nunca dispara e-mail, independente da preferência
- E se o envio de e-mail falhar, a notificação continua sendo criada/exibida normalmente no site
- E uma reexecução da rotina nunca reenvia o e-mail da mesma notificação — só dispara quando a notificação é criada pela primeira vez (`get_or_create` com `created=True`)

## Notas de Implementação

A revisão em 3 camadas achou dois problemas reais no `emails.py` original: (1) o `try/except` protegia só a chamada `send_mail(...)`, deixando a montagem da mensagem (`number_format`, f-strings) fora do bloco protegido -- um erro ali propagaria pro `try/except` genérico de `_notify_covered_bets`, que logaria uma mensagem enganosa ("falha ao processar o bet... pra notificação", quando a notificação já tinha sido criada com sucesso e só o e-mail teria falhado); (2) faltava a guarda contra e-mail vazio que o próprio padrão referenciado (`send_welcome_email`) já tem (`if created and instance.email:`). Corrigido: a função inteira ficou dentro do `try/except`, e um `if not user.email: return` foi adicionado antes de montar qualquer coisa.

Também corrigido um N+1 evitável: `NotificationPreference.objects.filter(user=bet.user).first()` rodava uma query por aposta premiada dentro do loop -- agora as preferências são pré-buscadas em lote (mesmo padrão já usado pra `LotteryResult` desde a Story 2.3/2.5) antes do loop começar.

Suíte final: 184 testes no projeto inteiro (era 178 no fim da Story 2.6) -- 100% passando.

## Log de Triagem da Revisão

**Patches aplicados:**
1. `try/except` de `emails.py` não cobria a montagem da mensagem, só o `send_mail` -- movido pra envolver a função inteira. *(Blind Hunter + Edge Case Hunter, achado independente)*
2. Faltava guarda contra `user.email` vazio (o padrão referenciado, `send_welcome_email`, já tem essa checagem). *(Edge Case Hunter)*
3. N+1 de `NotificationPreference` por aposta premiada -- corrigido com busca em lote antes do loop. *(Blind Hunter)*
4. Acento faltando no assunto do e-mail ("Voce" -> "Você"), inconsistente com o resto da própria mensagem e com o padrão referenciado. *(Blind Hunter)*
5. 6 testes novos cobrindo os gaps achados pela Verification Gap Reviewer: teste direto do `try/except` real de `emails.py` (mockando `send_mail`/`number_format` no próprio módulo, não só o wrapper de `jobs.py`), assunto e remetente do e-mail verificados (antes só o corpo/destinatário), asserções específicas por campo no corpo (`'Acertos: 5'` em vez de `'5'` solto, que também batia com o valor do prêmio), as 2 combinações de acerto-não-premiado que faltavam (`email_enabled=False` e sem preferência nenhuma), múltiplos usuários premiados na mesma execução (cada um recebe o próprio e-mail), e o guard de e-mail vazio.

**Adiado (`deferred-work.md`, 3 itens):** envio síncrono dentro do loop de cron (decisão consciente da própria fronteira desta story -- sem fila assíncrona); `prize_description` expondo a chave interna crua no e-mail (mesma causa raiz já registrada na Story 2.1); corpo do e-mail sem link/CTA concreto pro detalhe do jogo (exigiria configurar domínio via `django.contrib.sites`, fora do escopo).

**Falso positivo (sem ação):** nenhum -- todos os achados dos 3 revisores foram confirmados como reais (patch ou defer).

## Verificação

**Comandos executados:**
- `python manage.py test apps.loterias_core` -- 158 testes, 100% passando
- `python manage.py test` (suíte completa) -- 184 testes, 100% passando
- `python manage.py check` -- sem erro novo
