"""
Audit Engine App Configuration
==============================
"""

from django.apps import AppConfig


class AuditEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit_engine'
    verbose_name = 'Moteur d\'Audit'
