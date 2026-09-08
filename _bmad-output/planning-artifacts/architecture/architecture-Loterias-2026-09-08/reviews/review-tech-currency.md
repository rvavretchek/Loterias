# Revisão de Atualidade Técnica — ARCHITECTURE-SPINE.md (Loterias, 2026-09-08)

Escopo: verificar se toda afirmação técnica/de versão assumida na espinha dorsal foi de fato checada contra a realidade (arquivo do repositório ou web), e não afirmada a partir de dados de treinamento. Nenhum outro aspecto da espinha dorsal (decisões, estrutura, etc.) foi revisado.

Revisado: `_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md`, tabela de Stack (linhas 100-111) e AD-2 (linha 52).

## 1. Pins existentes (Django, django-allauth, gunicorn, requests) — CONFIRMADO

Lido `requirements.txt` diretamente:

```
Django==5.0.6
django-allauth==0.63.3
requests==2.32.3
gunicorn==22.0.0
```

A tabela de Stack da espinha dorsal lista exatamente esses quatro valores pra exatamente esses quatro pacotes — ela ratifica os pins existentes, não inventa nem diverge de nenhum deles. Sem problema.

## 2. django-crontab 0.7.1 (dependência nova) — PARCIALMENTE ERRADO, SUBESTIMA O RISCO

Checado a API JSON do PyPI (`https://pypi.org/pypi/django-crontab/json`) diretamente.

- **Afirmação da versão mais recente: CONFIRMADA.** 0.7.1 é de fato o release mais novo no PyPI. Essa parte é precisa.
- **Afirmação "sem release há mais de 12 meses": TECNICAMENTE VERDADEIRA MAS MATERIALMENTE ENGANOSA (severidade Média).** Histórico completo de releases pelo PyPI:

  | Versão | Publicado em |
  |---|---|
  | 0.6.0 | 2014-12-07 |
  | 0.7.0 | 2015-12-02 |
  | 0.7.1 | 2016-03-07 |

  A 0.7.1 foi lançada em **07/03/2016** — cerca de **10 anos atrás**, não "12+ meses" atrás. Enquadrar uma década de abandono como "sem release há mais de 12 meses" é um jeito defensável-mas-fraco de frasear um fato muito maior; um leitor passando os olhos pela tabela de Stack razoavelmente assumiria "obsoleto há um ano ou dois," não "sem tocar desde o governo Obama, antes do Django 1.10 existir." Isso parece um número afirmado/arredondado em vez de verificado — o dado real do PyPI estava disponível e mostra algo muito mais grave. Recomendo que a espinha dorsal declare a data real do último release (2016) em vez do mais vago "12+ meses," pra que o nível real de risco de manutenção fique visível pra quem ler a tabela de Stack depois.

- **Afirmação de compatibilidade com Django 5.x / "nenhum problema de quebra conhecido no Django 5": NÃO REFUTADA, MAS NÃO VERIFICÁVEL COMO ESTÁ ESCRITA (severidade Baixa-Média).** Checadas as issues do GitHub do projeto (`kraiz/django-crontab/issues`) via busca na web — nenhuma issue aberta relata explicitamente quebra sob Django 4 ou 5. Porém, a própria declaração de compatibilidade documentada do pacote (conforme PyPI/README) vai só até "django (1.8+)" sem limite superior e sem evidência de CI testando contra o Django 5 (o último commit é anos anterior ao Django 5 — o Django 5.0 saiu em dezembro de 2023). "Nenhum problema de quebra conhecido no Django 5" é tecnicamente preciso (nada encontrado) mas soa mais reconfortante do que "ninguém nunca testou essa combinação e o mantenedor parou de responder em 2016." O próprio plano de contingência da espinha dorsal (descartar o pacote, escrever as linhas de crontab diretamente) sugere que o autor já suspeitava disso, o que é bom — mas a prosa da tabela de Stack não transmite o quão rala é de fato a evidência do "nenhum problema conhecido."

## 3. SQLite ALTER TABLE RENAME COLUMN / RENAME TO na versão ≥3.25 — CONFIRMADO (com uma imprecisão)

Checado `sqlite.org/releaselog/3_25_0.html` diretamente.

