
import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

import logging

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.conf import settings
print(f"DEBUG: Initial SIMULATION_MODE setting: {getattr(settings, 'AMAZON_SIMULATION_MODE', 'Not Set')}")
settings.AMAZON_SIMULATION_MODE = True
print(f"DEBUG: Forced SIMULATION_MODE setting: {settings.AMAZON_SIMULATION_MODE}")

# Force logs to file
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
handler = logging.FileHandler('real_debug.log', mode='w', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger.addHandler(handler)

from apps.audit_engine.models import Audit
from apps.audit_engine.tasks import run_full_audit

def run_latest_audit():
    try:
        audit = Audit.objects.exclude(status='completed').last() # Prend le dernier non-terminé
        if not audit:
            print("No pending/running audit found to process.")
            # Si aucun non-terminé, on prend le tout dernier pour rejouer peut-être ?
            # Non, on évite.
            return

        print(f"Starting manual execution for Audit {audit.reference_code}...")
        
        # Execute the task synchronously
        result = run_full_audit(audit.id)
        print(f"Task finished with result: {result}")
        
        audit.refresh_from_db()
        print(f"Audit processing finished. Status: {audit.status}")
        if audit.status == 'failed':
             print(f"ERROR DETAILS: {audit.error_message}")
        print(f"Estimated Recovery: {audit.total_estimated_value}")
        print(f"Losses Detected: {audit.total_losses_detected}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("Running audit debug script...")
    run_latest_audit()
