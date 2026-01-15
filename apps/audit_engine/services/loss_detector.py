"""
Loss Detector Service
=====================
High-level service for orchestrating loss detection.
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

import pandas as pd

from apps.audit_engine.models import Audit, LostItem
from apps.audit_engine.services.data_processor import DataProcessor
from apps.audit_engine.services.reconciliation import ReconciliationService

logger = logging.getLogger(__name__)


class LossDetector:
    """
    High-level service that orchestrates the loss detection process.
    """
    
    def __init__(self, audit: Audit):
        """
        Initialize the loss detector.
        
        Args:
            audit: The Audit instance to detect losses for
        """
        self.audit = audit
        self.data_processor = DataProcessor()
        self.reconciliation = ReconciliationService(audit)
    
    def analyze(
        self,
        reports_data: Dict[str, pd.DataFrame]
    ) -> Dict:
        """
        Analyze report data and detect losses.
        
        Args:
            reports_data: Dictionary of report_type -> DataFrame
            
        Returns:
            Analysis results summary
        """
        logger.info(f"Starting loss analysis for audit {self.audit.reference_code}")
        
        # Process each report type
        adjustments_df = pd.DataFrame()
        reimbursements_df = pd.DataFrame()
        returns_df = pd.DataFrame()
        shipments_df = pd.DataFrame()
        inventory_df = pd.DataFrame()  # For inbound loss detection
        
        for report_type, df in reports_data.items():
            if df is None or len(df) == 0:
                continue
            
            report_type_upper = report_type.upper()
            
            if 'INVENTORY_ADJUSTMENTS' in report_type_upper or 'ADJUSTMENTS' in report_type_upper:
                adjustments_df = self.data_processor.process_inventory_adjustments(df)
                
            elif 'REIMBURSEMENT' in report_type_upper:
                reimbursements_df = self.data_processor.process_reimbursements(df)
                
            elif 'RETURN' in report_type_upper:
                returns_df = self.data_processor.process_returns(df)
                
            elif 'SHIPMENT' in report_type_upper or 'FULFILLED' in report_type_upper:
                shipments_df = self.data_processor.process_shipments(df)
            
            elif 'INVENTORY' in report_type_upper and 'ADJUSTMENT' not in report_type_upper:
                # Raw inventory data (for inbound loss detection)
                inventory_df = df  # Use as-is, reconciliation handles column mapping
        
        # Update progress
        self.audit.update_progress(60, 'Calculating product values...')
        
        # Calculate SKU values from reimbursements
        sku_values = self.data_processor.calculate_sku_values(adjustments_df, reimbursements_df)
        
        # Update progress
        self.audit.update_progress(70, 'Running reconciliation...')
        
        # Run reconciliation
        results = self.reconciliation.run_full_reconciliation(
            adjustments_df=adjustments_df,
            reimbursements_df=reimbursements_df,
            returns_df=returns_df,
            shipments_df=shipments_df,
            inventory_df=inventory_df,  # Pass inventory data for inbound loss detection
            sku_values=sku_values,
        )
        
        # Calculate additional stats
        total_items_analyzed = (
            len(adjustments_df) +
            len(reimbursements_df) +
            len(returns_df) +
            len(shipments_df) +
            len(inventory_df)
        )
        
        results['total_items_analyzed'] = total_items_analyzed
        
        logger.info(
            f"Analysis complete for audit {self.audit.reference_code}: "
            f"{results['total_losses_detected']} losses detected, "
            f"€{results['total_estimated_value']:.2f} estimated value"
        )
        
        return results
    
    def get_summary(self) -> Dict:
        """
        Get a summary of detected losses for this audit.
        
        Returns:
            Summary dictionary
        """
        lost_items = LostItem.objects.filter(audit=self.audit)
        
        total_value = sum(item.total_value for item in lost_items)
        reimbursed_value = sum(
            item.reimbursement_amount or Decimal('0')
            for item in lost_items
            if item.is_reimbursed
        )
        claimable_value = sum(
            item.total_value
            for item in lost_items
            if item.is_claimable
        )
        
        by_type = {}
        for item in lost_items:
            if item.loss_type not in by_type:
                by_type[item.loss_type] = {
                    'count': 0,
                    'quantity': 0,
                    'value': Decimal('0'),
                }
            by_type[item.loss_type]['count'] += 1
            by_type[item.loss_type]['quantity'] += item.quantity
            by_type[item.loss_type]['value'] += item.total_value
        
        return {
            'total_losses': lost_items.count(),
            'total_quantity': sum(item.quantity for item in lost_items),
            'total_value': total_value,
            'reimbursed_value': reimbursed_value,
            'claimable_value': claimable_value,
            'by_type': by_type,
        }
