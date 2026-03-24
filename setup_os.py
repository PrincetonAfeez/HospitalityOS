"""
HospitalityOS v4.0 - Project Environment Setup
Architect: Princeton Afeez
Description: Automates the creation of folders, master CSV databases, and 
             global configuration constants. 
"""

import os
import csv
from pathlib import Path

def setup_environment():
    """
    Scaffolds the directory structure and populates initial data for 
    a 'Ready-to-Run' state.
    """
    print("🛠️  Initializing HospitalityOS v4.0 Environment...")

    # 1. Define the Directory Structure
    # Added 'data/logs' specifically for Z-Reports and forensic audits
    folders = [
        "data",               # Master CSVs (Menu/Staff)
        "data/logs",          # Transaction & Shift Logs
        "data/backups",       # State recovery
        "settings"            # System configuration
    ]

    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"✅ Created Directory: /{folder}")

    # 2. Create Master MENU_FILE (data/menu.csv)
    # Note: These columns must match the logic in database.py
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
    # Format: Last Name, First Name (used by our Person class parser)
    staff_path = Path("data/staff.csv")
    staff_headers = ['staff_id', 'name', 'dept', 'hourly_rate']
    
    staff_data = [
        ['EMP-01', 'Afeez, Princeton', 'Manager', '35.00'],
        ['EMP-02', 'Doe, Jane', 'Server', '18.50'],
        ['EMP-03', 'Smith, John', 'Server', '18.50']
    ]

    with open(staff_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(staff_headers)
        writer.writerows(staff_data)
    print(f"👥 Generated Staff Database: {staff_path}")

    # 4. Generate restaurant_defaults.py (System Brain)
    # This ensures models.py doesn't crash on import
    settings_path = Path("settings/restaurant_defaults.py")
    settings_content = (
        "import os\n\n"
        "# --- Financial Defaults ---\n"
        "TAX_RATE = 0.0825         # 8.25% Sales Tax\n"
        "GRATUITY_RATE = 0.18      # 18% Auto-Gratuity\n"
        "GRATUITY_THRESHOLD = 6    # Party size for Auto-Grat\n\n"
        "# --- Labor & Operations ---\n"
        "MIN_WAGE = 15.50          # Local standard\n"
        "MAX_MODS = 3              # Max modifiers per item\n\n"
        "# --- File Paths ---\n"
        "MENU_FILE = 'data/menu.csv'\n"
        "STAFF_FILE = 'data/staff.csv'\n"
    )
    settings_path.write_text(settings_content)
    print(f"⚙️  Generated System Settings: {settings_path}")

    # 5. Initialize Security Log (Objective 4 Compliance)
    log_path = Path("data/logs/security.log")
    if not log_path.exists():
        with open(log_path, "w") as f:
            f.write("--- HOSPITALITY OS V4.0 SECURITY LOG INITIALIZED ---\n")
        print(f"🔒 Security Audit Trail Created: {log_path}")

    print("\n🚀 Environment v4.0 Ready!")
    print("💡 Launch Step: Run 'python launcher.py' to begin operations.")

if __name__ == "__main__":
    setup_environment()