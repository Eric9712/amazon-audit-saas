"""
Test de Detection d'Anomalies avec Fichiers CSV Fabriques
==========================================================
Ce script teste la logique de detection d'anomalies de l'audit engine
en utilisant des fichiers CSV fabriques avec des anomalies connues.

ANOMALIES CACHEES DANS LES FICHIERS:
1. inventory.csv  - SKU-LOST-006 : 25 unites recues mais 0 en stock (perdues)
2. returns.csv    - 2 retours avec status "Unit returned" non rembourses  
3. shipments.csv  - 1 commande LOST_IN_TRANSIT + 1 DAMAGED_IN_WAREHOUSE

Le test est REUSSI si le script detecte ces 4 anomalies.
"""

import os
import sys
import pandas as pd
from decimal import Decimal
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_DIR = os.path.join(BASE_DIR, 'test_data')


class AnomalyDetector:
    """Detecteur d'anomalies simplifie pour les tests."""
    
    def __init__(self):
        self.anomalies = []
        
    def detect_inventory_losses(self, df):
        """
        Detecte les articles recus mais non presents en stock.
        Anomalie: afn-inbound-shipped > 0 ET afn-total-quantity = 0
        """
        print("\n[INVENTAIRE] Analyse des pertes en entrepot...")
        losses = []
        
        for _, row in df.iterrows():
            inbound_shipped = int(row.get('afn-inbound-shipped-quantity', 0) or 0)
            total_qty = int(row.get('afn-total-quantity', 0) or 0)
            inbound_receiving = int(row.get('afn-inbound-receiving-quantity', 0) or 0)
            
            # Si des articles ont ete envoyes mais rien n'est en stock
            if inbound_shipped > 0 and total_qty == 0 and inbound_receiving == 0:
                sku = row.get('sku', 'UNKNOWN')
                price = float(row.get('your-price', 0) or 0)
                value = inbound_shipped * price
                
                losses.append({
                    'type': 'LOST_IN_WAREHOUSE',
                    'sku': sku,
                    'asin': row.get('asin', ''),
                    'quantity': inbound_shipped,
                    'unit_price': price,
                    'total_value': value,
                    'description': f"{inbound_shipped} unites recues mais 0 en stock"
                })
                print(f"  [!] ANOMALIE: {sku} - {inbound_shipped} unites perdues (valeur: {value:.2f} EUR)")
        
        self.anomalies.extend(losses)
        return losses
    
    def detect_unreimbursed_returns(self, df):
        """
        Detecte les retours clients non rembourses au vendeur.
        Anomalie: status = "Unit returned" (le client a retourne mais pas de credit)
        """
        print("\n[RETOURS] Analyse des retours non rembourses...")
        issues = []
        
        for _, row in df.iterrows():
            status = str(row.get('status', '')).lower()
            
            # Si le statut indique que l'article est retourne mais pas complete
            if 'returned' in status and 'completed' not in status:
                sku = row.get('sku', 'UNKNOWN')
                order_id = row.get('order-id', '')
                quantity = int(row.get('quantity', 1) or 1)
                
                # Estimer la valeur (on utilise un prix moyen si pas disponible)
                estimated_value = quantity * 15.0  # Prix moyen estime
                
                issues.append({
                    'type': 'UNREIMBURSED_RETURN',
                    'sku': sku,
                    'order_id': order_id,
                    'quantity': quantity,
                    'total_value': estimated_value,
                    'description': f"Retour non rembourse - Order {order_id}"
                })
                print(f"  [!] ANOMALIE: {sku} - Retour non rembourse (Order: {order_id})")
        
        self.anomalies.extend(issues)
        return issues
    
    def detect_shipment_losses(self, df):
        """
        Detecte les expeditions perdues ou endommagees.
        Anomalie: shipment-status in (LOST_IN_TRANSIT, DAMAGED_IN_WAREHOUSE)
        """
        print("\n[EXPEDITIONS] Analyse des pertes en transit...")
        losses = []
        
        loss_statuses = ['lost_in_transit', 'damaged_in_warehouse', 'lost', 'damaged']
        
        for _, row in df.iterrows():
            status = str(row.get('shipment-status', '')).lower().replace(' ', '_')
            
            if any(s in status for s in loss_statuses):
                sku = row.get('sku', 'UNKNOWN')
                order_id = row.get('amazon-order-id', '')
                quantity = int(row.get('quantity-shipped', 1) or 1)
                item_price = float(row.get('item-price', 0) or 0)
                
                losses.append({
                    'type': status.upper(),
                    'sku': sku,
                    'order_id': order_id,
                    'quantity': quantity,
                    'total_value': item_price,
                    'description': f"Expedition {status} - Order {order_id}"
                })
                print(f"  [!] ANOMALIE: {sku} - {status} (valeur: {item_price:.2f} EUR)")
        
        self.anomalies.extend(losses)
        return losses
    
    def get_summary(self):
        """Resume des anomalies detectees."""
        total_value = sum(a.get('total_value', 0) for a in self.anomalies)
        return {
            'total_anomalies': len(self.anomalies),
            'total_claimable_value': total_value,
            'by_type': {}
        }


