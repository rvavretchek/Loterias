---
title: 'Story 5.2 — Landing page do Lottiq'
type: 'feature'
created: '2026-09-21'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
baseline_commit: 'b8f4918'
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A página inicial do visitante é o layout antigo do Bootstrap; o Boss pediu pra aproveitar a landing que o Claude Design gerou (tela 01 do DS).

**Approach:** Novo `loterias_core/landing.html` recriando a tela 01 (hero com exemplo de jogo, três passos, loterias suportadas, foto e nota sobre prêmio estimado); `home` renderiza a landing pra visitante e `home.html` fica só com a área logada.

</frozen-after-approval>

## Implementation Notes

- Fiel à tela 01 de `Lottiq Telas.dc.html`, adaptada pra responsivo (grid de 1 coluna no celular; hero 2 colunas ≥768px). O cabeçalho é o do `base.html` (5.1). Adicionada a seção "Loterias que o Lottiq confere" (as 6 do `GAMES_CONFIG`, ícones Material Symbols) no lugar dos cards antigos.
- O cartão de exemplo diz "Exemplo · Mega-Sena" (o design tinha "Mega-Sena · 2921", que sugeria concurso real); textos seguem o vocabulário do DS.
- Foto: só `Jogadora.jpeg` (a do design), redimensionada pra 1000 px (97 KB) em `static/img/jogadora.jpg`. `Ganhador.jpeg` **não foi usada**: o celular na imagem mostra "Loteria Nacional" e um botão "Retirar", o que sugere pagamento e outra marca — contra as regras do DS ("quem paga é a Caixa").
- Rodapé sem links de Termos/Privacidade/Jogo responsável (as páginas não existem ainda).
- Card Multitenant e os 3 cards antigos já não existiam desde a Story 4.1; o bloco "Loterias Suportadas" antigo saiu.
- Suíte: 412 testes OK. Não verificado em navegador.
