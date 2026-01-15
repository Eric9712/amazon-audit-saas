"""
Payments Models
===============
Models for payment transactions and credit purchases.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PaymentTransaction(models.Model):
    """Record of all payment transactions."""
    
    class TransactionType(models.TextChoices):
        CREDIT_PURCHASE = 'credit_purchase', _('Achat de crédits')
        SUBSCRIPTION = 'subscription', _('Abonnement')
        REFUND = 'refund', _('Remboursement')
    
    class TransactionStatus(models.TextChoices):
        PENDING = 'pending', _('En attente')
        COMPLETED = 'completed', _('Complété')
        FAILED = 'failed', _('Échoué')
        REFUNDED = 'refunded', _('Remboursé')
        CANCELLED = 'cancelled', _('Annulé')
    
    class PaymentMethod(models.TextChoices):
        STRIPE = 'stripe', _('Carte Bancaire (Stripe)')
        BANK_TRANSFER = 'bank_transfer', _('Virement Bancaire')
        CHECK = 'check', _('Chèque Bancaire')
    
    seller_profile = models.ForeignKey(
        'accounts.SellerProfile',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        verbose_name=_('profil vendeur')
    )
    
    # Transaction details
    transaction_type = models.CharField(
        _('type'),
        max_length=30,
        choices=TransactionType.choices
    )
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING
    )
    payment_method = models.CharField(
        _('méthode de paiement'),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.STRIPE
    )
    reference_code = models.CharField(
        _('référence de commande'),
        max_length=20,
        blank=True,
        unique=True,
        null=True
    )
    
    # Amounts
    amount = models.DecimalField(_('montant'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('devise'), max_length=3, default='EUR')
    
    # Credits (for credit purchases)
    credits_purchased = models.IntegerField(_('crédits achetés'), default=0)
    
    # Stripe references
    stripe_payment_intent_id = models.CharField(
        _('ID Stripe Payment Intent'),
        max_length=100,
        blank=True,
        null=True
    )
    stripe_checkout_session_id = models.CharField(
        _('ID Stripe Checkout Session'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Metadata
    description = models.CharField(_('description'), max_length=500, blank=True)
    metadata = models.JSONField(_('métadonnées'), default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    completed_at = models.DateTimeField(_('complété le'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('transaction de paiement')
        verbose_name_plural = _('transactions de paiement')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} - €{self.amount} - {self.seller_profile.user.email}"
    
    def mark_completed(self):
        self.status = self.TransactionStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def mark_failed(self, reason: str = ''):
        self.status = self.TransactionStatus.FAILED
        self.metadata['failure_reason'] = reason
        self.save(update_fields=['status', 'metadata'])
    
    @staticmethod
    def generate_reference_code():
        """Generate a unique reference code for bank transfers."""
        import random
        import string
        
        while True:
            # Format: ORD-XXXX-XXXX (e.g., ORD-A7B2-9X4Y)
            chars = string.ascii_uppercase + string.digits
            part1 = ''.join(random.choices(chars, k=4))
            part2 = ''.join(random.choices(chars, k=4))
            code = f"ORD-{part1}-{part2}"
            
            if not PaymentTransaction.objects.filter(reference_code=code).exists():
                return code


class CreditPackage(models.Model):
    """Available credit packages for purchase."""
    
    name = models.CharField(_('nom'), max_length=100)
    credits = models.IntegerField(_('crédits'))
    price = models.DecimalField(_('prix'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('devise'), max_length=3, default='EUR')
    
    # Stripe
    stripe_price_id = models.CharField(
        _('ID prix Stripe'),
        max_length=100,
        blank=True
    )
    
    # Display
    is_popular = models.BooleanField(_('populaire'), default=False)
    is_active = models.BooleanField(_('actif'), default=True)
    sort_order = models.IntegerField(_('ordre'), default=0)
    
    class Meta:
        verbose_name = _('pack de crédits')
        verbose_name_plural = _('packs de crédits')
        ordering = ['sort_order', 'price']
    
    def __str__(self):
        return f"{self.name} - {self.credits} crédits - €{self.price}"
    
    @property
    def price_per_credit(self):
        if self.credits > 0:
            return self.price / self.credits
        return 0
