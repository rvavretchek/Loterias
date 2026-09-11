import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')

DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Aplicacoes Django
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Terceiros
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'django_crontab',

    # Apps locais
    'apps.accounts',
    'apps.loterias_core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.RequireCompleteAccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'loterias.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.loterias_core.context_processors.theme_context',
                'apps.loterias_core.context_processors.notifications_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'loterias.wsgi.application'

# Database - SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DATABASE_NAME', str(BASE_DIR / 'db.sqlite3')),
        'OPTIONS': {'timeout': 20},
    }
}

# Cache -- DatabaseCache (nao LocMemCache, que e por processo -- com 3 workers do gunicorn o
# rate limiter nativo do allauth pro reenvio de confirmacao de e-mail (ACCOUNT_RATE_LIMITS)
# ficaria inconsistente entre workers). Sem Redis de proposito (removido na Story 2.1).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
    }
}

# Cron (rotinas de dominio, ver apps/loterias_core/jobs.py)
# A entrada mensal de update_monthly_prize_values e redundante na pratica com a chamada de
# cold-start dentro de fetch_daily_results (roda todo dia, inclusive no dia 1) -- mantida como
# defesa em profundidade: se o cron diario ficar fora do ar por qualquer motivo num periodo em
# torno da virada de mes, o disparo mensal dedicado ainda garante ao menos uma tentativa.
# fetch_daily_results roda 3x seguidas (3h/3h15/3h30, Story 2.9) -- retry automatico sem logica
# nova (a funcao ja e idempotente); a ultima chamada usa --final, que avalia alerta ao operador
# pra par que continuar sem resultado ha tempo demais (ver jobs.py).
CRONJOBS = [
    ('0 3 * * *', 'django.core.management.call_command', ['fetch_daily_results']),
    ('15 3 * * *', 'django.core.management.call_command', ['fetch_daily_results']),
    ('30 3 * * *', 'django.core.management.call_command', ['fetch_daily_results', '--final']),
    ('0 4 1 * *', 'django.core.management.call_command', ['update_monthly_prize_values']),
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

PASSWORD_HASHERS = [
    'apps.accounts.hashers.PepperedArgon2PasswordHasher',
]
PASSWORD_PEPPER = os.getenv('PASSWORD_PEPPER', 'loterias-default-pepper')

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Django AllAuth
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

# Configuracoes de conta
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
# Cadastro (Epic 3/Story 3.1): so e-mail -- sem senha, sem nome/sobrenome. A conta nasce com
# senha inutilizavel (comportamento padrao do allauth quando nao ha password1 no form) ate a
# Story 3.3 (definicao de senha via link) ser concluida.
ACCOUNT_SIGNUP_FIELDS = ['email*']
ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE = False
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
# Story 3.3: clicar no vinculo nunca loga automaticamente -- CustomAccountAdapter redireciona
# pra definicao de senha (conta pendente) ou login com mensagem "ja confirmado" (conta ativa).
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_PASSWORD_MIN_LENGTH = 8
# Story 3.1, 2o AC: e-mail ja cadastrado nunca revela isso ao tentar cadastrar de novo -- ja e o
# default do allauth 0.63, explicito aqui pra documentar a decisao.
ACCOUNT_PREVENT_ENUMERATION = True
# Story 3.2: cooldown de 60s entre envios, por e-mail -- usa o rate limiter nativo do allauth (ja
# embutido em should_send_confirmation_mail), backend em CACHES. So UMA regra aqui de proposito:
# o limiter do allauth guarda o historico de TODAS as regras da mesma acao na MESMA cache key
# (allauth.core.ratelimit._cache_key nao diferencia por regra) -- com duas regras (60s + 1 dia)
# compartilhando essa entrada, cliques repetidos dentro do cooldown ainda inserem timestamps
# na regra diaria (que nao sabe que a outra regra bloqueou), esgotando a cota diaria sem
# nenhum e-mail ter saido, enquanto o uso "bem-comportado" (respeitando os 60s) nunca acumula
# o suficiente pra bater no limite diario de verdade -- achado real na revisao, nao hipotetico.
# O limite de 5/dia (Story 3.2, 3o AC) e implementado separadamente em
# ResendConfirmationEmailView, com sua PROPRIA cache key, incrementada so quando um e-mail e
# de fato despachado -- nunca compartilhando estado com este cooldown.
ACCOUNT_RATE_LIMITS = {
    'confirm_email': '1/60s/key',
}

# Custom forms
ACCOUNT_FORMS = {
    'signup': 'apps.accounts.forms.CustomSignupForm',
    'reset_password_from_key': 'apps.accounts.forms.InitialOrResetPasswordKeyForm',
}

# Custom adapter
ACCOUNT_ADAPTER = 'apps.accounts.adapter.CustomAccountAdapter'

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

# Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Lotérias <noreply@loterias.com>')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', 20))

# E-mail do operador (Boss) que recebe alerta de falha de captura de resultado (Story 2.9).
# Vazio por padrao -- send_capture_failure_alert so loga um aviso e nao envia nada se nao configurado.
OPERATOR_ALERT_EMAIL = os.getenv('OPERATOR_ALERT_EMAIL', '')

# Security
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
    CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
