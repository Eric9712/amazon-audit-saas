import os
import django
from django.contrib.auth import get_user_model

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

User = get_user_model()

# Hardcoded credentials for emergency access
# TODO: Delete this file after successful login!
email = "admin@amazon-audit.com"
password = "Admin123456!"

if not User.objects.filter(email=email).exists():
    print(f"Creating emergency superuser {email}...")
    User.objects.create_superuser(email=email, password=password)
    print("Superuser created successfully.")
else:
    print("Emergency superuser already exists. Resetting password...")
    user = User.objects.get(email=email)
    user.set_password(password)
    user.save()
    print("Password reset to default.")
