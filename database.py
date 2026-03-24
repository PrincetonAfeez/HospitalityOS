"""
HospitalityOS v4.0 - Database & Persistence Layer
Refactored: Monday Master Edition (March 2026)
Architect: Princeton Afeez
Description: Handles the complex 'Shared Brain' merge between static CSV 
             structures and live JSON snapshots.
"""

import csv
import os
import re
import sys
from decimal import Decimal
from datetime import datetime

# Internal System Imports
from storage import load_from_json, save_to_json
from models import Menu, MenuItem, Ledger, Staff
from utils import PathManager
from settings.restaurant_defaults import MENU_FILE, STAFF_FILE

# ==============================================================================
# INTEGRITY & STARTUP
# ==============================================================================

def check_database_integrity():
    """
    Commit 3: Use PathManager for OS-agnostic integrity checks.
    Ensures the system doesn't boot if essential data is missing.
    """
    # Resolve absolute paths for the required flat-file databases
    required_files = [
        PathManager.get_path(MENU_FILE), 
        PathManager.get_path(STAFF_FILE)
    ]
    
    all_ok = True
    for path in required_files:
        # Check if the file physically exists on the disk
        if not os.path.exists(path):
            print(f"🛑 CRITICAL ERROR: Required file '{path}' not found.")
            all_ok = False
            
    return all_ok

# ==============================================================================
# MENU PERSISTENCE (CSV LOADER)
# ==============================================================================

def load_menu_from_csv(filename):
    """
    Commit 2: Refactored with PathManager.
    Loads the 'True North' structure of the menu from the CSV master file.
    """
    # Use PathManager to ensure we are looking in the /data directory
    path = PathManager.get_path(filename)
    
    # Initialize a fresh Menu container object
    new_menu = Menu()
    
    try:
        # Open the CSV with UTF-8 encoding for special character support (e.g., Poké)
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows or rows without a primary item name
                if not row.get('name', '').strip():
                    continue 
                
                # Create a MenuItem instance from the CSV row data
                # Note: par_level and line_inv are cast to int for math safety
                item = MenuItem(
                    category=row['category'].strip(),
                    name=row['name'].strip(),
                    price=row['unit_price'].strip(),
                    line_inv=row['line_inv'].strip(),
                    walk_in_inv=row['walk_in_inv'].strip(),
                    freezer_inv=row['freezer_inv'].strip(),
                    par_level=row['par_level'].strip()
                )
                # Add the finalized item to the Menu's internal dictionary
                new_menu.add_item(item)
                
        print(f"📖 Menu Template Loaded: {len(new_menu.items)} items identified.")
        return new_menu
        
    except FileNotFoundError:
        print(f"❌ Error: {filename} was not found at {path}.")
        sys.exit(1) # Hard exit if we cannot load a menu

# ==============================================================================
# STATE MANAGEMENT (THE SHARED BRAIN MERGE)
# ==============================================================================

def load_system_state():
    """
    Commit 19 (Refined): Rehydrates Menu, Ledger, and Staff.
    Logic: Uses CSV for 'Structure' and JSON for 'Live Counts'.
    """
    # 1. Initialize the base 'Template' from the master CSV file
    menu = load_menu_from_csv(MENU_FILE)
    
    # 2. Attempt to load the 'Live Data' snapshot from the JSON Shared Brain
    state_path = PathManager.get_path("restaurant_state.json")
    data = load_from_json(state_path) # 'data' represents the raw JSON file
    
    # Defaults for fresh sessions
    ledger = Ledger()
    staff_members = []

    # If no JSON exists (e.g., first run of the day), return the CSV defaults
    if not data:
        print("ℹ️ No previous state found. Starting fresh from CSV defaults.")
        return menu, ledger, staff_members

    # 3. REBUILD MENU (The Merge Logic)
    # We extract the menu subset (live_data) from the larger state file
    live_data = data.get("menu_snapshot", {})
    
    for name, item in menu.items.items():
        # If the item from the CSV exists in the JSON snapshot...
        if name in live_data:
            # Overwrite the static CSV inventory with the live POS inventory
            saved_item_data = live_data[name]
            item.line_inv = int(saved_item_data.get("line_inv", item.line_inv))
            # Note: We do NOT overwrite price here, allowing CSV updates to take effect
    
    # Perform a health check on the merged counts
    menu.validate_integrity()
    
    # 4. REBUILD LEDGER (Financial Sync)
    # Convert string-based revenue back to Decimal for high-precision math
    saved_revenue = Decimal(str(data.get("net_sales", "0.00")))
    saved_count = data.get("transaction_count", 0)
    ledger = Ledger(initial_revenue=saved_revenue, initial_count=saved_count)
    
    # 5. REBUILD STAFF (Personnel Sync)
    # Re-instantiate staff objects from the JSON snapshot
    for staff_data in data.get("staff_snapshot", []):
        staff_members.append(Staff.from_dict(staff_data))

    print(f"✅ System Restored: {len(staff_members)} staff synced | Sales: ${ledger.total_revenue}")
    return menu, ledger, staff_members


def save_system_state(menu, ledger_revenue, transaction_count=0):
    """
    Commit 13: Uses PathManager and Atomic Save to persist system state.
    Captures a snapshot of current inventory and financials.
    """
    # Resolve the destination path via PathManager
    state_path = PathManager.get_path("restaurant_state.json")
    
    # Create the data payload (The "Snapshot")
    # item.to_dict() ensures we are saving raw data, not complex objects
    state_data = {
        "net_sales": str(ledger_revenue),
        "transaction_count": transaction_count,
        "menu_snapshot": {name: item.to_dict() for name, item in menu.items.items()},
        "last_updated": datetime.now().isoformat()
    }
    
    # Trigger the Atomic Save (Temp file -> OS Replace)
    if save_to_json(state_data, state_path):
        print(f"💾 Atomic Sync: State secured to {state_path}")
    else:
        print("⚠️ Warning: System state could not be saved to disk.")


# ==============================================================================
# AUTHENTICATION (STAFF ROSTER)
# ==============================================================================

def validate_staff_login(login_id):
    """
    Looks up a staff ID in staff.csv and returns a Staff object if found.
    Refactored to support complex name formatting and Decimal rates.
    """
    # Find the staff master list via PathManager
    staff_path = PathManager.get_path(STAFF_FILE)
    
    if not os.path.exists(staff_path):
        print(f"🛑 ERROR: Staff database ({staff_path}) missing.")
        return None
    
    with open(staff_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Case-insensitive comparison of the Staff ID
            if row['staff_id'].strip().upper() == login_id.strip().upper():
                
                # Parse the raw name string from the CSV
                raw_name = row['name'].strip().strip('"')
                
                # Regex to handle 'Last, First' standard formatting
                m = re.match(r'^([^,]+),\s*(.+)$', raw_name)
                if m:
                    last_name, first_name = m.group(1).strip(), m.group(2).strip()
                else:
                    # Fallback for 'First Last' or single-name entries
                    parts = raw_name.split()
                    if len(parts) >= 2:
                        first_name, last_name = parts[0], parts[-1]
                    else:
                        first_name, last_name = raw_name, "Unknown"

                # Return a live Staff object populated with the CSV data
                return Staff(
                    staff_id=row['staff_id'].strip(),
                    first_name=first_name,
                    last_name=last_name,
                    dept=row['dept'].strip(),
                    role=row['dept'].strip(),
                    # Use Decimal for the hourly rate to ensure payroll precision
                    hourly_rate=Decimal(row['hourly_rate'].strip())
                )

    # If no match is found after scanning the entire file
    print(f"❌ Login Denied: ID '{login_id}' not recognized.")
    return None