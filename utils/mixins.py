"""
Mixins
======
Reusable Django class-based view mixins.
"""

import logging
from typing import Optional

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views import View

logger = logging.getLogger(__name__)


class AmazonConnectedMixin(LoginRequiredMixin):
    """
    Mixin that ensures the user has connected their Amazon account.
    """
    
    amazon_redirect_url = 'dashboard:connect_amazon'
    amazon_message = "Veuillez d'abord connecter votre compte Amazon Seller Central."
    
    def dispatch(self, request, *args, **kwargs):
        # First check login (LoginRequiredMixin)
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Then check Amazon connection
        if not self.has_amazon_connection(request.user):
            return self.handle_no_amazon_connection(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_amazon_connection(self, user) -> bool:
        """Check if user has an active Amazon connection."""
        if not hasattr(user, 'seller_profile'):
            return False
        return user.seller_profile.is_amazon_connected
    
    def handle_no_amazon_connection(self, request):
        """Handle the case when user is not connected to Amazon."""
        messages.warning(request, self.amazon_message)
        return redirect(self.amazon_redirect_url)


class ActiveSubscriptionMixin(LoginRequiredMixin):
    """
    Mixin that ensures the user has an active subscription.
    """
    
    subscription_redirect_url = 'payments:pricing'
    subscription_message = "Cette fonctionnalité nécessite un abonnement actif."
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not self.has_active_subscription(request.user):
            return self.handle_no_subscription(request)
        
        return super().dispatch(request, *args, **kwargs)
    
    def has_active_subscription(self, user) -> bool:
        """Check if user has an active subscription."""
        if not hasattr(user, 'seller_profile'):
            return False
        return user.seller_profile.has_active_subscription
    
    def handle_no_subscription(self, request):
        """Handle the case when user doesn't have an active subscription."""
        messages.info(request, self.subscription_message)
        return redirect(self.subscription_redirect_url)


class AjaxResponseMixin:
    """
    Mixin that provides JSON response helpers for AJAX views.
    """
    
    def json_success(self, data: dict = None, message: str = None, status: int = 200) -> JsonResponse:
        """Return a successful JSON response."""
        response = {'success': True}
        if message:
            response['message'] = message
        if data:
            response['data'] = data
        return JsonResponse(response, status=status)
    
    def json_error(self, message: str, code: str = None, errors: dict = None, status: int = 400) -> JsonResponse:
        """Return an error JSON response."""
        response = {
            'success': False,
            'error': message,
        }
        if code:
            response['code'] = code
        if errors:
            response['errors'] = errors
        return JsonResponse(response, status=status)
    
    def json_unauthorized(self, message: str = "Authentication required") -> JsonResponse:
        """Return an unauthorized JSON response."""
        return self.json_error(message, code='UNAUTHORIZED', status=401)
    
    def json_forbidden(self, message: str = "Permission denied") -> JsonResponse:
        """Return a forbidden JSON response."""
        return self.json_error(message, code='FORBIDDEN', status=403)
    
    def json_not_found(self, message: str = "Resource not found") -> JsonResponse:
        """Return a not found JSON response."""
        return self.json_error(message, code='NOT_FOUND', status=404)


class OwnershipMixin:
    """
    Mixin that ensures a user can only access their own objects.
    """
    
    owner_field = 'user'  # Field on the model that references the owner
    
    def get_queryset(self):
        """Filter queryset to only include objects owned by the current user."""
        queryset = super().get_queryset()
        return queryset.filter(**{self.owner_field: self.request.user})


class AuditLogMixin:
    """
    Mixin that logs important actions for audit trail.
    """
    
    audit_action: str = None  # Override in subclass
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        
        if self.audit_action and request.user.is_authenticated:
            self.log_action(request, response)
        
        return response
    
    def log_action(self, request, response):
        """Log the action with relevant details."""
        logger.info(
            f"AUDIT: User {request.user.id} performed '{self.audit_action}' "
            f"from {request.META.get('REMOTE_ADDR', 'unknown')} "
            f"- Status: {response.status_code}"
        )


class FormMessageMixin:
    """
    Mixin that adds success/error messages to form views.
    """
    
    success_message: str = "Opération effectuée avec succès."
    error_message: str = "Une erreur s'est produite. Veuillez réessayer."
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, self.get_success_message(form))
        return response
    
    def form_invalid(self, form):
        response = super().form_invalid(form)
        messages.error(self.request, self.get_error_message(form))
        return response
    
    def get_success_message(self, form) -> str:
        """Override to customize success message based on form data."""
        return self.success_message
    
    def get_error_message(self, form) -> str:
        """Override to customize error message based on form errors."""
        return self.error_message


class PaginationMixin:
    """
    Mixin that provides pagination configuration.
    """
    
    paginate_by = 25
    page_kwarg = 'page'
    
    def get_paginate_by(self, queryset):
        """Allow override via query parameter."""
        per_page = self.request.GET.get('per_page')
        if per_page:
            try:
                per_page = int(per_page)
                if 1 <= per_page <= 100:
                    return per_page
            except ValueError:
                pass
        return self.paginate_by
