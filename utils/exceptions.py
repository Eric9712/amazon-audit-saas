"""
Custom Exceptions
=================
Application-specific exceptions for better error handling.
"""


class AmazonAuditBaseException(Exception):
    """Base exception for all Amazon Audit application errors."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code or 'UNKNOWN_ERROR'
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {
            'error': self.code,
            'message': self.message,
            'details': self.details,
        }


# =============================================================================
# AMAZON API EXCEPTIONS
# =============================================================================

class AmazonAPIException(AmazonAuditBaseException):
    """Base exception for Amazon SP-API related errors."""
    pass


class AmazonAuthenticationError(AmazonAPIException):
    """Raised when Amazon authentication fails."""
    
    def __init__(self, message: str = "Amazon authentication failed", details: dict = None):
        super().__init__(message, 'AMAZON_AUTH_ERROR', details)


class AmazonTokenExpiredError(AmazonAPIException):
    """Raised when the Amazon refresh token has expired."""
    
    def __init__(self, message: str = "Amazon token expired. Please reconnect your account.", details: dict = None):
        super().__init__(message, 'AMAZON_TOKEN_EXPIRED', details)


class AmazonThrottlingError(AmazonAPIException):
    """Raised when Amazon API returns 429 Too Many Requests."""
    
    def __init__(self, retry_after: int = None, message: str = None):
        msg = message or "Amazon API rate limit exceeded"
        details = {'retry_after_seconds': retry_after} if retry_after else {}
        super().__init__(msg, 'AMAZON_THROTTLING', details)
        self.retry_after = retry_after


class AmazonReportNotReadyError(AmazonAPIException):
    """Raised when an Amazon report is not yet ready for download."""
    
    def __init__(self, report_id: str, status: str):
        super().__init__(
            f"Report {report_id} is not ready. Current status: {status}",
            'REPORT_NOT_READY',
            {'report_id': report_id, 'status': status}
        )
        self.report_id = report_id
        self.status = status


class AmazonReportFailedError(AmazonAPIException):
    """Raised when an Amazon report generation has failed."""
    
    def __init__(self, report_id: str, reason: str = None):
        super().__init__(
            f"Report {report_id} generation failed: {reason or 'Unknown reason'}",
            'REPORT_FAILED',
            {'report_id': report_id, 'reason': reason}
        )


# =============================================================================
# AUDIT ENGINE EXCEPTIONS
# =============================================================================

class AuditException(AmazonAuditBaseException):
    """Base exception for audit-related errors."""
    pass


class AuditAlreadyRunningError(AuditException):
    """Raised when trying to start an audit while one is already running."""
    
    def __init__(self, user_id: int, existing_audit_id: int):
        super().__init__(
            "An audit is already running for this account",
            'AUDIT_ALREADY_RUNNING',
            {'user_id': user_id, 'existing_audit_id': existing_audit_id}
        )


class AuditNotFoundError(AuditException):
    """Raised when an audit is not found."""
    
    def __init__(self, audit_id: int):
        super().__init__(
            f"Audit with ID {audit_id} not found",
            'AUDIT_NOT_FOUND',
            {'audit_id': audit_id}
        )


class InsufficientDataError(AuditException):
    """Raised when there's not enough data to perform analysis."""
    
    def __init__(self, message: str = "Insufficient data for analysis"):
        super().__init__(message, 'INSUFFICIENT_DATA')


class DataProcessingError(AuditException):
    """Raised when data processing fails."""
    
    def __init__(self, message: str, step: str = None):
        super().__init__(
            message,
            'DATA_PROCESSING_ERROR',
            {'step': step}
        )


class ReconciliationError(AuditException):
    """Raised when the reconciliation algorithm encounters an error."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, 'RECONCILIATION_ERROR', details)


# =============================================================================
# PAYMENT EXCEPTIONS
# =============================================================================

class PaymentException(AmazonAuditBaseException):
    """Base exception for payment-related errors."""
    pass


class InsufficientCreditsError(PaymentException):
    """Raised when user doesn't have enough credits to download a case file."""
    
    def __init__(self, required_credits: int, available_credits: int):
        super().__init__(
            f"Insufficient credits. Required: {required_credits}, Available: {available_credits}",
            'INSUFFICIENT_CREDITS',
            {'required': required_credits, 'available': available_credits}
        )


class PaymentProcessingError(PaymentException):
    """Raised when a payment processing fails."""
    
    def __init__(self, message: str, stripe_error: str = None):
        super().__init__(
            message,
            'PAYMENT_PROCESSING_ERROR',
            {'stripe_error': stripe_error}
        )


# =============================================================================
# VALIDATION EXCEPTIONS
# =============================================================================

class ValidationException(AmazonAuditBaseException):
    """Base exception for validation errors."""
    
    def __init__(self, message: str, field: str = None):
        super().__init__(
            message,
            'VALIDATION_ERROR',
            {'field': field}
        )


class DuplicateClaimError(ValidationException):
    """Raised when trying to claim an item that was already claimed."""
    
    def __init__(self, item_id: str, previous_claim_date: str):
        super().__init__(
            f"Item {item_id} has already been claimed on {previous_claim_date}",
            'DUPLICATE_CLAIM'
        )
        self.details = {
            'item_id': item_id,
            'previous_claim_date': previous_claim_date
        }


class PrematureClaimError(ValidationException):
    """Raised when trying to claim an item before the 45-day waiting period."""
    
    def __init__(self, item_id: str, days_remaining: int):
        super().__init__(
            f"Cannot claim item {item_id} yet. {days_remaining} days remaining in the 45-day waiting period.",
            'PREMATURE_CLAIM'
        )
        self.details = {
            'item_id': item_id,
            'days_remaining': days_remaining
        }
