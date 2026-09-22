---
title: 'Story 5.3 — Entrar, criar conta e telas de conta no Lottiq Design System'
type: 'feature'
created: '2026-09-21'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '6ba00d4'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** As 11 telas de conta (entrar, cadastro, confirmação, reenvio, recuperação/criação de senha, perfil, completar cadastro) usam Bootstrap e crispy-forms.

**Approach:** Templates com os componentes do DS (`lq-auth-card`, campos, botões, banners), sem classes Bootstrap nem crispy. Um inclusion tag `{% lq_form form %}` (`apps/loterias_core/templatetags/lottiq_ui.py` + `templates/components/form.html`) renderiza qualquer Form Django com label, campo, ajuda e erro acessíveis (`aria-describedby`, `aria-invalid`), mantendo nomes/ids dos campos e todo o comportamento existente.

</frozen-after-approval>

## Implementation Notes

- Comportamento preservado: cooldown de reenvio (mesmo script e ids), mensagens genéricas, botão "Mostrar/Ocultar senha", validações do allauth. O tag sobrescreve a `class` dos widgets (os forms de `accounts` ainda setam `form-control`; limpar isso fica pra 5.7).
- Textos com acentuação correta (as telas antigas eram sem acento); um teste de `accounts` que assertava "Vinculo expirado ou invalido" foi atualizado pra "Vínculo expirado ou inválido".
- A tela de perfil perdeu o selo "Light/Dark Mode" (tema escuro fica pra próxima rodada) e mantém "Resumo da conta".
- crispy segue instalado: `preferencias_notificacao.html` ainda o usa (Story 5.6); removido na 5.7.
- Suíte: 415 testes OK. Não verificado em navegador.
