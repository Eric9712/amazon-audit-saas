"""
Django Development Settings
===========================
Settings for local development environment.
"""

from .base import *  # noqa: F401, F403

# =============================================================================
# DEBUG SETTINGS
# =============================================================================

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# =============================================================================
# EMAIL BACKEND (Console for development)
# =============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# =============================================================================
# DATABASE (SQLite for easy development)
# =============================================================================

# Use SQLite for simpler local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# =============================================================================
# CORS (Allow all in development)
# =============================================================================

CORS_ALLOW_ALL_ORIGINS = True

# =============================================================================
# DEBUG TOOLBAR
# =============================================================================

try:
    import debug_toolbar  # noqa: F401
    INSTALLED_APPS += ['debug_toolbar']  # noqa: F405
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa: F405
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
except ImportError:
    pass

# =============================================================================
# CACHING (Local memory for development)
# =============================================================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# =============================================================================
# DJANGO-ALLAUTH (Relaxed for development)
# =============================================================================

ACCOUNT_EMAIL_VERIFICATION = 'optional'

# =============================================================================
# SECURITY (Relaxed for development)
# =============================================================================

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# =============================================================================
# LOGGING (More verbose in development)
# =============================================================================

LOGGING['handlers']['console']['level'] = 'DEBUG'  # noqa: F405
LOGGING['loggers']['apps.audit_engine']['level'] = 'DEBUG'  # noqa: F405
LOGGING['loggers']['apps.amazon_integration']['level'] = 'DEBUG'  # noqa: F405

# =============================================================================
# CELERY (Eager execution for development)
# =============================================================================

# Uncomment to run Celery tasks synchronously (useful for debugging)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use in-memory broker and backend for development without Redis
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'

# =============================================================================
# STRIPE (Simulation mode for development)
# =============================================================================

# Enable simulation mode - no real Stripe calls
STRIPE_SIMULATION_MODE = True

# Amazon SP-API Simulation Mode
# Set to True to simulate Amazon responses (for development without credentials)
# Set to False to make real API calls
AMAZON_SIMULATION_MODE = False

# Amazon SP-API Sandbox Mode
# Set to True to use Amazon's sandbox endpoints (real API but test data)
# Set to False to use production endpoints
AMAZON_USE_SANDBOX = True

print("=" * 60)
print("[DEV] DEVELOPMENT MODE ACTIVE")
print("[DEV] Stripe simulation mode enabled (no real payments)")
print("[DEV] Amazon: SANDBOX MODE (test endpoints)")
print("=" * 60)
