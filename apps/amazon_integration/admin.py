"""
Amazon Integration Admin
========================
Django admin configuration for Amazon integration monitoring.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AmazonCredentials, APIRequestLog, ReportRequest


@admin.register(AmazonCredentials)
class AmazonCredentialsAdmin(admin.ModelAdmin):
    """Admin for Amazon credentials (sensitive data hidden)."""
    
    list_display = (
        'seller_profile',
        'seller_id',
        'marketplace_id',
        'get_token_status',
        'last_api_call_at',
        'updated_at',
    )
    list_filter = ('updated_at',)
    search_fields = (
        'seller_profile__user__email',
        'seller_id',
    )
    readonly_fields = (
        'seller_id',
        'marketplace_id',
        'marketplace_ids',
        'access_token_expires_at',
        'last_api_call_at',
        'created_at',
        'updated_at',
    )
    
    # Never show encrypted tokens
    exclude = ('_refresh_token_encrypted', '_access_token_encrypted', 'oauth_state')
    
    def get_token_status(self, obj):
        if obj.is_access_token_valid:
            return format_html('<span style="color: green;">✓ Valide</span>')
        return format_html('<span style="color: orange;">⚠ Expiré</span>')
    get_token_status.short_description = 'Token'


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    """Admin for API request logs."""
    
    list_display = (
        'id',
        'seller_profile',
        'method',
        'endpoint_short',
        'status_badge',
        'http_status_code',
        'duration_ms',
        'request_at',
    )
    list_filter = ('status', 'method', 'request_at')
    search_fields = ('endpoint', 'seller_profile__user__email')
    readonly_fields = (
        'seller_profile',
        'endpoint',
        'method',
        'request_params',
        'status',
        'http_status_code',
        'response_body',
        'error_message',
        'request_at',
        'response_at',
        'duration_ms',
        'retry_count',
    )
    date_hierarchy = 'request_at'
    
    def endpoint_short(self, obj):
        """Show truncated endpoint."""
        if len(obj.endpoint) > 50:
            return obj.endpoint[:50] + '...'
        return obj.endpoint
    endpoint_short.short_description = 'Endpoint'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'success': 'green',
            'failed': 'red',
            'throttled': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Statut'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReportRequest)
class ReportRequestAdmin(admin.ModelAdmin):
    """Admin for report requests."""
    
    list_display = (
        'id',
        'seller_profile',
        'report_type',
        'status_badge',
        'data_start_date',
        'data_end_date',
        'row_count',
        'created_at',
    )
    list_filter = ('status', 'report_type', 'created_at')
    search_fields = (
        'seller_profile__user__email',
        'report_id',
        'report_document_id',
    )
    readonly_fields = (
        'report_id',
        'report_document_id',
        'file_size_bytes',
        'row_count',
        'completed_at',
        'created_at',
        'updated_at',
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Vendeur', {
            'fields': ('seller_profile', 'marketplace_ids')
        }),
        ('Rapport', {
            'fields': (
                'report_type',
                'data_start_date',
                'data_end_date',
                'report_id',
                'report_document_id',
            )
        }),
        ('Statut', {
            'fields': ('status', 'error_message')
        }),
        ('Fichier', {
            'fields': ('file_path', 'file_size_bytes', 'row_count'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',),
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'gray',
            'processing': 'blue',
            'done': 'green',
            'downloaded': 'darkgreen',
            'failed': 'red',
            'cancelled': 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Statut'
