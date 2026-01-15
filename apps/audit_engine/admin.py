"""
Audit Engine Admin
==================
Django admin configuration for audit monitoring.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Audit, LostItem, ClaimCase, AuditReport


class LostItemInline(admin.TabularInline):
    """Inline for displaying lost items in audit."""
    model = LostItem
    extra = 0
    readonly_fields = (
        'sku', 'loss_type', 'quantity', 'total_value',
        'incident_date', 'is_reimbursed'
    )
    can_delete = False
    max_num = 20
    
    def has_add_permission(self, request, obj=None):
        return False


class ClaimCaseInline(admin.TabularInline):
    """Inline for displaying claim cases in audit."""
    model = ClaimCase
    extra = 0
    readonly_fields = (
        'reference_code', 'title', 'status', 'total_quantity',
        'total_value', 'is_paid'
    )
    can_delete = False
    max_num = 20
    
    def has_add_permission(self, request, obj=None):
        return False


class AuditReportInline(admin.TabularInline):
    """Inline for displaying audit reports."""
    model = AuditReport
    extra = 0
    readonly_fields = (
        'report_type', 'file_path', 'row_count',
        'is_processed', 'created_at'
    )
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Audit)
class AuditAdmin(admin.ModelAdmin):
    """Audit admin."""
    
    list_display = (
        'reference_code',
        'seller_profile',
        'status_badge',
        'progress_display',
        'date_range',
        'losses_summary',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'reference_code',
        'seller_profile__user__email',
        'seller_profile__amazon_seller_id',
    )
    readonly_fields = (
        'reference_code',
        'celery_task_id',
        'total_items_analyzed',
        'total_losses_detected',
        'total_estimated_value',
        'total_already_reimbursed',
        'total_claimable',
        'created_at',
        'started_at',
        'completed_at',
    )
    date_hierarchy = 'created_at'
    inlines = [AuditReportInline, ClaimCaseInline]
    
    fieldsets = (
        ('Informations', {
            'fields': (
                'reference_code',
                'seller_profile',
                'start_date',
                'end_date',
            )
        }),
        ('Statut', {
            'fields': (
                'status',
                'progress_percentage',
                'current_step',
                'error_message',
                'celery_task_id',
            )
        }),
        ('Résultats', {
            'fields': (
                'total_items_analyzed',
                'total_losses_detected',
                'total_estimated_value',
                'total_already_reimbursed',
                'total_claimable',
            )
        }),
        ('Dates', {
            'fields': ('created_at', 'started_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'fetching': 'blue',
            'processing': 'orange',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};"><strong>{}</strong></span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Statut'
    
    def progress_display(self, obj):
        if obj.status == 'completed':
            return '100%'
        return f"{obj.progress_percentage}%"
    progress_display.short_description = 'Progression'
    
    def date_range(self, obj):
        return f"{obj.start_date} → {obj.end_date}"
    date_range.short_description = 'Période'
    
    def losses_summary(self, obj):
        return format_html(
            '<strong>{}</strong> pertes<br/>€{:,.2f} réclamable',
            obj.total_losses_detected,
            obj.total_claimable
        )
    losses_summary.short_description = 'Résumé'


@admin.register(LostItem)
class LostItemAdmin(admin.ModelAdmin):
    """LostItem admin."""
    
    list_display = (
        'id',
        'audit_link',
        'sku',
        'loss_type',
        'quantity',
        'total_value',
        'incident_date',
        'is_reimbursed_badge',
        'claim_case_link',
    )
    list_filter = ('loss_type', 'is_reimbursed', 'incident_date')
    search_fields = ('sku', 'fnsku', 'asin', 'transaction_id')
    readonly_fields = (
        'unique_hash',
        'detected_at',
    )
    date_hierarchy = 'incident_date'
    
    def audit_link(self, obj):
        url = reverse('admin:audit_engine_audit_change', args=[obj.audit.pk])
        return format_html('<a href="{}">{}</a>', url, obj.audit.reference_code)
    audit_link.short_description = 'Audit'
    
    def is_reimbursed_badge(self, obj):
        if obj.is_reimbursed:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_reimbursed_badge.short_description = 'Remboursé'
    
    def claim_case_link(self, obj):
        if obj.claim_case:
            url = reverse('admin:audit_engine_claimcase_change', args=[obj.claim_case.pk])
            return format_html('<a href="{}">{}</a>', url, obj.claim_case.reference_code)
        return '-'
    claim_case_link.short_description = 'Dossier'


@admin.register(ClaimCase)
class ClaimCaseAdmin(admin.ModelAdmin):
    """ClaimCase admin."""
    
    list_display = (
        'reference_code',
        'title_short',
        'audit_link',
        'loss_type',
        'status_badge',
        'total_quantity',
        'total_value',
        'is_paid_badge',
        'download_count',
    )
    list_filter = ('status', 'loss_type', 'is_paid', 'created_at')
    search_fields = ('reference_code', 'sku', 'title')
    readonly_fields = (
        'reference_code',
        'download_count',
        'last_downloaded_at',
        'created_at',
        'updated_at',
        'claimed_at',
    )
    
    fieldsets = (
        ('Identification', {
            'fields': ('reference_code', 'audit', 'title', 'sku')
        }),
        ('Détails', {
            'fields': (
                'loss_type',
                'status',
                'total_quantity',
                'total_value',
                'currency',
                'earliest_date',
                'latest_date',
            )
        }),
        ('Contenu', {
            'fields': ('case_text', 'supporting_data', 'user_notes'),
            'classes': ('collapse',),
        }),
        ('Paiement et téléchargement', {
            'fields': (
                'is_paid',
                'download_count',
                'last_downloaded_at',
            )
        }),
        ('Résultat', {
            'fields': (
                'amazon_case_id',
                'outcome_amount',
                'outcome_notes',
                'claimed_at',
            ),
            'classes': ('collapse',),
        }),
    )
    
    def title_short(self, obj):
        if len(obj.title) > 40:
            return obj.title[:40] + '...'
        return obj.title
    title_short.short_description = 'Titre'
    
    def audit_link(self, obj):
        url = reverse('admin:audit_engine_audit_change', args=[obj.audit.pk])
        return format_html('<a href="{}">{}</a>', url, obj.audit.reference_code)
    audit_link.short_description = 'Audit'
    
    def status_badge(self, obj):
        colors = {
            'detected': 'gray',
            'pending': 'blue',
            'ready': 'green',
            'claimed': 'purple',
            'approved': 'darkgreen',
            'rejected': 'red',
            'partial': 'orange',
            'expired': 'gray',
            'duplicate': 'gray',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};"><strong>{}</strong></span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Statut'
    
    def is_paid_badge(self, obj):
        if obj.is_paid:
            return format_html('<span style="color: green;">✓ Payé</span>')
        return format_html('<span style="color: gray;">-</span>')
    is_paid_badge.short_description = 'Payé'


@admin.register(AuditReport)
class AuditReportAdmin(admin.ModelAdmin):
    """AuditReport admin."""
    
    list_display = (
        'id',
        'audit',
        'report_type',
        'row_count',
        'is_processed',
        'created_at',
    )
    list_filter = ('report_type', 'is_processed', 'created_at')
    search_fields = ('audit__reference_code', 'file_path')
    readonly_fields = ('created_at', 'processed_at')
