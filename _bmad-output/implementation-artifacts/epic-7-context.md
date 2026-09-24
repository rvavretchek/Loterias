# Epic 7 Context: Layout — Dicas Explicativas, Tema Escuro, Zona de AdSense e Consentimento de Cookies

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Fecha o segundo item do backlog de pré-homologação: dicas explicativas na home e nas Regras de Geração (feedback direto — a esposa do Boss achou a tela de gerar jogo confusa mesmo com a frase "Selecione um jogo abaixo" já existindo), tema escuro (tokens já existem no design system de origem, nunca importados), zona reservada pro Google AdSense (só o espaço, sem conta/integração real), e tela de consentimento de cookies/LGPD (pré-requisito legal pro AdSense futuro). Sem PRD formal; vem depois do Epic 6 (ordem pedida pelo Boss: testes antes de layout).

## Stories

- Story 7.1: Dicas explicativas na tela de gerar jogo
- Story 7.2: Dicas explicativas na tela de Regras de Geração
- Story 7.3: Zona reservada pro Google AdSense
- Story 7.4: Tema escuro
- Story 7.5: Tela de consentimento de cookies (LGPD)

## Requirements & Constraints

- Dica na home não compete com o fluxo de gerar jogo — perto do seletor, não bloqueia a ação, discreta/ausente pra quem já gerou jogo antes.
- Explicação de cada Regra de Geração fica perto do campo (mesmo padrão `aria-describedby` já usado pra ajuda de linha/coluna), cobre as 7 regras possíveis (`RULE_DEFINITIONS`).
- Zona do AdSense nunca fica dentro do fluxo de gerar/conferir jogo; sem conta/integração/script real nesta rodada.
- Tema escuro reusa os tokens `--dark-*` do design system de origem (nunca copiados pro app); o alternador de tema foi removido do cabeçalho no Epic 5 de propósito — volta agora.
- Consentimento de cookies: 3 opções (aceitar tudo, recusar tudo, configurar por categoria), nenhum cookie de rastreamento antes da escolha, decisão revisável depois.

## Technical Decisions

- `static/css/lottiq-tokens.css`/`lottiq.css` (Story 5.1) são os arquivos onde os tokens de tema escuro entram; `templates/base/base.html` é onde o alternador de tema volta ao cabeçalho.
- `templates/loterias_core/home.html` (área "jogo selecionado"/seletor, Stories 4.1/4.2/5.4) é onde a dica de uso entra.
- `templates/loterias_core/regras_geracao.html` (Story 4.3/5.5) é onde a explicação de cada regra entra, junto de `RULE_DEFINITIONS`/`_GRID_HELP` em `apps/loterias_core/views.py`.
- Nenhum cookie de rastreamento real existe hoje no projeto — a Story 7.5 é puramente preparatória (não há analytics/AdSense rodando ainda pra bloquear).

## Cross-Story Dependencies

Stories 7.1/7.2 são independentes das demais (conteúdo/UX pura, sem dependência técnica). Story 7.5 (consentimento) é pré-requisito *legal* pra ativação futura do AdSense da Story 7.3, mas não bloqueia a 7.3 em si (que só reserva o espaço). Story 7.4 (tema escuro) é independente, mas deve ser testada contra as telas de todas as stories anteriores (7.1/7.2/7.3) uma vez que elas existam, pra não quebrar em modo escuro.
