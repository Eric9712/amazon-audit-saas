"""
Amazon Integration App Configuration
=====================================
"""

from django.apps import AppConfig


class AmazonIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.amazon_integration'
    verbose_name = 'Intégration Amazon SP-API'
