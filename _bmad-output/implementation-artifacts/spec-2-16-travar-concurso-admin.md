---
title: 'Travar Concurso Não Normalizado no Django Admin'
type: 'bugfix'
created: '2026-09-14'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: '8ef0caf'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `contest` continua editável como texto livre em `GeneratedBetAdmin`/`LotteryResultAdmin`
(ausente de `readonly_fields`), nunca passando por `normalize_contest` -- um operador editando/criando
direto pelo admin recria o bug de duas grafias pro mesmo concurso real que a Story 2.12 corrigiu nas
3 views públicas.

**Approach:** Decisão do Boss: travar. Um `ModelForm` mixin (`_NormalizedContestFormMixin`) com
`clean_contest` que chama `normalize_contest` (mesma função da Story 2.12) e levanta
`ValidationError` com mensagem clara em caso de valor inválido; atribuído via `ModelAdmin.form` nos
2 admins (`GeneratedBetAdmin`, `LotteryResultAdmin`). Abordagem de formulário (não `save_model`)
porque mostra o erro inline no campo, no padrão nativo do Django admin, em vez de um 500/crash.
Nenhuma mudança de comportamento pros demais campos.

</frozen-after-approval>

## Code Map

- `apps/loterias_core/admin.py::_NormalizedContestFormMixin` -- `clean_contest` chama
  `normalize_contest`, propaga a mensagem original via `str(e)`/`from e`. Aplicado em
  `GeneratedBetAdminForm`, `LotteryResultAdminForm` e `CaptureFailureAlertAdminForm` (estendido na
  revisão -- mesmo risco de `unique_together` com `contest` livre).
- `apps/loterias_core/tests.py::AdminSmokeTests` -- 7 casos novos: normaliza/rejeita ao criar (2
  admins), normaliza ao editar, colisão real via `unique_together` depois de normalizar, e
  `CaptureFailureAlert`.

## Implementation Notes

Revisão em 3 camadas (Blind Hunter, Edge Case Hunter, Verification Gap Reviewer) sobre o diff
(~5.1kB, N=3). Patches aplicados: `except ValueError as e: raise ValidationError(str(e)) from e` (
evita duplicar a mensagem e a cadeia de exceção ruidosa); teste de edição (não só criação, que era
o relato original do bug); teste que prova a normalização fechando a colisão real via
`unique_together` (não só "valor normalizado" isolado); estendida a mesma proteção pro
`CaptureFailureAlertAdmin` (mesma classe de risco, achado do Blind Hunter). Um achado de baixíssimo
impacto deferido: `max_length=20` nativo do Django rejeita (com mensagem enganosa) um valor
hipotético de 20+ zeros à esquerda antes de `clean_contest` rodar -- cenário sem uso prático real.

## Verificação

**Comandos executados:**
- `./.venv/Scripts/python.exe manage.py test apps.loterias_core apps.accounts` -- **314 testes, OK**
  (era 307 antes desta story), `.venv` pinado (Python 3.11/Django 5.0.6).