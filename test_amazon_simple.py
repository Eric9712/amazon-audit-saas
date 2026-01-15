"""
Amazon SP-API Sandbox Connection Test (Simple Version)
"""
import os
import sys
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

from django.conf import settings

print("=" * 60)
print("TEST CONNEXION AMAZON SP-API")
print("=" * 60)

# Check settings
sim_mode = getattr(settings, 'AMAZON_SIMULATION_MODE', True)
sandbox_mode = getattr(settings, 'AMAZON_USE_SANDBOX', False)

print(f"AMAZON_SIMULATION_MODE = {sim_mode}")
print(f"AMAZON_USE_SANDBOX = {sandbox_mode}")

# Get SP-API settings
sp_settings = getattr(settings, 'AMAZON_SP_API_SETTINGS', {})
app_id = sp_settings.get('lwa_app_id', '')
client_secret = sp_settings.get('lwa_client_secret', '')

print(f"\nLWA App ID: {app_id[:30] if app_id else 'MANQUANT'}...")
print(f"LWA Client Secret: {'PRESENT' if client_secret and 'replace' not in client_secret else 'MANQUANT'}")

# Check if credentials are placeholders
if not app_id or 'replace' in app_id.lower():
    print("\n[ECHEC] Les credentials Amazon sont des placeholders.")
    print("Vous devez configurer votre .env avec vos VRAIES cles Amazon:")
    print("  - AMAZON_LWA_APP_ID=amzn1.application-oa2-client.xxxx")
    print("  - AMAZON_LWA_CLIENT_SECRET=amzn1.oa2-cs.v1.xxxx")
    print("  - AMAZON_REFRESH_TOKEN=Atzr|xxxx")
    sys.exit(1)

# Try to get refresh token
refresh_token = os.environ.get('AMAZON_REFRESH_TOKEN')

if not refresh_token:
    print("\nRecherche du refresh token en base de donnees...")
    try:
        from apps.amazon_integration.models import AmazonCredentials
        creds = AmazonCredentials.objects.exclude(
            _refresh_token_encrypted__isnull=True
        ).last()
        if creds:
            refresh_token = creds.refresh_token
            print(f"  -> Trouve en DB (ID: {creds.id})")
    except Exception as e:
        print(f"  -> Erreur DB: {e}")

if not refresh_token:
    print("\n[ECHEC] Aucun refresh token disponible.")
    print("Vous devez autoriser l'application sur Amazon Seller Central.")
    sys.exit(1)

print(f"Refresh Token: PRESENT ({len(refresh_token)} caracteres)")

# Test LWA authentication
print("\n" + "-" * 60)
print("Test authentification LWA...")

url = "https://api.amazon.com/auth/o2/token"
payload = {
    'grant_type': 'refresh_token',
    'refresh_token': refresh_token,
    'client_id': app_id,
    'client_secret': client_secret
}

try:
    response = requests.post(url, data=payload, timeout=15)
    print(f"HTTP Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        access_token = data.get('access_token', '')
        expires_in = data.get('expires_in', 0)
        print(f"  -> SUCCES! Token obtenu (valide {expires_in}s)")
        
        # Test API call
        print("\n" + "-" * 60)
        print("Test appel API SP-API...")
        
        api_url = "https://sellingpartnerapi-eu.amazon.com/sellers/v1/marketplaceParticipations"
        headers = {
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json',
        }
        
        api_response = requests.get(api_url, headers=headers, timeout=30)
        print(f"HTTP Status: {api_response.status_code}")
        
        if api_response.status_code == 200:
            print("  -> SUCCES! Appel API reussi")
            api_data = api_response.json()
            participations = api_data.get('payload', [])
            print(f"  -> Marketplaces: {len(participations)}")
            for p in participations[:3]:
                mp = p.get('marketplace', {})
                print(f"     - {mp.get('name')} ({mp.get('id')})")
            print("\n" + "=" * 60)
            print("TOUS LES TESTS PASSES AVEC SUCCES!")
            print("=" * 60)
        else:
            print(f"  -> ECHEC API: {api_response.text[:200]}")
            
    else:
        print(f"  -> ECHEC: {response.text[:200]}")
        
except Exception as e:
    print(f"  -> ERREUR: {e}")
    sys.exit(1)
