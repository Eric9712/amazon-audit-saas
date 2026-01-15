"""
Payments Admin
==============
"""

from django.contrib import admin
from .models import PaymentTransaction, CreditPackage


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'seller_profile', 'transaction_type', 'amount', 'status', 'credits_purchased', 'created_at')
    list_filter = ('transaction_type', 'status', 'created_at')
    search_fields = ('seller_profile__user__email', 'stripe_payment_intent_id')
    readonly_fields = ('created_at', 'completed_at')


@admin.register(CreditPackage)
class CreditPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'credits', 'price', 'is_popular', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order', 'is_popular')
    ordering = ['sort_order']
