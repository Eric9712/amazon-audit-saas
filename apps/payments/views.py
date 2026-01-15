"""
Payments Views
==============
Views for payment and credit management.
"""

import logging
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from apps.accounts.models import SellerProfile
from apps.payments.models import CreditPackage, PaymentTransaction

logger = logging.getLogger(__name__)


@login_required
def pricing(request):
    """Display pricing/credits page."""
    packages = CreditPackage.objects.filter(is_active=True).order_by('sort_order')
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    
    # Check if we're in simulation mode
    simulation_mode = getattr(settings, 'STRIPE_SIMULATION_MODE', False)
    
    return render(request, 'payments/pricing.html', {
        'packages': packages,
        'current_credits': seller_profile.credits_balance,
        'simulation_mode': simulation_mode,
    })


@login_required
def buy_credits(request, package_id):
    """Initiate credit purchase."""
    package = get_object_or_404(CreditPackage, pk=package_id, is_active=True)
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    
    # Check if we're in simulation mode
    simulation_mode = getattr(settings, 'STRIPE_SIMULATION_MODE', False)
    
    if simulation_mode:
        # Redirect to simulation confirmation page
        return redirect('payments:simulate_payment', package_id=package.id)
    
    # Check for payment method
    method = request.GET.get('method', 'stripe')
    
    if method == 'bank_transfer':
        # Generate reference and create pending transaction
        reference = PaymentTransaction.generate_reference_code()
        
        transaction = PaymentTransaction.objects.create(
            seller_profile=seller_profile,
            transaction_type=PaymentTransaction.TransactionType.CREDIT_PURCHASE,
            status=PaymentTransaction.TransactionStatus.PENDING,
            payment_method=PaymentTransaction.PaymentMethod.BANK_TRANSFER,
            amount=package.price,
            currency=package.currency,
            credits_purchased=package.credits,
            reference_code=reference,
            description=f"Achat {package.name} (Virement)",
        )
        
        return render(request, 'payments/bank_transfer.html', {
            'package': package,
            'transaction': transaction,
            'reference': reference,
            'bank_details': settings.BANK_DETAILS,
        })
    
    if method == 'check':
        # Generate reference and create pending transaction
        reference = PaymentTransaction.generate_reference_code()
        
        transaction = PaymentTransaction.objects.create(
            seller_profile=seller_profile,
            transaction_type=PaymentTransaction.TransactionType.CREDIT_PURCHASE,
            status=PaymentTransaction.TransactionStatus.PENDING,
            payment_method=PaymentTransaction.PaymentMethod.CHECK,
            amount=package.price,
            currency=package.currency,
            credits_purchased=package.credits,
            reference_code=reference,
            description=f"Achat {package.name} (Chèque)",
        )
        
        return render(request, 'payments/check_payment.html', {
            'package': package,
            'transaction': transaction,
            'reference': reference,
            'company_address': settings.COMPANY_ADDRESS,
        })
    
    # Real Stripe payment
    success_url = request.build_absolute_uri(reverse('payments:success'))
    cancel_url = request.build_absolute_uri(reverse('payments:pricing'))
    
    try:
        from apps.payments.services.stripe_service import StripeService
        stripe_service = StripeService()
        result = stripe_service.create_checkout_session(
            seller_profile=seller_profile,
            credit_package=package,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        
        return redirect(result['url'])
        
    except Exception as e:
        logger.error(f"Payment error: {str(e)}")
        messages.error(request, "Erreur lors de l'initialisation du paiement.")
        return redirect('payments:pricing')


@login_required
def simulate_payment(request, package_id):
    """Simulate payment page (development only)."""
    if not getattr(settings, 'STRIPE_SIMULATION_MODE', False):
        return redirect('payments:pricing')
    
    package = get_object_or_404(CreditPackage, pk=package_id, is_active=True)
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'confirm':
            # Create completed transaction
            transaction = PaymentTransaction.objects.create(
                seller_profile=seller_profile,
                transaction_type=PaymentTransaction.TransactionType.CREDIT_PURCHASE,
                amount=package.price,
                currency=package.currency,
                credits_purchased=package.credits,
                stripe_checkout_session_id=f"sim_{uuid.uuid4().hex[:16]}",
                description=f"Achat {package.name} (simulé)",
            )
            
            # Add credits
            seller_profile.add_credits(
                package.credits,
                f"Simulated purchase: {package.name}"
            )
            
            # Mark as completed
            transaction.mark_completed()
            
            messages.success(
                request, 
                f"✅ Paiement simulé réussi ! {package.credits} crédits ajoutés à votre compte."
            )
            return redirect('payments:success')
        
        elif action == 'cancel':
            messages.info(request, "Paiement annulé.")
            return redirect('payments:pricing')
    
    return render(request, 'payments/simulate_payment.html', {
        'package': package,
        'current_credits': seller_profile.credits_balance,
    })


@login_required
def payment_success(request):
    """Payment success page."""
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    return render(request, 'payments/success.html', {
        'current_credits': seller_profile.credits_balance,
    })


@login_required
def payment_history(request):
    """View payment history."""
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    
    transactions = PaymentTransaction.objects.filter(
        seller_profile=seller_profile
    ).order_by('-created_at')
    
    return render(request, 'payments/history.html', {
        'transactions': transactions,
        'current_credits': seller_profile.credits_balance,
    })
