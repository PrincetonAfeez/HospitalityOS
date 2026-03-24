"""
HospitalityOS v4.0 - Database & Persistence Layer
Handles CSV loading, state management, and staff authentication.
"""
import csv
import os
import re
from decimal import Decimal

# Import the new utility
from utils import PathManager 
from models import Menu, MenuItem, Staff
from storage import load_from_json, save_to_json

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

def initialize_system_state(menu):
    """
    Handles 'New Day' vs 'Continue Shift' logic.
    Returns the starting revenue figure as a Decimal.
    """
    state_path = PathManager.get_path("restaurant_state.json")
    state = load_from_json(state_path)
    
    if state:
        # Sync Inventory Snapshot to the Live Menu
        inventory_snapshot = state.get("menu_snapshot", [])
        for saved_item in inventory_snapshot:
            # Using our new Commit 5 fuzzy lookup
            live_item = menu.find_item(saved_item.get("name"))
            if live_item:
                live_item.line_inv = int(saved_item.get("line_inv", live_item.line_inv))

        # Check for resuming sales
        net_sales = state.get("net_sales", 0)
        if float(net_sales) > 0:
            ans = input(f"Resume previous shift with ${float(net_sales):.2f} in sales? (y/n): ").strip().lower()
            if ans in ('y', 'yes'):
                return Decimal(str(net_sales))
                
    print("Starting new shift with fresh ledger.")
    return Decimal("0.00")


def save_system_state(menu, revenue):
    """
    Writes current revenue to restaurant_state.json and persists live inventory
    levels back to menu.csv so stock changes survive a restart.
    """
    state = {
        "net_sales": float(revenue),
        "menu_snapshot": [item.to_dict() for item in menu.items]
    }
    save_to_json(state, "restaurant_state.json")

    # Build an index of live inventory by item name for fast lookup
    inv_index = {item.name: item.line_inv for item in menu.items}

    # Read current CSV, update line_inv for each row, write back
    try:
        rows = []
        fieldnames = None
        with open("menu.csv", newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                name = row.get('name', '').strip()
                if name in inv_index:
                    row['line_inv'] = str(inv_index[name])
                rows.append(row)

        with open("menu.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except OSError as e:
        print(f"WARNING: Could not persist inventory to menu.csv: {e}")


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
