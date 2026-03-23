import csv
import json
import os
from decimal import Decimal
from models import MenuItem, Menu, Staff
import tempfile
import shutil
from datetime import datetime

# Permission Levels: 1=Server, 2=Lead, 3=Manager
ROLE_PERMISSIONS = {
    "MANAGER": 3,
    "LEAD": 2,
    "SERVER": 1,
    "BOH": 1
}

def has_permission(staff: Staff, required_level: int) -> bool:
    """Commit 28: Role-Based Access Control (RBAC) logic."""
    # Assume 'dept' or a new 'role' field maps to our permissions
    user_role = staff.dept.upper() 
    return ROLE_PERMISSIONS.get(user_role, 0) >= required_level

def atomic_save_json(data, filename):
    """
    Commit 26: Prevents file corruption by writing to a temp file 
    and then performing an atomic 'swap'.
    """
    # Create temp file in the same directory
    fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(filename), text=True)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, indent=4)
    
    # Atomic swap: rename temp to original (overwrites existing safely)
    os.replace(temp_path, filename)

def archive_previous_state(filename="restaurant_state.json"):
    """Commit 27: Moves old state to a timestamped backup before reset."""
    if os.path.exists(filename):
        os.makedirs("backups", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        shutil.copy(filename, f"backups/state_backup_{timestamp}.json")
        print(f"📦 Shift archived to backups/state_backup_{timestamp}.json")

def load_menu_from_csv(file_path: str) -> Menu:
    restaurant_menu = Menu()
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # FIXED: Ensure key matches your CSV headers (price vs unit_price)
                # and ensures all fields are passed correctly
                item = MenuItem(
                    category=row['category'],
                    name=row['name'],
                    price=row['price'], 
                    line_inv=row['line_inv'],
                    walk_in=row['walk_in_inv'],
                    freezer=row['freezer_inv'],
                    par=row['par_level']
                )
                restaurant_menu.add_item(item)
    except FileNotFoundError:
        print(f"❌ Error: {file_path} not found.")
    except KeyError as e:
        print(f"❌ CSV Header Error: Missing column {e}")
    return restaurant_menu

def save_system_state(menu, net_sales, filename="restaurant_state.json"):
    """Saves the current sales and inventory breakdown to the 'Shared Brain'."""
    state = {
        "net_sales": float(net_sales),
        "inventory": {item.name: {
            "line": int(item.line_inv),
            "walk_in": int(item.walk_in_inv),
            "freezer": int(item.freezer_inv)
        } for item in menu.items}
    }
    with open(filename, "w") as f:
        json.dump(state, f, indent=4)

def load_system_state(menu, filename="restaurant_state.json"):
    """Loads previous session data into the menu objects."""
    try:
        with open(filename, "r") as f:
            state = json.load(f)
            # Restore inventory counts to objects
            for item in menu.items:
                if item.name in state.get("inventory", {}):
                    inv = state["inventory"][item.name]
                    item.line_inv = inv["line"]
                    item.walk_in_inv = inv["walk_in"]
                    item.freezer_inv = inv["freezer"]
            return Decimal(str(state.get("net_sales", "0.00")))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return Decimal("0.00")

def initialize_system_state(menu):
    """Handles the start-of-shift logic."""
    filename = "restaurant_state.json"
    print("\n" + "="*35)
    print(f"{'SYSTEM INITIALIZATION':^35}")
    print("="*35)
    
    # We ask the user to decide the state of the day
    choice = input("Is this a NEW service day? (yes/no): ").strip().lower()

    if choice == "yes":
        print("☀️  Starting New Service Day. Resetting inventory...")
        # We save the baseline state immediately
        save_system_state(menu, Decimal("0.00"))
        return Decimal("0.00")
    else:
        if os.path.exists(filename):
            print("🌙 Continuing Current Shift...")
            return load_system_state(menu)
        else:
            print("⚠️  No previous state found. Starting fresh.")
            return Decimal("0.00")

def validate_staff_login(staff_id, filename="staff.csv"):
    """Task 5: Look up staff member by ID with error protection."""
    if not os.path.exists(filename):
        print(f"⚠️ Error: {filename} missing.")
        return None
        
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Handle potential whitespace in CSV headers
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        
        for row in reader:
            if row['staff_id'].strip().upper() == staff_id.strip().upper():
                return Staff(row['staff_id'], row['name'], row['dept'])
    return None