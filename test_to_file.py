"""Test simple de detection d'anomalies - Sortie dans fichier."""
import os
import sys

# Redirect output to file
with open('test_output.txt', 'w', encoding='utf-8') as output_file:
    def log(msg):
        print(msg)
        output_file.write(msg + '\n')
        output_file.flush()
    
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
    
    # Suppress Django debug output
    import logging
    logging.disable(logging.CRITICAL)
    
    import django
    django.setup()
    import pandas as pd

    # Load files
    log("Chargement des fichiers...")
    inv = pd.read_csv('test_data/inventory.csv', sep='\t')
    ret = pd.read_csv('test_data/returns.csv', sep='\t')
    ship = pd.read_csv('test_data/shipments.csv', sep='\t')

    log(f"  Inventaire: {len(inv)} lignes")
    log(f"  Retours: {len(ret)} lignes")
    log(f"  Expeditions: {len(ship)} lignes")

    results = []

    # Check inventory losses
    log("\n[1] Analyse inventaire...")
    for _, r in inv.iterrows():
        shipped = int(r.get('afn-inbound-shipped-quantity', 0) or 0)
        total = int(r.get('afn-total-quantity', 0) or 0)
        receiving = int(r.get('afn-inbound-receiving-quantity', 0) or 0)
        if shipped > 0 and total == 0 and receiving == 0:
            sku = r['sku']
            price = float(r.get('your-price', 0) or 0)
            value = shipped * price
            results.append(('INVENTAIRE_PERDU', sku, shipped, value))
            log(f"    ANOMALIE: {sku} - {shipped} unites perdues (valeur: {value:.2f} EUR)")

    # Check returns not reimbursed
    log("\n[2] Analyse retours...")
    for _, r in ret.iterrows():
        status = str(r.get('status', '')).lower()
        if 'returned' in status and 'completed' not in status:
            sku = r['sku']
            order_id = r['order-id']
            qty = int(r.get('quantity', 1) or 1)
            results.append(('RETOUR_NON_REMBOURSE', sku, qty, 15.0 * qty))
            log(f"    ANOMALIE: {sku} - Retour non rembourse (Order: {order_id})")

    # Check shipment losses
    log("\n[3] Analyse expeditions...")
    for _, r in ship.iterrows():
        status = str(r.get('shipment-status', '')).lower()
        if 'lost' in status or 'damaged' in status:
            sku = r['sku']
            order_id = r['amazon-order-id']
            value = float(r.get('item-price', 0) or 0)
            results.append(('EXPEDITION_' + status.upper(), sku, 1, value))
            log(f"    ANOMALIE: {sku} - {status} (valeur: {value:.2f} EUR)")

    # Summary
    log("\n" + "=" * 60)
    log("RESUME DES ANOMALIES DETECTEES")
    log("=" * 60)
    log(f"Total: {len(results)} anomalies")

    total_value = sum(r[3] for r in results)
    log(f"Valeur totale reclamable: {total_value:.2f} EUR")

    log("\nDetail:")
    for i, (typ, sku, qty, val) in enumerate(results, 1):
        log(f"  {i}. [{typ}] {sku} - Qte: {qty} - Valeur: {val:.2f} EUR")

    # Expected: 1 inventory + 2 returns + 2 shipments = 5
    expected = 5
    log("\n" + "=" * 60)
    if len(results) == expected:
        log(">>> TEST REUSSI! Toutes les anomalies detectees.")
    else:
        log(f">>> TEST ECHOUE! Attendu: {expected}, Trouve: {len(results)}")
    log("=" * 60)

print("\nResultats ecrits dans test_output.txt")
