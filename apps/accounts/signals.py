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
        
        # Send welcome email
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            send_mail(
                subject="Bienvenue sur Amazon Audit !",
                message=f"""Bonjour {instance.get_short_name()},

Bienvenue sur Amazon Audit ! Votre compte a ete cree avec succes.

Pour commencer a recuperer l'argent que Amazon vous doit :
1. Connectez-vous a votre tableau de bord
2. Importez vos rapports Amazon Seller Central
3. Lancez votre premier audit gratuit

Si vous avez des questions, n'hesitez pas a nous contacter.

Cordialement,
L'equipe Amazon Audit
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.email],
                fail_silently=True,
            )
            logger.info(f"Welcome email sent to: {instance.email}")
        except Exception as e:
            logger.warning(f"Failed to send welcome email to {instance.email}: {e}")


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
