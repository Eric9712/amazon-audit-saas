"""
Dashboard Views
===============
Main dashboard views for the application.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from apps.accounts.models import SellerProfile
from apps.audit_engine.models import Audit, ClaimCase
from apps.audit_engine.constants import AuditStatus

logger = logging.getLogger(__name__)


@login_required
def home(request):
    """Main dashboard home page."""
    user = request.user
    seller_profile, created = SellerProfile.objects.get_or_create(user=user)
    
    # Get all audits for this seller
    all_audits = Audit.objects.filter(seller_profile=seller_profile)
    
    # Get recent audits (for display)
    recent_audits = all_audits.order_by('-created_at')[:5]
    
    # Get running audit if any (separate query, not from sliced queryset)
    running_audit = all_audits.filter(
        status__in=[AuditStatus.PENDING, AuditStatus.FETCHING_DATA, AuditStatus.PROCESSING]
    ).order_by('-created_at').first()
    
    # Get latest completed audit (separate query)
    latest_audit = all_audits.filter(status=AuditStatus.COMPLETED).order_by('-created_at').first()
    
    # Get unpaid cases
    unpaid_cases = ClaimCase.objects.filter(
        audit__seller_profile=seller_profile,
        is_paid=False,
    ).order_by('-total_value')[:10]
    
    # Calculate total claimable - handle Decimal properly
    total_claimable = sum((c.total_value or 0) for c in unpaid_cases)
    
    context = {
        'seller_profile': seller_profile,
        'recent_audits': recent_audits,
        'running_audit': running_audit,
        'latest_audit': latest_audit,
        'unpaid_cases': unpaid_cases,
        'total_claimable': total_claimable,
    }
    
    return render(request, 'dashboard/home.html', context)


@login_required
def connect_amazon(request):
    """Page for connecting Amazon account."""
    user = request.user
    seller_profile, _ = SellerProfile.objects.get_or_create(user=user)
    
    if seller_profile.is_amazon_connected:
        messages.info(request, "Votre compte Amazon est déjà connecté.")
        return redirect('dashboard:home')
    
    return render(request, 'dashboard/connect_amazon.html', {
        'seller_profile': seller_profile,
    })


@login_required
def audit_status(request, audit_id):
    """Audit status page (delegates to audit_engine)."""
    from apps.audit_engine.views import audit_status as engine_audit_status
    return engine_audit_status(request, audit_id)
