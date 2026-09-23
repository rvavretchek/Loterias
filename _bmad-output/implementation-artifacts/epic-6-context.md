# Epic 6 Context: Cobertura Sistemática de Testes e Validação do Runbook

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Fechar lacunas de teste concretas identificadas numa rodada de `bmad-party-mode` de pré-homologação (2026-09-23), sob uma convenção nova de 4 categorias de cobertura, e validar de verdade — pela primeira vez — o runbook de backup/restore do lab, cuja postura de descartabilidade de dado muda a partir de agora (homologação tratada como produção pra fins de preservação de dado). Sem PRD formal por trás; a intenção nasceu direto de decisão do Boss (mesmo caminho do Epic 5).

## Stories

- Story 6.1: Convenção de teste em 4 categorias (CLAUDE.md)
- Story 6.2: Cobertura de `normalize_contest`
- Story 6.3: Bloqueio de concurso já sorteado nos 3 pontos de entrada
- Story 6.4: Conferência retroativa de palpite manual salvo antes da captura
- Story 6.5: Todas as combinações possíveis de Regras de Geração
- Story 6.6: Fluxo ponta a ponta de uma aposta, manual e automática
- Story 6.7: Dividir `tests.py` por área funcional
- Story 6.8: Validar o runbook de backup/restore e atualizar a postura de dados do lab

## Requirements & Constraints

- Toda cobertura de teste NOVA (não retroativa) segue 4 categorias: caminho feliz, entrada inválida (formato errado/fora do intervalo), entrada vazia/ausente, fronteira/concorrência (duplicata, corrida, estado já existente).
- Concurso já sorteado (com `LotteryResult` capturado) é bloqueado nos 3 pontos de entrada de jogo: criação, regeneração, palpite manual — hoje só parte tem teste nomeado.
- Palpite manual salvo antes da captura do resultado precisa ser conferido retroativamente e marcado premiado/sem prêmio corretamente quando a captura roda depois (cron ou verificação manual) — sem falso positivo.
- Regras de Geração: toda combinação *possível* (realista, não o produto cartesiano infinito de valores) de regras ligadas por Jogo produz um jogo que satisfaz todas simultaneamente, ou relaxa exatamente 1 regra quando genuinamente inatingível — nunca viola uma regra ligada silenciosamente.
- `normalize_contest`: normaliza zero à esquerda; rejeita vazio/não numérico vindo de formulário com erro claro; ao salvar direto num model (sem formulário), preserva valor legado não numérico sem quebrar.
- Fluxo ponta a ponta (manual e automático): geração/registro → captura de resultado → cálculo de prêmio → notificação, nenhuma etapa mockada por inteiro/pulada.
- `tests.py` (~4000 linhas hoje) divide por área funcional (geração/regras, histórico, notificações, admin) como consequência de organizar a cobertura nova — não reforma isolada tocando teste que já passava sem necessidade.
- Runbook de backup/restore (`deploy/lab/README.md`) nunca foi exercitado de verdade — precisa rodar ponta a ponta com evidência (contagem de linhas batendo antes/depois).
- Postura do lab muda: a nota "enquanto lab de teste, volume recriável livremente" some do README; dados não devem mais ser destruídos livremente a partir de agora.

## Technical Decisions

- `_block_if_contest_already_drawn` (views.py) já implementa o bloqueio de concurso já sorteado — a lacuna é só de teste, não de comportamento.
- `bet_satisfies_rules`/`generate_bet_with_relaxation` (utils.py) e `RULE_NAMES_BY_GAME` (models.py) definem o universo de regras testável por Jogo.
- `LotteryResult.objects.save_official_result()` (manager novo, retro Epic 2/5) é o ponto único de captura de resultado — usado tanto pelo cron quanto pela verificação manual, relevante pro teste de conferência retroativa (Story 6.4).
- `calculate_bet_prize`/`_calculate_prize_for_draw` (utils.py) calculam prêmio e retornam `matched_numbers`/`matched_clovers`/`draw`, usados tanto por notificações quanto pelo detalhe do jogo.

## Cross-Story Dependencies

Story 6.7 (dividir `tests.py`) organiza o que as Stories 6.2-6.6 escrevem — deve vir depois delas, não antes. Story 6.1 (convenção) vem primeiro, define o padrão que as Stories 6.2-6.6 seguem. Story 6.8 (runbook) é independente das demais, pode rodar em paralelo/qualquer ordem.
