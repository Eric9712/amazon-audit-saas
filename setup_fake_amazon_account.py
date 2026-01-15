
import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from apps.accounts.models import SellerProfile
from apps.amazon_integration.models import AmazonCredentials

User = get_user_model()

def setup_fake_account():
    # Get or create admin user
    user, created = User.objects.get_or_create(
        email='admin@example.com', 
        defaults={
            'is_staff': True, 
            'is_superuser': True,
            'first_name': 'Admin',
            'last_name': 'User'
        }
    )
    if created:
        user.set_password('adminpass')
        user.save()
        print(f"Created user: {user.email}")
    else:
        print(f"Using existing user: {user.email}")

    # Create Seller Profile
    profile, _ = SellerProfile.objects.get_or_create(user=user)
    
    # Create fake credentials
    credentials, created = AmazonCredentials.objects.get_or_create(
        seller_profile=profile,
        defaults={
            'access_token': 'fake-access-token',
            'refresh_token': 'fake-refresh-token',
            'seller_id': 'A1FAKE_SELLER_ID',
            'marketplace_id': 'A13V1IB3VIYBER', # France
            'marketplace_ids': ['A13V1IB3VIYBER'],
            'access_token_expires_at': timezone.now() + timedelta(days=365)
        }
    )
    
    # Update profile connection status
    profile.amazon_seller_id = credentials.seller_id
    profile.amazon_marketplace_ids = credentials.marketplace_ids
    profile.amazon_connected_at = timezone.now()
    profile.amazon_token_expires_at = credentials.access_token_expires_at
    profile.save()
    
    print("✅ Fake Amazon account connected successfully!")
    print("You can now go to /dashboard/ to see the connected state and run an audit.")

if __name__ == '__main__':
    setup_fake_account()
