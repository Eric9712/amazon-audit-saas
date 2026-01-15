"""
Accounts Signals
================
Signal handlers for the accounts app.
"""

import logging

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import User, SellerProfile, LoginHistory

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_seller_profile(sender, instance, created, **kwargs):
    """Create a SellerProfile when a User is created."""
    if created:
        SellerProfile.objects.get_or_create(user=instance)
        logger.info(f"Created SellerProfile for user: {instance.email}")


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """Log successful login attempts."""
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    LoginHistory.objects.create(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        login_successful=True,
    )
    
    logger.info(f"Successful login: {user.email} from {ip_address}")


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempts."""
    ip_address = get_client_ip(request) if request else 'unknown'
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''
    email = credentials.get('username', credentials.get('email', 'unknown'))
    
    # Try to find user for logging
    try:
        user = User.objects.get(email=email)
        LoginHistory.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            login_successful=False,
        )
    except User.DoesNotExist:
        pass
    
    logger.warning(f"Failed login attempt for: {email} from {ip_address}")


def get_client_ip(request):
    """Extract client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip
