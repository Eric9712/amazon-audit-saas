"""
Audit Engine Celery Tasks
=========================
Asynchronous tasks for running audits in the background.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.accounts.models import SellerProfile
from apps.audit_engine.models import Audit, AuditReport
from apps.audit_engine.constants import AuditStatus
from apps.amazon_integration.services.reports_service import ReportsService
from apps.audit_engine.services.data_processor import DataProcessor
from apps.audit_engine.services.loss_detector import LossDetector
from apps.audit_engine.services.case_generator import CaseGenerator
from utils.helpers import calculate_date_range

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_full_audit(self, audit_id: int):
    """
    Run a complete audit for a seller.
    This is the main task that orchestrates the entire audit process.
    
    Args:
        audit_id: ID of the Audit to run
    """
    try:
        audit = Audit.objects.get(pk=audit_id)
    except Audit.DoesNotExist:
        logger.error(f"Audit {audit_id} not found")
        return {'error': 'Audit not found'}
    
    logger.info(f"Starting audit {audit.reference_code} for {audit.seller_profile.user.email}")
    
    # Mark as started
    audit.mark_started(self.request.id)
    
    try:
        # =====================================================================
        # STEP 1: Request and download reports from Amazon
        # =====================================================================
        audit.update_progress(10, 'Requesting reports from Amazon...')
        
        reports_service = ReportsService(audit.seller_profile)
        
        # Request all needed reports
        report_requests = reports_service.request_all_audit_reports(
            start_date=audit.start_date,
            end_date=audit.end_date,
        )
        
        audit.update_progress(20, f'Waiting for {len(report_requests)} reports...')
        
        # Wait for reports and download them
        reports_data = {}
        
        for i, report_request in enumerate(report_requests):
            progress = 20 + int((i / len(report_requests)) * 30)
            audit.update_progress(progress, f'Downloading report {i+1}/{len(report_requests)}...')
            
            try:
                # Wait for report to be ready
                reports_service.wait_for_report(report_request, max_wait_seconds=600)
                
                # Download
                file_path, df = reports_service.download_report(report_request)
                reports_data[report_request.report_type] = df
                
                # Save audit report record
                AuditReport.objects.create(
                    audit=audit,
                    report_request=report_request,
                    report_type=report_request.report_type,
                    file_path=file_path,
                    row_count=len(df),
                )
                
            except Exception as e:
                with open('error_log.txt', 'a') as f:
                    import traceback
                    f.write(f"CRITICAL: Failed to get report {report_request.report_type}: {type(e)} {str(e)}\n")
                    traceback.print_exc(file=f)
                logger.error(f"Failed to get report {report_request.report_type}: {str(e)}")
                # Continue with other reports
                continue
        
        if not reports_data:
            raise Exception("No reports could be downloaded from Amazon")
        
        # =====================================================================
        # STEP 2: Analyze data and detect losses
        # =====================================================================
        audit.mark_processing()
        audit.update_progress(50, 'Analyzing data...')
        
        loss_detector = LossDetector(audit)
        analysis_results = loss_detector.analyze(reports_data)
        
        # =====================================================================
        # STEP 3: Generate claim cases
        # =====================================================================
        audit.update_progress(80, 'Generating claim cases...')
        
        case_generator = CaseGenerator(audit)
        cases_count = case_generator.generate_cases()
        
        # =====================================================================
        # STEP 4: Finalize and save results
        # =====================================================================
        audit.update_progress(95, 'Finalizing...')
        
        # Get final summary
        summary = loss_detector.get_summary()
        
        # Mark completed
        audit.mark_completed(
            total_items=analysis_results.get('total_items_analyzed', 0),
            total_losses=summary['total_losses'],
            estimated_value=summary['total_value'],
            already_reimbursed=summary['reimbursed_value'],
            claimable=summary['claimable_value'],
        )
        
        logger.info(
            f"Audit {audit.reference_code} completed: "
            f"{summary['total_losses']} losses, "
            f"€{summary['claimable_value']:.2f} claimable, "
            f"{cases_count} cases generated"
        )
        
        # =====================================================================
        # STEP 5: Send notification email
        # =====================================================================
        # Call directly instead of .delay() to avoid Celery broker connection
        send_audit_complete_email(audit.pk)
        
        return {
            'success': True,
            'audit_id': audit.pk,
            'reference': audit.reference_code,
            'losses': summary['total_losses'],
            'claimable_value': float(summary['claimable_value']),
            'cases_generated': cases_count,
        }
        
    except Exception as e:
        import traceback
        with open('main_error.txt', 'w') as f:
            traceback.print_exc(file=f)
        logger.exception(f"Audit {audit.reference_code} failed: {str(e)}")
        audit.mark_failed(str(e))
        
        # Retry for transient errors
        if 'throttl' in str(e).lower() or '429' in str(e):
            raise self.retry(exc=e, countdown=120)
        
        return {'success': False, 'error': str(e)}


@shared_task
def send_audit_complete_email(audit_id: int):
    """Send email notification when audit is complete."""
    try:
        audit = Audit.objects.select_related('seller_profile__user').get(pk=audit_id)
    except Audit.DoesNotExist:
        return
    
    user = audit.seller_profile.user
    
    if not user.email_notifications:
        return
    
    # Render email template
    context = {
        'user': user,
        'audit': audit,
        'claimable_amount': audit.total_claimable,
        'cases_count': audit.claim_cases.count(),
    }
    
    html_content = render_to_string('emails/audit_complete.html', context)
    text_content = render_to_string('emails/audit_complete.txt', context)
    
    send_mail(
        subject=f"🎉 Votre audit Amazon est terminé - {audit.total_claimable}€ récupérables",
        message=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_content,
        fail_silently=True,
    )
    
    logger.info(f"Sent audit complete email to {user.email}")


@shared_task
def check_stale_audits():
    """Check for audits that have been running too long and mark them as failed."""
    stale_threshold = timezone.now() - timedelta(hours=2)
    
    stale_audits = Audit.objects.filter(
        status__in=[AuditStatus.PENDING, AuditStatus.FETCHING_DATA, AuditStatus.PROCESSING],
        started_at__lt=stale_threshold,
    )
    
    for audit in stale_audits:
        logger.warning(f"Marking stale audit {audit.reference_code} as failed")
        audit.mark_failed("Audit timed out after 2 hours")
    
    return {'stale_audits_marked': stale_audits.count()}


@shared_task
def cleanup_temp_files():
    """Clean up temporary files older than 7 days."""
    import os
    import shutil
    from pathlib import Path
    
    reports_dir = Path(settings.MEDIA_ROOT) / 'reports'
    
    if not reports_dir.exists():
        return {'cleaned': 0}
    
    cutoff = timezone.now() - timedelta(days=7)
    cleaned = 0
    
    for seller_dir in reports_dir.iterdir():
        if not seller_dir.is_dir():
            continue
        
        for file_path in seller_dir.glob('*'):
            if file_path.is_file():
                mtime = timezone.datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    file_path.unlink()
                    cleaned += 1
    
    logger.info(f"Cleaned up {cleaned} old report files")
    return {'cleaned': cleaned}
