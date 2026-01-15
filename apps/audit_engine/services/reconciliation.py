"""
Reconciliation Service
======================
Core reconciliation algorithm for detecting inventory discrepancies.
"""

import hashlib
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit_engine.models import Audit, LostItem, ClaimCase
from apps.audit_engine.constants import (
    LossType,
    ClaimStatus,
    LOSS_DETECTION_DELAY_DAYS,
    LOSS_REASON_CODES,
    REIMBURSABLE_REASON_CODES,
)
from utils.helpers import is_within_45_day_window
from utils.exceptions import ReconciliationError

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Service for reconciling Amazon inventory data and detecting losses.
    """
    
    def __init__(self, audit: Audit):
        """
        Initialize the reconciliation service.
        
        Args:
            audit: The Audit instance to reconcile data for
        """
        self.audit = audit
        self.seller_profile = audit.seller_profile
        self.delay_days = getattr(settings, 'LOSS_DETECTION_DELAY_DAYS', 45)
        
        # Cutoff date for claims (45-day rule)
        self.claim_cutoff_date = timezone.now().date() - timedelta(days=self.delay_days)
        
        # Statistics
        self.stats = {
            'total_adjustments': 0,
            'losses_detected': 0,
            'already_reimbursed': 0,
            'within_45_days': 0,
            'duplicates_skipped': 0,
        }
    
    def _generate_unique_hash(
        self,
        sku: str,
        incident_date: date,
        transaction_id: str,
        quantity: int,
        loss_type: str
    ) -> str:
        """
        Generate a unique hash for a lost item to prevent duplicates.
        
        Args:
            sku: Product SKU
            incident_date: Date of the incident
            transaction_id: Amazon transaction ID
            quantity: Quantity lost
            loss_type: Type of loss
            
        Returns:
            SHA-256 hash string
        """
        unique_string = f"{self.seller_profile.pk}|{sku}|{incident_date}|{transaction_id}|{quantity}|{loss_type}"
        return hashlib.sha256(unique_string.encode()).hexdigest()
    
    def detect_warehouse_losses(
        self,
        adjustments_df: pd.DataFrame,
        reimbursements_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect inventory losses from adjustments not covered by reimbursements.
        
        Args:
            adjustments_df: Processed inventory adjustments
            reimbursements_df: Processed reimbursements
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if len(adjustments_df) == 0:
            logger.info("No adjustments to analyze")
            return losses
        
        logger.info(f"Analyzing {len(adjustments_df)} adjustments for losses")
        
        # Create reimbursement lookup
        reimbursed_set = set()
        if len(reimbursements_df) > 0:
            for _, row in reimbursements_df.iterrows():
                key = f"{row.get('sku', '')}|{str(row.get('approval_date', ''))[:10]}"
                reimbursed_set.add(key)
        
        # Analyze each adjustment
        for idx, row in adjustments_df.iterrows():
            self.stats['total_adjustments'] += 1
            
            sku = str(row.get('sku', ''))
            quantity = int(row.get('quantity', 0))
            reason_code = str(row.get('reason_code', '')).upper()
            
            # Skip positive adjustments (gains)
            if quantity >= 0:
                continue
            
            # Determine loss type from reason code
            loss_type = self._get_loss_type(reason_code)
            
            if not loss_type:
                continue  # Unknown reason code, skip
            
            # Get incident date
            adjusted_date = row.get('adjusted_date')
            if pd.isna(adjusted_date):
                continue
            
            if hasattr(adjusted_date, 'date'):
                incident_date = adjusted_date.date()
            else:
                incident_date = pd.to_datetime(adjusted_date).date()
            
            # Check if within 45-day window (too recent to claim)
            if is_within_45_day_window(incident_date):
                self.stats['within_45_days'] += 1
                continue
            
            # Check if already reimbursed (simple check)
            reimbursement_key = f"{sku}|{incident_date}"
            if reimbursement_key in reimbursed_set:
                self.stats['already_reimbursed'] += 1
                continue
            
            # Get unit value
            unit_value = sku_values.get(sku, Decimal('10.00'))  # Default value if unknown
            
            # Create loss record
            transaction_id = str(row.get('transaction_id', f"ADJ_{idx}"))
            
            loss = {
                'sku': sku,
                'fnsku': str(row.get('fnsku', '')),
                'asin': str(row.get('asin', '')),
                'loss_type': loss_type,
                'quantity': abs(quantity),
                'unit_value': unit_value,
                'total_value': unit_value * abs(quantity),
                'incident_date': incident_date,
                'transaction_id': transaction_id,
                'fulfillment_center': str(row.get('fulfillment_center_id', '')),
                'reason_code': reason_code,
                'reason_description': LOSS_REASON_CODES.get(reason_code, ''),
            }
            
            losses.append(loss)
            self.stats['losses_detected'] += 1
        
        logger.info(
            f"Detected {len(losses)} losses from {self.stats['total_adjustments']} adjustments. "
            f"Skipped: {self.stats['already_reimbursed']} reimbursed, "
            f"{self.stats['within_45_days']} within 45 days"
        )
        
        return losses
    
    def detect_return_discrepancies(
        self,
        returns_df: pd.DataFrame,
        adjustments_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect customer returns that were never received back into inventory.
        
        Args:
            returns_df: Processed returns
            adjustments_df: Processed adjustments (to check for reinstatements)
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if len(returns_df) == 0:
            logger.info("No returns to analyze")
            return losses
        
        logger.info(f"Analyzing {len(returns_df)} returns for discrepancies")
        
        # Group returns by SKU for comparison
        # In a real implementation, you'd compare order-by-order
        # For now, we detect returns with certain statuses that indicate issues
        
        issue_statuses = ['DAMAGED', 'DEFECTIVE', 'LOST', 'DISPOSED']
        
        for idx, row in returns_df.iterrows():
            status = str(row.get('status', '')).upper()
            
            if not any(s in status for s in issue_statuses):
                continue
            
            sku = str(row.get('sku', ''))
            quantity = int(row.get('quantity', 1))
            order_id = str(row.get('order_id', ''))
            
            # Get return date
            return_date = row.get('return_date')
            if pd.isna(return_date):
                continue
            
            if hasattr(return_date, 'date'):
                incident_date = return_date.date()
            else:
                incident_date = pd.to_datetime(return_date).date()
            
            # Check 45-day rule
            if is_within_45_day_window(incident_date):
                continue
            
            # Determine loss type
            if 'DAMAGED' in status or 'DEFECTIVE' in status:
                loss_type = LossType.CUSTOMER_RETURN_DAMAGED
            else:
                loss_type = LossType.CUSTOMER_RETURN_LOST
            
            # Get unit value
            unit_value = sku_values.get(sku, Decimal('10.00'))
            
            loss = {
                'sku': sku,
                'fnsku': str(row.get('fnsku', '')),
                'asin': str(row.get('asin', '')),
                'loss_type': loss_type,
                'quantity': quantity,
                'unit_value': unit_value,
                'total_value': unit_value * quantity,
                'incident_date': incident_date,
                'transaction_id': f"RET_{order_id}",
                'order_id': order_id,
                'fulfillment_center': '',
                'reason_code': 'R',
                'reason_description': f"Return issue: {status}",
            }
            
            losses.append(loss)
        
        logger.info(f"Detected {len(losses)} return discrepancies")
        
        return losses
    
    def detect_shipment_discrepancies(
        self,
        shipments_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect inbound shipment discrepancies (shipped vs received).
        
        Args:
            shipments_df: Processed shipments
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if len(shipments_df) == 0 or 'quantity_discrepancy' not in shipments_df.columns:
            logger.info("No shipment discrepancies to analyze")
            return losses
        
        # Filter significant discrepancies
        discrepancies = shipments_df[shipments_df['quantity_discrepancy'] > 0].copy()
        
        logger.info(f"Analyzing {len(discrepancies)} shipment discrepancies")
        
        for idx, row in discrepancies.iterrows():
            sku = str(row.get('sku', ''))
            quantity_lost = int(row.get('quantity_discrepancy', 0))
            
            if quantity_lost <= 0:
                continue
            
            # Get shipment date
            shipment_date = row.get('shipment_date')
            if pd.isna(shipment_date):
                continue
            
            if hasattr(shipment_date, 'date'):
                incident_date = shipment_date.date()
            else:
                incident_date = pd.to_datetime(shipment_date).date()
            
            # Check 45-day rule
            if is_within_45_day_window(incident_date):
                continue
            
            # Get unit value
            unit_value = sku_values.get(sku, Decimal('10.00'))
            
            shipment_id = str(row.get('shipment_id', f"SHIP_{idx}"))
            
            loss = {
                'sku': sku,
                'fnsku': str(row.get('fnsku', '')),
                'asin': str(row.get('asin', '')),
                'loss_type': LossType.LOST_INBOUND,
                'quantity': quantity_lost,
                'unit_value': unit_value,
                'total_value': unit_value * quantity_lost,
                'incident_date': incident_date,
                'transaction_id': f"SHIP_{shipment_id}",
                'fulfillment_center': '',
                'reason_code': 'I',
                'reason_description': f"Inbound shipment discrepancy: {shipment_id}",
            }
            
            losses.append(loss)
        
        logger.info(f"Detected {len(losses)} shipment discrepancies")
        
        return losses
    
    def detect_inventory_inbound_losses(
        self,
        inventory_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect items received in inbound shipments but showing 0 in stock.
        This indicates items lost during the receiving process.
        
        Args:
            inventory_df: Inventory data with inbound and stock quantities
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if inventory_df is None or len(inventory_df) == 0:
            return losses
        
        logger.info(f"Analyzing {len(inventory_df)} inventory items for inbound losses")
        
        for _, row in inventory_df.iterrows():
            # Check for inbound-shipped-quantity column (various naming conventions)
            inbound_shipped = 0
            for col in ['afn-inbound-shipped-quantity', 'inbound-shipped-quantity', 'inbound_shipped']:
                if col in row.index:
                    inbound_shipped = int(row.get(col, 0) or 0)
                    break
            
            # Check total quantity
            total_qty = 0
            for col in ['afn-total-quantity', 'total-quantity', 'total_quantity']:
                if col in row.index:
                    total_qty = int(row.get(col, 0) or 0)
                    break
            
            # Check receiving quantity
            receiving_qty = 0
            for col in ['afn-inbound-receiving-quantity', 'inbound-receiving-quantity']:
                if col in row.index:
                    receiving_qty = int(row.get(col, 0) or 0)
                    break
            
            # Anomaly: Items shipped but none in stock and none receiving
            if inbound_shipped > 0 and total_qty == 0 and receiving_qty == 0:
                sku = str(row.get('sku', ''))
                
                # Get unit value
                price_val = row.get('your-price', row.get('price', 0))
                unit_value = Decimal(str(price_val or 0)) if price_val else sku_values.get(sku, Decimal('10.00'))
                
                loss = {
                    'sku': sku,
                    'fnsku': str(row.get('fnsku', '')),
                    'asin': str(row.get('asin', '')),
                    'loss_type': LossType.LOST_INBOUND,
                    'quantity': inbound_shipped,
                    'unit_value': unit_value,
                    'total_value': unit_value * inbound_shipped,
                    'incident_date': timezone.now().date() - timedelta(days=60),  # Estimated
                    'transaction_id': f"INV_INBOUND_{sku}",
                    'fulfillment_center': '',
                    'reason_code': 'INBOUND_LOST',
                    'reason_description': f"{inbound_shipped} units shipped but 0 in inventory",
                }
                losses.append(loss)
                logger.info(f"  Detected inbound loss: {sku} - {inbound_shipped} units")
        
        logger.info(f"Detected {len(losses)} inbound inventory losses")
        return losses
    
    def detect_unreimbursed_returns(
        self,
        returns_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect customer returns with status indicating return received
        but seller was never reimbursed.
        
        Args:
            returns_df: Returns data
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if returns_df is None or len(returns_df) == 0:
            return losses
        
        logger.info(f"Analyzing {len(returns_df)} returns for unreimbursed items")
        
        for _, row in returns_df.iterrows():
            status = str(row.get('status', row.get('detailed-disposition', ''))).lower()
            
            # Look for returns that show "returned" but not "completed"
            # This indicates the customer returned but seller wasn't credited
            if 'returned' in status and 'completed' not in status:
                sku = str(row.get('sku', ''))
                order_id = str(row.get('order-id', row.get('order_id', '')))
                quantity = int(row.get('quantity', 1) or 1)
                
                # Get return date
                return_date = row.get('return-date', row.get('return_date'))
                if pd.isna(return_date):
                    incident_date = timezone.now().date() - timedelta(days=60)
                else:
                    if hasattr(return_date, 'date'):
                        incident_date = return_date.date()
                    else:
                        incident_date = pd.to_datetime(return_date).date()
                
                # Skip if within 45 days
                if is_within_45_day_window(incident_date):
                    continue
                
                # Get unit value (estimate if not available)
                unit_value = sku_values.get(sku, Decimal('15.00'))
                
                loss = {
                    'sku': sku,
                    'fnsku': str(row.get('fnsku', '')),
                    'asin': str(row.get('asin', '')),
                    'loss_type': LossType.NO_REIMBURSEMENT,
                    'quantity': quantity,
                    'unit_value': unit_value,
                    'total_value': unit_value * quantity,
                    'incident_date': incident_date,
                    'transaction_id': f"RET_UNREIM_{order_id}",
                    'order_id': order_id,
                    'fulfillment_center': '',
                    'reason_code': 'RETURN_NOT_REIMBURSED',
                    'reason_description': f"Customer return not credited to seller - Order {order_id}",
                }
                losses.append(loss)
                logger.info(f"  Detected unreimbursed return: {sku} - Order {order_id}")
        
        logger.info(f"Detected {len(losses)} unreimbursed returns")
        return losses
    
    def detect_fulfillment_losses(
        self,
        shipments_df: pd.DataFrame,
        sku_values: Dict[str, Decimal]
    ) -> List[Dict]:
        """
        Detect fulfillment losses from shipment status:
        - LOST_IN_TRANSIT
        - DAMAGED_IN_WAREHOUSE
        
        Args:
            shipments_df: Shipments/fulfillment data
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            List of detected loss dictionaries
        """
        losses = []
        
        if shipments_df is None or len(shipments_df) == 0:
            return losses
        
        logger.info(f"Analyzing {len(shipments_df)} shipments for fulfillment losses")
        
        loss_statuses = ['lost_in_transit', 'lost', 'damaged_in_warehouse', 'damaged']
        
        for _, row in shipments_df.iterrows():
            status = str(row.get('shipment-status', row.get('status', ''))).lower().replace(' ', '_')
            
            if not any(s in status for s in loss_statuses):
                continue
            
            sku = str(row.get('sku', ''))
            order_id = str(row.get('amazon-order-id', row.get('order-id', '')))
            
            # Get quantity
            quantity = int(row.get('quantity-shipped', row.get('quantity', 1)) or 1)
            
            # Get shipment date
            ship_date = row.get('shipment-date', row.get('ship-date'))
            if pd.isna(ship_date):
                incident_date = timezone.now().date() - timedelta(days=60)
            else:
                if hasattr(ship_date, 'date'):
                    incident_date = ship_date.date()
                else:
                    incident_date = pd.to_datetime(ship_date).date()
            
            # Skip if within 45 days
            if is_within_45_day_window(incident_date):
                continue
            
            # Determine loss type
            if 'damaged' in status:
                loss_type = LossType.DAMAGED_WAREHOUSE
            else:
                loss_type = LossType.LOST_WAREHOUSE
            
            # Get value from item-price or estimates
            item_price = row.get('item-price', row.get('price', 0))
            if item_price and not pd.isna(item_price):
                total_value = Decimal(str(item_price))
                unit_value = total_value / quantity if quantity > 0 else Decimal('10.00')
            else:
                unit_value = sku_values.get(sku, Decimal('10.00'))
                total_value = unit_value * quantity
            
            loss = {
                'sku': sku,
                'fnsku': str(row.get('fnsku', '')),
                'asin': str(row.get('asin', '')),
                'loss_type': loss_type,
                'quantity': quantity,
                'unit_value': unit_value,
                'total_value': total_value,
                'incident_date': incident_date,
                'transaction_id': f"FULFILL_{order_id}",
                'order_id': order_id,
                'fulfillment_center': '',
                'reason_code': status.upper(),
                'reason_description': f"Fulfillment issue: {status}",
            }
            losses.append(loss)
            logger.info(f"  Detected fulfillment loss: {sku} - {status}")
        
        logger.info(f"Detected {len(losses)} fulfillment losses")
        return losses
    
    def _get_loss_type(self, reason_code: str) -> Optional[str]:
        """
        Map Amazon reason code to LossType.
        
        Args:
            reason_code: Amazon reason code
            
        Returns:
            LossType constant or None
        """
        reason_code = reason_code.upper()
        
        mapping = {
            'M': LossType.LOST_WAREHOUSE,
            'L': LossType.LOST_WAREHOUSE,
            'E': LossType.DAMAGED_WAREHOUSE,
            'D': LossType.DAMAGED_WAREHOUSE,
            'K': LossType.DESTROYED,
            'G': LossType.CUSTOMER_RETURN_DAMAGED,
            'H': LossType.CUSTOMER_RETURN_DAMAGED,
        }
        
        return mapping.get(reason_code)
    
    @transaction.atomic
    def save_losses(self, losses: List[Dict]) -> int:
        """
        Save detected losses to database, checking for duplicates.
        
        Args:
            losses: List of loss dictionaries
            
        Returns:
            Number of losses saved
        """
        saved_count = 0
        
        for loss in losses:
            # Generate unique hash
            unique_hash = self._generate_unique_hash(
                sku=loss['sku'],
                incident_date=loss['incident_date'],
                transaction_id=loss['transaction_id'],
                quantity=loss['quantity'],
                loss_type=loss['loss_type']
            )
            
            # Check for existing
            if LostItem.objects.filter(unique_hash=unique_hash).exists():
                self.stats['duplicates_skipped'] += 1
                continue
            
            # Create lost item
            LostItem.objects.create(
                audit=self.audit,
                sku=loss['sku'],
                fnsku=loss.get('fnsku', ''),
                asin=loss.get('asin', ''),
                loss_type=loss['loss_type'],
                quantity=loss['quantity'],
                unit_value=loss['unit_value'],
                total_value=loss['total_value'],
                currency='EUR',
                transaction_id=loss['transaction_id'],
                order_id=loss.get('order_id', ''),
                fulfillment_center=loss.get('fulfillment_center', ''),
                reason_code=loss.get('reason_code', ''),
                reason_description=loss.get('reason_description', ''),
                incident_date=loss['incident_date'],
                unique_hash=unique_hash,
            )
            
            saved_count += 1
        
        logger.info(
            f"Saved {saved_count} losses. "
            f"Duplicates skipped: {self.stats['duplicates_skipped']}"
        )
        
        return saved_count
    
    def run_full_reconciliation(
        self,
        adjustments_df: pd.DataFrame,
        reimbursements_df: pd.DataFrame,
        returns_df: pd.DataFrame = None,
        shipments_df: pd.DataFrame = None,
        inventory_df: pd.DataFrame = None,
        sku_values: Dict[str, Decimal] = None
    ) -> Dict:
        """
        Run the full reconciliation process.
        
        Args:
            adjustments_df: Processed inventory adjustments
            reimbursements_df: Processed reimbursements
            returns_df: Processed returns (optional)
            shipments_df: Processed shipments (optional)
            inventory_df: Raw inventory data (optional)
            sku_values: Dictionary of SKU -> unit value
            
        Returns:
            Summary of reconciliation results
        """
        if sku_values is None:
            sku_values = {}
        
        all_losses = []
        
        # Detect warehouse losses
        warehouse_losses = self.detect_warehouse_losses(
            adjustments_df,
            reimbursements_df,
            sku_values
        )
        all_losses.extend(warehouse_losses)
        
        # Detect return discrepancies (existing method)
        if returns_df is not None and len(returns_df) > 0:
            return_losses = self.detect_return_discrepancies(
                returns_df,
                adjustments_df,
                sku_values
            )
            all_losses.extend(return_losses)
            
            # Also check for unreimbursed returns
            unreimbursed_losses = self.detect_unreimbursed_returns(
                returns_df,
                sku_values
            )
            all_losses.extend(unreimbursed_losses)
        
        # Detect shipment discrepancies (existing method)
        if shipments_df is not None and len(shipments_df) > 0:
            shipment_losses = self.detect_shipment_discrepancies(
                shipments_df,
                sku_values
            )
            all_losses.extend(shipment_losses)
            
            # Also check for fulfillment losses (lost in transit, damaged)
            fulfillment_losses = self.detect_fulfillment_losses(
                shipments_df,
                sku_values
            )
            all_losses.extend(fulfillment_losses)
            
        # Detect inbound inventory losses
        if inventory_df is not None and len(inventory_df) > 0:
            inbound_losses = self.detect_inventory_inbound_losses(
                inventory_df,
                sku_values
            )
            all_losses.extend(inbound_losses)
        
        # Save to database
        saved_count = self.save_losses(all_losses)
        
        # Calculate totals
        total_value = sum(loss['total_value'] for loss in all_losses)
        
        return {
            'total_losses_detected': len(all_losses),
            'losses_saved': saved_count,
            'duplicates_skipped': self.stats['duplicates_skipped'],
            'within_45_days_skipped': self.stats['within_45_days'],
            'already_reimbursed': self.stats['already_reimbursed'],
            'total_estimated_value': total_value,
            'by_type': self._count_by_type(all_losses),
        }
    
    def _count_by_type(self, losses: List[Dict]) -> Dict[str, int]:
        """Count losses by type."""
        counts = {}
        for loss in losses:
            loss_type = loss['loss_type']
            counts[loss_type] = counts.get(loss_type, 0) + 1
        return counts
