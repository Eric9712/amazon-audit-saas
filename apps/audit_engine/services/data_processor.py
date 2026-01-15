"""
Data Processor Service
======================
Pandas-based data processing for Amazon reports.
Performs vectorized operations for high performance.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from django.utils import timezone

from utils.exceptions import DataProcessingError
from utils.helpers import parse_amazon_date, parse_amazon_decimal
from apps.audit_engine.constants import COLUMN_MAPPINGS

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    High-performance data processor using Pandas for Amazon report analysis.
    Uses vectorized operations instead of loops for speed.
    """
    
    def __init__(self):
        """Initialize the data processor."""
        self.column_mappings = COLUMN_MAPPINGS
    
    def normalize_columns(self, df: pd.DataFrame, report_type: str) -> pd.DataFrame:
        """
        Normalize column names to standardized format.
        
        Args:
            df: Raw DataFrame from Amazon report
            report_type: Type of report for column mapping
            
        Returns:
            DataFrame with normalized column names
        """
        if report_type not in self.column_mappings:
            logger.warning(f"No column mapping for report type: {report_type}")
            return df
        
        mappings = self.column_mappings[report_type]
        rename_map = {}
        
        for standard_name, possible_names in mappings.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    rename_map[possible_name] = standard_name
                    break
        
        if rename_map:
            df = df.rename(columns=rename_map)
            logger.debug(f"Renamed {len(rename_map)} columns for {report_type}")
        
        return df
    
    def clean_numeric_column(self, series: pd.Series) -> pd.Series:
        """
        Clean and convert a column to numeric values.
        Handles various number formats (European, currency symbols, etc.)
        
        Args:
            series: Pandas Series to clean
            
        Returns:
            Cleaned numeric Series
        """
        if series.dtype in ('int64', 'float64'):
            return series
        
        # Remove currency symbols and spaces
        cleaned = series.astype(str).str.replace(r'[€$£¥\s]', '', regex=True)
        
        # Handle European format (1.234,56)
        # Check if comma is used as decimal separator
        has_comma = cleaned.str.contains(',').any()
        has_dot = cleaned.str.contains(r'\.').any()
        
        if has_comma and has_dot:
            # Mixed format, assume comma is decimal for numbers like 1.234,56
            cleaned = cleaned.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        elif has_comma:
            # Only comma, assume it's decimal separator
            cleaned = cleaned.str.replace(',', '.', regex=False)
        
        # Convert to numeric
        return pd.to_numeric(cleaned, errors='coerce')
    
    def clean_date_column(self, series: pd.Series) -> pd.Series:
        """
        Clean and convert a column to datetime.
        
        Args:
            series: Pandas Series to clean
            
        Returns:
            Datetime Series
        """
        return pd.to_datetime(series, errors='coerce', utc=True)
    
    def process_inventory_adjustments(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Process inventory adjustments report.
        
        Args:
            df: Raw adjustments DataFrame
            
        Returns:
            Processed DataFrame with normalized columns and types
        """
        logger.info(f"Processing inventory adjustments: {len(df)} rows")
        
        # Normalize columns
        df = self.normalize_columns(df, 'inventory_adjustments')
        
        # Ensure required columns exist
        required = ['sku', 'adjusted_date', 'quantity', 'reason']
        missing = [col for col in required if col not in df.columns]
        
        if missing:
            # Try alternate column names
            for col in missing:
                if col == 'adjusted_date' and 'date' in df.columns:
                    df['adjusted_date'] = df['date']
                elif col == 'quantity' and 'qty' in df.columns:
                    df['quantity'] = df['qty']
        
        # Convert types
        if 'adjusted_date' in df.columns:
            df['adjusted_date'] = self.clean_date_column(df['adjusted_date'])
        
        if 'quantity' in df.columns:
            df['quantity'] = self.clean_numeric_column(df['quantity'])
        
        # Filter out zero quantity adjustments
        df = df[df['quantity'] != 0].copy()
        
        # Extract reason code (first character or full reason)
        if 'reason' in df.columns:
            df['reason_code'] = df['reason'].str[0].fillna('')
        
        logger.info(f"Processed adjustments: {len(df)} non-zero rows")
        
        return df
    
    def process_reimbursements(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Process reimbursements report.
        
        Args:
            df: Raw reimbursements DataFrame
            
        Returns:
            Processed DataFrame
        """
        logger.info(f"Processing reimbursements: {len(df)} rows")
        
        # Normalize columns
        df = self.normalize_columns(df, 'reimbursements')
        
        # Convert types
        if 'approval_date' in df.columns:
            df['approval_date'] = self.clean_date_column(df['approval_date'])
        
        for col in ['quantity', 'amount']:
            if col in df.columns:
                df[col] = self.clean_numeric_column(df[col])
        
        # Filter positive amounts
        if 'amount' in df.columns:
            df = df[df['amount'] > 0].copy()
        
        logger.info(f"Processed reimbursements: {len(df)} rows with positive amounts")
        
        return df
    
    def process_returns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Process customer returns report.
        
        Args:
            df: Raw returns DataFrame
            
        Returns:
            Processed DataFrame
        """
        logger.info(f"Processing returns: {len(df)} rows")
        
        # Normalize columns
        df = self.normalize_columns(df, 'returns')
        
        # Convert types
        if 'return_date' in df.columns:
            df['return_date'] = self.clean_date_column(df['return_date'])
        
        if 'quantity' in df.columns:
            df['quantity'] = self.clean_numeric_column(df['quantity']).fillna(1)
        
        logger.info(f"Processed returns: {len(df)} rows")
        
        return df
    
    def process_shipments(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Process FBA shipments report.
        
        Args:
            df: Raw shipments DataFrame
            
        Returns:
            Processed DataFrame
        """
        logger.info(f"Processing shipments: {len(df)} rows")
        
        # Normalize columns
        df = self.normalize_columns(df, 'shipments')
        
        # Convert types
        if 'shipment_date' in df.columns:
            df['shipment_date'] = self.clean_date_column(df['shipment_date'])
        
        for col in ['quantity_shipped', 'quantity_received']:
            if col in df.columns:
                df[col] = self.clean_numeric_column(df[col]).fillna(0)
        
        # Calculate discrepancy
        if 'quantity_shipped' in df.columns and 'quantity_received' in df.columns:
            df['quantity_discrepancy'] = df['quantity_shipped'] - df['quantity_received']
        
        logger.info(f"Processed shipments: {len(df)} rows")
        
        return df
    
    def calculate_sku_values(
        self,
        df: pd.DataFrame,
        reimbursements_df: pd.DataFrame = None
    ) -> Dict[str, Decimal]:
        """
        Calculate average unit value for each SKU.
        Uses reimbursement data to estimate values.
        
        Args:
            df: Main data DataFrame with SKU column
            reimbursements_df: Reimbursements DataFrame with amounts
            
        Returns:
            Dictionary of SKU -> unit value
        """
        sku_values = {}
        
        if reimbursements_df is not None and len(reimbursements_df) > 0:
            # Calculate value from reimbursements where we have both quantity and amount
            if 'sku' in reimbursements_df.columns and 'amount' in reimbursements_df.columns:
                # Group by SKU and calculate average unit value
                grouped = reimbursements_df.groupby('sku').agg({
                    'amount': 'sum',
                    'quantity': 'sum'
                }).reset_index()
                
                # Filter valid rows
                valid = grouped[(grouped['quantity'] > 0) & (grouped['amount'] > 0)]
                
                for _, row in valid.iterrows():
                    sku = row['sku']
                    unit_value = Decimal(str(row['amount'])) / Decimal(str(row['quantity']))
                    sku_values[sku] = round(unit_value, 2)
        
        logger.info(f"Calculated values for {len(sku_values)} SKUs")
        
        return sku_values
    
    def aggregate_by_sku(
        self,
        df: pd.DataFrame,
        group_cols: List[str] = None,
        agg_cols: Dict[str, str] = None
    ) -> pd.DataFrame:
        """
        Aggregate data by SKU for summary.
        
        Args:
            df: DataFrame to aggregate
            group_cols: Columns to group by (default: ['sku'])
            agg_cols: Aggregation specifications
            
        Returns:
            Aggregated DataFrame
        """
        if group_cols is None:
            group_cols = ['sku']
        
        if agg_cols is None:
            agg_cols = {
                'quantity': 'sum',
            }
            if 'total_value' in df.columns:
                agg_cols['total_value'] = 'sum'
        
        # Only include columns that exist
        valid_agg = {k: v for k, v in agg_cols.items() if k in df.columns}
        
        if not valid_agg:
            return df.groupby(group_cols).size().reset_index(name='count')
        
        return df.groupby(group_cols).agg(valid_agg).reset_index()
    
    def merge_reports(
        self,
        adjustments_df: pd.DataFrame,
        reimbursements_df: pd.DataFrame,
        returns_df: pd.DataFrame = None
    ) -> pd.DataFrame:
        """
        Merge multiple reports for reconciliation.
        
        Args:
            adjustments_df: Processed adjustments
            reimbursements_df: Processed reimbursements
            returns_df: Processed returns (optional)
            
        Returns:
            Merged DataFrame for analysis
        """
        # Start with adjustments as base
        merged = adjustments_df.copy()
        
        # Create a reimbursement lookup by SKU and date range
        if len(reimbursements_df) > 0:
            # Aggregate reimbursements by SKU
            reimb_agg = reimbursements_df.groupby('sku').agg({
                'amount': 'sum',
                'quantity': 'sum'
            }).reset_index()
            reimb_agg.columns = ['sku', 'total_reimbursed_amount', 'total_reimbursed_qty']
            
            # Merge
            merged = merged.merge(reimb_agg, on='sku', how='left')
            merged['total_reimbursed_amount'] = merged['total_reimbursed_amount'].fillna(0)
            merged['total_reimbursed_qty'] = merged['total_reimbursed_qty'].fillna(0)
        else:
            merged['total_reimbursed_amount'] = 0
            merged['total_reimbursed_qty'] = 0
        
        return merged
    
    def detect_anomalies(
        self,
        df: pd.DataFrame,
        threshold_std: float = 2.0
    ) -> pd.DataFrame:
        """
        Detect anomalies in the data using statistical methods.
        
        Args:
            df: DataFrame to analyze
            threshold_std: Number of standard deviations for anomaly detection
            
        Returns:
            DataFrame of anomalous records
        """
        if 'quantity' not in df.columns:
            return pd.DataFrame()
        
        # Calculate z-scores for quantity
        mean = df['quantity'].mean()
        std = df['quantity'].std()
        
        if std == 0:
            return pd.DataFrame()
        
        df['z_score'] = (df['quantity'] - mean) / std
        anomalies = df[abs(df['z_score']) > threshold_std].copy()
        
        logger.info(f"Detected {len(anomalies)} anomalies (threshold: {threshold_std} std)")
        
        return anomalies
