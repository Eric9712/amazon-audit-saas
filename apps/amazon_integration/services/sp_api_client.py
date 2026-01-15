"""
Amazon SP-API Client
====================
Main client for interacting with Amazon SP-API.
Includes automatic retry with exponential backoff for rate limiting (429 errors).
"""

import logging
import time
from typing import Any, Dict, Optional
from functools import wraps

import requests
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import SellerProfile
from apps.amazon_integration.models import AmazonCredentials, APIRequestLog
from apps.amazon_integration.services.auth_service import AmazonAuthService
from utils.exceptions import (
    AmazonAPIException,
    AmazonThrottlingError,
    AmazonAuthenticationError,
)

logger = logging.getLogger(__name__)


# SP-API Regional endpoints
SP_API_ENDPOINTS = {
    'NA': 'https://sellingpartnerapi-na.amazon.com',  # North America
    'EU': 'https://sellingpartnerapi-eu.amazon.com',  # Europe
    'FE': 'https://sellingpartnerapi-fe.amazon.com',  # Far East
}

# Marketplace to region mapping
MARKETPLACE_REGIONS = {
    # Europe
    'A1PA6795UKMFR9': 'EU',   # Germany
    'A1RKKUPIHCS9HS': 'EU',   # Spain
    'A13V1IB3VIYBER': 'EU',   # France
    'A1F83G8C2ARO7P': 'EU',   # UK
    'APJ6JRA9NG5V4': 'EU',    # Italy
    'A1805IZSGTT6HS': 'EU',   # Netherlands
    'A2NODRKZP88ZB9': 'EU',   # Sweden
    'A21TJRUUN4KGV': 'EU',    # Poland
    'A33AVAJ2PDY3EV': 'EU',   # Turkey
    
    # North America
    'ATVPDKIKX0DER': 'NA',    # USA
    'A2EUQ1WTGCTBG2': 'NA',   # Canada
    'A1AM78C64UM0Y8': 'NA',   # Mexico
    
    # Far East
    'A1VC38T7YXB528': 'FE',   # Japan
    'A39IBJ37TRP1C6': 'FE',   # Australia
}


