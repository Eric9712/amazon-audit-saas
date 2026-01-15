"""Test simple de detection d'anomalies."""
import os
import sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django
django.setup()
import pandas as pd

# Load files
print("Chargement des fichiers...")
inv = pd.read_csv('test_data/inventory.csv', sep='\t')
ret = pd.read_csv('test_data/returns.csv', sep='\t')
ship = pd.read_csv('test_data/shipments.csv', sep='\t')

print(f"  Inventaire: {len(inv)} lignes")
print(f"  Retours: {len(ret)} lignes")
print(f"  Expeditions: {len(ship)} lignes")

results = []

# Check inventory losses
print("\n[1] Analyse inventaire...")
for _, r in inv.iterrows():
    shipped = int(r.get('afn-inbound-shipped-quantity', 0) or 0)
    total = int(r.get('afn-total-quantity', 0) or 0)
    receiving = int(r.get('afn-inbound-receiving-quantity', 0) or 0)
    if shipped > 0 and total == 0 and receiving == 0:
        sku = r['sku']
        price = float(r.get('your-price', 0) or 0)
        value = shipped * price
        results.append(('INVENTAIRE_PERDU', sku, shipped, value))
        print(f"    ANOMALIE: {sku} - {shipped} unites perdues (valeur: {value:.2f} EUR)")

# Check returns not reimbursed
print("\n[2] Analyse retours...")
for _, r in ret.iterrows():
    status = str(r.get('status', '')).lower()
    if 'returned' in status and 'completed' not in status:
        sku = r['sku']
        order_id = r['order-id']
        qty = int(r.get('quantity', 1) or 1)
        results.append(('RETOUR_NON_REMBOURSE', sku, qty, 15.0 * qty))
        print(f"    ANOMALIE: {sku} - Retour non rembourse (Order: {order_id})")

# Check shipment losses
print("\n[3] Analyse expeditions...")
for _, r in ship.iterrows():
    status = str(r.get('shipment-status', '')).lower()
    if 'lost' in status or 'damaged' in status:
        sku = r['sku']
        order_id = r['amazon-order-id']
        value = float(r.get('item-price', 0) or 0)
        results.append(('EXPEDITION_' + status.upper(), sku, 1, value))
        print(f"    ANOMALIE: {sku} - {status} (valeur: {value:.2f} EUR)")

# Summary
print("\n" + "=" * 60)
print("RESUME DES ANOMALIES DETECTEES")
print("=" * 60)
print(f"Total: {len(results)} anomalies")

total_value = sum(r[3] for r in results)
print(f"Valeur totale reclamable: {total_value:.2f} EUR")

print("\nDetail:")
for i, (typ, sku, qty, val) in enumerate(results, 1):
    print(f"  {i}. [{typ}] {sku} - Qte: {qty} - Valeur: {val:.2f} EUR")

# Expected: 1 inventory + 2 returns + 2 shipments = 5
expected = 5
print("\n" + "=" * 60)
if len(results) == expected:
    print(">>> TEST REUSSI! Toutes les anomalies detectees.")
else:
    print(f">>> TEST ECHOUE! Attendu: {expected}, Trouve: {len(results)}")
print("=" * 60)
