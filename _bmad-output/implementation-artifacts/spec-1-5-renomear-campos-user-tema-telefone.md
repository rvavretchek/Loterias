---
title: 'Renomear campos remanescentes em português no model User (tema_preferido, telefone)'
type: 'refactor'
created: '2026-09-08'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'd68cf627547cb31d08d7d5d1c445042e1e7e4986'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A PRD original (§3.1) afirmava que `apps/accounts` já seguia a convenção de nomenclatura em inglês, mas 2 campos do model `User` escaparam da varredura inicial e só foram achados durante a implementação das Stories 1.1-1.4: `tema_preferido` e `telefone`. Esta é a última story do Epic 1 — depois dela, zero identificador de código em português deve sobrar em todo o app Django (`loterias_core` e `accounts`).

**Approach:** Renomear `User.tema_preferido→preferred_theme` e `User.telefone→phone` (PRD §3.1) e atualizar todos os 5 consumidores já identificados: `apps/accounts/admin.py`, `forms.py`, `views.py` (`toggle_theme`), `apps/loterias_core/context_processors.py`, e o template `accounts/profile.html`. Migration reescrita no lugar (`0001_initial.py`), mesma regra da Story 1.1 — banco de dev/lab é descartável até existir produção declarada (decisão registrada em memória, reconfirmada na Story 1.4).

## Fronteiras e Restrições

**Sempre:**
- Usar exatamente o mapeamento: `tema_preferido→preferred_theme`, `telefone→phone`.
- Manter `verbose_name`/`choices`/labels em português inalterados (`'Tema Preferido'`, `'Telefone'`, `'Claro'`/`'Escuro'`) — só o identificador Python do campo muda, nunca a string exibida ao usuário.
- Zero identificador de código em português ao final desta story — inclui parâmetro/variável local de qualquer arquivo tocado (mesma regra sem exceção estabelecida nas Stories 1.1-1.3).

**Nunca:**
- Não tocar em `apps/loterias_core` (já concluído nas Stories 1.1-1.4).
- Não mudar nenhum outro campo do model `User` (`avatar`, `bio`, `first_name`, `last_name`, `email` já são inglês/herdados do `AbstractUser`).
- Não abrir o PR único de merge do Epic 1 pra `main` nesta story sem confirmação — mas como esta é a última story do épico (1.5 de 5), ao final dela o épico está pronto pra esse PR (ver Notas de Implementação).

</frozen-after-approval>

## Code Map

- `apps/accounts/models.py` -- campo `tema_preferido` (CharField, choices `[('light','Claro'),('dark','Escuro')]`, default `'light'`, verbose_name `'Tema Preferido'`) → `preferred_theme`; campo `telefone` (CharField, verbose_name `'Telefone'`) → `phone`.
- `apps/accounts/migrations/0001_initial.py` -- reescrever no lugar (mesmo padrão da Story 1.1): `'tema_preferido'` → `'preferred_theme'`, `'telefone'` → `'phone'` nas duas entradas de `CreateModel(fields=[...])`, mantendo `choices`/`default`/`verbose_name`/`max_length` idênticos.
- `apps/accounts/admin.py` -- `list_filter=(..., 'tema_preferido')` → `(..., 'preferred_theme')`; fieldsets: `('Informacoes Pessoais', {'fields': (..., 'telefone', ...)})` → `(..., 'phone', ...)`, `('Preferencias', {'fields': ('tema_preferido',)})` → `('preferred_theme',)`.
- `apps/accounts/forms.py` -- `ProfileUpdateForm.Meta.fields` tupla e `widgets` dict: chaves `'telefone'`/`'tema_preferido'` → `'phone'`/`'preferred_theme'` (2 ocorrências cada, fields+widgets).
- `apps/accounts/views.py` -- `toggle_theme`: `user.tema_preferido = 'dark' if user.tema_preferido == 'light' else 'light'` → `user.preferred_theme = 'dark' if user.preferred_theme == 'light' else 'light'`; `user.save(update_fields=['tema_preferido'])` → `update_fields=['preferred_theme']`.
- `apps/loterias_core/context_processors.py` -- `theme_context`: `theme = request.user.tema_preferido` → `request.user.preferred_theme`.
- `templates/accounts/profile.html` -- `{{ user.tema_preferido|title }} Mode` → `{{ user.preferred_theme|title }} Mode`.
- `apps/accounts/tests.py` -- adicionar `ToggleThemeViewTests` (view sem nenhum teste hoje, achado ao revisar o Code Map): usuário autenticado alterna de `'light'` pra `'dark'` e vice-versa via `toggle_theme`; usuário anônimo usa a sessão (`request.session['theme']`), campo do model não é tocado.