def with_retry(max_retries: int = 5, base_delay: float = 2.0, max_delay: float = 120.0):
    """
    Decorator for automatic retry with exponential backoff.
    Implements Amazon's recommended throttling handling.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = base_delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except AmazonThrottlingError as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Use Retry-After header if available, otherwise exponential backoff
                        wait_time = e.retry_after if e.retry_after else delay
                        wait_time = min(wait_time, max_delay)
                        
                        logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Waiting {wait_time:.1f}s before retry..."
                        )
                        
                        time.sleep(wait_time)
                        delay = min(delay * 2, max_delay)  # Exponential backoff
                    else:
                        logger.error(f"Max retries exceeded after {max_retries + 1} attempts")
                        
                except AmazonAuthenticationError:
                    # Don't retry auth errors
                    raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class SPAPIClient:
    """
    Client for Amazon Selling Partner API with automatic token refresh
    and rate limit handling.
    """
    
    def __init__(self, seller_profile: SellerProfile):
        """
        Initialize the SP-API client.
        
        Args:
            seller_profile: SellerProfile instance with Amazon credentials
        """
        self.seller_profile = seller_profile
        self.auth_service = AmazonAuthService(seller_profile)
        
        # Determine region from marketplace
        marketplace_ids = seller_profile.amazon_marketplace_ids or []
        self.region = 'EU'  # Default to Europe
        
        if marketplace_ids:
            first_marketplace = marketplace_ids[0]
            self.region = MARKETPLACE_REGIONS.get(first_marketplace, 'EU')
        
        self.base_url = SP_API_ENDPOINTS[self.region]
        
        # Check for simulation mode or placeholder credentials
        sp_api_settings = getattr(settings, 'AMAZON_SP_API_SETTINGS', {})
        app_id = sp_api_settings.get('lwa_app_id', '')
        self.simulation_mode = getattr(settings, 'AMAZON_SIMULATION_MODE', False) or 'replace-me' in app_id
        
        if self.simulation_mode:
            logger.warning("SP-API Client running in SIMULATION MODE. No real requests will be made.")

        logger.debug(f"Initialized SP-API client for region: {self.region}")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with valid access token.
        
        Returns:
            Dictionary of headers
        """
        access_token = self.auth_service.get_valid_access_token()
        
        return {
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def _handle_response(self, response: requests.Response, log_entry: APIRequestLog = None) -> Dict:
        """
        Handle API response, including error handling.
        
        Args:
            response: requests Response object
            log_entry: Optional APIRequestLog for logging
            
        Returns:
            Parsed JSON response
            
        Raises:
            AmazonThrottlingError: If rate limited (429)
            AmazonAPIException: For other API errors
        """
        if log_entry:
            log_entry.http_status_code = response.status_code
        
        # Rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            
            if log_entry:
                log_entry.mark_throttled(retry_seconds)
            
            raise AmazonThrottlingError(
                retry_after=retry_seconds,
                message=f"Amazon API rate limit exceeded"
            )
        
        # Authentication errors
        if response.status_code in (401, 403):
            if log_entry:
                log_entry.mark_failed(response.status_code, "Authentication failed")
            
            raise AmazonAuthenticationError(
                f"Authentication failed with status {response.status_code}"
            )
        
        # Other errors
        if not response.ok:
            error_body = response.text[:500] if response.text else "No error details"
            
            if log_entry:
                log_entry.mark_failed(response.status_code, error_body)
            
            raise AmazonAPIException(
                f"API request failed with status {response.status_code}: {error_body}",
                code=f"HTTP_{response.status_code}"
            )
        
        # Success
        if log_entry:
            log_entry.mark_success(response.status_code, response.text[:1000])
        
        try:
            return response.json()
        except ValueError:
            return {'raw_response': response.text}
    
    def _create_log_entry(
        self,
        endpoint: str,
        method: str,
        params: Dict = None
    ) -> APIRequestLog:
        """
        Create an API request log entry.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            params: Request parameters
            
        Returns:
            APIRequestLog instance
        """
        return APIRequestLog.objects.create(
            seller_profile=self.seller_profile,
            endpoint=endpoint,
            method=method,
            request_params=params or {}
        )
    
    @with_retry(max_retries=5, base_delay=2.0)
    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make a GET request to SP-API.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            
        Returns:
            JSON response
        """
        url = f"{self.base_url}{endpoint}"
        log_entry = self._create_log_entry(endpoint, 'GET', params)
        
        # Simulation Mode
        if getattr(settings, 'AMAZON_SIMULATION_MODE', False):
            self.simulation_mode = True
            
        if self.simulation_mode:
            logger.info(f"SIMULATION GET {endpoint}")
            return self._mock_response(endpoint, params=params)
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params or {},
                timeout=60
            )
            
            return self._handle_response(response, log_entry)
            
        except requests.exceptions.Timeout:
            log_entry.mark_failed(error_message="Request timed out")
            raise AmazonAPIException("Request timed out", code="TIMEOUT")
            
        except requests.exceptions.RequestException as e:
            log_entry.mark_failed(error_message=str(e))
            raise AmazonAPIException(f"Request failed: {str(e)}", code="REQUEST_ERROR")
    
    @with_retry(max_retries=5, base_delay=2.0)
    def post(self, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """
        Make a POST request to SP-API.
        
        Args:
            endpoint: API endpoint (without base URL)
            data: Request body
            params: Query parameters
            
        Returns:
            JSON response
        """
        url = f"{self.base_url}{endpoint}"
        log_entry = self._create_log_entry(endpoint, 'POST', {'params': params, 'body': data})
        
        # Simulation Mode
        if getattr(settings, 'AMAZON_SIMULATION_MODE', False):
            self.simulation_mode = True
            
        if self.simulation_mode:
            logger.info(f"SIMULATION POST {endpoint}")
            return self._mock_response(endpoint, params=params, data=data)
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=data or {},
                params=params or {},
                timeout=60
            )
            
            return self._handle_response(response, log_entry)
            
        except requests.exceptions.Timeout:
            log_entry.mark_failed(error_message="Request timed out")
            raise AmazonAPIException("Request timed out", code="TIMEOUT")
            
        except requests.exceptions.RequestException as e:
            log_entry.mark_failed(error_message=str(e))
            raise AmazonAPIException(f"Request failed: {str(e)}", code="REQUEST_ERROR")
    
    def _mock_response(self, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Generate mock responses for simulation mode."""
        import random
        import uuid
        from datetime import datetime, timedelta
        
        # Simulate network delay
        time.sleep(0.5)
        
        # ... (rest of the mock implementation - see below)
        
        # Reports API - Create
        if endpoint.endswith('/reports') and data and 'reportType' in data:
            return {'reportId': f"sim-report-{uuid.uuid4().hex[:10]}"}
        
        # Documents API (check BEFORE reports status to avoid false match)
        if '/documents/' in endpoint:
            return {
                'reportDocumentId': endpoint.split('/')[-1],
                'url': f"https://mock-amazon.com/download/{uuid.uuid4().hex}",
                'compressionAlgorithm': None
            }
            
        # Reports API - Get Status
        if '/reports/' in endpoint and not endpoint.endswith('/reports'):
            report_id = endpoint.split('/')[-1]
            return {
                'reportId': report_id,
                'processingStatus': 'DONE', 
                'reportDocumentId': f"sim-doc-{uuid.uuid4().hex[:10]}"
            }
            
        # Inventory API
        if '/fba/inventory/v1/summaries' in endpoint:
            return {
                'payload': {
                    'inventorySummaries': [
                        {
                            'asin': f'B00{i}FAKE',
                            'fnSku': f'X00{i}FAKE',
                            'sellerSku': f'SKU-{i}-FAKE',
                            'condition': 'NewItem',
                            'inventoryDetails': {
                                'fulfillableQuantity': random.randint(0, 100),
                                'inboundWorkingQuantity': random.randint(0, 20),
                                'inboundShippedQuantity': random.randint(0, 20),
                                'inboundReceivingQuantity': random.randint(0, 20),
                                'reservedQuantity': {
                                    'totalReservedQuantity': random.randint(0, 10),
                                    'pendingCustomerOrderQuantity': random.randint(0, 5),
                                    'pendingTransshipmentQuantity': random.randint(0, 5),
                                    'fcProcessingQuantity': random.randint(0, 2),
                                }
                            }
                        } for i in range(5)
                    ]
                }
            }
            
        return {}

    def download_document(self, url: str) -> bytes:
        """
        Download a document (report) from a pre-signed URL.
        Handles simulation mode for mock URLs.
        """
        # Simulation Mode
        if getattr(settings, 'AMAZON_SIMULATION_MODE', False):
            self.simulation_mode = True

        if self.simulation_mode and "mock-amazon.com" in url:
            logger.info("Generating mock report content for simulation")
            return self._generate_mock_report_content()

        log_entry = self._create_log_entry(url[:100], 'GET', {'type': 'document_download'})
        
        try:
            response = requests.get(url, timeout=300)  # 5 minute timeout for large files
            response.raise_for_status()
            
            log_entry.mark_success(response.status_code, f"Downloaded {len(response.content)} bytes")
            
            return response.content
            
        except requests.exceptions.RequestException as e:
            log_entry.mark_failed(error_message=str(e))
            raise AmazonAPIException(f"Failed to download document: {str(e)}")

    def _generate_mock_report_content(self) -> bytes:
        """Generate fake TSV content for reports."""
        import random
        from datetime import datetime, timedelta
        
        # Determine report type based on context (simplified for now, generic content)
        # In a real scenario we'd track what report type corresponds to the document ID
        
        # Generating a generic FBA Inventory/Event style TSV
        headers = [
            "start-date", "end-date", "dates", "transaction-type", "payment-type", "detail", "amount", "quantity", "product-title",
            "sku", "fnsku", "asin", "reason", "status", "condition", "currency-code", "fulfillment-center-id", "disposition",
            "adjusted-date", "approval-date", "shipment-date", "return-date", "shipment-id"
        ]
        
        lines = ["\t".join(headers)]
        
        for i in range(20):
            date_str = (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
            lines.append("\t".join([
                date_str, date_str, date_str, 
                random.choice(["Order", "Refund", "Adjustment"]), 
                "Product charges", 
                "Payment", 
                str(random.uniform(10.0, 100.0)), 
                str(random.randint(1, 5)), 
                f"Product {i}",
                f"SKU-{i}", f"FNSKU-{i}", f"ASIN-{i}",
                "D", "Unsellable", "CustomerDamaged", "EUR", "CDG1", "SELLABLE"
            ]))
            
        return "\n".join(lines).encode('utf-8')

    # ... (rest of existing methods from get_marketplace_participations down)
    
    # ==========================================================================
    # SELLERS API
    # ==========================================================================
    
    def get_marketplace_participations(self) -> Dict:
        if self.simulation_mode:
             return {
                'payload': [
                    {
                        'marketplace': {'id': 'A13V1IB3VIYBER', 'countryCode': 'FR', 'name': 'Amazon.fr'},
                        'participation': {'isParticipating': True, 'hasSuspendedListings': False}
                    }
                ]
            }
        return self.get('/sellers/v1/marketplaceParticipations')

    # ... (rest of methods)

    
    # ==========================================================================
    # REPORTS API
    # ==========================================================================
    
    def create_report(
        self,
        report_type: str,
        marketplace_ids: list,
        data_start_time: str = None,
        data_end_time: str = None
    ) -> Dict:
        """
        Request a new report.
        
        Args:
            report_type: Report type identifier
            marketplace_ids: List of marketplace IDs
            data_start_time: ISO 8601 start time (optional)
            data_end_time: ISO 8601 end time (optional)
            
        Returns:
            Report creation response with report_id
        """
        body = {
            'reportType': report_type,
            'marketplaceIds': marketplace_ids,
        }
        
        if data_start_time:
            body['dataStartTime'] = data_start_time
        if data_end_time:
            body['dataEndTime'] = data_end_time
        
        return self.post('/reports/2021-06-30/reports', data=body)
    
    def get_report(self, report_id: str) -> Dict:
        """
        Get report status and metadata.
        
        Args:
            report_id: Amazon report ID
            
        Returns:
            Report data including status
        """
        return self.get(f'/reports/2021-06-30/reports/{report_id}')
    
    def get_report_document(self, report_document_id: str) -> Dict:
        """
        Get report document URL for download.
        
        Args:
            report_document_id: Report document ID
            
        Returns:
            Document metadata including download URL
        """
        return self.get(f'/reports/2021-06-30/documents/{report_document_id}')
    
    # ==========================================================================
    # FBA INVENTORY API
    # ==========================================================================
    
    def get_inventory_summaries(
        self,
        marketplace_ids: list,
        granularity_type: str = 'Marketplace',
        next_token: str = None
    ) -> Dict:
        """
        Get FBA inventory summaries.
        
        Args:
            marketplace_ids: List of marketplace IDs
            granularity_type: Granularity level
            next_token: Pagination token
            
        Returns:
            Inventory summary data
        """
        params = {
            'marketplaceIds': ','.join(marketplace_ids),
            'granularityType': granularity_type,
            'granularityId': marketplace_ids[0],
        }
        
        if next_token:
            params['nextToken'] = next_token
        
        return self.get('/fba/inventory/v1/summaries', params=params)
    
    # ==========================================================================
    # FBA INBOUND API
    # ==========================================================================
    
    def get_shipments(
        self,
        marketplace_id: str,
        query_type: str = 'SHIPMENT',
        shipment_status_list: list = None,
        last_updated_after: str = None,
        last_updated_before: str = None,
        next_token: str = None
    ) -> Dict:
        """
        Get FBA inbound shipments.
        
        Args:
            marketplace_id: Marketplace ID
            query_type: 'SHIPMENT' or 'DATE_RANGE'
            shipment_status_list: Filter by status
            last_updated_after: ISO 8601 datetime
            last_updated_before: ISO 8601 datetime
            next_token: Pagination token
            
        Returns:
            Shipment data
        """
        params = {
            'MarketplaceId': marketplace_id,
            'QueryType': query_type,
        }
        
        if shipment_status_list:
            params['ShipmentStatusList'] = ','.join(shipment_status_list)
        if last_updated_after:
            params['LastUpdatedAfter'] = last_updated_after
        if last_updated_before:
            params['LastUpdatedBefore'] = last_updated_before
        if next_token:
            params['NextToken'] = next_token
        
        return self.get('/fba/inbound/v0/shipments', params=params)
