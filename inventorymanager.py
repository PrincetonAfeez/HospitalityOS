"""
HospitalityOS v4.0 - Nightly Inventory & Shrinkage Auditor
Architect: Princeton Afeez
Description: Automatically bridges POS sales with Physical counts. 
             Detects theft (shrinkage), manages prep levels, and 
             generates duplicate-proof shopping lists.
"""

import csv        # Standard library for reading/writing menu.csv
import sys        # Used for safe system exits during critical errors
import json       # Used to parse the POS 'Shared Brain' (restaurant_state.json)
import os         # Handles file existence checks and directory lookups
# Use re for the 'Laser Eye' Regex to prevent duplicate shopping entries
import re         
from datetime import datetime # Timestamping for audit logs and CSV naming
from decimal import Decimal   # Critical for financial precision (avoids float errors)

# --- INTERNAL MODULE IMPORTS ---
from utils import PathManager, print_divider # Handles cross-platform paths and UI
from validator import get_int                 # Ensures manager input is numeric

# =================================================================
# PHASE 1: CUSTOM EXCEPTIONS & DATA LOADING
# =================================================================

class InventoryError(Exception):
    """Custom exception class to handle business-logic errors during inventory counts."""
    # This inherits from the base Exception class to stop logic when counts are impossible
    pass 

def load_inventory_from_menu():
    """Reads the master inventory data, prices, and par levels from menu.csv."""
    # Use the PathManager to find the absolute path regardless of OS
    full_path = PathManager.get_path("menu.csv")
    
    # Initialize an empty list to store dictionary objects for each menu item
    inventory_list = []  
    
    try:
        # Open the CSV file in read mode with UTF-8 encoding to prevent character errors
        with open(full_path, mode="r", newline="", encoding="utf-8") as file:
            # Create a reader that maps the header row (name, unit_price, etc.) to keys
            reader = csv.DictReader(file)  
          
            for row in reader:  # Iterate through every row (item) in the spreadsheet
                # Convert string-based CSV data into numeric types for calculations
                row["unit_price"] = Decimal(str(row["unit_price"]))  # Precision for money
                row["line_inv"] = int(row["line_inv"])        # Current line stock
                row["walk_in_inv"] = int(row["walk_in_inv"])  # Secondary storage stock
                row["freezer_inv"] = int(row["freezer_inv"])  # Frozen storage stock
                row["par_level"] = int(row["par_level"])      # The 'Safety' threshold
                
                # FEATURE 6: Pre-calculate total building stock available at shift start
                # Summing all three storage locations into one 'Starting' value
                row["starting_inv"] = row["line_inv"] + row["walk_in_inv"] + row["freezer_inv"]
                inventory_list.append(row)  # Append the processed item to our list
        return inventory_list  # Return the list of items for the audit loop
    except FileNotFoundError:  # Handle the error if the menu.csv file is missing
        print(f"❌ Error: {full_path} not found. Run setup_os.py.")
        sys.exit()  # Terminate the program safely to avoid a crash

def load_sales_data():
    """Loads POS state and builds an inventory dict from the Shared Brain."""
    # Locate the restaurant_state.json file via PathManager
    filename = PathManager.get_path("restaurant_state.json")
    
    try:
        with open(filename, "r") as f:
            # Parse the JSON file into a Python dictionary
            data = json.load(f)
            
        # Build the {name: current_qty} dict from the 'inventory_snapshot' key
        # This allows the audit loop to quickly look up items by their name
        inventory_map = data.get("inventory_snapshot", {})
        return inventory_map
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback: If POS never ran today, return an empty map
        return {}

# =================================================================
# PHASE 2: PROCESSING (THE "INPUT" LOOP)
# =================================================================

