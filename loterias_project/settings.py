"""
Django settings for loterias_project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-key-change-in-production-abc123xyz789'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

CSRF_TRUSTED_ORIGINS = [
    f'http://{host.strip()}' for host in ALLOWED_HOSTS if host.strip()
]

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------
FEATURE_FLAGS = {
    'ENABLE_SCHEDULED_TASKS': os.environ.get('ENABLE_SCHEDULED_TASKS', 'True').lower() in ('true', '1', 'yes'),
    'ENABLE_API_FETCH': os.environ.get('ENABLE_API_FETCH', 'True').lower() in ('true', '1', 'yes'),
}

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'django_crontab',
    'anymail',
    # Local
    'accounts',
    'jogos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'loterias_project.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'loterias_project.wsgi.application'

# ---------------------------------------------------------------------------
# Database — SQLite
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'jogos:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---------------------------------------------------------------------------
# Email — Brevo SMTP
# Para dev sem IP fixo, trocar para: EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-relay.brevo.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('BREVO_SMTP_USER', '9ae7e0001@smtp-brevo.com')
EMAIL_HOST_PASSWORD = os.environ.get('BREVO_SMTP_KEY', '')

# Fallback: API HTTP (sem restrição de IP) — descomentar se SMTP não funcionar
# EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
# ANYMAIL = {'BREVO_API_KEY': os.environ.get('BREVO_API_KEY', '')}

DEFAULT_FROM_EMAIL = 'Loterias <ricardo.vavretchek@initiall.com.br>'

# ---------------------------------------------------------------------------
# Cron jobs — scheduled tasks
# ---------------------------------------------------------------------------
# Horários: 22h (primeira tentativa), 01h (+3h retry), 07h (+9h retry)
CRONJOBS = [
    ('0 22 * * *', 'django.core.management.call_command', ['check_ganhadores']),
    ('0  1 * * *', 'django.core.management.call_command', ['check_ganhadores']),
    ('0  7 * * *', 'django.core.management.call_command', ['check_ganhadores']),
]

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
