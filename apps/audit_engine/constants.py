"""
Audit Engine Constants
======================
Constants and configuration values for the audit engine.
"""

from django.conf import settings


# =============================================================================
# TIMING RULES
# =============================================================================

# Amazon's 45-day rule: Don't claim losses within this period
LOSS_DETECTION_DELAY_DAYS = getattr(settings, 'LOSS_DETECTION_DELAY_DAYS', 45)

# Maximum history to analyze (months)
MAX_HISTORY_MONTHS = getattr(settings, 'MAX_HISTORY_MONTHS', 18)


# =============================================================================
# LOSS TYPES
# =============================================================================

class LossType:
    """Types of inventory losses that can be detected."""
    
    LOST_INBOUND = 'lost_inbound'           # Lost during inbound shipment
    LOST_WAREHOUSE = 'lost_warehouse'        # Lost in Amazon warehouse
    DAMAGED_WAREHOUSE = 'damaged_warehouse'  # Damaged in warehouse
    DAMAGED_INBOUND = 'damaged_inbound'      # Damaged during receiving
    DESTROYED = 'destroyed'                  # Destroyed by Amazon
    CUSTOMER_RETURN_LOST = 'return_lost'     # Customer return never received
    CUSTOMER_RETURN_DAMAGED = 'return_damaged'  # Customer return damaged
    WRONG_REIMBURSEMENT = 'wrong_reimbursement'  # Incorrect reimbursement amount
    NO_REIMBURSEMENT = 'no_reimbursement'    # Expected reimbursement not received
    OVERCHARGED_FEE = 'overcharged_fee'      # Overcharged FBA fees
    
    CHOICES = [
        (LOST_INBOUND, 'Perdu à la réception'),
        (LOST_WAREHOUSE, 'Perdu en entrepôt'),
        (DAMAGED_WAREHOUSE, 'Endommagé en entrepôt'),
        (DAMAGED_INBOUND, 'Endommagé à la réception'),
        (DESTROYED, 'Détruit par Amazon'),
        (CUSTOMER_RETURN_LOST, 'Retour client perdu'),
        (CUSTOMER_RETURN_DAMAGED, 'Retour client endommagé'),
        (WRONG_REIMBURSEMENT, 'Remboursement incorrect'),
        (NO_REIMBURSEMENT, 'Aucun remboursement'),
        (OVERCHARGED_FEE, 'Frais surtarifés'),
    ]


# =============================================================================
# CLAIM STATUS
# =============================================================================

class ClaimStatus:
    """Status of claim cases."""
    
    DETECTED = 'detected'         # Just detected, not yet reviewed
    PENDING_REVIEW = 'pending'    # Waiting for user review
    READY_TO_CLAIM = 'ready'      # Ready to be claimed with Amazon
    CLAIMED = 'claimed'           # Claim submitted to Amazon
    APPROVED = 'approved'         # Amazon approved the reimbursement
    REJECTED = 'rejected'         # Amazon rejected the claim
    PARTIAL = 'partial'           # Partially reimbursed
    EXPIRED = 'expired'           # Too old to claim
    DUPLICATE = 'duplicate'       # Duplicate case
    
    CHOICES = [
        (DETECTED, 'Détecté'),
        (PENDING_REVIEW, 'En attente de révision'),
        (READY_TO_CLAIM, 'Prêt à réclamer'),
        (CLAIMED, 'Réclamé'),
        (APPROVED, 'Approuvé'),
        (REJECTED, 'Rejeté'),
        (PARTIAL, 'Partiellement remboursé'),
        (EXPIRED, 'Expiré'),
        (DUPLICATE, 'Doublon'),
    ]


# =============================================================================
# AUDIT STATUS
# =============================================================================

class AuditStatus:
    """Status of an audit."""
    
    PENDING = 'pending'           # Waiting to start
    FETCHING_DATA = 'fetching'    # Downloading reports from Amazon
    PROCESSING = 'processing'     # Analyzing data
    COMPLETED = 'completed'       # Audit completed
    FAILED = 'failed'             # Audit failed
    CANCELLED = 'cancelled'       # Audit cancelled by user
    
    CHOICES = [
        (PENDING, 'En attente'),
        (FETCHING_DATA, 'Téléchargement des données'),
        (PROCESSING, 'Traitement en cours'),
        (COMPLETED, 'Terminé'),
        (FAILED, 'Échec'),
        (CANCELLED, 'Annulé'),
    ]


# =============================================================================
# REPORT COLUMN MAPPINGS
# =============================================================================

