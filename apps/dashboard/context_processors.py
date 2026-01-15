"""
Dashboard Context Processors
============================
"""

from django.conf import settings


def stripe_context(request):
    """Add Stripe public key to all templates."""
    return {
        'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,
    }
