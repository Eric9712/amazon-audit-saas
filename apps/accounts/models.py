"""
Accounts Models
===============
Custom user model and seller profile for Amazon sellers.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from utils.helpers import generate_secure_token


class UserManager(BaseUserManager):
    """
    Custom user manager that uses email as the unique identifier.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a regular user with the given email and password.
        """
        if not email:
            raise ValueError(_('L\'adresse email est obligatoire'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser with the given email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model using email as the primary identifier.
    """
    
    # Remove username, use email as primary identifier
    username = None
    email = models.EmailField(
        _('adresse email'),
        unique=True,
        error_messages={
            'unique': _('Un utilisateur avec cette adresse email existe déjà.'),
        }
    )
    
    # Profile fields
    first_name = models.CharField(_('prénom'), max_length=150, blank=True)
    last_name = models.CharField(_('nom'), max_length=150, blank=True)
    phone = models.CharField(_('téléphone'), max_length=20, blank=True)
    company_name = models.CharField(_('nom de l\'entreprise'), max_length=200, blank=True)
    
    # Preferences
    email_notifications = models.BooleanField(
        _('notifications par email'),
        default=True,
        help_text=_('Recevoir les notifications de fin d\'audit par email')
    )
    preferred_language = models.CharField(
        _('langue préférée'),
        max_length=5,
        default='fr',
        choices=[
            ('fr', 'Français'),
            ('en', 'English'),
            ('de', 'Deutsch'),
            ('es', 'Español'),
            ('it', 'Italiano'),
        ]
    )
    
    # Metadata
    date_joined = models.DateTimeField(_('date d\'inscription'), default=timezone.now)
    last_login = models.DateTimeField(_('dernière connexion'), null=True, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = _('utilisateur')
        verbose_name_plural = _('utilisateurs')
        ordering = ['-date_joined']
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else self.email
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name if self.first_name else self.email.split('@')[0]
    
    @property
    def display_name(self):
        """Return a display name for the user."""
        if self.company_name:
            return self.company_name
        return self.get_full_name()


class SellerProfile(models.Model):
    """
    Extended profile for Amazon sellers.
    Contains subscription info and Amazon connection status.
    """
    
    class SubscriptionTier(models.TextChoices):
        FREE = 'free', _('Gratuit')
        STARTER = 'starter', _('Starter')
        PRO = 'pro', _('Professionnel')
        ENTERPRISE = 'enterprise', _('Entreprise')
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='seller_profile',
        verbose_name=_('utilisateur')
    )
    
    # Amazon Connection Status
    amazon_seller_id = models.CharField(
        _('ID vendeur Amazon'),
        max_length=50,
        blank=True,
        null=True,
        unique=True
    )
    amazon_marketplace_ids = models.JSONField(
        _('marketplaces Amazon'),
        default=list,
        blank=True,
        help_text=_('Liste des IDs de marketplace connectés')
    )
    amazon_connected_at = models.DateTimeField(
        _('date de connexion Amazon'),
        null=True,
        blank=True
    )
    amazon_token_expires_at = models.DateTimeField(
        _('expiration du token Amazon'),
        null=True,
        blank=True
    )
    
    # Subscription
    subscription_tier = models.CharField(
        _('niveau d\'abonnement'),
        max_length=20,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE
    )
    subscription_started_at = models.DateTimeField(
        _('début de l\'abonnement'),
        null=True,
        blank=True
    )
    subscription_ends_at = models.DateTimeField(
        _('fin de l\'abonnement'),
        null=True,
        blank=True
    )
    stripe_customer_id = models.CharField(
        _('ID client Stripe'),
        max_length=100,
        blank=True,
        null=True
    )
    stripe_subscription_id = models.CharField(
        _('ID abonnement Stripe'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Credits (for pay-per-case model)
    credits_balance = models.IntegerField(
        _('solde de crédits'),
        default=0,
        help_text=_('Crédits disponibles pour télécharger des dossiers')
    )
    
    # Statistics
    total_audits_run = models.IntegerField(_('nombre total d\'audits'), default=0)
    total_claims_generated = models.IntegerField(_('nombre total de réclamations'), default=0)
    total_estimated_recovery = models.DecimalField(
        _('montant total estimé récupérable'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifié le'), auto_now=True)
    
    class Meta:
        verbose_name = _('profil vendeur')
        verbose_name_plural = _('profils vendeurs')
    
    def __str__(self):
        return f"Profil de {self.user.email}"
    
    @property
    def is_amazon_connected(self) -> bool:
        """Check if Amazon account is connected and token is valid."""
        if not self.amazon_seller_id:
            return False
        
        if self.amazon_token_expires_at:
            return self.amazon_token_expires_at > timezone.now()
        
        return True
    
    @property
    def has_active_subscription(self) -> bool:
        """Check if user has an active paid subscription."""
        if self.subscription_tier == self.SubscriptionTier.FREE:
            return False
        
        if self.subscription_ends_at:
            return self.subscription_ends_at > timezone.now()
        
        return True
    
    @property
    def subscription_is_expiring_soon(self) -> bool:
        """Check if subscription expires within 7 days."""
        if not self.subscription_ends_at:
            return False
        
        expiry_threshold = timezone.now() + timezone.timedelta(days=7)
        return self.subscription_ends_at <= expiry_threshold
    
    def add_credits(self, amount: int, description: str = ''):
        """Add credits to the user's balance."""
        self.credits_balance += amount
        self.save(update_fields=['credits_balance', 'updated_at'])
        
        # Log the transaction
        CreditTransaction.objects.create(
            seller_profile=self,
            amount=amount,
            transaction_type=CreditTransaction.TransactionType.CREDIT,
            description=description
        )
    
    def deduct_credits(self, amount: int, description: str = '') -> bool:
        """
        Deduct credits from the user's balance.
        Returns True if successful, False if insufficient balance.
        """
        if self.credits_balance < amount:
            return False
        
        self.credits_balance -= amount
        self.save(update_fields=['credits_balance', 'updated_at'])
        
        # Log the transaction
        CreditTransaction.objects.create(
            seller_profile=self,
            amount=-amount,
            transaction_type=CreditTransaction.TransactionType.DEBIT,
            description=description
        )
        
        return True
    
    def disconnect_amazon(self):
        """Disconnect the Amazon account."""
        self.amazon_seller_id = None
        self.amazon_marketplace_ids = []
        self.amazon_connected_at = None
        self.amazon_token_expires_at = None
        self.save(update_fields=[
            'amazon_seller_id',
            'amazon_marketplace_ids',
            'amazon_connected_at',
            'amazon_token_expires_at',
            'updated_at'
        ])


class CreditTransaction(models.Model):
    """
    Log of all credit transactions for audit trail.
    """
    
    class TransactionType(models.TextChoices):
        CREDIT = 'credit', _('Crédit')
        DEBIT = 'debit', _('Débit')
        REFUND = 'refund', _('Remboursement')
        BONUS = 'bonus', _('Bonus')
    
    seller_profile = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='credit_transactions',
        verbose_name=_('profil vendeur')
    )
    amount = models.IntegerField(_('montant'))
    transaction_type = models.CharField(
        _('type de transaction'),
        max_length=20,
        choices=TransactionType.choices
    )
    description = models.TextField(_('description'), blank=True)
    reference = models.CharField(_('référence'), max_length=100, blank=True)
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('transaction de crédits')
        verbose_name_plural = _('transactions de crédits')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount} - {self.seller_profile.user.email}"


class LoginHistory(models.Model):
    """
    Track user login history for security monitoring.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_history',
        verbose_name=_('utilisateur')
    )
    ip_address = models.GenericIPAddressField(_('adresse IP'))
    user_agent = models.TextField(_('user agent'), blank=True)
    login_successful = models.BooleanField(_('connexion réussie'), default=True)
    login_at = models.DateTimeField(_('date de connexion'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('historique de connexion')
        verbose_name_plural = _('historiques de connexion')
        ordering = ['-login_at']
    
    def __str__(self):
        status = 'Succès' if self.login_successful else 'Échec'
        return f"{self.user.email} - {status} - {self.login_at}"


class APIKey(models.Model):
    """
    API keys for programmatic access (future feature).
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_('utilisateur')
    )
    name = models.CharField(_('nom'), max_length=100)
    key_prefix = models.CharField(_('préfixe de clé'), max_length=8)
    key_hash = models.CharField(_('hash de clé'), max_length=128)
    is_active = models.BooleanField(_('active'), default=True)
    last_used_at = models.DateTimeField(_('dernière utilisation'), null=True, blank=True)
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    expires_at = models.DateTimeField(_('expire le'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('clé API')
        verbose_name_plural = _('clés API')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
    
    @classmethod
    def generate_key(cls):
        """Generate a new API key."""
        return generate_secure_token(32)
    
    @property
    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return self.expires_at <= timezone.now()
    
    @property
    def is_valid(self) -> bool:
        """Check if the key is valid (active and not expired)."""
        return self.is_active and not self.is_expired
