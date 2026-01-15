"""
Django Production Settings
==========================
Secure settings for production deployment.
"""

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
import os

from .base import *  # noqa: F401, F403

# =============================================================================
# DEBUG (Must be False in production)
# =============================================================================

DEBUG = False

import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Allow Render.com domains
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# IMPORTANT: CSRF TRUSTED ORIGINS for Django 4.0+
# This is required to login to admin dashboard on Render
CSRF_TRUSTED_ORIGINS = []
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Allow additional hosts from env
additional_hosts = os.environ.get('ALLOWED_HOSTS', '').split(',')
for host in additional_hosts:
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

# =============================================================================
# SECURITY SETTINGS
# =============================================================================

# Force HTTPS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS Settings
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie Security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# =============================================================================
# EMAIL (Production - Mailgun)
# =============================================================================

EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'

ANYMAIL = {
    'MAILGUN_API_KEY': env('MAILGUN_API_KEY', default=''),  # noqa: F405
    'MAILGUN_SENDER_DOMAIN': env('MAILGUN_SENDER_DOMAIN', default=''),  # noqa: F405
}

# =============================================================================
# CACHING (Redis in production)
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),  # noqa: F405
    }
}

# =============================================================================
# SENTRY ERROR MONITORING
# =============================================================================

SENTRY_DSN = env('SENTRY_DSN', default='')  # noqa: F405

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# =============================================================================
# DJANGO-ALLAUTH (Strict in production)
# =============================================================================

ACCOUNT_EMAIL_VERIFICATION = 'mandatory'

# =============================================================================
# LOGGING (Production level)
# =============================================================================

LOGGING['handlers']['console']['level'] = 'WARNING'  # noqa: F405
LOGGING['loggers']['django']['level'] = 'WARNING'  # noqa: F405

# =============================================================================
# STATIC FILES
# =============================================================================

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =============================================================================
# ALLOWED HOSTS (Must be configured)
# =============================================================================

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ['localhost', '127.0.0.1']:  # noqa: F405
    raise ValueError(
        "ALLOWED_HOSTS must be properly configured in production. "
        "Set the ALLOWED_HOSTS environment variable."
    )

# Validate critical production keys
if not env('STRIPE_SECRET_KEY', default=''):  # noqa: F405
    raise ValueError("STRIPE_SECRET_KEY is missing in production environment!")

if not env('STRIPE_WEBHOOK_SECRET', default=''):  # noqa: F405
    raise ValueError("STRIPE_WEBHOOK_SECRET is missing in production environment!")

print("=" * 60)
print("🔒 PRODUCTION MODE ACTIVE")
print("=" * 60)
