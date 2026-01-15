"""
Amazon SP-API Authentication Service
=====================================
Handles OAuth2 LWA (Login with Amazon) authentication flow.
"""

import logging
import secrets
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import SellerProfile
from apps.amazon_integration.models import AmazonCredentials
from utils.exceptions import AmazonAuthenticationError, AmazonTokenExpiredError

logger = logging.getLogger(__name__)


# Amazon LWA endpoints
LWA_TOKEN_URL = 'https://api.amazon.com/auth/o2/token'
LWA_AUTHORIZE_URL = 'https://www.amazon.com/ap/oa'

# SP-API endpoints for seller info
SP_API_BASE_URL = 'https://sellingpartnerapi-eu.amazon.com'


class AmazonAuthService:
    """
    Service for handling Amazon OAuth2 authentication.
    """
    
    def __init__(self, seller_profile: SellerProfile = None):
        """
        Initialize the auth service.
        
        Args:
            seller_profile: SellerProfile instance (optional, for token refresh)
        """
        self.seller_profile = seller_profile
        self.credentials = None
        
        if seller_profile:
            try:
                self.credentials = seller_profile.amazon_credentials
            except AmazonCredentials.DoesNotExist:
                pass
        
        # Load app credentials from settings
        sp_api_settings = getattr(settings, 'AMAZON_SP_API_SETTINGS', {})
        self.lwa_app_id = sp_api_settings.get('lwa_app_id', '')
        self.lwa_client_secret = sp_api_settings.get('lwa_client_secret', '')

        if not self.lwa_app_id or not self.lwa_client_secret:
            logger.error("Amazon LWA credentials found in settings")
            # We don't raise here to allow instantiation for other purposes, 
            # but methods needing auth will fail or should check.

    
    def get_authorization_url(self, redirect_uri: str, marketplace_id: str = None) -> Tuple[str, str]:
        """
        Generate the Amazon OAuth authorization URL.
        
        Args:
            redirect_uri: URL to redirect after authorization
            marketplace_id: Optional marketplace ID to pre-select
            
        Returns:
            Tuple of (authorization_url, state_token)
        """
        # Generate CSRF state token
        state = secrets.token_urlsafe(32)
        
        params = {
            'application_id': self.lwa_app_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'version': 'beta',  # Required for SP-API
        }
        
        # Store state in session or database for verification
        
        url = f"{LWA_AUTHORIZE_URL}?{urlencode(params)}"
        
        logger.info(f"Generated Amazon auth URL for redirect: {redirect_uri}")
        
        return url, state
    
    def exchange_authorization_code(
        self,
        authorization_code: str,
        redirect_uri: str,
        seller_profile: SellerProfile
    ) -> AmazonCredentials:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            authorization_code: The code received from Amazon OAuth callback
            redirect_uri: The same redirect URI used in authorization
            seller_profile: The seller profile to associate credentials with
            
        Returns:
            AmazonCredentials instance with tokens stored
        """
        logger.info(f"Exchanging auth code for seller: {seller_profile.user.email}")
        
        try:
            response = requests.post(
                LWA_TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'code': authorization_code,
                    'redirect_uri': redirect_uri,
                    'client_id': self.lwa_app_id,
                    'client_secret': self.lwa_client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            response.raise_for_status()
            data = response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to exchange auth code: {str(e)}")
            raise AmazonAuthenticationError(
                f"Failed to authenticate with Amazon: {str(e)}"
            )
        
        # Extract tokens
        access_token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        expires_in = data.get('expires_in', 3600)
        
        if not access_token or not refresh_token:
            raise AmazonAuthenticationError(
                "Invalid response from Amazon: missing tokens"
            )
        
        # Create or update credentials
        credentials, created = AmazonCredentials.objects.get_or_create(
            seller_profile=seller_profile
        )
        
        credentials.access_token = access_token
        credentials.refresh_token = refresh_token
        credentials.access_token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        credentials.save()
        
        # Fetch seller info
        self.credentials = credentials
        seller_info = self._fetch_seller_info(access_token)
        
        if seller_info:
            credentials.seller_id = seller_info.get('seller_id', '')
            credentials.marketplace_id = seller_info.get('marketplace_id', '')
            credentials.marketplace_ids = seller_info.get('marketplace_ids', [])
            credentials.save()
            
            # Update seller profile
            seller_profile.amazon_seller_id = credentials.seller_id
            seller_profile.amazon_marketplace_ids = credentials.marketplace_ids
            seller_profile.amazon_connected_at = timezone.now()
            seller_profile.amazon_token_expires_at = credentials.access_token_expires_at
            seller_profile.save()
        
        logger.info(f"Successfully authenticated seller: {credentials.seller_id}")
        
        return credentials
    
    def refresh_access_token(self) -> str:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            New access token
        """
        if not self.credentials:
            raise AmazonAuthenticationError("No credentials available")
        
        refresh_token = self.credentials.refresh_token
        
        if not refresh_token:
            raise AmazonTokenExpiredError(
                "No refresh token available. Please reconnect your Amazon account."
            )
        
        logger.info(f"Refreshing access token for seller: {self.seller_profile.user.email}")
        
        try:
            response = requests.post(
                LWA_TOKEN_URL,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.lwa_app_id,
                    'client_secret': self.lwa_client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 400:
                error_data = response.json()
                error = error_data.get('error', '')
                
                if error == 'invalid_grant':
                    raise AmazonTokenExpiredError(
                        "Refresh token has expired. Please reconnect your Amazon account."
                    )
            
            response.raise_for_status()
            data = response.json()
            
        except AmazonTokenExpiredError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise AmazonAuthenticationError(f"Failed to refresh token: {str(e)}")
        
        access_token = data.get('access_token')
        expires_in = data.get('expires_in', 3600)
        new_refresh_token = data.get('refresh_token')  # Sometimes Amazon rotates refresh tokens
        
        if not access_token:
            raise AmazonAuthenticationError("No access token in refresh response")
        
        # Update stored tokens
        self.credentials.update_tokens(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=new_refresh_token
        )
        
        # Update seller profile token expiry
        self.seller_profile.amazon_token_expires_at = self.credentials.access_token_expires_at
        self.seller_profile.save(update_fields=['amazon_token_expires_at'])
        
        logger.info(f"Successfully refreshed token for seller: {self.seller_profile.user.email}")
        
        return access_token
    
    def get_valid_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token
        """
        if not self.credentials:
            raise AmazonAuthenticationError("No credentials available")
        
        if self.credentials.is_access_token_valid:
            return self.credentials.access_token
        
        return self.refresh_access_token()
    
    def _fetch_seller_info(self, access_token: str) -> Optional[Dict]:
        """
        Fetch seller information using the Sellers API.
        
        Args:
            access_token: Valid access token
            
        Returns:
            Dictionary with seller info or None
        """
        try:
            response = requests.get(
                f"{SP_API_BASE_URL}/sellers/v1/marketplaceParticipations",
                headers={
                    'x-amz-access-token': access_token,
                    'Content-Type': 'application/json',
                },
                timeout=30
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch seller info: {response.status_code}")
                return None
            
            data = response.json()
            participations = data.get('payload', [])
            
            if not participations:
                return None
            
            # Get primary marketplace
            marketplace_ids = []
            primary_marketplace = None
            seller_id = None
            
            for participation in participations:
                marketplace = participation.get('marketplace', {})
                mp_id = marketplace.get('id')
                
                if mp_id:
                    marketplace_ids.append(mp_id)
                    
                    if not primary_marketplace:
                        primary_marketplace = mp_id
                
                seller = participation.get('participation', {})
                if not seller_id:
                    seller_id = seller.get('sellerId')
            
            return {
                'seller_id': seller_id,
                'marketplace_id': primary_marketplace,
                'marketplace_ids': marketplace_ids,
            }
            
        except Exception as e:
            logger.error(f"Error fetching seller info: {str(e)}")
            return None
    
    def verify_connection(self) -> bool:
        """
        Verify the Amazon connection is still valid.
        
        Returns:
            True if connection is valid
        """
        try:
            access_token = self.get_valid_access_token()
            seller_info = self._fetch_seller_info(access_token)
            return seller_info is not None
        except Exception as e:
            logger.error(f"Connection verification failed: {str(e)}")
            return False