def run_inventory_audit():
    """Main logic loop for manager data entry, validation, and math processing."""
    # Load the static menu data and the dynamic POS sales data
    inventory = load_inventory_from_menu()  
    shared_brain_inv = load_sales_data()        
    
    # Storage container dictionary to collect data for the final reporting function
    audit_results = {
        "shrinkage": [],    # Items where units went missing mysteriously
        "waste": [],        # Items recorded as waste/comps by the manager
        "prep": [],         # Items requiring a pull from walk-in/freezer
        "shopping": [],     # Items that must be purchased from vendors
        "total_sold_val": Decimal("0.00"),  # Accumulator for net revenue
        "total_waste_val": Decimal("0.00"), # Financial loss due to recorded waste
        "total_shrink_val": Decimal("0.00") # Financial loss due to unrecorded shrinkage
    }

    # Render the Professional UX Header
    print("\n" + "═"*60)
    print(f"{'HOSPITALITY OS: NIGHTLY MANAGER AUDIT':^60}")
    print("═"*60)

    for item in inventory:  # Process every menu item found in the CSV
        print(f"\n📝 RECORDING: {item['name'].upper()}")  # Visual separator per item
        
        # SYNC LOGIC: Compare CSV starting count vs POS ending count
        # Formula: Starting line count - Current POS snapshot = Units Sold
        # If the item isn't in the POS yet, we default to the starting line count
        pos_inventory_remaining = shared_brain_inv.get(item['name'], item['line_inv'])
        pos_sold_calculated = item['line_inv'] - pos_inventory_remaining
        
        # UX: Provide a 'Hint' to the manager based on POS activity
        if pos_sold_calculated > 0:
            print(f"  [ 💡 POS reports {pos_sold_calculated} units sold today ]")
        
        print(f"  [ 📦 Morning Start (Total Building): {item['starting_inv']} ]")

        # FEATURE 1: Loop for current item until data entry passes all logical checks
        while True: 
            try:
                # FEATURE 2 & 4: Safe numeric input using our central validator
                sold = get_int(f"  Units SOLD (Confirm POS {pos_sold_calculated}): ", min_val=0)
                waste = get_int(f"  Units WASTED/COMPED: ", min_val=0)
                physical = get_int(f"  FINAL PHYSICAL COUNT (Total): ", min_val=0)

                # FEATURE 3: FAT FINGER GUARDRAIL - Verification prompt for high numbers
                # Helps prevent accidentally typing '200' instead of '20'
                if sold > 100 or waste > 100 or physical > 100:
                    confirm = input(f"  ⚠️  {max(sold, waste, physical)} seems unusually high. Confirm? (y/n): ").lower()
                    if confirm != 'y': continue  # Restart the loop for this specific item

                # FEATURE 6: IMPOSSIBLE COUNT EXCEPTION
                # Logic: You cannot sell/waste/have more than the starting inventory
                if (sold + waste + physical) > item['starting_inv']:
                    # Trigger custom exception to force re-entry
                    raise InventoryError(f"Math Error: Only started with {item['starting_inv']} {item['name']}.")
                
                # FEATURE 5: FINANCIAL MATH - Calculate dollar value of sold units
                item_sales_val = sold * item["unit_price"]
                audit_results["total_sold_val"] += item_sales_val  # Add to shift net revenue
                
                # WASTE TRACKING: Process items intentionally removed (e.g., dropped on floor)
                if waste > 0:
                    waste_loss = waste * item["unit_price"]
                    audit_results["total_waste_val"] += waste_loss # Track the 'Known' loss
                    # Log details for the final report table
                    audit_results["waste"].append({
                        "name": item['name'], "qty": waste, 
                        "loss": waste_loss, "base_sales": item_sales_val
                    })

                # SHRINKAGE MATH: Detect 'Unknown' inventory loss (Theft or unrecorded waste)
                # Expected = What started - (What sold + What was wasted)
                expected = item["starting_inv"] - sold - waste  
                if physical < expected:  # If reality is less than what the math says...
                    missing = expected - physical  # Calculate the gap (the shrinkage)
                    shrink_loss = missing * item["unit_price"]  # Value of missing goods
                    audit_results["total_shrink_val"] += shrink_loss  # Track the 'Unknown' loss
                    # Log details for the final report table
                    audit_results["shrinkage"].append({
                        "name": item['name'], "qty": missing, 
                        "loss": shrink_loss, "base_sales": item_sales_val
                    })
                
                # FEATURE 7: PREP vs SHOPPING LOGIC
                # Logic: If physical count < Par, we need to restock
                if physical < item["par_level"]:  
                    shortage = item["par_level"] - physical  # Units needed to reach safety
                    
                    # PREP: If walk-in or freezer has enough, it's an internal move
                    if (item["walk_in_inv"] + item["freezer_inv"]) >= shortage:
                        audit_results["prep"].append({"name": item['name'], "qty": shortage})
                    # SHOPPING: If the building is empty, we must order from a vendor
                    else:
                        audit_results["shopping"].append({"name": item['name'], "qty": shortage})

                break  # Exit the 'while' loop; input is validated and math is complete
            except InventoryError as e:  # Catch the custom exception
                print(f"  ❌ {e} Please re-verify the numbers.") 
        
    # Hand off the final collected results to the modular Reporting function
    print_audit_report(audit_results)
    return audit_results["total_sold_val"]

# =================================================================
# PHASE 3: REPORTING (THE "OUTPUT")
# =================================================================

