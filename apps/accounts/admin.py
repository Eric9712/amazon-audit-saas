"""
Accounts Admin
==============
Django admin configuration for user management.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html

from .models import User, SellerProfile, CreditTransaction, LoginHistory, APIKey


class SellerProfileInline(admin.StackedInline):
    """Inline for SellerProfile in User admin."""
    model = SellerProfile
    can_delete = False
    verbose_name_plural = 'Profil Vendeur'
    fk_name = 'user'
    
    fieldsets = (
        ('Connexion Amazon', {
            'fields': (
                'amazon_seller_id',
                'amazon_marketplace_ids',
                'amazon_connected_at',
                'amazon_token_expires_at',
            )
        }),
        ('Abonnement', {
            'fields': (
                'subscription_tier',
                'subscription_started_at',
                'subscription_ends_at',
                'stripe_customer_id',
                'stripe_subscription_id',
            )
        }),
        ('Crédits', {
            'fields': ('credits_balance',)
        }),
        ('Statistiques', {
            'fields': (
                'total_audits_run',
                'total_claims_generated',
                'total_estimated_recovery',
            ),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = (
        'amazon_connected_at',
        'total_audits_run',
        'total_claims_generated',
        'total_estimated_recovery',
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin."""
    
    list_display = (
        'email',
        'display_name',
        'company_name',
        'is_active',
        'get_amazon_status',
        'get_subscription',
        'date_joined',
    )
    list_filter = (
        'is_active',
        'is_staff',
        'seller_profile__subscription_tier',
        'preferred_language',
        'date_joined',
    )
    search_fields = ('email', 'first_name', 'last_name', 'company_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informations personnelles'), {
            'fields': ('first_name', 'last_name', 'phone', 'company_name')
        }),
        (_('Préférences'), {
            'fields': ('email_notifications', 'preferred_language')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        (_('Dates importantes'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )
    
    inlines = [SellerProfileInline]
    readonly_fields = ('date_joined', 'last_login')
    
    def display_name(self, obj):
        return obj.display_name
    display_name.short_description = 'Nom affiché'
    
    def get_amazon_status(self, obj):
        if hasattr(obj, 'seller_profile') and obj.seller_profile.is_amazon_connected:
            return format_html(
                '<span style="color: green;">✓ Connecté</span>'
            )
        return format_html(
            '<span style="color: gray;">○ Non connecté</span>'
        )
    get_amazon_status.short_description = 'Amazon'
    
    def get_subscription(self, obj):
        if hasattr(obj, 'seller_profile'):
            tier = obj.seller_profile.subscription_tier
            colors = {
                'free': 'gray',
                'starter': 'blue',
                'pro': 'green',
                'enterprise': 'purple',
            }
            color = colors.get(tier, 'gray')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                obj.seller_profile.get_subscription_tier_display()
            )
        return '-'
    get_subscription.short_description = 'Abonnement'


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    """SellerProfile admin for standalone management."""
    
    list_display = (
        'user',
        'amazon_seller_id',
        'subscription_tier',
        'credits_balance',
        'total_audits_run',
        'is_amazon_connected_display',
        'created_at',
    )
    list_filter = (
        'subscription_tier',
        'created_at',
    )
    search_fields = (
        'user__email',
        'user__company_name',
        'amazon_seller_id',
    )
    readonly_fields = (
        'total_audits_run',
        'total_claims_generated',
        'total_estimated_recovery',
        'created_at',
        'updated_at',
    )
    
    def is_amazon_connected_display(self, obj):
        if obj.is_amazon_connected:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    is_amazon_connected_display.short_description = 'Amazon Connecté'


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    """CreditTransaction admin."""
    
    list_display = (
        'seller_profile',
        'transaction_type',
        'amount',
        'description',
        'created_at',
    )
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('seller_profile__user__email', 'description', 'reference')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    """LoginHistory admin."""
    
    list_display = (
        'user',
        'ip_address',
        'login_successful',
        'login_at',
    )
    list_filter = ('login_successful', 'login_at')
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('user', 'ip_address', 'user_agent', 'login_successful', 'login_at')
    date_hierarchy = 'login_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """APIKey admin."""
    
    list_display = (
        'name',
        'user',
        'key_prefix',
        'is_active',
        'last_used_at',
        'expires_at',
        'created_at',
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__email', 'key_prefix')
    readonly_fields = ('key_prefix', 'key_hash', 'created_at', 'last_used_at')