# Standard column names for different report types
COLUMN_MAPPINGS = {
    'inventory_adjustments': {
        'adjusted_date': ['adjusted-date', 'adjusted_date', 'date'],
        'fnsku': ['fnsku', 'fn-sku'],
        'sku': ['sku', 'seller-sku', 'seller_sku'],
        'asin': ['asin'],
        'disposition': ['disposition'],
        'reason': ['reason'],
        'quantity': ['quantity', 'qty'],
        'fulfillment_center_id': ['fulfillment-center-id', 'fc-id', 'warehouse'],
    },
    'reimbursements': {
        'reimbursement_id': ['reimbursement-id', 'reimbursement_id'],
        'case_id': ['case-id', 'case_id'],
        'approval_date': ['approval-date', 'approval_date'],
        'sku': ['sku', 'seller-sku'],
        'fnsku': ['fnsku'],
        'asin': ['asin'],
        'reason': ['reason'],
        'quantity': ['quantity-reimbursed-cash', 'quantity', 'qty'],
        'amount': ['amount-total', 'amount', 'reimbursement-amount'],
        'currency': ['currency-unit', 'currency'],
    },
    'returns': {
        'return_date': ['return-date', 'return_date'],
        'order_id': ['order-id', 'order_id', 'amazon-order-id'],
        'sku': ['sku', 'seller-sku'],
        'asin': ['asin'],
        'fnsku': ['fnsku'],
        'quantity': ['quantity', 'qty'],
        'status': ['status', 'detailed-disposition'],
        'reason': ['reason', 'customer-reason'],
    },
    'shipments': {
        'shipment_id': ['shipment-id', 'shipment_id', 'fba-shipment-id'],
        'shipment_name': ['shipment-name'],
        'shipment_date': ['shipment-date', 'ship-date'],
        'sku': ['sku', 'seller-sku'],
        'quantity_shipped': ['quantity-shipped', 'shipped-quantity'],
        'quantity_received': ['quantity-received', 'received-quantity'],
    },
}


# =============================================================================
# ADJUSTMENT REASON CODES
# =============================================================================

# Amazon inventory adjustment reason codes that indicate a loss
LOSS_REASON_CODES = {
    # Warehouse losses
    'M': 'Unrecoverable Inventory - Missing',
    'E': 'Warehouse Damage',
    'D': 'Damaged',
    'L': 'Lost',
    
    # Customer returns
    'G': 'Customer Damaged',
    'H': 'Defective - Customer Return',
    
    # Other
    'K': 'Destroyed',
    'F': 'Expired',
    'Q': 'Quality Issue',
}

# Reason codes that should result in automatic reimbursement from Amazon
REIMBURSABLE_REASON_CODES = ['M', 'E', 'D', 'L', 'K']


# =============================================================================
# CASE FILE TEMPLATES
# =============================================================================

CASE_FILE_TEMPLATE_LOST = """
Objet : Demande de remboursement pour unités perdues - {sku}

Bonjour,

Je sollicite un remboursement pour les unités suivantes qui ont été perdues dans votre centre de distribution :

**Détails du produit :**
- SKU : {sku}
- FNSKU : {fnsku}
- ASIN : {asin}
- Titre : {title}

**Détails de la perte :**
- Date de l'incident : {incident_date}
- Centre de distribution : {fulfillment_center}
- Quantité perdue : {quantity} unités
- Valeur estimée : {estimated_value}

**Preuves :**
- Rapport d'ajustement d'inventaire: Pièce jointe
- Transaction ID: {transaction_id}

Conformément à la politique FBA, je demande un remboursement pour ces unités perdues dans vos centres de distribution.

Cordialement,
{seller_name}
ID Vendeur : {seller_id}
""".strip()

CASE_FILE_TEMPLATE_DAMAGED = """
Objet : Demande de remboursement pour unités endommagées - {sku}

Bonjour,

Je sollicite un remboursement pour les unités suivantes qui ont été endommagées dans votre centre de distribution :

**Détails du produit :**
- SKU : {sku}
- FNSKU : {fnsku}
- ASIN : {asin}
- Titre : {title}

**Détails des dommages :**
- Date de l'incident : {incident_date}
- Centre de distribution : {fulfillment_center}
- Quantité endommagée : {quantity} unités
- Valeur estimée : {estimated_value}
- Raison : {damage_reason}

**Preuves :**
- Rapport d'ajustement d'inventaire: Pièce jointe
- Transaction ID: {transaction_id}

Les dommages ont été causés par vos équipes de manutention, conformément aux données du rapport d'ajustement.

Cordialement,
{seller_name}
ID Vendeur : {seller_id}
""".strip()

CASE_FILE_TEMPLATE_RETURN = """
Objet : Demande de remboursement pour retour client non reçu - {sku}

Bonjour,

Un client a retourné un article mais celui-ci n'a pas été correctement enregistré dans mon inventaire :

**Détails du produit :**
- SKU : {sku}
- FNSKU : {fnsku}
- ASIN : {asin}
- Titre : {title}

**Détails du retour :**
- ID Commande : {order_id}
- Date du retour : {return_date}
- Quantité retournée : {quantity} unités
- Valeur estimée : {estimated_value}

**Problème :**
Le client a été remboursé mais l'article n'a jamais été reçu ou réintégré à mon inventaire vendable. 
Conformément à la politique FBA, si un retour n'est pas reçu dans les 45 jours, un remboursement doit être accordé.

Cordialement,
{seller_name}
ID Vendeur : {seller_id}
""".strip()
