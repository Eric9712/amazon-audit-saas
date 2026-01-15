"""
Amazon SP-API Sandbox Connection Test
=====================================
Ce script teste la connexion au Sandbox Amazon de manière rigoureuse.
Il vérifie étape par étape:
1. La présence et validité des credentials
2. L'obtention d'un token LWA (Login with Amazon)
3. Un appel API de test au Sandbox

PRÉREQUIS: Vous devez avoir configuré votre .env avec vos VRAIES clés Amazon Developer:
- AMAZON_LWA_APP_ID (ou LWA_APP_ID)
- AMAZON_LWA_CLIENT_SECRET (ou LWA_CLIENT_SECRET)
- AMAZON_REFRESH_TOKEN (optionnel si stocké en DB)
"""

import os
import sys
import json
import requests
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

from django.conf import settings

# Console colors
class Colors:
    OK = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    INFO = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, description):
    print(f"\n{Colors.BOLD}[ÉTAPE {step_num}]{Colors.END} {description}")
    print("-" * 50)

def print_ok(msg):
    print(f"{Colors.OK}✓ {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.WARN}⚠ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.INFO}→ {msg}{Colors.END}")


def step1_check_config():
    """Vérifier la configuration et les credentials."""
    print_step(1, "Vérification de la configuration")
    
    errors = []
    warnings = []
    
    # Check simulation mode
    sim_mode = getattr(settings, 'AMAZON_SIMULATION_MODE', True)
    sandbox_mode = getattr(settings, 'AMAZON_USE_SANDBOX', False)
    
    print_info(f"AMAZON_SIMULATION_MODE = {sim_mode}")
    print_info(f"AMAZON_USE_SANDBOX = {sandbox_mode}")
    
    if sim_mode:
        print_warn("Le mode SIMULATION est activé. Désactivez-le pour utiliser le Sandbox réel.")
        errors.append("AMAZON_SIMULATION_MODE doit être False")
    else:
        print_ok("Mode simulation désactivé")
    
    if sandbox_mode:
        print_ok("Mode Sandbox activé")
    else:
        print_warn("Mode Sandbox désactivé (appels de production)")
    
    # Check SP-API settings
    sp_settings = getattr(settings, 'AMAZON_SP_API_SETTINGS', {})
    
    app_id = sp_settings.get('lwa_app_id', '')
    client_secret = sp_settings.get('lwa_client_secret', '')
    
    if not app_id or 'replace-me' in app_id:
        print_fail(f"LWA App ID manquant ou placeholder: '{app_id[:20]}...'")
        errors.append("LWA_APP_ID non configuré")
    else:
        print_ok(f"LWA App ID présent: {app_id[:15]}...")
    
    if not client_secret or 'replace-me' in client_secret:
        print_fail("LWA Client Secret manquant ou placeholder")
        errors.append("LWA_CLIENT_SECRET non configuré")
    else:
        print_ok(f"LWA Client Secret présent: {client_secret[:10]}...")
    
    return len(errors) == 0, sp_settings


