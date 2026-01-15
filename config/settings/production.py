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
# DEBUG (Must be False in production, unless debugging)
# =============================================================================

# Permet d'activer le DEBUG si la variable d'environnement est 'True'
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

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
# SECURITY SETTINGS (RELAXED FOR RENDER DEBUGGING)
# =============================================================================

# Render handles SSL termination, so redirect might cause loops/errors if headers missing
SECURE_SSL_REDIRECT = False 
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS Settings
SECURE_HSTS_SECONDS = 0 # Disabled for debugging
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Cookie Security (Relaxed)
SESSION_COOKIE_SECURE = False # Try False if admin login fails loops
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'SAMEORIGIN' # Allow same origin frames

# =============================================================================
# EMAIL (Production - Mailgun or Console fallback)
# =============================================================================

MAILGUN_API_KEY = env('MAILGUN_API_KEY', default='')  # noqa: F405
MAILGUN_SENDER_DOMAIN = env('MAILGUN_SENDER_DOMAIN', default='')  # noqa: F405

if MAILGUN_API_KEY and MAILGUN_SENDER_DOMAIN:
    EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'
    ANYMAIL = {
        'MAILGUN_API_KEY': MAILGUN_API_KEY,
        'MAILGUN_SENDER_DOMAIN': MAILGUN_SENDER_DOMAIN,
    }
else:
    # Fallback: No real emails, just log them
    print("WARNING: Mailgun not configured. Emails will be logged to console.")
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# =============================================================================
# CACHING (Redis in production)
# =============================================================================

# =============================================================================
# CACHING & ASYNC TASKS
# =============================================================================

REDIS_URL = os.environ.get('REDIS_URL')

if REDIS_URL:
    # Use Redis if available
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
else:
    # Fallback to Local Memory (No Redis required)
    print("WARNING: No REDIS_URL found. Using Local Memory Cache & Synchronous Tasks.")
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
    # Run tasks immediately (Synchronous)
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_BROKER_URL = 'memory://'

# =============================================================================
# SENTRY ERROR MONITORING
# =============================================================================

SENTRY_DSN = env('SENTRY_DSN', default='')  # noqa: F405

if SENTRY_DSN:
    integrations = [DjangoIntegration()]
    
    # Only add Celery/Redis integration if Redis is present
    if REDIS_URL:
        integrations.append(CeleryIntegration())
        integrations.append(RedisIntegration())
        
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=integrations,
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )

# =============================================================================
# DJANGO-ALLAUTH (Strict in production)
# =============================================================================

# Disable email verification since Mailgun is not configured
ACCOUNT_EMAIL_VERIFICATION = 'none'

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
