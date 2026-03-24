"""
HospitalityOS v4.0 - Database & Persistence Layer
Architect: Princeton Afeez
Description: Handles the loading and saving of the 'Shared Brain'. 
             Fully integrated with PathManager for cross-platform stability.
"""

import csv
import json
import os
from decimal import Decimal

# --- INTERNAL MODULE IMPORTS ---
from utils import PathManager
from models import Menu, MenuItem, DailyLedger, Staff

def check_database_integrity():
    """
    Validation: Verifies that core CSV files exist before the system boots.
    Uses PathManager to resolve locations dynamically.
    """
    # Define critical files for a successful boot
    required_files = ["menu.csv", "staff.csv"]
    
    for filename in required_files:
        path = PathManager.get_path(filename)
        if not os.path.exists(path):
            print(f"🛑 CRITICAL ERROR: Missing {filename} at {path}")
            return False
    return True

def load_system_state():
    """
    Hydration: Rebuilds the Menu, Staff, and Ledger objects from disk.
    This is the first logic executed by main.py after login.
    """
    menu = Menu()
    staff_list = []
    
    # 1. Resolve absolute paths using the Smart Router
    menu_path = PathManager.get_path("menu.csv")
    staff_path = PathManager.get_path("staff.csv")
    state_path = PathManager.get_path("restaurant_state.json")

    # 2. Load Master Menu
    try:
        with open(menu_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                item = MenuItem(
                    name=row['name'],
                    price=row['unit_price'],
                    category=row['category'],
                    walk_in=row['walk_in_inv'],
                    freezer=row['freezer_inv'],
                    par_level=row['par_level'],
                    line_inv=row['line_inv']
                )
                menu.add_item(item)
    except Exception as e:
        print(f"⚠️  Menu Load Error: {e}")

    # 3. Load Staff Database
    try:
        with open(staff_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Splitting "Last, First" naming convention for the Person model
                last, first = row['name'].split(', ')
                member = Staff(row['staff_id'], first, last, row['dept'], row['dept'], row['hourly_rate'])
                staff_list.append(member)
    except Exception as e:
        print(f"⚠️  Staff Load Error: {e}")

    # 4. Load Revenue & Inventory State (The Dynamic 'Shared Brain')
    ledger = DailyLedger()
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            state = json.load(f)
            ledger.total_revenue = Decimal(state.get("total_revenue", "0.00"))
            ledger.transaction_count = state.get("transaction_count", 0)
            
            # Restore saved inventory counts to override CSV defaults
            for name, qty in state.get("inventory_snapshot", {}).items():
                item = menu.find_item(name, include_inactive=True)
                if item: item.line_inv = qty

    return menu, ledger, staff_list

def save_system_state(menu, revenue, txn_count):
    """
    Atomic Sync: Saves current memory state to JSON.
    Uses PathManager to ensure it lands in the correct /data/ folder.
    """
    state_path = PathManager.get_path("restaurant_state.json")
    
    # Capture current stock levels across the whole restaurant
    inventory_snapshot = {item.name: item.line_inv for item in menu.items.values()}
    
    state_data = {
        "timestamp": str(os.path.getmtime(PathManager.get_path("menu.csv"))),
        "total_revenue": str(revenue),
        "transaction_count": txn_count,
        "inventory_snapshot": inventory_snapshot
    }
    
    with open(state_path, "w") as f:
        json.dump(state_data, f, indent=4)
    
    print(f"💾 System state synced to: {state_path}")