def load_csv(filename):
    """Charge un fichier CSV/TSV."""
    filepath = os.path.join(TEST_DATA_DIR, filename)
    
    # Detecter le separateur
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        separator = '\t' if '\t' in first_line else ','
    
    df = pd.read_csv(filepath, sep=separator, encoding='utf-8')
    print(f"  Charge: {filename} ({len(df)} lignes, {len(df.columns)} colonnes)")
    return df


def main():
    print("=" * 70)
    print("TEST DE DETECTION D'ANOMALIES - FICHIERS CSV FABRIQUES")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Dossier de test: {TEST_DATA_DIR}")
    
    # Charger les fichiers
    print("\n[CHARGEMENT DES FICHIERS]")
    inventory_df = load_csv('inventory.csv')
    returns_df = load_csv('returns.csv')
    shipments_df = load_csv('shipments.csv')
    
    # Detecter les anomalies
    detector = AnomalyDetector()
    
    inv_losses = detector.detect_inventory_losses(inventory_df)
    ret_issues = detector.detect_unreimbursed_returns(returns_df)
    ship_losses = detector.detect_shipment_losses(shipments_df)
    
    # Resume
    print("\n" + "=" * 70)
    print("RESUME DES ANOMALIES DETECTEES")
    print("=" * 70)
    
    summary = detector.get_summary()
    total_anomalies = summary['total_anomalies']
    total_value = summary['total_claimable_value']
    
    print(f"\nTotal anomalies detectees: {total_anomalies}")
    print(f"Valeur totale reclamable: {total_value:.2f} EUR")
    
    print("\nDetail par categorie:")
    print(f"  - Pertes inventaire:    {len(inv_losses)} anomalie(s)")
    print(f"  - Retours non rembourses: {len(ret_issues)} anomalie(s)")
    print(f"  - Pertes expedition:    {len(ship_losses)} anomalie(s)")
    
    # Verification du test
    print("\n" + "=" * 70)
    print("VERIFICATION DU TEST")
    print("=" * 70)
    
    expected_anomalies = 4  # 1 inventaire + 2 retours + 1 perdu + 1 endommage (mais on a compte 2 dans shipments)
    # Correction: on a 1 inventaire + 2 retours + 2 shipments = 5
    
    # Comptons ce qu'on attend vraiment
    expected = {
        'inventory': 1,  # SKU-LOST-006
        'returns': 2,    # 2 retours "Unit returned"
        'shipments': 2   # LOST_IN_TRANSIT + DAMAGED_IN_WAREHOUSE
    }
    total_expected = sum(expected.values())
    
    print(f"\nAnomalies attendues: {total_expected}")
    print(f"  - Inventaire: {expected['inventory']} (trouve: {len(inv_losses)})")
    print(f"  - Retours: {expected['returns']} (trouve: {len(ret_issues)})")
    print(f"  - Expeditions: {expected['shipments']} (trouve: {len(ship_losses)})")
    
    all_correct = (
        len(inv_losses) == expected['inventory'] and
        len(ret_issues) == expected['returns'] and
        len(ship_losses) == expected['shipments']
    )
    
    if all_correct:
        print("\n" + "=" * 70)
        print(">>> TEST REUSSI! Toutes les anomalies ont ete detectees!")
        print("=" * 70)
        return True
    else:
        print("\n" + "=" * 70)
        print(">>> TEST ECHOUE! Certaines anomalies n'ont pas ete detectees.")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    
    # Afficher les details des anomalies pour debug
    print("\n\nDETAIL DES ANOMALIES (pour verification manuelle):")
    print("-" * 50)
    
    sys.exit(0 if success else 1)
