---
title: 'Story 7.3 — Zona reservada pro Google AdSense'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-7-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Não existe nenhum espaço reservado no layout pra futuros anúncios — se o AdSense for ativado um dia, a página inteira precisaria ser redesenhada.

**Approach:** Um bloco `{% block ad_zone %}` em `base/base.html`, entre o conteúdo e o rodapé, presente em toda página — visível (moldura tracejada, rótulo "Espaço reservado"), sem nenhuma integração real (sem conta, sem script do Google).

</frozen-after-approval>

## Implementation Notes

- `templates/base/base.html`: `{% block ad_zone %}` entre `</main>`/`{% block content %}` e o `<footer>` -- sempre depois de qualquer form/conteúdo da página (nunca dentro do fluxo de gerar/conferir jogo), com `role="complementary"` e rótulo honesto "Espaço reservado" (não finge ser um anúncio real). Componente `.lq-ad-zone` novo em `lottiq.css` (moldura tracejada, sem cor "de anúncio").
- Presente em toda página por padrão (inclusive telas de conta) -- decisão deliberada de simplicidade: um único ponto de manutenção em vez de precisar lembrar de incluir em cada template.
- Suíte: 437 testes OK (436 + 1 novo, cobrindo home/histórico/estatísticas e confirmando ausência de qualquer script real do Google).
