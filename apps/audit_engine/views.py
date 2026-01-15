"""
Audit Engine Views
==================
Views for audit management and results display.
"""

import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone

from apps.accounts.models import SellerProfile
from apps.audit_engine.models import Audit, ClaimCase, LostItem
from apps.audit_engine.constants import AuditStatus
from apps.audit_engine.tasks import run_full_audit
from apps.audit_engine.services.case_generator import CaseGenerator
from utils.helpers import calculate_date_range
from utils.decorators import require_amazon_connected

logger = logging.getLogger(__name__)


@login_required
@require_amazon_connected
def start_audit(request):
    """Start a new audit."""
    user = request.user
    seller_profile = user.seller_profile
    
    # Check for existing running audit
    running_audit = Audit.objects.filter(
        seller_profile=seller_profile,
        status__in=[AuditStatus.PENDING, AuditStatus.FETCHING_DATA, AuditStatus.PROCESSING]
    ).first()
    
    if running_audit:
        messages.warning(
            request,
            f"Un audit est déjà en cours ({running_audit.reference_code}). "
            "Veuillez attendre qu'il se termine."
        )
        return redirect('dashboard:audit_status', audit_id=running_audit.pk)
    
    if request.method == 'POST':
        # Calculate date range (18 months back)
        start_date, end_date = calculate_date_range(months_back=18)
        
        # Create audit
        audit = Audit.objects.create(
            seller_profile=seller_profile,
            start_date=start_date,
            end_date=end_date,
            status=AuditStatus.PENDING,
        )
        
        # Launch async task
        # Launch async task
        try:
            run_full_audit.delay(audit.pk)
        except Exception as e:
            logger.warning(f"Broker connection failed ({e}). Running audit synchronously.")
            run_full_audit(audit.pk)
        
        logger.info(f"Started audit {audit.reference_code} for {user.email}")
        
        messages.success(
            request,
            f"Votre audit a été lancé ! Référence: {audit.reference_code}. "
            "Vous recevrez un email quand il sera terminé."
        )
        
        return redirect('dashboard:audit_status', audit_id=audit.pk)
    
    # GET: show confirmation page
    start_date, end_date = calculate_date_range(months_back=18)
    
    return render(request, 'dashboard/start_audit.html', {
        'seller_profile': seller_profile,
        'start_date': start_date,
        'end_date': end_date,
        'period_months': 18,
    })


@login_required
def audit_status(request, audit_id):
    """Check audit status."""
    audit = get_object_or_404(
        Audit,
        pk=audit_id,
        seller_profile=request.user.seller_profile
    )
    
    return render(request, 'dashboard/audit_status.html', {
        'audit': audit,
    })


@login_required
def audit_status_api(request, audit_id):
    """API endpoint for audit status polling."""
    try:
        audit = Audit.objects.get(
            pk=audit_id,
            seller_profile=request.user.seller_profile
        )
    except Audit.DoesNotExist:
        return JsonResponse({'error': 'Audit not found'}, status=404)
    
    return JsonResponse({
        'id': audit.pk,
        'reference': audit.reference_code,
        'status': audit.status,
        'status_display': audit.get_status_display(),
        'progress': audit.progress_percentage,
        'current_step': audit.current_step,
        'is_running': audit.is_running,
        'is_completed': audit.is_completed,
        'error_message': audit.error_message if audit.status == AuditStatus.FAILED else None,
        'results': {
            'losses_detected': audit.total_losses_detected,
            'estimated_value': float(audit.total_estimated_value),
            'claimable': float(audit.total_claimable),
        } if audit.is_completed else None,
    })


@login_required
def audit_results(request, audit_id):
    """Display audit results."""
    audit = get_object_or_404(
        Audit,
        pk=audit_id,
        seller_profile=request.user.seller_profile,
        status=AuditStatus.COMPLETED
    )
    
    cases = audit.claim_cases.all().order_by('-total_value')
    
    return render(request, 'dashboard/audit_results.html', {
        'audit': audit,
        'cases': cases,
        'total_cases': cases.count(),
    })


@login_required
def case_detail(request, case_id):
    """View case details."""
    case = get_object_or_404(
        ClaimCase,
        pk=case_id,
        audit__seller_profile=request.user.seller_profile
    )
    
    items = case.items.all().order_by('-incident_date')
    
    return render(request, 'dashboard/case_detail.html', {
        'case': case,
        'items': items,
        'audit': case.audit,
    })


@login_required
@require_POST
def download_case(request, case_id):
    """Download case file (requires payment)."""
    case = get_object_or_404(
        ClaimCase,
        pk=case_id,
        audit__seller_profile=request.user.seller_profile
    )
    
    seller_profile = request.user.seller_profile
    
    # Check if already paid or has credits
    if not case.is_paid:
        # Check credits
        from django.conf import settings
        credits_needed = 1  # 1 credit per case
        
        if seller_profile.credits_balance < credits_needed:
            messages.error(
                request,
                "Crédits insuffisants. Veuillez acheter des crédits pour télécharger ce dossier."
            )
            return redirect('payments:buy_credits')
        
        # Deduct credits
        success = seller_profile.deduct_credits(
            credits_needed,
            f"Download case {case.reference_code}"
        )
        
        if success:
            case.is_paid = True
            case.save(update_fields=['is_paid'])
    
    # Generate text file
    case_generator = CaseGenerator(case.audit)
    content = case_generator.export_case_to_text(case)
    
    # Record download
    case.record_download()
    
    # Return as downloadable file
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    filename = f"dossier_{case.reference_code}.txt"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@login_required
def audit_history(request):
    """View audit history."""
    audits = Audit.objects.filter(
        seller_profile=request.user.seller_profile
    ).order_by('-created_at')
    
    return render(request, 'dashboard/audit_history.html', {
        'audits': audits,
    })
