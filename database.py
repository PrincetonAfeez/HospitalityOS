"""
HospitalityOS v4.0 - Database & Persistence Layer
Handles CSV loading, state management, and staff authentication.
"""
import csv
import os
import re
from decimal import Decimal
from storage import load_from_json, save_to_json
from datetime import datetime
from models import Menu, MenuItem, Ledger, Staff  # Ensure Ledger is included here
from utils import PathManager

# ==============================================================================
# INTEGRITY & STARTUP
# ==============================================================================

def check_database_integrity():
    """Commit 3: Use PathManager for integrity checks."""
    # Resolve absolute paths for the check
    required_files = [PathManager.get_path("menu.csv"), PathManager.get_path("staff.csv")]
    all_ok = True
    for path in required_files:
        if not os.path.exists(path):
            print(f"CRITICAL ERROR: Required file '{path}' not found.")
            all_ok = False
    return all_ok

# ==============================================================================
# MENU PERSISTENCE
# ==============================================================================

def load_menu_from_csv(filename):
    """
    Commit 2: Refactor to use PathManager for OS-agnostic pathing.
    """
    # Resolve the absolute path using our utility
    path = PathManager.get_path(filename)
    
    menu = Menu()
    # Open using the resolved 'path' variable
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('name', '').strip():
                continue 
            item = MenuItem(
                category=row['category'].strip(),
                name=row['name'].strip(),
                price=row['unit_price'].strip(),
                line_inv=row['line_inv'].strip(),
                walk_in=row['walk_in_inv'].strip(),
                freezer=row['freezer_inv'].strip(),
                par=row['par_level'].strip()
            )
            menu.add_item(item)
    print(f"Menu loaded: {len(menu.items)} items.")
    return menu

# ==============================================================================
# STATE MANAGEMENT
# ==============================================================================

def load_system_state():
    """
    Commit 19 (Refined): Rehydrates Menu, Ledger, and Staff.
    """
    state_path = PathManager.get_path("restaurant_state.json")
    data = load_from_json(state_path)
    
    # Initialize fresh instances in case no file exists
    menu = Menu()
    ledger = Ledger()
    staff_members = [] # Or a StaffManager() if you have one

    if not data:
        print("ℹ️ No previous state found. Starting fresh.")
        return menu, ledger, staff_members

    # 1. Rebuild Menu
    for item_data in data.get("menu_snapshot", []):
        menu.add_item(MenuItem.from_dict(item_data))

    # 2. Rebuild Ledger
    saved_revenue = Decimal(data.get("net_sales", "0.00"))
    saved_count = data.get("transaction_count", 0)
    ledger = Ledger(initial_revenue=saved_revenue, initial_count=saved_count)
    
    # 3. Rebuild Staff (Assuming you have a Staff.from_dict method)
    for staff_data in data.get("staff_snapshot", []):
        # Change 'Staff' to your actual class name if different
        staff_members.append(Staff.from_dict(staff_data))

    print(f"✅ System Restored: {len(staff_members)} staff members synced.")
    return menu, ledger, staff_members


def save_system_state(menu, ledger):
    """
    Commit 13: Uses PathManager and Atomic Save to persist system state.
    Captures a snapshot of inventory and total revenue.
    """
    state_path = PathManager.get_path("restaurant_state.json")
    
    # Create the data payload (The "Snapshot")
    state_data = {
        "net_sales": str(ledger.total_revenue),
        "transaction_count": ledger.transaction_count,
        "menu_snapshot": [item.to_dict() for item in menu.items.values()],
        "last_updated": datetime.now().isoformat()
    }
    
    # Use our Commit 12 Atomic Save
    if save_to_json(state_data, state_path):
        print(f"✔️ System state successfully secured to {state_path}")
    else:
        print("⚠️ Warning: System state could not be saved.")


# ==============================================================================
# AUTHENTICATION
# ==============================================================================

def validate_staff_login(login_id):
    """
    Looks up a staff ID in staff.csv and returns a Staff object if found.
    CSV name format: "Last, First"
    """
    staff_path = PathManager.get_path("staff.csv")
    if not os.path.exists(staff_path):
        print(f"ERROR: {staff_path} not found.")
        return None
    
    with open(staff_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['staff_id'].strip().upper() == login_id.strip().upper():
                # Parse name — accepts "Last, First", "Last,First", or "First Last"
                raw_name = row['name'].strip().strip('"')
                m = re.match(r'^([^,]+),\s*(.+)$', raw_name)
                if m:
                    last_name, first_name = m.group(1).strip(), m.group(2).strip()
                else:
                    parts = raw_name.split()
                    if len(parts) >= 2:
                        first_name, last_name = parts[0], parts[-1]
                        print(f"WARNING: Name '{raw_name}' not in 'Last, First' format; parsed as First='{first_name}' Last='{last_name}'.")
                    else:
                        first_name, last_name = raw_name, "Unknown"
                        print(f"WARNING: Cannot parse name '{raw_name}'; using as first name.")
                return Staff(
                    staff_id=row['staff_id'].strip(),
                    first_name=first_name,
                    last_name=last_name,
                    dept=row['dept'].strip(),
                    role=row['dept'].strip(),
                    hourly_rate=float(row['hourly_rate'].strip())
                )

    print(f"Login failed: ID '{login_id}' not found. Try again.")
    return None
