"""
Helper Functions
================
Utility functions used across the application.
"""

import hashlib
import secrets
import string
import re
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from decimal import Decimal, ROUND_HALF_UP

import pytz
from django.conf import settings
from django.utils import timezone


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Length of the token in characters
        
    Returns:
        A secure random string
    """
    return secrets.token_urlsafe(length)


def generate_reference_code(prefix: str = 'AUD') -> str:
    """
    Generate a unique reference code for audits and cases.
    Format: PREFIX-YYYYMMDD-XXXXXX (e.g., AUD-20240115-A3B2C1)
    
    Args:
        prefix: 3-character prefix for the code
        
    Returns:
        A unique reference code
    """
    today = timezone.now().strftime('%Y%m%d')
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix}-{today}-{random_part}"


def hash_sensitive_data(data: str) -> str:
    """
    Create a SHA-256 hash of sensitive data for comparison purposes.
    Used for idempotency checks (ensuring we don't process duplicates).
    
    Args:
        data: String data to hash
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def calculate_date_range(months_back: int = 18) -> tuple:
    """
    Calculate the date range for audit (18 months back by default).
    Also accounts for the 45-day rule.
    
    Args:
        months_back: Number of months of history to fetch
        
    Returns:
        Tuple of (start_date, end_date) as date objects
    """
    now = timezone.now()
    
    # End date is 45 days ago (Amazon's 45-day rule)
    delay_days = getattr(settings, 'LOSS_DETECTION_DELAY_DAYS', 45)
    end_date = (now - timedelta(days=delay_days)).date()
    
    # Start date is X months before end date
    start_date = (end_date - timedelta(days=months_back * 30)).replace(day=1)
    
    return start_date, end_date


def is_within_45_day_window(event_date: date) -> bool:
    """
    Check if a date is within the 45-day waiting period.
    Items within this window should NOT be claimed yet.
    
    Args:
        event_date: The date of the inventory event
        
    Returns:
        True if within 45-day window (too early to claim)
    """
    delay_days = getattr(settings, 'LOSS_DETECTION_DELAY_DAYS', 45)
    cutoff_date = timezone.now().date() - timedelta(days=delay_days)
    return event_date > cutoff_date


def days_until_claimable(event_date: date) -> int:
    """
    Calculate how many days until an item becomes claimable.
    
    Args:
        event_date: The date of the inventory event
        
    Returns:
        Number of days remaining (0 if already claimable)
    """
    delay_days = getattr(settings, 'LOSS_DETECTION_DELAY_DAYS', 45)
    claimable_date = event_date + timedelta(days=delay_days)
    today = timezone.now().date()
    
    if claimable_date <= today:
        return 0
    
    return (claimable_date - today).days


def format_currency(amount: Decimal, currency: str = 'EUR') -> str:
    """
    Format a decimal amount as currency.
    
    Args:
        amount: Decimal amount
        currency: Currency code (EUR, USD, etc.)
        
    Returns:
        Formatted currency string
    """
    amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    symbols = {
        'EUR': '€',
        'USD': '$',
        'GBP': '£',
    }
    
    symbol = symbols.get(currency, currency)
    
    # French format for EUR
    if currency == 'EUR':
        formatted = f"{amount:,.2f}".replace(',', ' ').replace('.', ',')
        return f"{formatted} {symbol}"
    else:
        return f"{symbol}{amount:,.2f}"


def cents_to_decimal(cents: int) -> Decimal:
    """
    Convert cents (integer) to decimal euros.
    
    Args:
        cents: Amount in cents
        
    Returns:
        Decimal amount in euros
    """
    return Decimal(cents) / Decimal(100)


def decimal_to_cents(amount: Decimal) -> int:
    """
    Convert decimal euros to cents (integer).
    Used for Stripe which expects amounts in cents.
    
    Args:
        amount: Decimal amount in euros
        
    Returns:
        Integer amount in cents
    """
    return int((Decimal(str(amount)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def parse_amazon_date(date_str: str) -> Optional[date]:
    """
    Parse various Amazon date formats.
    
    Args:
        date_str: Date string from Amazon reports
        
    Returns:
        Python date object or None if parsing fails
    """
    if not date_str or date_str.strip() == '':
        return None
    
    date_str = str(date_str).strip()
    
    # Common Amazon date formats
    formats = [
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            if hasattr(parsed, 'date'):
                return parsed.date()
            return parsed
        except ValueError:
            continue
    
    return None


def parse_amazon_decimal(value: Any) -> Optional[Decimal]:
    """
    Parse decimal values from Amazon reports (handles various formats).
    
    Args:
        value: Value from Amazon report
        
    Returns:
        Decimal or None
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    if isinstance(value, Decimal):
        return value
    
    # Handle string values
    value = str(value).strip()
    
    if value == '' or value.lower() in ('n/a', 'null', 'none', '-'):
        return None
    
    # Remove currency symbols and spaces
    value = re.sub(r'[€$£¥\s]', '', value)
    
    # Handle European format (1.234,56 -> 1234.56)
    if ',' in value and '.' in value:
        if value.rfind(',') > value.rfind('.'):
            value = value.replace('.', '').replace(',', '.')
        else:
            value = value.replace(',', '')
    elif ',' in value:
        # Could be either thousands separator or decimal separator
        parts = value.split(',')
        if len(parts) == 2 and len(parts[1]) == 2:
            # Likely European decimal format
            value = value.replace(',', '.')
        else:
            # Likely thousands separator
            value = value.replace(',', '')
    
    try:
        return Decimal(value)
    except Exception:
        return None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe filesystem storage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Limit length
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:200 - len(ext) - 1] + ('.' + ext if ext else '')
    
    return filename or 'unnamed'


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    Useful for batch processing.
    
    Args:
        lst: List to split
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def mask_sensitive_string(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive string, showing only last N characters.
    
    Args:
        value: String to mask
        visible_chars: Number of characters to keep visible
        
    Returns:
        Masked string (e.g., "****1234")
    """
    if not value:
        return ''
    
    if len(value) <= visible_chars:
        return '*' * len(value)
    
    return '*' * (len(value) - visible_chars) + value[-visible_chars:]


def calculate_estimated_refund(items: List[Dict]) -> Dict[str, Any]:
    """
    Calculate the estimated refund amount from a list of lost items.
    
    Args:
        items: List of lost item dictionaries with 'value' key
        
    Returns:
        Dictionary with total, by category, etc.
    """
    total = Decimal('0')
    by_type = {}
    
    for item in items:
        value = parse_amazon_decimal(item.get('value', 0)) or Decimal('0')
        total += value
        
        item_type = item.get('type', 'unknown')
        if item_type not in by_type:
            by_type[item_type] = Decimal('0')
        by_type[item_type] += value
    
    return {
        'total': total,
        'by_type': by_type,
        'item_count': len(items),
        'average_per_item': total / len(items) if items else Decimal('0'),
    }


def get_marketplace_info(marketplace_id: str) -> Dict[str, str]:
    """
    Get marketplace information from marketplace ID.
    
    Args:
        marketplace_id: Amazon marketplace ID
        
    Returns:
        Dictionary with marketplace details
    """
    marketplaces = {
        'A1PA6795UKMFR9': {'name': 'Amazon.de', 'country': 'Germany', 'currency': 'EUR'},
        'A1RKKUPIHCS9HS': {'name': 'Amazon.es', 'country': 'Spain', 'currency': 'EUR'},
        'A13V1IB3VIYBER': {'name': 'Amazon.fr', 'country': 'France', 'currency': 'EUR'},
        'A1F83G8C2ARO7P': {'name': 'Amazon.co.uk', 'country': 'United Kingdom', 'currency': 'GBP'},
        'APJ6JRA9NG5V4': {'name': 'Amazon.it', 'country': 'Italy', 'currency': 'EUR'},
        'A1805IZSGTT6HS': {'name': 'Amazon.nl', 'country': 'Netherlands', 'currency': 'EUR'},
        'A2NODRKZP88ZB9': {'name': 'Amazon.se', 'country': 'Sweden', 'currency': 'SEK'},
        'A21TJRUUN4KGV': {'name': 'Amazon.pl', 'country': 'Poland', 'currency': 'PLN'},
        'A33AVAJ2PDY3EV': {'name': 'Amazon.com.tr', 'country': 'Turkey', 'currency': 'TRY'},
        'ATVPDKIKX0DER': {'name': 'Amazon.com', 'country': 'United States', 'currency': 'USD'},
        'A2EUQ1WTGCTBG2': {'name': 'Amazon.ca', 'country': 'Canada', 'currency': 'CAD'},
        'A1AM78C64UM0Y8': {'name': 'Amazon.com.mx', 'country': 'Mexico', 'currency': 'MXN'},
    }
    
    return marketplaces.get(marketplace_id, {
        'name': 'Unknown',
        'country': 'Unknown',
        'currency': 'USD'
    })
