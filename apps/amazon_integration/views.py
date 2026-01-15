"""
Amazon Integration Views
========================
Views for Amazon OAuth callback and connection management.
"""

import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.accounts.models import SellerProfile
from apps.amazon_integration.models import AmazonCredentials
from apps.amazon_integration.services.auth_service import AmazonAuthService
from utils.exceptions import AmazonAuthenticationError

logger = logging.getLogger(__name__)


@login_required
def initiate_amazon_auth(request):
    """
    Initiate Amazon OAuth flow.
    Generates authorization URL and redirects user to Amazon.
    """
    user = request.user
    
    # Ensure seller profile exists
    seller_profile, _ = SellerProfile.objects.get_or_create(user=user)
    
    # Generate redirect URI
    redirect_uri = request.build_absolute_uri(reverse('amazon_integration:oauth_callback'))
    
    # Get authorization URL
    auth_service = AmazonAuthService()
    auth_url, state = auth_service.get_authorization_url(redirect_uri)
    
    # Store state in session for CSRF protection
    request.session['amazon_oauth_state'] = state
    request.session['amazon_oauth_redirect_uri'] = redirect_uri
    
    logger.info(f"Initiating Amazon OAuth for user: {user.email}")
    
    return redirect(auth_url)


@login_required
def oauth_callback(request):
    """
    Handle OAuth callback from Amazon.
    Exchanges authorization code for tokens and stores them.
    """
    user = request.user
    
    # Check for errors from Amazon
    error = request.GET.get('error')
    if error:
        error_description = request.GET.get('error_description', 'Unknown error')
        logger.warning(f"Amazon OAuth error for user {user.email}: {error} - {error_description}")
        messages.error(
            request,
            f"Amazon a refusé l'autorisation: {error_description}"
        )
        return redirect('dashboard:connect_amazon')
    
    # Get authorization code
    spapi_oauth_code = request.GET.get('spapi_oauth_code')
    selling_partner_id = request.GET.get('selling_partner_id')
    
    if not spapi_oauth_code:
        messages.error(
            request,
            "Code d'autorisation manquant. Veuillez réessayer."
        )
        return redirect('dashboard:connect_amazon')
    
    # Verify state (CSRF protection)
    state = request.GET.get('state')
    expected_state = request.session.get('amazon_oauth_state')
    
    if state != expected_state:
        logger.warning(f"State mismatch for user {user.email}: {state} != {expected_state}")
        messages.error(
            request,
            "Erreur de sécurité. Veuillez réessayer."
        )
        return redirect('dashboard:connect_amazon')
    
    # Get redirect URI from session
    redirect_uri = request.session.get('amazon_oauth_redirect_uri')
    
    # Clean up session
    request.session.pop('amazon_oauth_state', None)
    request.session.pop('amazon_oauth_redirect_uri', None)
    
    try:
        # Get or create seller profile
        seller_profile, _ = SellerProfile.objects.get_or_create(user=user)
        
        # Exchange code for tokens
        auth_service = AmazonAuthService()
        credentials = auth_service.exchange_authorization_code(
            authorization_code=spapi_oauth_code,
            redirect_uri=redirect_uri,
            seller_profile=seller_profile,
        )
        
        logger.info(
            f"Successfully connected Amazon account for user {user.email} "
            f"(Seller ID: {credentials.seller_id})"
        )
        
        messages.success(
            request,
            "Votre compte Amazon a été connecté avec succès! "
            "Vous pouvez maintenant lancer votre premier audit."
        )
        
        return redirect('dashboard:home')
        
    except AmazonAuthenticationError as e:
        logger.error(f"Amazon auth error for user {user.email}: {str(e)}")
        messages.error(
            request,
            f"Erreur de connexion Amazon: {e.message}"
        )
        return redirect('dashboard:connect_amazon')
        
    except Exception as e:
        logger.exception(f"Unexpected error during Amazon OAuth for user {user.email}")
        messages.error(
            request,
            "Une erreur inattendue s'est produite. Veuillez réessayer."
        )
        return redirect('dashboard:connect_amazon')


@login_required
def check_connection_status(request):
    """
    API endpoint to check Amazon connection status.
    Returns JSON with connection status.
    """
    user = request.user
    
    try:
        seller_profile = user.seller_profile
        
        if not seller_profile.is_amazon_connected:
            return JsonResponse({
                'connected': False,
                'message': 'Amazon account not connected',
            })
        
        # Verify connection is still valid
        auth_service = AmazonAuthService(seller_profile)
        is_valid = auth_service.verify_connection()
        
        if is_valid:
            return JsonResponse({
                'connected': True,
                'seller_id': seller_profile.amazon_seller_id,
                'marketplaces': seller_profile.amazon_marketplace_ids,
                'connected_at': seller_profile.amazon_connected_at.isoformat() if seller_profile.amazon_connected_at else None,
            })
        else:
            return JsonResponse({
                'connected': False,
                'message': 'Amazon connection expired or invalid',
            })
            
    except SellerProfile.DoesNotExist:
        return JsonResponse({
            'connected': False,
            'message': 'Seller profile not found',
        })
    except Exception as e:
        logger.error(f"Error checking connection status: {str(e)}")
        return JsonResponse({
            'connected': False,
            'message': 'Error checking connection status',
        }, status=500)


@login_required
@require_http_methods(['POST'])
def disconnect_amazon(request):
    """
    Disconnect Amazon account.
    """
    user = request.user
    
    try:
        seller_profile = user.seller_profile
        
        # Delete credentials
        AmazonCredentials.objects.filter(seller_profile=seller_profile).delete()
        
        # Clear profile
        seller_profile.disconnect_amazon()
        
        logger.info(f"User {user.email} disconnected their Amazon account")
        
        messages.success(
            request,
            "Votre compte Amazon a été déconnecté."
        )
        
    except SellerProfile.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error disconnecting Amazon: {str(e)}")
        messages.error(
            request,
            "Erreur lors de la déconnexion. Veuillez réessayer."
        )
    
    return redirect('accounts:profile')


@login_required
def amazon_settings(request):
    """
    Amazon connection settings page.
    """
    user = request.user
    seller_profile, _ = SellerProfile.objects.get_or_create(user=user)
    
    credentials = None
    if seller_profile.is_amazon_connected:
        try:
            credentials = seller_profile.amazon_credentials
        except AmazonCredentials.DoesNotExist:
            pass
    
    return render(request, 'amazon_integration/settings.html', {
        'seller_profile': seller_profile,
        'credentials': credentials,
    })
