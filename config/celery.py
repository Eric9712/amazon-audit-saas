"""
Celery Configuration for Amazon Audit SaaS
==========================================
Configures Celery for asynchronous task processing.
Used for long-running audit tasks that can take 5-10 minutes.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

# Create Celery app
app = Celery('amazon_audit')

# Load config from Django settings, using CELERY_ namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# =============================================================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# =============================================================================

app.conf.beat_schedule = {
    # Check for stale audits every hour
    'check-stale-audits': {
        'task': 'apps.audit_engine.tasks.check_stale_audits',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'maintenance'},
    },
    
    # Clean up old temporary files daily at 3 AM
    'cleanup-temp-files': {
        'task': 'apps.audit_engine.tasks.cleanup_temp_files',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'maintenance'},
    },
    
    # Refresh API tokens that are expiring soon (every 6 hours)
    'refresh-expiring-tokens': {
        'task': 'apps.amazon_integration.tasks.refresh_expiring_tokens',
        'schedule': crontab(minute=0, hour='*/6'),
        'options': {'queue': 'maintenance'},
    },
}

# =============================================================================
# TASK ROUTING
# =============================================================================

app.conf.task_routes = {
    # Heavy audit tasks go to dedicated queue
    'apps.audit_engine.tasks.run_full_audit': {'queue': 'audits'},
    'apps.audit_engine.tasks.process_report': {'queue': 'audits'},
    
    # Quick tasks
    'apps.audit_engine.tasks.generate_case_file': {'queue': 'default'},
    'apps.amazon_integration.tasks.*': {'queue': 'default'},
    
    # Maintenance tasks
    'apps.audit_engine.tasks.check_stale_audits': {'queue': 'maintenance'},
    'apps.audit_engine.tasks.cleanup_temp_files': {'queue': 'maintenance'},
}

# =============================================================================
# RETRY CONFIGURATION (For API throttling - Exponential Backoff)
# =============================================================================

app.conf.task_default_retry_delay = 2  # Start with 2 seconds
app.conf.task_max_retries = 10
app.conf.task_retry_backoff = True  # Enable exponential backoff
app.conf.task_retry_backoff_max = 600  # Max 10 minutes between retries


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f'Request: {self.request!r}')
    return 'Celery is working!'
