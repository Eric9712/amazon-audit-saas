"""
Audit Engine Models
===================
Models for tracking audits, lost items, and claim cases.
"""

from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from utils.helpers import generate_reference_code
from .constants import LossType, ClaimStatus, AuditStatus


class Audit(models.Model):
    """
    Represents a complete audit run for a seller.
    """
    
    seller_profile = models.ForeignKey(
        'accounts.SellerProfile',
        on_delete=models.CASCADE,
        related_name='audits',
        verbose_name=_('profil vendeur')
    )
    
    # Reference
    reference_code = models.CharField(
        _('code de référence'),
        max_length=50,
        unique=True,
        db_index=True
    )
    
    # Date range analyzed
    start_date = models.DateField(_('date de début'))
    end_date = models.DateField(_('date de fin'))
    
    # Status
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=AuditStatus.CHOICES,
        default=AuditStatus.PENDING
    )
    progress_percentage = models.IntegerField(_('progression'), default=0)
    current_step = models.CharField(_('étape en cours'), max_length=200, blank=True)
    error_message = models.TextField(_('message d\'erreur'), blank=True)
    
    # Celery task tracking
    celery_task_id = models.CharField(
        _('ID tâche Celery'),
        max_length=100,
        blank=True,
        null=True
    )
    
    # Results summary
    total_items_analyzed = models.IntegerField(_('articles analysés'), default=0)
    total_losses_detected = models.IntegerField(_('pertes détectées'), default=0)
    total_estimated_value = models.DecimalField(
        _('valeur totale estimée'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_already_reimbursed = models.DecimalField(
        _('déjà remboursé'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    total_claimable = models.DecimalField(
        _('réclamable'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    started_at = models.DateTimeField(_('démarré le'), null=True, blank=True)
    completed_at = models.DateTimeField(_('terminé le'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('audit')
        verbose_name_plural = _('audits')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller_profile', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reference_code']),
        ]
    
    def __str__(self):
        return f"Audit {self.reference_code} - {self.seller_profile.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = generate_reference_code('AUD')
        super().save(*args, **kwargs)
    
    @property
    def duration_seconds(self) -> int:
        """Calculate audit duration in seconds."""
        if not self.started_at:
            return 0
        
        end_time = self.completed_at or timezone.now()
        return int((end_time - self.started_at).total_seconds())
    
    @property
    def is_running(self) -> bool:
        """Check if audit is currently running."""
        return self.status in (AuditStatus.PENDING, AuditStatus.FETCHING_DATA, AuditStatus.PROCESSING)
    
    @property
    def is_completed(self) -> bool:
        """Check if audit is completed."""
        return self.status == AuditStatus.COMPLETED
    
    def update_progress(self, percentage: int, step: str = ''):
        """Update audit progress."""
        self.progress_percentage = min(100, max(0, percentage))
        if step:
            self.current_step = step
        self.save(update_fields=['progress_percentage', 'current_step'])
    
    def mark_started(self, celery_task_id: str = None):
        """Mark audit as started."""
        self.status = AuditStatus.FETCHING_DATA
        self.started_at = timezone.now()
        if celery_task_id:
            self.celery_task_id = celery_task_id
        self.save(update_fields=['status', 'started_at', 'celery_task_id'])
    
    def mark_processing(self):
        """Mark audit as processing data."""
        self.status = AuditStatus.PROCESSING
        self.save(update_fields=['status'])
    
    def mark_completed(
        self,
        total_items: int,
        total_losses: int,
        estimated_value: Decimal,
        already_reimbursed: Decimal,
        claimable: Decimal
    ):
        """Mark audit as completed with results."""
        self.status = AuditStatus.COMPLETED
        self.progress_percentage = 100
        self.current_step = 'Terminé'
        self.completed_at = timezone.now()
        self.total_items_analyzed = total_items
        self.total_losses_detected = total_losses
        self.total_estimated_value = estimated_value
        self.total_already_reimbursed = already_reimbursed
        self.total_claimable = claimable
        self.save()
        
        # Update seller profile stats
        self.seller_profile.total_audits_run += 1
        self.seller_profile.total_estimated_recovery = (
            self.seller_profile.total_estimated_recovery or Decimal('0')
        ) + claimable
        self.seller_profile.save(update_fields=[
            'total_audits_run',
            'total_estimated_recovery',
            'updated_at'
        ])
    
    def mark_failed(self, error_message: str):
        """Mark audit as failed."""
        self.status = AuditStatus.FAILED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])


class LostItem(models.Model):
    """
    Represents a single lost/damaged item detected during an audit.
    This is the granular level before grouping into cases.
    """
    
    audit = models.ForeignKey(
        Audit,
        on_delete=models.CASCADE,
        related_name='lost_items',
        verbose_name=_('audit')
    )
    
    # Product identification
    sku = models.CharField(_('SKU'), max_length=100, db_index=True)
    fnsku = models.CharField(_('FNSKU'), max_length=50, blank=True)
    asin = models.CharField(_('ASIN'), max_length=20, blank=True)
    product_title = models.CharField(_('titre du produit'), max_length=500, blank=True)
    
    # Loss details
    loss_type = models.CharField(
        _('type de perte'),
        max_length=30,
        choices=LossType.CHOICES
    )
    quantity = models.IntegerField(_('quantité'))
    unit_value = models.DecimalField(
        _('valeur unitaire'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    total_value = models.DecimalField(
        _('valeur totale'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    currency = models.CharField(_('devise'), max_length=3, default='EUR')
    
    # Amazon references
    transaction_id = models.CharField(
        _('ID transaction'),
        max_length=100,
        blank=True,
        db_index=True
    )
    order_id = models.CharField(_('ID commande'), max_length=50, blank=True)
    fulfillment_center = models.CharField(_('centre de distribution'), max_length=20, blank=True)
    reason_code = models.CharField(_('code raison'), max_length=10, blank=True)
    reason_description = models.CharField(_('description raison'), max_length=200, blank=True)
    
    # Dates
    incident_date = models.DateField(_('date de l\'incident'))
    detected_at = models.DateTimeField(_('détecté le'), auto_now_add=True)
    
    # Reimbursement tracking
    reimbursement_id = models.CharField(
        _('ID remboursement'),
        max_length=100,
        blank=True,
        null=True
    )
    reimbursement_amount = models.DecimalField(
        _('montant remboursé'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    is_reimbursed = models.BooleanField(_('remboursé'), default=False)
    
    # Idempotency check (to prevent duplicate claims)
    unique_hash = models.CharField(
        _('hash unique'),
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_('Hash pour éviter les doublons')
    )
    
    # Link to case (if grouped)
    claim_case = models.ForeignKey(
        'ClaimCase',
        on_delete=models.SET_NULL,
        related_name='items',
        null=True,
        blank=True,
        verbose_name=_('dossier de réclamation')
    )
    
    class Meta:
        verbose_name = _('article perdu')
        verbose_name_plural = _('articles perdus')
        ordering = ['-incident_date']
        indexes = [
            models.Index(fields=['audit', 'loss_type']),
            models.Index(fields=['sku', '-incident_date']),
            models.Index(fields=['is_reimbursed', '-incident_date']),
        ]
    
    def __str__(self):
        return f"{self.sku} - {self.get_loss_type_display()} - {self.quantity} unités"
    
    def save(self, *args, **kwargs):
        # Calculate total value
        self.total_value = self.quantity * self.unit_value
        super().save(*args, **kwargs)
    
    @property
    def is_claimable(self) -> bool:
        """Check if this item can be claimed (not reimbursed, not too recent)."""
        if self.is_reimbursed:
            return False
        
        from utils.helpers import is_within_45_day_window
        return not is_within_45_day_window(self.incident_date)


class ClaimCase(models.Model):
    """
    A grouped claim case that combines related lost items into a single dossier.
    This is what the user will download and submit to Amazon.
    """
    
    audit = models.ForeignKey(
        Audit,
        on_delete=models.CASCADE,
        related_name='claim_cases',
        verbose_name=_('audit')
    )
    
    # Reference
    reference_code = models.CharField(
        _('code de référence'),
        max_length=50,
        unique=True,
        db_index=True
    )
    
    # Case details
    title = models.CharField(_('titre'), max_length=200)
    loss_type = models.CharField(
        _('type de perte'),
        max_length=30,
        choices=LossType.CHOICES
    )
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=ClaimStatus.CHOICES,
        default=ClaimStatus.DETECTED
    )
    
    # Aggregated info
    sku = models.CharField(_('SKU principal'), max_length=100)
    total_quantity = models.IntegerField(_('quantité totale'))
    total_value = models.DecimalField(
        _('valeur totale'),
        max_digits=12,
        decimal_places=2
    )
    currency = models.CharField(_('devise'), max_length=3, default='EUR')
    
    # Date range of incidents
    earliest_date = models.DateField(_('date la plus ancienne'))
    latest_date = models.DateField(_('date la plus récente'))
    
    # Generated content
    case_text = models.TextField(
        _('texte de réclamation'),
        blank=True,
        help_text=_('Texte pré-généré pour la réclamation')
    )
    supporting_data = models.JSONField(
        _('données complémentaires'),
        default=dict,
        blank=True
    )
    
    # User interaction
    user_notes = models.TextField(_('notes utilisateur'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifié le'), auto_now=True)
    claimed_at = models.DateTimeField(_('réclamé le'), null=True, blank=True)
    
    # Outcome tracking
    amazon_case_id = models.CharField(
        _('ID cas Amazon'),
        max_length=50,
        blank=True
    )
    outcome_amount = models.DecimalField(
        _('montant obtenu'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    outcome_notes = models.TextField(_('notes sur le résultat'), blank=True)
    
    # Download tracking
    download_count = models.IntegerField(_('nombre de téléchargements'), default=0)
    last_downloaded_at = models.DateTimeField(
        _('dernier téléchargement'),
        null=True,
        blank=True
    )
    is_paid = models.BooleanField(
        _('payé'),
        default=False,
        help_text=_('Le dossier a été acheté')
    )
    
    class Meta:
        verbose_name = _('dossier de réclamation')
        verbose_name_plural = _('dossiers de réclamation')
        ordering = ['-total_value']
        indexes = [
            models.Index(fields=['audit', 'status']),
            models.Index(fields=['status', '-total_value']),
            models.Index(fields=['sku', '-created_at']),
        ]
    
    def __str__(self):
        return f"Case {self.reference_code} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = generate_reference_code('CAS')
        super().save(*args, **kwargs)
    
    @property
    def item_count(self) -> int:
        """Number of items in this case."""
        return self.items.count()
    
    @property
    def is_downloadable(self) -> bool:
        """Check if case can be downloaded."""
        return self.status in (ClaimStatus.READY_TO_CLAIM, ClaimStatus.PENDING_REVIEW)
    
    def mark_claimed(self, amazon_case_id: str = None):
        """Mark the case as claimed."""
        self.status = ClaimStatus.CLAIMED
        self.claimed_at = timezone.now()
        if amazon_case_id:
            self.amazon_case_id = amazon_case_id
        self.save(update_fields=['status', 'claimed_at', 'amazon_case_id', 'updated_at'])
    
    def record_download(self):
        """Record a download of this case."""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.save(update_fields=['download_count', 'last_downloaded_at'])


class AuditReport(models.Model):
    """
    Stores raw report data downloaded during an audit.
    """
    
    audit = models.ForeignKey(
        Audit,
        on_delete=models.CASCADE,
        related_name='audit_reports',
        verbose_name=_('audit')
    )
    
    report_request = models.ForeignKey(
        'amazon_integration.ReportRequest',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_reports',
        verbose_name=_('demande de rapport')
    )
    
    report_type = models.CharField(_('type de rapport'), max_length=100)
    file_path = models.CharField(_('chemin du fichier'), max_length=500)
    row_count = models.IntegerField(_('nombre de lignes'), null=True)
    
    # Processing status
    is_processed = models.BooleanField(_('traité'), default=False)
    processed_at = models.DateTimeField(_('traité le'), null=True, blank=True)
    processing_notes = models.TextField(_('notes de traitement'), blank=True)
    
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('rapport d\'audit')
        verbose_name_plural = _('rapports d\'audit')
        ordering = ['audit', 'report_type']
    
    def __str__(self):
        return f"{self.report_type} for Audit {self.audit.reference_code}"