- `ALTER TABLE ... RENAME COLUMN ... TO ...` foi adicionado no SQLite **3.25.0, lançado em 15/09/2018**. Confirmado e preciso — é exatamente o que a AD-2 e a tabela de Stack afirmam.
- Imprecisão menor (severidade Baixa, não é um bug de correção): a frase da espinha dorsal agrupa "RENAME COLUMN/RENAME TO" como se ambos tivessem chegado juntos na 3.25. `ALTER TABLE ... RENAME TO ...` (renomear uma *tabela*) é muito mais antigo que a 3.25 — antecede esse release por uma margem enorme; o que a 3.25.0 (e o follow-up da 3.26.0) de fato mudou pro rename de tabela foi corrigir a atualização correta de referências dentro de triggers e views, não introduzir a sintaxe. A afirmação de fundo da espinha dorsal ("≥3.25 suporta ambos nativamente, sem reconstrução de tabela") ainda é verdadeira, então isso não invalida o argumento de segurança da AD-2 — só está frouxamente frasado de um jeito que exagera o quão novo é o `RENAME TO`.

## 4. SQLite empacotado no Python 3.11 "bem acima da 3.25" — CONFIRMADO

Checado na web os changelogs de release do Python 3.11.x. As versões de SQLite empacotadas/do instalador Windows do Python 3.11 variam de **3.39.4** (início da série 3.11.x) até **3.45.1** (3.11.9, lançado em 02/04/2024) ao longo da série de patches 3.11. Os dois limites estão confortavelmente acima da 3.25.0 (2018), então a afirmação "bem acima da 3.25" da espinha dorsal pro sqlite3 empacotado do Python 3.11 é precisa. (A versão exata de patch depende de qual 3.11.x está de fato instalado/pinado no venv do projeto, o que não foi verificado localmente — nenhum interpretador `python3.11` foi encontrado neste ambiente pra checar `sqlite3.sqlite_version` diretamente — mas todo dado de 3.11.x encontrado está bem distante do limite de 3.25, então a afirmação se sustenta independente da versão exata de patch.)

## 5. Outras tecnologias nomeadas na seção de Stack

- **Justificativa do pin do Python 3.11** ("Django 5.0.6 não suporta 3.13+"): não reverificada de forma independente nesta passada (fora dos quatro itens explicitamente atribuídos mais as afirmações de crontab/SQLite) — sinalizando como não checada em vez de confirmada. Prioridade baixa de perseguir já que é uma afirmação amplamente documentada e facilmente refutável sobre a própria matriz de suporte do Django, mas não estava no checklist explícito desta revisão e nenhuma busca foi feita a respeito.
- **Remoção de celery/redis**: a tabela de stack só diz pra removê-los conforme o não-objetivo do §5 do PRD — nenhuma afirmação de versão/atualidade sendo feita aqui, nada a verificar.
- Nenhum outro número de versão aparece na tabela de Stack ou na prosa ao redor além dos seis cobertos acima.

## Resumo de severidades

| # | Afirmação | Veredito | Severidade |
|---|---|---|---|
| 1 | Pins de Django/allauth/gunicorn/requests batem com requirements.txt | Confirmado | — |
| 2a | django-crontab 0.7.1 é o mais recente no PyPI | Confirmado | — |
| 2b | "Sem release há mais de 12 meses" | Verdadeiro mas subestima um pacote obsoleto há ~10 anos | Média |
| 2c | "Nenhum problema de quebra conhecido no Django 5" | Preciso como está escrito mas a evidência é rala (nenhum CI de Django 4/5 já rodado) | Baixa-Média |
| 3 | SQLite ≥3.25 suporta RENAME COLUMN/RENAME TO nativamente | Confirmado (RENAME TO antecede a 3.25; a redação confunde os dois) | Baixa |
| 4 | SQLite empacotado no Python 3.11 "bem acima da 3.25" | Confirmado (3.39.4–3.45.1 ao longo da série 3.11.x) | — |
| 5 | Justificativa do pin do Python 3.11 (Django 5.0.6 vs 3.13+) | Não checada nesta passada | Não verificado (fora do escopo do checklist explícito) |
