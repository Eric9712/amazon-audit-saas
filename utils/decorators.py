"""
Custom Decorators
=================
Reusable decorators for the application.
"""

import functools
import logging
import time
from typing import Callable, Any

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def require_amazon_connected(view_func: Callable) -> Callable:
    """
    Decorator that ensures the user has connected their Amazon account.
    Redirects to connection page if not connected.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'seller_profile'):
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.warning(
                request,
                "Veuillez d'abord connecter votre compte Amazon Seller Central."
            )
            return redirect('dashboard:connect_amazon')
        
        if not request.user.seller_profile.is_amazon_connected:
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.warning(
                request,
                "Votre connexion Amazon a expiré. Veuillez vous reconnecter."
            )
            return redirect('dashboard:connect_amazon')
        
        return view_func(request, *args, **kwargs)
    
    return login_required(wrapper)


def require_active_subscription(view_func: Callable) -> Callable:
    """
    Decorator that ensures the user has an active paid subscription.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'seller_profile'):
            raise PermissionDenied("Profil vendeur requis.")
        
        if not request.user.seller_profile.has_active_subscription:
            from django.shortcuts import redirect
            from django.contrib import messages
            messages.info(
                request,
                "Cette fonctionnalité nécessite un abonnement actif."
            )
            return redirect('payments:pricing')
        
        return view_func(request, *args, **kwargs)
    
    return login_required(wrapper)


def ajax_login_required(view_func: Callable) -> Callable:
    """
    Decorator for AJAX views that returns JSON error if not authenticated.
    """
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required',
                'redirect': '/accounts/login/'
            }, status=401)
        return view_func(request, *args, **kwargs)
    
    return wrapper


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator that logs the execution time of a function.
    Useful for performance monitoring of audit tasks.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        logger.info(
            f"Function '{func.__name__}' executed in {execution_time:.2f} seconds"
        )
        
        return result
    
    return wrapper


def retry_on_exception(
    exceptions: tuple = (Exception,),
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger_instance: logging.Logger = None
) -> Callable:
    """
    Decorator that retries a function on specified exceptions with exponential backoff.
    Used for handling Amazon API throttling (429 errors).
    
    Args:
        exceptions: Tuple of exceptions to catch and retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        logger_instance: Logger to use for logging retries
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logger_instance or logger
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        log.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for "
                            f"'{func.__name__}': {str(e)}. Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        log.error(
                            f"All {max_retries + 1} attempts failed for '{func.__name__}'"
                        )
            
            raise last_exception
        
        return wrapper
    
    return decorator


def cache_result(timeout: int = 300) -> Callable:
    """
    Simple in-memory cache decorator for expensive function calls.
    
    Args:
        timeout: Cache timeout in seconds (default 5 minutes)
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            current_time = time.time()
            
            # Check if cached and not expired
            if key in cache:
                result, cached_time = cache[key]
                if current_time - cached_time < timeout:
                    return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache[key] = (result, current_time)
            
            return result
        
        # Add method to clear cache
        def clear_cache():
            cache.clear()
        
        wrapper.clear_cache = clear_cache
        return wrapper
    
    return decorator
