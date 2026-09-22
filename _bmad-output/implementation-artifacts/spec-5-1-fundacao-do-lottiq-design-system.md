---
title: 'Story 5.1 — Fundação do Lottiq Design System e renomeação para Lottiq'
type: 'feature'
created: '2026-09-21'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'e2f4ebe'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O app tem identidade "Gerador de Loterias" em Bootstrap/Inter; o Boss quer o Lottiq Design System em toda a interface e o produto chamado Lottiq (Epic 5).

**Approach:** Tokens e componentes do DS como CSS por classe (`static/css/lottiq-tokens.css`, `lottiq.css`), cabeçalho/rodapé/mensagens do `base.html` refeitos com a marca e sem depender de Bootstrap JS, e renomeação de títulos, e-mails e `site_name`. Bootstrap segue carregado (CSS+JS+ícones) até a Story 5.7 para as telas ainda não migradas; `legacy.css` guarda os estilos antigos apontando pras cores do DS.

</frozen-after-approval>

## Implementation Notes

- Fonte: projeto "Lottiq Design System" (Claude Design, id `0c84487b-28fe-468a-a294-a0f55f0df75c`). Tokens copiados; componentes React traduzidos pra classes `lq-*` (botão, campo, switch, bola de número, cartão, badge de status, banner, estado vazio, menu). Colisão de nome no DS (`--text-body` é cor e fonte): a cor virou `--text-body-color`.
- `base.html`: cabeçalho DS (marca, navegação Gerar / Meus jogos / Estatísticas com estado ativo, sino de avisos — âmbar só quando há acerto —, menu da conta em `<details>` sem JS), mensagens como banners (sucesso/info somem em 5 s; aviso/erro ficam até fechar; `role=alert` em erro), rodapé com aviso "Não somos a Caixa Econômica Federal".
- **Tema escuro removido da interface** (o botão de alternar saiu; `data-theme` não é mais aplicado) — o dark do DS fica para a próxima rodada, por decisão do Boss. A view/context processor de tema continuam no código, sem uso visual.
- Marca: `static/img/lottiq-mark.svg` (símbolo do DS sem os metadados C2PA). O logo completo do Boss (`images/Lottiq_Logo.*`) entra na landing (5.2).
- Renomeação "Gerador de Loterias" → "Lottiq" em títulos de templates, `adapter.py`, `signals.py`, `emails.py`. README e CLAUDE.md ficam pra Story 5.7.
- Suíte: 411 testes OK (3 testes do sino atualizados de `bi-bell-fill`/`bg-*` pra `lq-bell*`; novos testes de marca, navegação e estáticos). Não verificado em navegador.
