"""
Stripe Webhooks
===============
Handle Stripe webhook events.
"""

import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid Stripe webhook payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid Stripe webhook signature")
        return HttpResponse(status=400)
    
    # Handle events
    event_type = event['type']
    data = event['data']['object']
    
    logger.info(f"Received Stripe webhook: {event_type}")
    
    if event_type == 'checkout.session.completed':
        stripe_service = StripeService()
        stripe_service.handle_checkout_completed(data)
    
    elif event_type == 'payment_intent.succeeded':
        logger.info(f"Payment succeeded: {data.get('id')}")
    
    elif event_type == 'payment_intent.payment_failed':
        logger.warning(f"Payment failed: {data.get('id')}")
    
    return HttpResponse(status=200)