def step2_get_lwa_token(sp_settings):
    """Obtenir un token LWA."""
    print_step(2, "Authentification LWA (Login with Amazon)")
    
    app_id = sp_settings.get('lwa_app_id', '')
    client_secret = sp_settings.get('lwa_client_secret', '')
    
    # Try to get refresh token from env or DB
    refresh_token = os.environ.get('AMAZON_REFRESH_TOKEN')
    
    if not refresh_token:
        print_info("Refresh token non trouvé dans .env, recherche en base de données...")
        try:
            from apps.amazon_integration.models import AmazonCredentials
            creds = AmazonCredentials.objects.exclude(
                _refresh_token_encrypted__isnull=True
            ).last()
            if creds:
                refresh_token = creds.refresh_token
                print_ok(f"Refresh token trouvé en DB (credential ID: {creds.id})")
            else:
                print_fail("Aucun refresh token trouvé en base de données")
        except Exception as e:
            print_fail(f"Erreur lecture DB: {e}")
    
    if not refresh_token:
        print_fail("Aucun refresh token disponible. Vous devez d'abord autoriser l'application sur Amazon Seller Central.")
        return False, None
    
    print_info("Tentative d'échange du refresh token contre un access token...")
    
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': app_id,
        'client_secret': client_secret
    }
    
    try:
        response = requests.post(url, data=payload, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in')
            
            print_ok(f"TOKEN LWA OBTENU AVEC SUCCÈS!")
            print_info(f"Validité: {expires_in} secondes")
            print_info(f"Token: {access_token[:20]}...")
            
            return True, access_token
        else:
            print_fail(f"Échec authentification: HTTP {response.status_code}")
            print_info(f"Réponse: {response.text[:200]}")
            
            # Parse error for more details
            try:
                err = response.json()
                if 'error' in err:
                    print_fail(f"Erreur Amazon: {err.get('error')} - {err.get('error_description', '')}")
            except:
                pass
                
            return False, None
            
    except requests.exceptions.Timeout:
        print_fail("Timeout lors de la connexion à Amazon LWA")
        return False, None
    except requests.exceptions.RequestException as e:
        print_fail(f"Erreur réseau: {e}")
        return False, None


def step3_test_sandbox_api(access_token):
    """Tester un appel API au Sandbox."""
    print_step(3, "Test appel API Sandbox")
    
    # Use EU endpoint for France
    base_url = "https://sellingpartnerapi-eu.amazon.com"
    
    # Test endpoint: Get Marketplaces (simple read-only call)
    # This endpoint should work in sandbox mode
    endpoint = "/sellers/v1/marketplaceParticipations"
    url = f"{base_url}{endpoint}"
    
    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    
    print_info(f"Endpoint: {endpoint}")
    print_info(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        print_info(f"Status HTTP: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_ok("APPEL API RÉUSSI!")
            
            # Parse marketplaces
            participations = data.get('payload', [])
            if participations:
                print_info(f"Marketplaces trouvées: {len(participations)}")
                for p in participations[:3]:  # Show first 3
                    mp = p.get('marketplace', {})
                    print_info(f"  - {mp.get('name')} ({mp.get('id')})")
            
            return True, data
            
        elif response.status_code == 403:
            print_fail("Accès refusé (403). Vérifiez les permissions de votre application.")
            print_info(f"Réponse: {response.text[:300]}")
            return False, None
            
        elif response.status_code == 401:
            print_fail("Non autorisé (401). Le token est peut-être invalide.")
            print_info(f"Réponse: {response.text[:300]}")
            return False, None
            
        else:
            print_fail(f"Erreur API: HTTP {response.status_code}")
            print_info(f"Réponse: {response.text[:300]}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print_fail(f"Erreur réseau: {e}")
        return False, None


def main():
    print("=" * 60)
    print(f"{Colors.BOLD}TEST DE CONNEXION AMAZON SP-API SANDBOX{Colors.END}")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Check configuration
    config_ok, sp_settings = step1_check_config()
    if not config_ok:
        print(f"\n{Colors.FAIL}{'='*60}")
        print("ÉCHEC: Configuration incomplète")
        print("Veuillez configurer votre .env avec vos vraies clés Amazon.")
        print(f"{'='*60}{Colors.END}")
        return False
    
    # Step 2: Get LWA token
    token_ok, access_token = step2_get_lwa_token(sp_settings)
    if not token_ok:
        print(f"\n{Colors.FAIL}{'='*60}")
        print("ÉCHEC: Impossible d'obtenir un token Amazon")
        print("Vérifiez vos credentials ou réautorisez l'application.")
        print(f"{'='*60}{Colors.END}")
        return False
    
    # Step 3: Test API call
    api_ok, data = step3_test_sandbox_api(access_token)
    if not api_ok:
        print(f"\n{Colors.WARN}{'='*60}")
        print("ATTENTION: Token obtenu mais l'appel API a échoué")
        print("L'authentification fonctionne, mais il y a peut-être")
        print("un problème de permissions ou de Sandbox.")
        print(f"{'='*60}{Colors.END}")
        return False
    
    # All tests passed!
    print(f"\n{Colors.OK}{'='*60}")
    print(f"{Colors.BOLD}✓ TOUS LES TESTS PASSÉS AVEC SUCCÈS!{Colors.END}")
    print(f"{Colors.OK}La connexion Amazon SP-API est opérationnelle.")
    print(f"{'='*60}{Colors.END}")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
