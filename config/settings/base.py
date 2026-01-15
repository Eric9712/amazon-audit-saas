"""
Django Base Settings - Amazon Audit SaaS
========================================
Common settings shared across all environments.
"""

import os
from pathlib import Path
from datetime import timedelta

import environ

# =============================================================================
# PATH CONFIGURATION
# =============================================================================

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environ
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# =============================================================================
# CORE DJANGO SETTINGS
# =============================================================================

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
]

LOCAL_APPS = [
    'apps.accounts.apps.AccountsConfig',
    'apps.amazon_integration.apps.AmazonIntegrationConfig',
    'apps.audit_engine.apps.AuditEngineConfig',
    'apps.payments.apps.PaymentsConfig',
    'apps.dashboard.apps.DashboardConfig',
    'apps.pages.apps.PagesConfig',
    'apps.messaging.apps.MessagingConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

# =============================================================================
# TEMPLATES
# =============================================================================

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
                'apps.dashboard.context_processors.stripe_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# =============================================================================
# DATABASE
# =============================================================================

DATABASES = {
    'default': env.db('DATABASE_URL', default='postgres://postgres:postgres@localhost:5432/amazon_audit_db')
}

DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

# =============================================================================
# AUTHENTICATION
# =============================================================================

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Django-allauth settings
SITE_ID = 1
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None  # Our User model has no username field
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_SESSION_REMEMBER = True

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC & MEDIA FILES
# =============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =============================================================================
# DEFAULT PRIMARY KEY FIELD TYPE
# =============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max per task
CELERY_RESULT_EXTENDED = True
# CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'  # Requires django-celery-beat

# Retry settings for rate limiting
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

# =============================================================================
# REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# =============================================================================
# CORS SETTINGS
# =============================================================================

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[
    'http://localhost:8000',
    'http://127.0.0.1:8000',
])

# =============================================================================
# STRIPE SETTINGS
# =============================================================================

STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY', default='')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET', default='')
CASE_FILE_PRICE_CENTS = env.int('CASE_FILE_PRICE_CENTS', default=500)

# =============================================================================
# AMAZON SP-API SETTINGS
# =============================================================================

AMAZON_SP_API_SETTINGS = {
    'refresh_token': env('AMAZON_SP_API_REFRESH_TOKEN', default=''),
    'lwa_app_id': env('AMAZON_SP_API_LWA_APP_ID', default=''),
    'lwa_client_secret': env('AMAZON_SP_API_LWA_CLIENT_SECRET', default=''),
    'aws_access_key': env('AMAZON_SP_API_AWS_ACCESS_KEY', default=''),
    'aws_secret_key': env('AMAZON_SP_API_AWS_SECRET_KEY', default=''),
    'role_arn': env('AMAZON_SP_API_ROLE_ARN', default=''),
}

# =============================================================================
# AUDIT ENGINE SETTINGS
# =============================================================================

# Amazon 45-day rule: ignore losses less than this many days old
LOSS_DETECTION_DELAY_DAYS = env.int('LOSS_DETECTION_DELAY_DAYS', default=45)

# Maximum months of historical data to fetch
MAX_HISTORY_MONTHS = env.int('MAX_HISTORY_MONTHS', default=18)

# =============================================================================
# EMAIL SETTINGS
# =============================================================================

DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@amazonaudit.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# =============================================================================
# AMAZON SP-API
# =============================================================================

AMAZON_SP_API_SETTINGS = {
    'lwa_app_id': env('AMAZON_LWA_APP_ID', default=''),
    'lwa_client_secret': env('AMAZON_LWA_CLIENT_SECRET', default=''),
    'access_key': env('AMAZON_AWS_ACCESS_KEY', default=''),
    'secret_key': env('AMAZON_AWS_SECRET_KEY', default=''),
    'role_arn': env('AMAZON_ROLE_ARN', default=''),
}

print(f"DEBUG: APP_ID from env: '{env('AMAZON_LWA_APP_ID', default='default')}'")
print(f"DEBUG: AMAZON_SP_API_SETTINGS: {AMAZON_SP_API_SETTINGS}")

# =============================================================================
# LOGGING
# =============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['mail_admins', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'apps.audit_engine': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.amazon_integration': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# =============================================================================
# BANK DETAILS (For Wire Transfer)
# =============================================================================

BANK_DETAILS = {
    'bank_name': env('BANK_NAME', default='Ma Banque'),
    'iban': env('BANK_IBAN', default='FR76 XXXX XXXX XXXX XXXX XXXX XXX'),
    'bic': env('BANK_BIC', default='XXXXXXXX'),
    'holder_name': env('BANK_HOLDER_NAME', default='SAS AMAZON AUDIT'),
}