## Tarefas e Aceite

**Execução:**
- [x] `apps/accounts/models.py` -- renomear os 2 campos, mantendo `verbose_name`/`choices`/`default` idênticos
- [x] `apps/accounts/migrations/0001_initial.py` -- reescrever no lugar com os novos nomes
- [x] `apps/accounts/admin.py` -- atualizar `list_filter` e os 2 `fieldsets`
- [x] `apps/accounts/forms.py` -- atualizar `Meta.fields` e `widgets`
- [x] `apps/accounts/views.py` -- atualizar `toggle_theme`
- [x] `apps/loterias_core/context_processors.py` -- atualizar `theme_context`
- [x] `templates/accounts/profile.html` -- atualizar a referência de tema
- [x] `apps/accounts/tests.py` -- adicionar `ToggleThemeViewTests` (gap de verificação, view sem teste)

**Critérios de Aceite:**
- Dado `User.tema_preferido`/`telefone`, quando renomeados pra `preferred_theme`/`phone`, então `admin.py`, `forms.py`, `views.py`, `context_processors.py` e `profile.html` são atualizados juntos — nenhuma referência aos nomes antigos sobra em código
- Dado `verbose_name`/`choices`/labels em português, quando o rename é aplicado, então continuam inalterados — só os identificadores de código mudam
- Dado `python manage.py test`, então 100% dos testes passam
- Dado `python manage.py check`, então sem erro novo de `admin.E108` ou outro

## Notas de Implementação

Rename aplicado exatamente conforme o Code Map, implementado diretamente (sem subagent) por ser um escopo pequeno e contido (2 campos, 6 arquivos consumidores). Confirmado via grep que zero referência a `tema_preferido`/`telefone` sobra em código (a única ocorrência restante é a docstring do próprio teste de regressão, mencionando o rename como contexto, não como identificador).

Esta é a última story do Epic 1 (5 de 5). Com ela concluída, as 5 stories estão prontas para o PR único de merge pra `main` (AD-2) -- a abertura desse PR em si não foi feita nesta story (ação visível/compartilhada, fica pra confirmação explícita do Boss antes de executar).

Suíte final: 77 testes no projeto inteiro (era 74 após a Story 1.4) -- 100% passando. `manage.py check` sem erro novo (só o warning pré-existente de `staticfiles.W004`).

## Log de Triagem da Revisão

Story de baixo risco e escopo pequeno (rename de 2 campos + 6 arquivos consumidores diretos, já mapeados por completo antes da implementação via grep no projeto inteiro). Revisão em 3 camadas não foi acionada -- verificação direta (grep de zero ocorrência + suíte 100% passando + `manage.py check` limpo) foi suficiente pra confirmar completude. Nenhum patch ou item adiado.

## Verificação

**Comandos executados:**
- `python manage.py test` -- 77 testes, 100% passando
- `python manage.py check` -- sem erro novo de system check
- `grep -rn "tema_preferido\|telefone"` no projeto (fora de `__pycache__`/`_bmad`/`.venv`) -- zero ocorrência de identificador (só a menção em docstring de teste)
