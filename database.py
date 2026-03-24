"""
HospitalityOS v4.0 - Database & Persistence Layer
Handles CSV loading, state management, and staff authentication.
"""
import csv
import os
import re
from decimal import Decimal

from models import Menu, MenuItem, Staff
from storage import load_from_json, save_to_json


# ==============================================================================
# INTEGRITY & STARTUP
# ==============================================================================

def check_database_integrity():
    """Verifies required data files exist before allowing system startup."""
    required_files = ["menu.csv", "staff.csv"]
    all_ok = True
    for filename in required_files:
        if not os.path.exists(filename):
            print(f"CRITICAL ERROR: Required file '{filename}' not found.")
            all_ok = False
    if all_ok:
        print("Database integrity check passed.")
    return all_ok


# ==============================================================================
# MENU PERSISTENCE
# ==============================================================================

def load_menu_from_csv(filename):
    """
    Parses menu.csv into a live Menu object containing MenuItem instances.
    Expected columns: category, name, unit_price, line_inv, walk_in_inv, freezer_inv, par_level
    """
    menu = Menu()
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('name', '').strip():
                continue  # Skip blank rows
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
    state = load_from_json("restaurant_state.json")
    if state and float(state.get("net_sales", 0)) > 0:
        ans = input(
            f"Previous shift data found (${float(state['net_sales']):.2f} in sales). "
            f"Resume? (y/n): "
        ).strip().lower()
        if ans in ('y', 'yes'):
            print("Resuming previous shift.")
            return Decimal(str(state['net_sales']))
    print("Starting new shift.")
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
    if not os.path.exists("staff.csv"):
        print("ERROR: staff.csv not found.")
        return None

    with open("staff.csv", newline='', encoding='utf-8') as f:
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
