"""
HospitalityOS v4.0 - Nightly Inventory & Shrinkage Auditor
Architect: Princeton Afeez
Description: Automatically bridges POS sales with Physical counts. 
             Detects theft (shrinkage), manages prep levels, and 
             generates duplicate-proof shopping lists.
"""

import csv        # Standard library for parsing/writing the menu.csv database
import sys        # Used for clean process termination during critical file errors
import json       # For deep-parsing the POS 'Shared Brain' (restaurant_state.json)
import os         # Essential for file existence validation and path handling
import re         # 'Laser Eye' Regex to ensure shopping lists remain duplicate-proof
from datetime import datetime # Core for time-stamping audits and historical logging
from decimal import Decimal   # Mandatory for currency to prevent floating-point math errors

# --- INTERNAL MODULE IMPORTS ---
# Ensure these exist in your /utils and /validator directories
from utils import PathManager, RESTAURANT_STATE_NAME, print_divider
from validator import get_int                 # Custom input wrapper for type-safety

# =================================================================
# PHASE 1: DATA STRUCTURES & PERSISTENCE ENGINE
# =================================================================

class InventoryError(Exception):
    """Custom exception to halt logic when physical reality contradicts starting stock."""
    pass 

def load_inventory_from_menu():
    """Extracts master inventory, pricing, and par thresholds from the CSV database."""
    # Resolve the path dynamically to ensure it works on Windows, Mac, or Linux
    full_path = PathManager.get_path("menu.csv")
    
    # Storage for the list of item dictionaries
    inventory_list = []  
    
    try:
        # Open in read-mode with UTF-8 to support special characters (e.g., currency symbols)
        with open(full_path, mode="r", newline="", encoding="utf-8") as file:
            # DictReader maps the header row to keys for each subsequent row
            reader = csv.DictReader(file)  
          
            for row in reader:  
                # Convert strings to Decimals/Ints immediately to enable math operations
                row["unit_price"] = Decimal(str(row["unit_price"]))  # Financial precision
                row["line_inv"] = int(row["line_inv"])        # Front-of-house stock
                row["walk_in_inv"] = int(row["walk_in_inv"])  # Main cold storage
                row["freezer_inv"] = int(row["freezer_inv"])  # Frozen storage
                row["par_level"] = int(row["par_level"])      # Reorder trigger point
                
                # Calculate the 'Snapshot' of all units currently in the building
                row["starting_inv"] = row["line_inv"] + row["walk_in_inv"] + row["freezer_inv"]
                inventory_list.append(row)  # Add processed object to the collection
        return inventory_list  # Return list for the audit loop
    except FileNotFoundError:  
        print(f"❌ Error: {full_path} not found. Please verify the /data directory.")
        sys.exit()  # Exit to prevent the script from running on null data

