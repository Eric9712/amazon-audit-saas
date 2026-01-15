"""
Payments Admin
==============
"""

from django.contrib import admin, messages
from .models import PaymentTransaction, CreditPackage


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'seller_profile', 'transaction_type', 'amount', 'status', 'payment_method', 'reference_code', 'credits_purchased', 'created_at')
    list_filter = ('transaction_type', 'status', 'payment_method', 'created_at')
    search_fields = ('seller_profile__user__email', 'stripe_payment_intent_id', 'reference_code')
    readonly_fields = ('created_at', 'completed_at', 'reference_code')
    actions = ['mark_as_paid']
    
    @admin.action(description='Valider le paiement (Virement Reçu)')
    def mark_as_paid(self, request, queryset):
        """Mark selected transactions as paid and deliver credits."""
        updated_count = 0
        already_paid_count = 0
        
        for transaction in queryset:
            if transaction.status == PaymentTransaction.TransactionStatus.COMPLETED:
                already_paid_count += 1
                continue
            
            # Add credits to seller
            transaction.seller_profile.add_credits(
                transaction.credits_purchased,
                f"Virement reçu: {transaction.reference_code}"
            )
            
            # Mark as completed
            transaction.mark_completed()
            updated_count += 1
        
        if updated_count > 0:
            self.message_user(request, f"{updated_count} transactions validées et crédits livrés.", messages.SUCCESS)
        
        if already_paid_count > 0:
            self.message_user(request, f"{already_paid_count} transactions étaient déjà validées.", messages.WARNING)


@admin.register(CreditPackage)
class CreditPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'credits', 'price', 'is_popular', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order', 'is_popular')
    ordering = ['sort_order']
