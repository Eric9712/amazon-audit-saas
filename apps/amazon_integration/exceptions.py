"""
Amazon Integration Exceptions
=============================
Custom exceptions for Amazon API integration.
"""

from utils.exceptions import AmazonAPIException


class SPAPIError(AmazonAPIException):
    """Base exception for SP-API errors."""
    pass


class InvalidMarketplaceError(SPAPIError):
    """Raised when an invalid marketplace is specified."""
    
    def __init__(self, marketplace_id: str):
        super().__init__(
            f"Invalid marketplace ID: {marketplace_id}",
            'INVALID_MARKETPLACE',
            {'marketplace_id': marketplace_id}
        )


class ReportTypeNotSupportedError(SPAPIError):
    """Raised when a report type is not supported."""
    
    def __init__(self, report_type: str):
        super().__init__(
            f"Report type not supported: {report_type}",
            'REPORT_TYPE_NOT_SUPPORTED',
            {'report_type': report_type}
        )


class SellerNotAuthorizedError(SPAPIError):
    """Raised when the seller hasn't authorized the application."""
    
    def __init__(self):
        super().__init__(
            "Seller has not authorized this application. Please reconnect your Amazon account.",
            'SELLER_NOT_AUTHORIZED'
        )


class ReportDownloadError(SPAPIError):
    """Raised when a report cannot be downloaded."""
    
    def __init__(self, report_id: str, reason: str):
        super().__init__(
            f"Failed to download report {report_id}: {reason}",
            'REPORT_DOWNLOAD_ERROR',
            {'report_id': report_id, 'reason': reason}
        )