def save_new_inventory_state(inventory_list):
    """
    Writes menu.csv — fieldnames MUST match database.load_system_state DictReader keys
    (category, name, unit_price, line_inv, walk_in_inv, freezer_inv, par_level) or reloads break.
    """
    full_path = PathManager.get_path("menu.csv")
    fieldnames = ["category", "name", "unit_price", "line_inv", "walk_in_inv", "freezer_inv", "par_level"]
    
    try:
        with open(full_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader() # Write the standardized headers
            for item in inventory_list:
                # Filter out the temporary 'starting_inv' key before writing
                clean_row = {k: item[k] for k in fieldnames}
                writer.writerow(clean_row)
        print("💾 SYSTEM: Master Inventory (menu.csv) has been updated for tomorrow.")
    except Exception as e:
        print(f"⚠️ CRITICAL: Failed to save inventory state. Error: {e}")

def load_sales_data():
    """Pulls current POS snapshots to reconcile 'Expected' vs 'Actual' stock."""
    filename = PathManager.get_path(RESTAURANT_STATE_NAME)

    try:
        with open(filename, "r") as f:
            data = json.load(f)
            # Map item names to their quantities for O(1) lookup speed
            return data.get("inventory_snapshot", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {} # Return empty if no sales were recorded today

# =================================================================
# PHASE 2: THE AUDIT ENGINE (LOGIC & RECONCILIATION)
# =================================================================

def run_inventory_audit():
    """Primary controller for inventory reconciliation and manager data entry."""
    inventory = load_inventory_from_menu()  # Load base data
    shared_brain_inv = load_sales_data()    # Load sales data    
    
    # Global state container for the nightly report
    audit_results = {
        "shrinkage": [], "waste": [], "prep": [], "shopping": [],
        "total_sold_val": Decimal("0.00"), 
        "total_waste_val": Decimal("0.00"), 
        "total_shrink_val": Decimal("0.00")
    }

    print("\n" + "═"*60)
    print(f"{'HOSPITALITY OS v4.0: NIGHTLY MANAGER AUDIT':^60}")
    print("═"*60)

    for item in inventory:  
        print(f"\n📝 ITEM: {item['name'].upper()}") 
        
        # Determine how many units the POS 'thinks' should be left on the line
        pos_inventory_remaining = shared_brain_inv.get(item['name'], item['line_inv'])
        # Math: Expected Line Sales = Morning Start - Current Snapshot
        pos_sold_calculated = item['line_inv'] - pos_inventory_remaining
        
        if pos_sold_calculated > 0:
            print(f"  [ 💡 POS Insight: {pos_sold_calculated} units sold today ]")
        
        # User input loop with validation guardrails
        while True: 
            try:
                # Capture manager observations
                sold = get_int(f"  Confirm SOLD: ", min_val=0)
                waste = get_int(f"  Confirm WASTE: ", min_val=0)
                physical_total = get_int(f"  FINAL TOTAL PHYSICAL COUNT: ", min_val=0)

                # FAT FINGER GUARD: Flags suspiciously high entries
                if sold > 150 or waste > 50:
                    if input(f"  ⚠️  Confirm high volume ({max(sold, waste)})? (y/n): ").lower() != 'y':
                        continue 

                # THE MATH GUARDRAIL: Reality check against building capacity
                if (sold + waste + physical_total) > item['starting_inv']:
                    raise InventoryError(f"Impossibility detected. Building only held {item['starting_inv']}.")
                
                # Financial tracking
                item_sales_val = sold * item["unit_price"]
                audit_results["total_sold_val"] += item_sales_val
                
                # Logic for Known Loss (Waste)
                if waste > 0:
                    w_loss = waste * item["unit_price"]
                    audit_results["total_waste_val"] += w_loss
                    audit_results["waste"].append({"name": item['name'], "qty": waste, "loss": w_loss, "base_sales": item_sales_val})

                # Logic for Unknown Loss (Shrinkage/Theft)
                expected_remaining = item["starting_inv"] - sold - waste  
                if physical_total < expected_remaining:
                    missing = expected_remaining - physical_total
                    s_loss = missing * item["unit_price"]
                    audit_results["total_shrink_val"] += s_loss
                    audit_results["shrinkage"].append({"name": item['name'], "qty": missing, "loss": s_loss, "base_sales": item_sales_val})
                
                # Logic for Reordering (Prep vs Shopping)
                if physical_total < item["par_level"]:  
                    shortage = item["par_level"] - physical_total
                    # Check if we have stock in back-rooms before adding to shopping list
                    if (item["walk_in_inv"] + item["freezer_inv"]) >= shortage:
                        audit_results["prep"].append({"name": item['name'], "qty": shortage})
                    else:
                        audit_results["shopping"].append({"name": item['name'], "qty": shortage})

                # UPDATE LOCAL STATE: Reflect the new physical count for the CSV save
                item['line_inv'] = physical_total
                item['walk_in_inv'] = 0 # Assume manager moved all back-stock to line if they did an audit
                item['freezer_inv'] = 0
                break 

            except InventoryError as e:
                print(f"  ❌ {e} Please re-count.") 
        
    # Execute Phase 2: Persist the changes back to the drive
    save_new_inventory_state(inventory)
    # Execute Phase 3: Display results
    print_audit_report(audit_results)
    return audit_results["total_sold_val"]

# =================================================================
# PHASE 3: REPORTING & EXTERNAL LOGGING
# =================================================================

def print_audit_report(results):
    """Generates the terminal UI report and the permanent audit trail."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    file_date = now.strftime("%Y-%m-%d")
    
    # Financial reconciliation
    total_net = results["total_sold_val"]
    potential = total_net + results["total_waste_val"] + results["total_shrink_val"]
    
    # UI Header
    print("\n\n" + "═"*60)
    print(f"{'OFFICIAL SHIFT REVENUE & AUDIT REPORT':^60}")
    print(f"{timestamp:^60}")
    print("═"*60)

    # Main Revenue Table
    print(f"\n[{'FINANCIAL SUMMARY':^25}]")
    print(f"  NET SALES:                      ${total_net:>12.2f}")
    print(f"  WASTE LOSS:                    -${results['total_waste_val']:>12.2f}")
    print(f"  SHRINKAGE LOSS:                -${results['total_shrink_val']:>12.2f}")
    print(f"  POTENTIAL GROSS:                ${potential:>12.2f}")

    # Shrinkage Analysis Table
    print("\n" + "─"*75)
    print(f"{'SHRINKAGE REPORT':<25} | {'QTY':>5} | {'LOSS $':>10} | {'% IMPACT'}")
    print("-" * 75)
    if results["shrinkage"]:
        for s in results["shrinkage"]:
            impact = (s['loss'] / s['base_sales'] * 100) if s['base_sales'] > 0 else 0
            print(f"{s['name']:<25} | {s['qty']:>5} | ${s['loss']:>9.2f} | {impact:>9.1f}%")
    else:
        print("  ✅ NO UNKNOWN LOSS DETECTED.")

    # Permanent Audit Log Persistence
    with open(PathManager.get_path("audit_history.log"), "a", encoding="utf-8") as f:
        # Appends a single line for high-level GM review later
        f.write(f"[{timestamp}] NET: ${total_net:.2f} | SHRINK: ${results['total_shrink_val']:.2f}\n")

    # Smart Shopping List Generation
    if results["shopping"]:
        csv_path = PathManager.get_path(f"shopping_list_{file_date}.csv")
        file_exists = os.path.isfile(csv_path)

        with open(csv_path, "a+", newline="") as f:
            f.seek(0)
            existing = f.read()
            writer = csv.writer(f)
            if not file_exists: writer.writerow(["Item", "Qty"])
            
            for s in results["shopping"]:
                # REGEX Check: Ensure we don't order the same item twice in one night
                if not re.search(f"^{re.escape(s['name'])}", existing, re.MULTILINE):
                    writer.writerow([s['name'], s['qty']]) 
        print(f"\n✅ SHOPPING LIST UPDATED: {csv_path}") 

if __name__ == "__main__":
    try:
        run_inventory_audit()
    except KeyboardInterrupt:
        print("\n\n⚠️  Audit Aborted. System state remains unchanged.")
        sys.exit()