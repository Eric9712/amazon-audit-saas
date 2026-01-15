
import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

print("=== DEBUT DEBUG IMPORTS ===")

print("1. Importing ReportRequest...")
try:
    from apps.amazon_integration.models import ReportRequest
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")
    
print("2. Importing LossDetector...")
try:
    from apps.audit_engine.services.loss_detector import LossDetector
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

print("3. Importing CaseGenerator...")
try:
    from apps.audit_engine.services.case_generator import CaseGenerator
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

print("4. Importing tasks...")
try:
    from apps.audit_engine.tasks import run_full_audit
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

print("=== FIN DEBUG IMPORTS ===")