def print_audit_report(results):
    """Handles the UI display, permanent history logging, and CSV list generation."""
    now = datetime.now()  # Capture current date/time
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")  # For the log file
    file_date = now.strftime("%Y-%m-%d")           # For the shopping CSV
    
    # Resolve the log path via PathManager
    history_log = PathManager.get_path("audit_history.log")

    # FINANCIAL SUMMARY CALCULATIONS
    total_net = results["total_sold_val"]
    # Potential Revenue = Net Sales + Money lost to Waste + Money lost to Shrink
    potential = total_net + results["total_waste_val"] + results["total_shrink_val"]
    
    # Output the primary financial table to the terminal
    print("\n\n" + "═"*60)
    print(f"{'OFFICIAL AUDIT & REVENUE REPORT':^60}")
    print(f"{timestamp:^60}")
    print("═"*60)

    print(f"\n[{'SHIFT REVENUE SUMMARY':^25}]")
    print(f"  TOTAL NET SALES (SOLD):         ${total_net:>12.2f}")
    print(f"  TOTAL WASTE VALUE:              ${results['total_waste_val']:>12.2f}")
    print(f"  TOTAL SHRINKAGE LOSS:           ${results['total_shrink_val']:>12.2f}")
    print(f"  TOTAL POTENTIAL REVENUE:        ${potential:>12.2f}")

    # Display the Shrinkage Breakdown table (Feature 5 & 6)
    print("\n" + "─"*75)
    print(f"{'SHRINKAGE (UNKNOWN LOSS)':<25} | {'QTY':>5} | {'LOSS $':>10} | {'% IMPACT'}")
    print("-" * 75)
    if results["shrinkage"]:
        for s in results["shrinkage"]:
            # Calculate % impact relative to actual item sales
            s_pct = (s['loss'] / s['base_sales'] * 100) if s['base_sales'] > 0 else 100.0
            print(f"{s['name']:<25} | {s['qty']:>5} | ${s['loss']:>9.2f} | {s_pct:>9.1f}%")
    else:
        print("  ✅ EXCELLENT: No shrinkage detected this shift.")

    # Display the Waste/Comp Log table (Feature 6)
    print("\n" + "─"*75)
    print(f"{'WASTE & COMPS (KNOWN LOSS)':<25} | {'QTY':>5} | {'LOSS $':>10} | {'% IMPACT'}")
    print("-" * 75)
    if results["waste"]:
        for w in results["waste"]:
            w_pct = (w['loss'] / w['base_sales'] * 100) if w['base_sales'] > 0 else 100.0
            print(f"{w['name']:<25} | {w['qty']:>5} | ${w['loss']:>9.2f} | {w_pct:>9.1f}%")
    else:
        print("  ✅ No waste recorded this shift.")

    # Display the Kitchen Prep List (Internal Stock Pulls)
    print("\n" + "─"*45)
    print(f"{'KITCHEN PREP LIST (RESTOCK)':<30} | {'QTY':>5}")
    print("-" * 45)
    if results["prep"]:
        for p in results["prep"]: print(f"{p['name']:<30} | {p['qty']:>5}")
    else:
        print("  ✅ All line levels are sufficient.")

    # PERMANENT LOGGING: Append the summary to audit_history.log
    with open(history_log, "a", encoding="utf-8") as f:
        # Append mode ensures we keep a multi-year audit trail
        f.write(f"[{timestamp}] NET: ${total_net:.2f} | WASTE: ${results['total_waste_val']:.2f} | SHRINK: ${results['total_shrink_val']:.2f}\n")

    # FEATURE 7: Generate a unique CSV Shopping List (The 'Smart Logger')
    if results["shopping"]:
        csv_name = f"shopping_list_{file_date}.csv"
        csv_path = PathManager.get_path(csv_name)
        
        file_exists = os.path.isfile(csv_path)

        # Use 'a+' (Append + Read) to check for duplicates before writing
        with open(csv_path, "a+", newline="") as f:
            f.seek(0)  # Reset pointer to start of file to read existing entries
            existing_content = f.read()
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow(["Item", "Qty to Order"]) # Write header for new files
            
            for s in results["shopping"]:
                # REGEX: Search for the item name at the start of any line
                # This ensures we don't list 'Margarita' twice in the same day
                if not re.search(f"^{re.escape(s['name'])}", existing_content, re.MULTILINE):
                    writer.writerow([s['name'], s['qty']]) 
                else:
                    print(f"  ⏭️  SmartSync: {s['name']} already on today's order. Skipping duplicate.")
                    
        print(f"\n✅ REORDER LIST READY: {csv_path}") 

# Standard execution block
if __name__ == "__main__":
    try:
        run_inventory_audit()
    except KeyboardInterrupt:
        # Safe exit if the manager hits Ctrl+C
        print("\n\n⚠️  Audit Interrupted by User. No data saved.")
        sys.exit()