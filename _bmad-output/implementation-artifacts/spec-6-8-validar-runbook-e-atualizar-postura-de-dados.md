---
title: 'Story 6.8 — Validar o runbook de backup/restore e atualizar a postura de dados do lab'
type: 'feature'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/implementation-artifacts/epic-6-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O runbook de backup/validação de migration (`deploy/lab/README.md`) nunca foi exercitado de verdade — sem saber se funciona, a "postura de não destruir mais dado" que o Boss decidiu não tem lastro nenhum.

**Approach:** Rodar o drill completo contra o volume real do lab (ubt-host01), corrigir o runbook com o que o drill revelou, e substituir a nota "pode ser recriado livremente" por uma postura condizente com homologação tratada como produção pra dados.

</frozen-after-approval>

## Implementation Notes

- Drill executado de ponta a ponta em 2026-09-23 contra `ubt-host01` (SSH já configurado de sessão anterior). Sem migration pendente pra aplicar de verdade (local e no lab batiam) — o drill validou o *mecanismo* (backup, cópia, validação, comparação de contagem/amostra), não uma migration real.
- **2 achados reais que corrigiram o runbook:** (1) `deploy/lab/.env` é `-rw-------` (só root) — `docker compose run`/`exec` falham com "permission denied" rodando como `operador01` (o Compose precisa ler o `.env` mesmo só pra montar a config); a correção usa `docker run` direto com `-e` explícito (valores dummy pra `SECRET_KEY`/`PASSWORD_PEPPER`, que não afetam leitura/migration de dado) pra validação, e `docker exec <container-já-rodando>` (não `docker compose exec`) pra checagem no volume real. (2) `/opt/loterias-backups` não existia — o próprio `docker run` do passo 1 cria o diretório sozinho (o daemon roda como root), sem precisar de `sudo` do `operador01` (que não tem sudo geral sem senha nesse host).
- Resultado do drill: backup real criado e mantido em `/opt/loterias-backups/db.sqlite3.20260923-164700`; contagem de `GeneratedBet` bateu nos 3 pontos (cópia antes do migrate, cópia depois, volume real) — 29 em todos.
- `deploy/lab/README.md`: nota antiga de "descartável enquanto lab de teste" removida; runbook reescrito com os comandos corrigidos (`docker run`/`docker exec` no lugar de `docker compose run`/`exec`) e uma nota de postura explicando a mudança e citando o drill como evidência.
- Nada foi commitado além da doc — não havia migration real pra aplicar nesta story.
