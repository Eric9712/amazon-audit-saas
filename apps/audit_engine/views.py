"""
Audit Engine Views
==================
Views for audit management and results display.
"""

import logging
import csv
import io
from datetime import date, datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone

from apps.accounts.models import SellerProfile
from apps.audit_engine.models import Audit, ClaimCase, LostItem, AuditReport
from apps.audit_engine.constants import AuditStatus
from apps.audit_engine.tasks import run_full_audit
from apps.audit_engine.services.case_generator import CaseGenerator
from utils.helpers import calculate_date_range

logger = logging.getLogger(__name__)


@login_required
def start_audit(request):
    """Start a new audit."""
    user = request.user
    seller_profile = user.seller_profile
    
    running_audit = Audit.objects.filter(
        seller_profile=seller_profile,
        status__in=[AuditStatus.PENDING, AuditStatus.FETCHING_DATA, AuditStatus.PROCESSING]
    ).first()
    
    if running_audit:
        messages.warning(request, f"Un audit est deja en cours ({running_audit.reference_code}).")
        return redirect('dashboard:audit_status', audit_id=running_audit.pk)
    
    if request.method == 'POST':
        start_date, end_date = calculate_date_range(months_back=18)
        
        audit = Audit.objects.create(
            seller_profile=seller_profile,
            start_date=start_date,
            end_date=end_date,
            status=AuditStatus.PENDING,
        )
        
        try:
            run_full_audit.delay(audit.pk)
        except Exception as e:
            logger.warning(f"Broker connection failed ({e}). Running audit synchronously.")
            run_full_audit(audit.pk)
        
        messages.success(request, f"Votre audit a ete lance ! Reference: {audit.reference_code}.")
        return redirect('dashboard:audit_status', audit_id=audit.pk)
    
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
    audit = get_object_or_404(Audit, pk=audit_id, seller_profile=request.user.seller_profile)
    return render(request, 'dashboard/audit_status.html', {'audit': audit})


@login_required
def audit_status_api(request, audit_id):
    """API endpoint for audit status polling."""
    try:
        audit = Audit.objects.get(pk=audit_id, seller_profile=request.user.seller_profile)
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
    case = get_object_or_404(ClaimCase, pk=case_id, audit__seller_profile=request.user.seller_profile)
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
    case = get_object_or_404(ClaimCase, pk=case_id, audit__seller_profile=request.user.seller_profile)
    seller_profile = request.user.seller_profile
    
    if not case.is_paid:
        credits_needed = 1
        if seller_profile.credits_balance < credits_needed:
            messages.error(request, "Credits insuffisants.")
            return redirect('payments:buy_credits')
        
        success = seller_profile.deduct_credits(credits_needed, f"Download case {case.reference_code}")
        if success:
            case.is_paid = True
            case.save(update_fields=['is_paid'])
    
    case_generator = CaseGenerator(case.audit)
    content = case_generator.export_case_to_text(case)
    case.record_download()
    
    response = HttpResponse(content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="dossier_{case.reference_code}.txt"'
    return response


@login_required
def audit_history(request):
    """View audit history."""
    audits = Audit.objects.filter(seller_profile=request.user.seller_profile).order_by('-created_at')
    return render(request, 'dashboard/audit_history.html', {'audits': audits})


@login_required
def upload_reports(request):
    """Upload Amazon reports manually (CSV files)."""
    seller_profile, _ = SellerProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        uploaded_file = request.FILES.get('report_file')
        
        if not uploaded_file:
            messages.error(request, "Veuillez selectionner un fichier.")
            return redirect('audit_engine:upload_reports')
        
        if not uploaded_file.name.endswith(('.csv', '.txt')):
            messages.error(request, "Format invalide. Veuillez importer un fichier CSV ou TXT.")
            return redirect('audit_engine:upload_reports')
        
        try:
            file_content = uploaded_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(file_content))
            rows = list(reader)
            
            if not rows:
                messages.error(request, "Le fichier est vide ou mal formate.")
                return redirect('audit_engine:upload_reports')
            
            audit = Audit.objects.create(
                seller_profile=seller_profile,
                start_date=date.today().replace(month=1, day=1),
                end_date=date.today(),
                status=AuditStatus.COMPLETED,
                current_step="Analyse du fichier importe",
            )
            
            AuditReport.objects.create(
                audit=audit,
                report_type='reimbursements',
                raw_data={'rows': rows[:1000], 'total_rows': len(rows)},
            )
            
            losses_detected = 0
            total_value = Decimal('0.00')
            
            for row in rows:
                amount = row.get('amount-total', row.get('total', row.get('montant', '0')))
                try:
                    amount_value = Decimal(str(amount).replace(',', '.').replace(' ', ''))
                    if amount_value < 0:
                        losses_detected += 1
                        total_value += abs(amount_value)
                        
                        LostItem.objects.create(
                            audit=audit,
                            loss_type='inventory_lost',
                            sku=row.get('sku', row.get('SKU', 'UNKNOWN')),
                            fnsku=row.get('fnsku', row.get('FNSKU', '')),
                            quantity=1,
                            estimated_value=abs(amount_value),
                            incident_date=date.today(),
                            status='detected',
                            raw_data=row,
                        )
                except (ValueError, TypeError):
                    continue
            
            audit.current_step = "Analyse terminee"
            audit.save()
            
            seller_profile.is_amazon_connected = True
            seller_profile.save()
            
            messages.success(request, f"Fichier analyse ! {len(rows)} lignes, {losses_detected} anomalies ({total_value:.2f} EUR).")
            return redirect('audit_engine:audit_results', audit_id=audit.pk)
            
        except Exception as e:
            logger.error(f"Error processing uploaded file: {e}")
            messages.error(request, f"Erreur lors de l'analyse du fichier: {str(e)}")
            return redirect('audit_engine:upload_reports')
    
    return render(request, 'dashboard/upload_reports.html', {'seller_profile': seller_profile})
