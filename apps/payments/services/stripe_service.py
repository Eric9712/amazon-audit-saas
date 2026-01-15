"""
Stripe Service
==============
Service for handling Stripe payments.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

import stripe
from django.conf import settings
from django.urls import reverse

from apps.accounts.models import SellerProfile
from apps.payments.models import PaymentTransaction, CreditPackage

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment operations."""
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
    
    def create_checkout_session(
        self,
        seller_profile: SellerProfile,
        credit_package: CreditPackage,
        success_url: str,
        cancel_url: str
    ) -> Dict:
        """
        Create a Stripe Checkout Session for credit purchase.
        """
        try:
            # Create or get Stripe customer
            customer_id = self._get_or_create_customer(seller_profile)
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                mode='payment',
                line_items=[{
                    'price_data': {
                        'currency': credit_package.currency.lower(),
                        'unit_amount': int(credit_package.price * 100),
                        'product_data': {
                            'name': credit_package.name,
                            'description': f'{credit_package.credits} crédits pour télécharger des dossiers',
                        },
                    },
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'seller_profile_id': seller_profile.pk,
                    'credit_package_id': credit_package.pk,
                    'credits': credit_package.credits,
                },
            )
            
            # Create pending transaction
            PaymentTransaction.objects.create(
                seller_profile=seller_profile,
                transaction_type=PaymentTransaction.TransactionType.CREDIT_PURCHASE,
                amount=credit_package.price,
                currency=credit_package.currency,
                credits_purchased=credit_package.credits,
                stripe_checkout_session_id=session.id,
                description=f"Achat {credit_package.name}",
            )
            
            return {
                'session_id': session.id,
                'url': session.url,
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise
    
    def _get_or_create_customer(self, seller_profile: SellerProfile) -> str:
        """Get or create Stripe customer ID."""
        if seller_profile.stripe_customer_id:
            return seller_profile.stripe_customer_id
        
        user = seller_profile.user
        
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name,
            metadata={
                'seller_profile_id': seller_profile.pk,
            }
        )
        
        seller_profile.stripe_customer_id = customer.id
        seller_profile.save(update_fields=['stripe_customer_id'])
        
        return customer.id
    
    def handle_checkout_completed(self, session: Dict) -> bool:
        """Handle completed checkout session webhook."""
        session_id = session.get('id')
        
        try:
            transaction = PaymentTransaction.objects.get(
                stripe_checkout_session_id=session_id
            )
        except PaymentTransaction.DoesNotExist:
            logger.error(f"Transaction not found for session: {session_id}")
            return False
        
        if transaction.status == PaymentTransaction.TransactionStatus.COMPLETED:
            return True  # Already processed
        
        # Add credits to seller
        seller_profile = transaction.seller_profile
        seller_profile.add_credits(
            transaction.credits_purchased,
            f"Purchase via Stripe: {session_id}"
        )
        
        # Mark transaction complete
        transaction.stripe_payment_intent_id = session.get('payment_intent')
        transaction.mark_completed()
        
        logger.info(
            f"Added {transaction.credits_purchased} credits to {seller_profile.user.email}"
        )
        
        return True
