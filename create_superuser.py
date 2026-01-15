"""
Superuser Creation Script
Creates admin user from environment variables (secure).
"""
import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

User = get_user_model()

# Read from environment variables (SECURE)
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if email and password:
    if not User.objects.filter(email=email).exists():
        print(f"Creating superuser {email}...")
        User.objects.create_superuser(email=email, password=password)
        print("Superuser created successfully.")
    else:
        print(f"Superuser {email} already exists.")
else:
    print("WARNING: DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD not set.")
    print("Skipping superuser creation. Set these in Render environment variables.")
