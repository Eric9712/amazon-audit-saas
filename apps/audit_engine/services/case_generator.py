"""
Case Generator Service
======================
Service for generating claim cases from detected losses.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

from django.db import transaction
from django.db.models import Sum, Min, Max, Count
from django.utils import timezone

from apps.audit_engine.models import Audit, LostItem, ClaimCase
from apps.audit_engine.constants import LossType, ClaimStatus
from utils.helpers import format_currency

logger = logging.getLogger(__name__)


CASE_TEMPLATE = """
Objet : Demande de remboursement - {sku}

Bonjour,

Je sollicite un remboursement pour les unités suivantes :

**Détails du produit :**
- SKU : {sku}
- FNSKU : {fnsku}
- ASIN : {asin}

**Détails de la perte :**
- Date : {incident_date}
- Quantité : {quantity} unités
- Valeur estimée : {estimated_value}
- Transaction ID: {transaction_id}

Cordialement,
{seller_name}
ID Vendeur : {seller_id}
""".strip()


class CaseGenerator:
    """Service for generating claim cases from detected losses."""
    
    def __init__(self, audit: Audit):
        self.audit = audit
        self.seller_profile = audit.seller_profile
    
    def generate_cases(self) -> int:
        """Generate claim cases by grouping losses by SKU and type."""
        logger.info(f"Generating cases for audit {self.audit.reference_code}")
        
        unassigned_items = LostItem.objects.filter(
            audit=self.audit,
            claim_case__isnull=True,
            is_reimbursed=False,
        ).exclude(
            incident_date__gt=timezone.now().date() - timezone.timedelta(days=45)
        )
        
        if not unassigned_items.exists():
            return 0
        
        groups = unassigned_items.values('sku', 'loss_type').annotate(
            total_quantity=Sum('quantity'),
            total_value=Sum('total_value'),
            item_count=Count('id'),
            earliest_date=Min('incident_date'),
            latest_date=Max('incident_date'),
        ).order_by('-total_value')
        
        cases_created = 0
        for group in groups:
            case = self._create_case_for_group(group, unassigned_items)
            if case:
                cases_created += 1
        
        logger.info(f"Generated {cases_created} cases")
        return cases_created
    
    @transaction.atomic
    def _create_case_for_group(self, group: Dict, items_queryset) -> Optional[ClaimCase]:
        sku = group['sku']
        loss_type = group['loss_type']
        loss_type_display = dict(LossType.CHOICES).get(loss_type, loss_type)
        title = f"{loss_type_display} - {sku}"
        
        group_items = items_queryset.filter(sku=sku, loss_type=loss_type)
        first_item = group_items.first()
        
        case = ClaimCase.objects.create(
            audit=self.audit,
            title=title,
            loss_type=loss_type,
            status=ClaimStatus.READY_TO_CLAIM,
            sku=sku,
            total_quantity=group['total_quantity'],
            total_value=group['total_value'],
            currency='EUR',
            earliest_date=group['earliest_date'],
            latest_date=group['latest_date'],
        )
        
        case.case_text = self._generate_case_text(case, first_item)
        case.save(update_fields=['case_text'])
        group_items.update(claim_case=case)
        
        return case
    
    def _generate_case_text(self, case: ClaimCase, sample_item: LostItem) -> str:
        seller_name = self.seller_profile.user.display_name
        seller_id = self.seller_profile.amazon_seller_id or 'N/A'
        formatted_value = format_currency(case.total_value, case.currency)
        
        return CASE_TEMPLATE.format(
            sku=case.sku,
            fnsku=sample_item.fnsku if sample_item else '',
            asin=sample_item.asin if sample_item else '',
            incident_date=case.earliest_date.strftime('%d/%m/%Y'),
            quantity=case.total_quantity,
            estimated_value=formatted_value,
            transaction_id=sample_item.transaction_id if sample_item else 'See attached',
            seller_name=seller_name,
            seller_id=seller_id,
        )
    
    def export_case_to_text(self, case: ClaimCase) -> str:
        sep = "=" * 60
        content = f"""
{sep}
DOSSIER DE RÉCLAMATION AMAZON
{sep}

Référence : {case.reference_code}
Type : {case.get_loss_type_display()}
SKU : {case.sku}
Quantité : {case.total_quantity} unités
Valeur : {format_currency(case.total_value, case.currency)}

{sep}
TEXTE À COPIER
{sep}

{case.case_text}

{sep}
"""
        return content
