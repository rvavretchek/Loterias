# 🎰 Gerador de Loterias - Django

Sistema web moderno para geração de apostas de loterias brasileiras, desenvolvido com Django, SQLite e multitenancy.

## ✨ Funcionalidades

- **Geração Inteligente**: Algoritmo que respeita regras de sequencia e evita repetições
- **Autenticação por E-mail**: Cadastro e login via e-mail com verificação (django-allauth)
- **Temas Diurno/Noturno**: Interface moderna com alternância entre tema claro e escuro
- **Histórico Completo**: Mantem registro de todos os jogos gerados
- **Estatísticas**: Analise de números mais frequentes e padrões
- **6 Loterias**: Mega-Sena, Milionária, Lotomania, Lotofacil, Quina, Dupla-Sena

## 🚀 Tecnologias

- **Django 5.0.6**
- **django-allauth** (Autenticacao)
- **Bootstrap 5** + **Crispy Forms**
- **SQLite3**

## 📁 Estrutura do Projeto

```
loterias_django/
├── apps/
│   ├── accounts/          # Usuarios
│   └── loterias_core/     # Jogos, Estatisticas, Utils
├── loterias/              # Configuracoes Django
├── templates/             # Templates HTML
│   ├── base/             # Template base com tema
│   ├── account/          # Templates do allauth
│   ├── accounts/         # Perfil, cadastro
│   └── loterias_core/    # Home, historico, estatisticas
├── static/               # CSS, JS, imagens
├── manage.py
└── requirements.txt
```

## 🔧 Instalação

### 1. Clone o repositório

```bash
cd loterias_django
```

### 2. Crie o ambiente virtual

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
# Edite o arquivo .env com suas configuracoes
```

### 5. Execute as migrações

```bash
python manage.py migrate
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

## 📧 Configuração de E-mail

Para envio de e-mails reais, configure no `.env`:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
DEFAULT_FROM_EMAIL=Lotérias <noreply@loterias.com>
```

Para desenvolvimento, os e-mails sao exibidos no console por padrao.

## 🎨 Temas

O sistema possui tema claro e escuro. O usuario pode alternar clicando no icone de sol/lua na navbar. A preferencia e salva no perfil do usuario.

## 📝 Comandos Uteis

```bash
# Shell Django
python manage.py shell

# Coletar arquivos estaticos
python manage.py collectstatic
```

## 🔒 Segurança

- CSRF protection habilitado
- XSS filtering
- Clickjacking protection
- Password validators
- Email verification obrigatoria
- HTTPS em producao

## 📄 Licença

MIT License

---

Desenvolvido com <3 e Django
