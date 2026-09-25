---
title: 'Story 7.5 — Tela de consentimento de cookies (LGPD)'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Não existe hoje nenhum cookie de rastreamento real no Lottiq (sem analytics, sem AdSense ativo) -- mas a Story 7.3 já reservou o espaço pra futuro AdSense, e ativá-lo de verdade um dia vai exigir consentimento prévio (LGPD). Sem essa peça agora, a ativação futura fica bloqueada até alguém lembrar de construir isso.

**Approach:** Puramente preparatório -- sem model novo, sem JS de terceiro. Um cookie próprio de 1ª parte (`lottiq_cookies`, JSON, `httponly`) grava a decisão do visitante (necessários sempre ativos, analytics e marketing/anúncios como categorias opcionais). Banner fixo no rodapé da viewport, 3 ações (aceitar tudo / recusar tudo / configurar por categoria), aparece em toda página até haver decisão. Link no rodapé do site ("Preferências de cookies") reabre o banner a qualquer momento pra revisão.

</frozen-after-approval>

## Implementation Notes

- `apps/loterias_core/context_processors.py`: `cookie_consent_context` lê `request.COOKIES['lottiq_cookies']` (JSON), devolve `cookie_consent` (`None` = ainda sem decisão) ou dict `{necessary: True, analytics: bool, marketing: bool}`. JSON inválido/corrompido tratado como `None` (mostra o banner de novo, nunca quebra a página) -- mesmo padrão de falha-soft do `notifications_context`. Registrado em `TEMPLATE_CONTEXT_PROCESSORS`.
- `apps/loterias_core/views.py`: `save_cookie_consent_view` (`@require_POST`) -- 3 caminhos (`choice`: `accept_all`, `reject_all`, `custom` com checkboxes `analytics`/`marketing` do form). Redirect via `next` (POST, validado com `url_has_allowed_host_and_scheme`, mesmo padrão já usado em `mark_notification_read_view`) -- nunca via `HTTP_REFERER` direto. `response.set_cookie('lottiq_cookies', ..., max_age=365 dias, samesite='Lax', httponly=True)`.
- `apps/loterias_core/urls.py`: `cookies/preferencias/` -> `save_cookie_consent`.
- `apps/accounts/middleware.py`: `save_cookie_consent` adicionado a `EXEMPT_URL_NAMES` (mesmo motivo do `toggle_theme` -- o banner aparece em toda página, inclusive `complete_profile`, e precisa continuar funcionando com perfil incompleto).
- `templates/base/base.html`: banner fixo (`.lq-cookie-banner`) mostrado quando `not cookie_consent` OU `request.GET.revisar_cookies` está presente -- 2 botões diretos (aceitar/recusar, cada um um form próprio) + botão "Configurar" que revela (JS inline, sem lib nova, mesmo padrão do dismiss de banner já existente) um terceiro form com as 3 categorias (necessários sempre marcado/desabilitado, analytics e marketing como checkbox, pré-marcados conforme a decisão anterior quando já existe uma). Rodapé ganhou o link "Preferências de cookies" (`?revisar_cookies=1`), sempre visível.
- Categorias analytics/marketing não controlam nada de verdade ainda (nenhum script real existe) -- são só a base pronta pro dia em que a Story 7.3 for ativada de verdade.
- Suíte: cobre (a) banner aparece sem cookie de decisão, some quando existe, (b) aceitar tudo / recusar tudo / customizar gravam os 3 valores certos no cookie, (c) cookie corrompido não quebra a página (volta a mostrar o banner), (d) `save_cookie_consent` isento do gate de perfil incompleto, (e) link "Preferências de cookies" reabre o banner mesmo com decisão já tomada, com as categorias pré-marcadas conforme a decisão anterior, (f) GET não permitido no endpoint (405).
- Achado durante a implementação: um teste já existente (`test_default_checkboxes_rendered_correctly_in_html`, preferências de notificação) contava `type="checkbox"` na página inteira esperando exatamente 2 -- passou a contar também as 3 checkboxes do banner global de cookies. Corrigido restringindo a contagem ao form de notificação (`<form method="post">...</form>`), não é mais uma regressão real, é a página inteira mesmo tendo mais checkboxes agora.
- Verificado ao vivo via curl contra o servidor de desenvolvimento local: banner aparece sem cookie, `POST /cookies/preferencias/` com `choice=accept_all` grava `Set-Cookie: lottiq_cookies=...; HttpOnly; Max-Age=31536000; SameSite=Lax` com os 3 valores `true`, banner some na visita seguinte, `?revisar_cookies=1` reabre com as categorias pré-marcadas.
- Suíte completa: 451 testes OK (440 + 13 novos, com 1 ajuste em teste pré-existente).
