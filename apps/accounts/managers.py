"""
Accounts Managers
=================
Custom model managers for accounts app.
"""

from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.utils import timezone


class ActiveUserManager(BaseUserManager):
    """
    Manager that returns only active users.
    """
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class AmazonConnectedManager(models.Manager):
    """
    Manager that returns only seller profiles with active Amazon connections.
    """
    
    def get_queryset(self):
        return super().get_queryset().filter(
            amazon_seller_id__isnull=False
        ).exclude(
            amazon_seller_id=''
        )
    
    def with_valid_token(self):
        """Return profiles with non-expired tokens."""
        return self.get_queryset().filter(
            models.Q(amazon_token_expires_at__isnull=True) |
            models.Q(amazon_token_expires_at__gt=timezone.now())
        )
    
    def with_expiring_token(self, days=7):
        """Return profiles with tokens expiring within X days."""
        expiry_threshold = timezone.now() + timezone.timedelta(days=days)
        return self.get_queryset().filter(
            amazon_token_expires_at__isnull=False,
            amazon_token_expires_at__lte=expiry_threshold,
            amazon_token_expires_at__gt=timezone.now()
        )


class SubscribedManager(models.Manager):
    """
    Manager that returns only seller profiles with active subscriptions.
    """
    
    def get_queryset(self):
        return super().get_queryset().exclude(
            subscription_tier='free'
        ).filter(
            models.Q(subscription_ends_at__isnull=True) |
            models.Q(subscription_ends_at__gt=timezone.now())
        )
    
    def expiring_soon(self, days=7):
        """Return profiles with subscriptions expiring within X days."""
        expiry_threshold = timezone.now() + timezone.timedelta(days=days)
        return self.get_queryset().filter(
            subscription_ends_at__isnull=False,
            subscription_ends_at__lte=expiry_threshold,
            subscription_ends_at__gt=timezone.now()
        )
