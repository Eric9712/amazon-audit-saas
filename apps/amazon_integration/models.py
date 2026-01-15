"""
Amazon Integration Models
=========================
Models for storing Amazon API credentials and request logs.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from cryptography.fernet import Fernet
from django.conf import settings

import base64
import hashlib


def get_encryption_key():
    """
    Generate a Fernet-compatible encryption key from Django's SECRET_KEY.
    """
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


class AmazonCredentials(models.Model):
    """
    Securely stores Amazon SP-API credentials for each seller.
    Tokens are encrypted at rest.
    """
    
    seller_profile = models.OneToOneField(
        'accounts.SellerProfile',
        on_delete=models.CASCADE,
        related_name='amazon_credentials',
        verbose_name=_('profil vendeur')
    )
    
    # Encrypted tokens
    _refresh_token_encrypted = models.BinaryField(
        verbose_name=_('token de rafraîchissement (chiffré)'),
        null=True,
        blank=True
    )
    _access_token_encrypted = models.BinaryField(
        verbose_name=_('token d\'accès (chiffré)'),
        null=True,
        blank=True
    )
    
    # Token metadata
    access_token_expires_at = models.DateTimeField(
        _('expiration du token d\'accès'),
        null=True,
        blank=True
    )
    
    # Seller info from Amazon
    seller_id = models.CharField(
        _('ID vendeur'),
        max_length=50,
        blank=True
    )
    marketplace_id = models.CharField(
        _('ID marketplace principal'),
        max_length=50,
        blank=True
    )
    marketplace_ids = models.JSONField(
        _('IDs des marketplaces'),
        default=list,
        blank=True
    )
    
    # OAuth state token (for CSRF protection during OAuth flow)
    oauth_state = models.CharField(
        _('état OAuth'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifié le'), auto_now=True)
    last_api_call_at = models.DateTimeField(
        _('dernier appel API'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('credentials Amazon')
        verbose_name_plural = _('credentials Amazon')
    
    def __str__(self):
        return f"Credentials pour {self.seller_profile.user.email}"
    
    def _encrypt(self, data: str) -> bytes:
        """Encrypt a string value."""
        if not data:
            return None
        fernet = Fernet(get_encryption_key())
        return fernet.encrypt(data.encode())
    
    def _decrypt(self, data: bytes) -> str:
        """Decrypt a bytes value."""
        if not data:
            return None
        fernet = Fernet(get_encryption_key())
        return fernet.decrypt(data).decode()
    
    @property
    def refresh_token(self) -> str:
        """Get decrypted refresh token."""
        return self._decrypt(self._refresh_token_encrypted)
    
    @refresh_token.setter
    def refresh_token(self, value: str):
        """Set and encrypt refresh token."""
        self._refresh_token_encrypted = self._encrypt(value)
    
    @property
    def access_token(self) -> str:
        """Get decrypted access token."""
        return self._decrypt(self._access_token_encrypted)
    
    @access_token.setter
    def access_token(self, value: str):
        """Set and encrypt access token."""
        self._access_token_encrypted = self._encrypt(value)
    
    @property
    def is_access_token_valid(self) -> bool:
        """Check if access token is still valid."""
        if not self.access_token or not self.access_token_expires_at:
            return False
        # Add 5 minute buffer
        return self.access_token_expires_at > timezone.now() + timezone.timedelta(minutes=5)
    
    def update_tokens(self, access_token: str, expires_in: int, refresh_token: str = None):
        """
        Update tokens after a refresh.
        
        Args:
            access_token: New access token
            expires_in: Seconds until expiration
            refresh_token: New refresh token (optional)
        """
        self.access_token = access_token
        self.access_token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        
        if refresh_token:
            self.refresh_token = refresh_token
        
        self.save(update_fields=[
            '_access_token_encrypted',
            'access_token_expires_at',
            '_refresh_token_encrypted' if refresh_token else None,
            'updated_at'
        ])


class APIRequestLog(models.Model):
    """
    Log of all Amazon API requests for monitoring and debugging.
    """
    
    class RequestStatus(models.TextChoices):
        PENDING = 'pending', _('En attente')
        SUCCESS = 'success', _('Succès')
        FAILED = 'failed', _('Échec')
        THROTTLED = 'throttled', _('Rate limited')
    
    seller_profile = models.ForeignKey(
        'accounts.SellerProfile',
        on_delete=models.CASCADE,
        related_name='api_request_logs',
        verbose_name=_('profil vendeur'),
        null=True,
        blank=True
    )
    
    # Request details
    endpoint = models.CharField(_('endpoint'), max_length=500)
    method = models.CharField(_('méthode HTTP'), max_length=10)
    request_params = models.JSONField(_('paramètres'), default=dict, blank=True)
    
    # Response details
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING
    )
    http_status_code = models.IntegerField(_('code HTTP'), null=True, blank=True)
    response_body = models.TextField(_('corps de la réponse'), blank=True)
    error_message = models.TextField(_('message d\'erreur'), blank=True)
    
    # Timing
    request_at = models.DateTimeField(_('date de la requête'), auto_now_add=True)
    response_at = models.DateTimeField(_('date de la réponse'), null=True, blank=True)
    duration_ms = models.IntegerField(_('durée (ms)'), null=True, blank=True)
    
    # Retry info
    retry_count = models.IntegerField(_('nombre de tentatives'), default=0)
    
    class Meta:
        verbose_name = _('log de requête API')
        verbose_name_plural = _('logs de requêtes API')
        ordering = ['-request_at']
        indexes = [
            models.Index(fields=['seller_profile', '-request_at']),
            models.Index(fields=['status', '-request_at']),
            models.Index(fields=['endpoint', '-request_at']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status}"
    
    def mark_success(self, http_status_code: int, response_body: str = ''):
        """Mark the request as successful."""
        self.status = self.RequestStatus.SUCCESS
        self.http_status_code = http_status_code
        self.response_body = response_body[:5000] if response_body else ''  # Limit size
        self.response_at = timezone.now()
        
        if self.request_at:
            delta = self.response_at - self.request_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        
        self.save()
    
    def mark_failed(self, http_status_code: int = None, error_message: str = ''):
        """Mark the request as failed."""
        self.status = self.RequestStatus.FAILED
        self.http_status_code = http_status_code
        self.error_message = error_message
        self.response_at = timezone.now()
        
        if self.request_at:
            delta = self.response_at - self.request_at
            self.duration_ms = int(delta.total_seconds() * 1000)
        
        self.save()
    
    def mark_throttled(self, retry_after: int = None):
        """Mark the request as throttled (rate limited)."""
        self.status = self.RequestStatus.THROTTLED
        self.http_status_code = 429
        self.error_message = f"Rate limited. Retry after: {retry_after}s" if retry_after else "Rate limited"
        self.response_at = timezone.now()
        self.save()


class ReportRequest(models.Model):
    """
    Track Amazon report requests and their status.
    Reports are requested asynchronously and must be polled for completion.
    """
    
    class ReportType(models.TextChoices):
        # Inventory reports
        FBA_INVENTORY = 'GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA', _('Inventaire FBA')
        FBA_INVENTORY_AGE = 'GET_FBA_INVENTORY_AGED_DATA', _('Âge inventaire FBA')
        
        # Reimbursement reports
        FBA_REIMBURSEMENTS = 'GET_FBA_REIMBURSEMENTS_DATA', _('Remboursements FBA')
        
        # Shipment reports
        FBA_SHIPMENTS = 'GET_AMAZON_FULFILLED_SHIPMENTS_DATA_GENERAL', _('Expéditions FBA')
        FBA_CUSTOMER_SHIPMENT_SALES = 'GET_FBA_FULFILLMENT_CUSTOMER_SHIPMENT_SALES_DATA', _('Ventes expédiées')
        
        # Returns reports
        FBA_RETURNS = 'GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA', _('Retours FBA')
        
        # Removal reports
        FBA_REMOVAL_ORDER = 'GET_FBA_FULFILLMENT_REMOVAL_ORDER_DETAIL_DATA', _('Ordres de retrait')
        FBA_REMOVAL_SHIPMENT = 'GET_FBA_FULFILLMENT_REMOVAL_SHIPMENT_DETAIL_DATA', _('Expéditions de retrait')
        
        # Inventory adjustments
        FBA_INVENTORY_ADJUSTMENTS = 'GET_FBA_FULFILLMENT_INVENTORY_ADJUSTMENTS_DATA', _('Ajustements inventaire')
        
        # Monthly storage fees
        FBA_STORAGE_FEES = 'GET_FBA_STORAGE_FEE_CHARGES_DATA', _('Frais de stockage')
    
    class ReportStatus(models.TextChoices):
        PENDING = 'pending', _('En attente')
        PROCESSING = 'processing', _('En cours')
        DONE = 'done', _('Terminé')
        DOWNLOADED = 'downloaded', _('Téléchargé')
        FAILED = 'failed', _('Échec')
        CANCELLED = 'cancelled', _('Annulé')
    
    seller_profile = models.ForeignKey(
        'accounts.SellerProfile',
        on_delete=models.CASCADE,
        related_name='report_requests',
        verbose_name=_('profil vendeur')
    )
    
    # Report details
    report_type = models.CharField(
        _('type de rapport'),
        max_length=100,
        choices=ReportType.choices
    )
    marketplace_ids = models.JSONField(
        _('marketplaces'),
        default=list
    )
    
    # Amazon report IDs
    report_id = models.CharField(
        _('ID de rapport Amazon'),
        max_length=100,
        blank=True,
        null=True,
        db_index=True
    )
    report_document_id = models.CharField(
        _('ID de document de rapport'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Date range
    data_start_date = models.DateField(_('date de début des données'))
    data_end_date = models.DateField(_('date de fin des données'))
    
    # Status
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING
    )
    error_message = models.TextField(_('message d\'erreur'), blank=True)
    
    # File storage
    file_path = models.CharField(
        _('chemin du fichier'),
        max_length=500,
        blank=True
    )
    file_size_bytes = models.BigIntegerField(
        _('taille du fichier (octets)'),
        null=True,
        blank=True
    )
    row_count = models.IntegerField(
        _('nombre de lignes'),
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifié le'), auto_now=True)
    completed_at = models.DateTimeField(_('terminé le'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('demande de rapport')
        verbose_name_plural = _('demandes de rapports')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller_profile', 'report_type', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['report_id']),
        ]
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.seller_profile.user.email}"
    
    def mark_processing(self, report_id: str):
        """Mark the report as processing (Amazon has accepted the request)."""
        self.report_id = report_id
        self.status = self.ReportStatus.PROCESSING
        self.save(update_fields=['report_id', 'status', 'updated_at'])
    
    def mark_done(self, report_document_id: str):
        """Mark the report as done (ready for download)."""
        self.report_document_id = report_document_id
        self.status = self.ReportStatus.DONE
        self.completed_at = timezone.now()
        self.save(update_fields=[
            'report_document_id',
            'status',
            'completed_at',
            'updated_at'
        ])
    
    def mark_downloaded(self, file_path: str, file_size: int, row_count: int = None):
        """Mark the report as downloaded."""
        self.file_path = file_path
        self.file_size_bytes = file_size
        self.row_count = row_count
        self.status = self.ReportStatus.DOWNLOADED
        self.save(update_fields=[
            'file_path',
            'file_size_bytes',
            'row_count',
            'status',
            'updated_at'
        ])
    
    def mark_failed(self, error_message: str):
        """Mark the report as failed."""
        self.status = self.ReportStatus.FAILED
        self.error_message = error_message
        self.save(update_fields=['status', 'error_message', 'updated_at'])
