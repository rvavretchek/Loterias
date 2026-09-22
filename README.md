# Lottiq

Aplicação Django que gera, guarda e confere jogos para seis loterias brasileiras (Mega-Sena, +Milionária, Lotomania, Lotofácil, Quina, Dupla-Sena). Single-tenant, multiusuário: todo usuário compartilha um único banco SQLite.

## Funcionalidades

- **Geração com regras personalizadas**: cada usuário configura, por Jogo, limites de sequência, espaço entre sequências, distribuição no volante etc. (tela "Regras de Geração"); sem personalização, vale a regra adaptativa padrão.
- **Palpite manual**: além de gerar, dá pra guardar um jogo já feito na lotérica.
- **Autenticação por e-mail**: cadastro e login via e-mail com verificação obrigatória (django-allauth).
- **Histórico com filtros**: por Jogo, período e premiados, com paginação.
- **Conferência automática**: rotina diária busca o resultado oficial da Caixa e avisa acerto (no site e, opcionalmente, por e-mail).
- **Estatísticas**: números mais frequentes e proporção de jogos com/sem sequência, por Jogo.

## Tecnologias

- **Django 5.0.6**
- **django-allauth** (autenticação)
- **Lottiq Design System** — CSS próprio (`static/css/lottiq*.css`), sem framework de UI; ícones Material Symbols Rounded
- **SQLite3**

## Estrutura do projeto

```
├── apps/
│   ├── accounts/          # Usuários
│   └── loterias_core/     # Jogos, regras de geração, estatísticas, utils
├── loterias/              # Configurações Django
├── templates/             # Templates HTML
│   ├── base/              # Template base (cabeçalho, rodapé, mensagens)
│   ├── account/           # Templates do allauth
│   ├── accounts/          # Perfil, cadastro
│   ├── components/        # Componentes de template reutilizáveis (ex. formulário)
│   └── loterias_core/     # Home, histórico, regras, estatísticas
├── static/                # CSS (Lottiq Design System), imagens
├── manage.py
└── requirements.txt
```

## Instalação

### 1. Clone o repositório

```bash
cd Loterias
```

### 2. Crie o ambiente virtual (fixado em Python 3.11 — Django 5.0.6 não suporta 3.13+)

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure o ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

### 5. Execute as migrações

```bash
python manage.py migrate
python manage.py createcachetable
```

### 6. Crie um superusuário

```bash
python manage.py createsuperuser
```

### 7. Inicie o servidor

```bash
python manage.py runserver
```

Acesse: http://localhost:8000

## Configuração de e-mail

Para envio de e-mails reais, configure no `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
DEFAULT_FROM_EMAIL=Lottiq <noreply@lottiq.com>
```

Para desenvolvimento, os e-mails são exibidos no console por padrão.

## Comandos úteis

```bash
# Shell Django
python manage.py shell

# Coletar arquivos estáticos
python manage.py collectstatic

# Testes
python manage.py test
```

## Segurança

- Proteção CSRF habilitada
- Filtro XSS
- Proteção contra clickjacking
- Validadores de senha (Argon2id com pepper)
- Verificação de e-mail obrigatória
- HTTPS em produção

## Licença

MIT License
