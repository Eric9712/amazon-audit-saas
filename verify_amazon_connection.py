
import os
import django
import sys
import requests
import json
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.conf import settings

def test_lwa_connection():
    """
    Test connectivity to Amazon's Login with Amazon (LWA) service.
    This verifies that the Refresh Token, Client ID, and Client Secret are valid.
    """
    print("=" * 60)
    print("TEST CONNEXION AMAZON SP-API (MODE RÉEL)")
    print("=" * 60)

    # 1. Vérification des variables d'environnement
    client_id = os.environ.get('LWA_APP_ID') or os.environ.get('AMAZON_LWA_CLIENT_ID')
    client_secret = os.environ.get('LWA_CLIENT_SECRET') or os.environ.get('AMAZON_LWA_CLIENT_SECRET')
    refresh_token = os.environ.get('AMAZON_REFRESH_TOKEN')

    print(f"[*] Vérification des credentials...")
    
    missing = []
    if not client_id: missing.append("LWA_APP_ID / AMAZON_LWA_CLIENT_ID")
    if not client_secret: missing.append("LWA_CLIENT_SECRET / AMAZON_LWA_CLIENT_SECRET")
    # Note: refresh_token might be stored in DB, but for this test script we need one source
    # We will try to get it from the latest AmazonCredentials in DB if env var is missing
    
    from apps.amazon_integration.models import AmazonCredentials
    creds = AmazonCredentials.objects.last()
    
    if not refresh_token and creds:
        try:
            refresh_token = creds.refresh_token
            print(f"[*] Refresh token récupéré depuis la base de données (ID: {creds.id})")
        except Exception as e:
            print(f"[!] Erreur lecture token DB: {e}")

    if not refresh_token:
         missing.append("AMAZON_REFRESH_TOKEN (ni dans .env ni dans DB)")

    if missing:
        print(f"[X] ECHEC: Credentials manquants: {', '.join(missing)}")
        return False

    print(f"[OK] Client ID: {client_id[:4]}...{client_id[-4:]}")
    print(f"[OK] Refresh Token: Présent")

    # 2. Tentative d'échange du Refresh Token contre un Access Token
    print("\n[*] Tentative d'authentification auprès d'Amazon LWA...")
    
    url = "https://api.amazon.com/auth/o2/token"
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in')
            print(f"[OK] AUTHENTIFICATION RÉUSSIE !")
            print(f"[*] Access Token reçu (valide {expires_in} secondes)")
            print(f"[*] Token: {access_token[:10]}...")
            return True
        else:
            print(f"[X] ECHEC AUTHENTIFICATION: {response.status_code}")
            print(f"[*] Réponse: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[X] ERREUR RÉSEAU: {str(e)}")
        return False

if __name__ == "__main__":
    if settings.AMAZON_SIMULATION_MODE:
        print("[!] ATTENTION: Le mode SIMULATION est encore activé dans settings!")
        print("    Veuillez le passer à False dans config/settings/development.py")
    else:
        success = test_lwa_connection()
        if success:
            print("\n>>> SUCCÈS: La connexion technique avec Amazon est validée.")
        else:
            print("\n>>> ÉCHEC: Impossible de se connecter à Amazon. Vérifiez vos clés.")
