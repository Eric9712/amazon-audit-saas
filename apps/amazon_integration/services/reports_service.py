"""
Amazon Reports Service
======================
Service for requesting, polling, and downloading Amazon reports.
"""

import gzip
import io
import logging
import os
import time
from datetime import date, datetime
from typing import List, Optional, Tuple

import pandas as pd
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import SellerProfile
from apps.amazon_integration.models import ReportRequest
from apps.amazon_integration.services.sp_api_client import SPAPIClient
from utils.exceptions import (
    AmazonReportNotReadyError,
    AmazonReportFailedError,
    DataProcessingError,
)
from utils.helpers import sanitize_filename

logger = logging.getLogger(__name__)


# Report status values from Amazon
REPORT_STATUS_DONE = 'DONE'
REPORT_STATUS_FATAL = 'FATAL'
REPORT_STATUS_CANCELLED = 'CANCELLED'
REPORT_STATUS_IN_PROGRESS = 'IN_PROGRESS'
REPORT_STATUS_IN_QUEUE = 'IN_QUEUE'


class ReportsService:
    """
    Service for handling Amazon report requests and downloads.
    """
    
    def __init__(self, seller_profile: SellerProfile):
        """
        Initialize the reports service.
        
        Args:
            seller_profile: SellerProfile with Amazon connection
        """
        self.seller_profile = seller_profile
        self.client = SPAPIClient(seller_profile)
        self.marketplace_ids = seller_profile.amazon_marketplace_ids or []
        
        # Reports storage directory
        self.reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports', str(seller_profile.pk))
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def request_report(
        self,
        report_type: str,
        start_date: date,
        end_date: date,
        marketplace_ids: List[str] = None
    ) -> ReportRequest:
        """
        Request a new report from Amazon.
        
        Args:
            report_type: Report type constant
            start_date: Start date for report data
            end_date: End date for report data
            marketplace_ids: Optional list of marketplaces (defaults to all)
            
        Returns:
            ReportRequest instance
        """
        marketplaces = marketplace_ids or self.marketplace_ids
        
        if not marketplaces:
            raise DataProcessingError("No marketplaces configured", step="request_report")
        
        # Create database record
        report_request = ReportRequest.objects.create(
            seller_profile=self.seller_profile,
            report_type=report_type,
            marketplace_ids=marketplaces,
            data_start_date=start_date,
            data_end_date=end_date,
        )
        
        logger.info(
            f"Requesting report {report_type} for {self.seller_profile.user.email} "
            f"from {start_date} to {end_date}"
        )
        
        try:
            # Format dates for Amazon API
            start_time = datetime.combine(start_date, datetime.min.time()).isoformat() + 'Z'
            end_time = datetime.combine(end_date, datetime.max.time()).isoformat() + 'Z'
            
            # Request report from Amazon
            response = self.client.create_report(
                report_type=report_type,
                marketplace_ids=marketplaces,
                data_start_time=start_time,
                data_end_time=end_time,
            )
            
            report_id = response.get('reportId')
            
            if not report_id:
                raise DataProcessingError(
                    "No report ID in Amazon response",
                    step="request_report"
                )
            
            report_request.mark_processing(report_id)
            logger.info(f"Report requested successfully. Amazon report ID: {report_id}")
            
            return report_request
            
        except Exception as e:
            logger.error(f"Failed to request report: {str(e)}")
            report_request.mark_failed(str(e))
            raise
    
    def check_report_status(self, report_request: ReportRequest) -> str:
        """
        Check the status of a report request.
        
        Args:
            report_request: ReportRequest to check
            
        Returns:
            Report status string
        """
        if not report_request.report_id:
            return 'pending'
        
        try:
            response = self.client.get_report(report_request.report_id)
            status = response.get('processingStatus', 'UNKNOWN')
            
            logger.debug(f"Report {report_request.report_id} status: {status}")
            
            if status == REPORT_STATUS_DONE:
                report_document_id = response.get('reportDocumentId')
                if report_document_id:
                    report_request.mark_done(report_document_id)
                    
            elif status == REPORT_STATUS_FATAL:
                report_request.mark_failed("Report processing failed on Amazon side")
                
            elif status == REPORT_STATUS_CANCELLED:
                report_request.status = ReportRequest.ReportStatus.CANCELLED
                report_request.save()
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to check report status: {str(e)}")
            raise
    
    def wait_for_report(
        self,
        report_request: ReportRequest,
        max_wait_seconds: int = 600,
        poll_interval: int = 30
    ) -> ReportRequest:
        """
        Wait for a report to complete, polling periodically.
        
        Args:
            report_request: ReportRequest to wait for
            max_wait_seconds: Maximum time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Updated ReportRequest
            
        Raises:
            AmazonReportNotReadyError: If report doesn't complete in time
            AmazonReportFailedError: If report fails
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            status = self.check_report_status(report_request)
            
            if status == REPORT_STATUS_DONE:
                logger.info(f"Report {report_request.report_id} is ready")
                return report_request
            
            if status in (REPORT_STATUS_FATAL, REPORT_STATUS_CANCELLED):
                raise AmazonReportFailedError(
                    report_request.report_id,
                    f"Report ended with status: {status}"
                )
            
            logger.debug(f"Report not ready, waiting {poll_interval}s...")
            time.sleep(poll_interval)
        
        raise AmazonReportNotReadyError(
            report_request.report_id,
            f"Report not ready after {max_wait_seconds}s"
        )
    
    def download_report(self, report_request: ReportRequest) -> Tuple[str, pd.DataFrame]:
        """
        Download a completed report and parse it.
        
        Args:
            report_request: Completed ReportRequest
            
        Returns:
            Tuple of (file_path, DataFrame)
        """
        if report_request.status != ReportRequest.ReportStatus.DONE:
            raise DataProcessingError(
                f"Cannot download report with status: {report_request.status}",
                step="download_report"
            )
        
        if not report_request.report_document_id:
            raise DataProcessingError(
                "No report document ID available",
                step="download_report"
            )
        
        logger.info(f"Downloading report document: {report_request.report_document_id}")
        
        try:
            # Get download URL
            doc_response = self.client.get_report_document(report_request.report_document_id)
            
            download_url = doc_response.get('url')
            compression = doc_response.get('compressionAlgorithm')
            
            if not download_url:
                raise DataProcessingError(
                    "No download URL in document response",
                    step="download_report"
                )
            
            # Download content
            content = self.client.download_document(download_url)
            
            # Decompress if needed
            if compression == 'GZIP':
                content = gzip.decompress(content)
            
            # Save to file
            filename = sanitize_filename(
                f"{report_request.report_type}_{report_request.data_start_date}_"
                f"{report_request.data_end_date}_{report_request.report_id}.tsv"
            )
            file_path = os.path.join(self.reports_dir, filename)
            
            with open(file_path, 'wb') as f:
                f.write(content)
            
            file_size = len(content)
            
            # Parse to DataFrame
            df = self._parse_report_content(content)
            row_count = len(df)
            
            # Update report request
            report_request.mark_downloaded(file_path, file_size, row_count)
            
            logger.info(
                f"Downloaded {filename}: {row_count} rows, {file_size} bytes"
            )
            
            return file_path, df
            
        except Exception as e:
            logger.error(f"Failed to download report: {str(e)}")
            report_request.mark_failed(f"Download failed: {str(e)}")
            raise
    
    def _parse_report_content(self, content: bytes) -> pd.DataFrame:
        """
        Parse report content into a Pandas DataFrame.
        
        Args:
            content: Raw report content (TSV format)
            
        Returns:
            Parsed DataFrame
        """
        try:
            # Amazon reports are tab-separated
            df = pd.read_csv(
                io.BytesIO(content),
                sep='\t',
                encoding='utf-8',
                dtype=str,  # Read everything as string initially
                na_values=['', 'N/A', 'null'],
                low_memory=False,
            )
            
            # Clean column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('-', '_')
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to parse report content: {str(e)}")
            raise DataProcessingError(f"Failed to parse report: {str(e)}", step="parse_report")
    
    def request_all_audit_reports(
        self,
        start_date: date,
        end_date: date
    ) -> List[ReportRequest]:
        """
        Request all reports needed for a full audit.
        
        Args:
            start_date: Start of audit period
            end_date: End of audit period
            
        Returns:
            List of ReportRequest objects
        """
        # Reports needed for full reconciliation
        report_types = [
            ReportRequest.ReportType.FBA_INVENTORY,
            ReportRequest.ReportType.FBA_REIMBURSEMENTS,
            ReportRequest.ReportType.FBA_SHIPMENTS,
            ReportRequest.ReportType.FBA_RETURNS,
            ReportRequest.ReportType.FBA_REMOVAL_ORDER,
            ReportRequest.ReportType.FBA_INVENTORY_ADJUSTMENTS,
        ]
        
        requests = []
        
        for report_type in report_types:
            try:
                report_request = self.request_report(
                    report_type=report_type,
                    start_date=start_date,
                    end_date=end_date,
                )
                requests.append(report_request)
                
                # Small delay between requests to avoid throttling
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to request {report_type}: {str(e)}")
                # Continue with other reports
                continue
        
        logger.info(f"Requested {len(requests)} reports for audit")
        return requests
    
    def download_all_ready_reports(
        self,
        report_requests: List[ReportRequest]
    ) -> dict:
        """
        Download all ready reports.
        
        Args:
            report_requests: List of ReportRequest objects
            
        Returns:
            Dictionary of report_type -> DataFrame
        """
        results = {}
        
        for report_request in report_requests:
            # Check/update status
            status = self.check_report_status(report_request)
            
            if status == REPORT_STATUS_DONE:
                try:
                    file_path, df = self.download_report(report_request)
                    results[report_request.report_type] = df
                except Exception as e:
                    logger.error(
                        f"Failed to download {report_request.report_type}: {str(e)}"
                    )
        
        return results
