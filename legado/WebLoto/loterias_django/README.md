# 🎰 Gerador de Loterias - Django

Sistema web moderno para geracao de apostas de loterias brasileiras, desenvolvido com Django, SQLite e multitenancy.

## ✨ Funcionalidades

- **Geracao Inteligente**: Algoritmo que respeita regras de sequencia e evita repeticoes
- **Multitenancy**: Cada organizacao/tenant tem seu proprio banco de dados SQLite isolado
- **Autenticacao por E-mail**: Cadastro e login via e-mail com verificacao (django-allauth)
- **Temas Diurno/Noturno**: Interface moderna com alternancia entre tema claro e escuro
- **Historico Completo**: Mantem registro de todos os jogos gerados
- **Estatisticas**: Analise de numeros mais frequentes e padroes
- **6 Loterias**: Mega-Sena, Milionaria, Lotomania, Lotofacil, Quina, Dupla-Sena

## 🚀 Tecnologias

- **Django 5.0.6**
- **django-sqlite-tenants** (Multitenancy com SQLite)
- **django-allauth** (Autenticacao)
- **Bootstrap 5** + **Crispy Forms**
- **SQLite3**

## 📁 Estrutura do Projeto

```
loterias_django/
├── apps/
│   ├── accounts/          # Usuarios, Tenants, Dominios
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

## 🔧 Instalacao

### 1. Clone o repositorio

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

### 3. Instale as dependencias

```bash
pip install -r requirements.txt
```

### 4. Configure o ambiente

```bash
cp .env.example .env
# Edite o arquivo .env com suas configuracoes
```

### 5. Execute as migracoes

```bash
python manage.py migrate
```

### 6. Crie um superusuario

```bash
python manage.py createsuperuser
```

### 7. Inicie o servidor

```bash
python manage.py runserver
```

Acesse: http://localhost:8000

## 🏢 Multitenancy

O projeto utiliza **django-sqlite-tenants** para multitenancy. Cada tenant tem seu proprio banco SQLite isolado.

### Criar um Tenant

```bash
python manage.py create_tenant meu-tenant --name "Minha Organizacao" --domain "meu-tenant.local"
```

### Acessar um Tenant

- **Modo Subfolder**: http://localhost:8000/r/meu-tenant/
- **Modo Domain**: http://meu-tenant.localhost:8000

### Migrar Tenants

```bash
# Migrar todos os tenants
python manage.py migrate_tenant

# Migrar tenant especifico
python manage.py migrate_tenant --tenant meu-tenant
```

## 📧 Configuracao de E-mail

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

# Criar tenant
python manage.py create_tenant <slug> --name "Nome" --domain "dominio.com"

# Migrar tenants
python manage.py migrate_tenant

# Coletar arquivos estaticos
python manage.py collectstatic
```

## 🔒 Seguranca

- CSRF protection habilitado
- XSS filtering
- Clickjacking protection
- Password validators
- Email verification obrigatoria
- HTTPS em producao

## 📄 Licenca

MIT License

---

Desenvolvido com <3 e Django
