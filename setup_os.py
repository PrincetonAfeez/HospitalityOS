"""
HospitalityOS v4.0 - Project Environment Setup
Architect: Princeton Afeez
Description: Automates the creation of folders and master CSV databases.
             Run this once before starting main.py for the first time.
"""

import os
import csv
from pathlib import Path

def setup_environment():
    print("🛠️  Initializing HospitalityOS Environment...")

    # 1. Define the Directory Structure
    # We use a nested structure to separate static data from dynamic logs
    folders = [
        "data",               # Master CSVs (Menu/Staff)
        "data/logs",          # Transaction & Shift Logs
        "data/backups",       # Future-proofing for state backups
        "settings"            # System defaults
    ]

    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"✅ Created Directory: /{folder}")

    # 2. Create Master MENU_FILE (data/menu.csv)
    menu_path = Path("data/menu.csv")
    menu_headers = ['category', 'name', 'unit_price', 'line_inv', 'walk_in_inv', 'freezer_inv', 'par_level']
    
    menu_data = [
        ['Mains', 'Classic Burger', '15.50', '20', '50', '100', '15'],
        ['Mains', 'Salmon Pasta', '22.00', '10', '25', '0', '8'],
        ['Drinks', 'Draft Beer', '7.00', '40', '160', '0', '20'],
        ['Drinks', 'Margarita', '12.00', '15', '30', '0', '10'],
        ['Sides', 'Truffle Fries', '8.50', '30', '100', '200', '25']
    ]

    with open(menu_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(menu_headers)
        writer.writerows(menu_data)
    print(f"📝 Generated Master Menu: {menu_path}")

    # 3. Create Master STAFF_FILE (data/staff.csv)
    staff_path = Path("data/staff.csv")
    staff_headers = ['staff_id', 'name', 'dept', 'hourly_rate']
    
    staff_data = [
        ['EMP-01', '"Afeez, Princeton"', 'Manager', '35.00'],
        ['EMP-02', '"Doe, Jane"', 'Server', '18.50'],
        ['EMP-03', '"Smith, John"', 'Server', '18.50']
    ]

    with open(staff_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(staff_headers)
        writer.writerows(staff_data)
    print(f"👥 Generated Staff Database: {staff_path}")

    # 4. Create dummy restaurant_defaults.py if it doesn't exist
    settings_path = Path("settings/restaurant_defaults.py")
    if not settings_path.exists():
        settings_content = (
            "MENU_FILE = 'data/menu.csv'\n"
            "STAFF_FILE = 'data/staff.csv'\n"
        )
        settings_path.write_text(settings_content)
        print(f"⚙️  Generated System Settings: {settings_path}")

    print("\n🚀 Environment Ready! You can now run 'python main.py'.")
    print("💡 Login Hint: Use 'EMP-01' for Manager access.")

if __name__ == "__main__":
    setup_environment()