"""
HospitalityOS v4.0 - Project Environment Setup
Creates folders, seed CSVs, manager_auth.json, and optionally seeds settings.

Never overwrites settings/restaurant_defaults.py if it already exists (single source of truth).
Use restaurant_defaults.example.py as the template for new environments.
"""

import csv
import json
import shutil
from pathlib import Path

# Repo root = directory containing this script
ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / "settings"
DATA = ROOT / "data"
LOGS = DATA / "logs"
BACKUPS = DATA / "backups"


def setup_environment() -> None:
    print("[*] Initializing HospitalityOS v4.0 environment...")

    for folder in (DATA, LOGS, BACKUPS, SETTINGS):
        folder.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] Directory: {folder.relative_to(ROOT)}")

    menu_path = DATA / "menu.csv"
    menu_headers = ["category", "name", "unit_price", "line_inv", "walk_in_inv", "freezer_inv", "par_level"]
    menu_data = [
        ["Mains", "Classic Burger", "15.50", "20", "50", "100", "15"],
        ["Mains", "Salmon Pasta", "22.00", "10", "25", "0", "8"],
        ["Drinks", "Draft Beer", "7.00", "40", "160", "0", "20"],
        ["Drinks", "Margarita", "12.00", "15", "30", "0", "10"],
        ["Sides", "Truffle Fries", "8.50", "30", "100", "200", "25"],
    ]
    with open(menu_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(menu_headers)
        w.writerows(menu_data)
    print(f"  [OK] Menu: {menu_path.relative_to(ROOT)}")

    staff_path = DATA / "staff.csv"
    staff_headers = ["staff_id", "name", "dept", "hourly_rate"]
    # Rates at/above MIN_WAGE when using default Decimal MIN_WAGE (see restaurant_defaults.py)
    staff_data = [
        ["EMP-01", "Afeez, Princeton", "Manager", "35.00"],
        ["EMP-02", "Doe, Jane", "Server", "20.00"],
        ["EMP-03", "Smith, John", "Server", "20.00"],
    ]
    with open(staff_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(staff_headers)
        w.writerows(staff_data)
    print(f"  [OK] Staff: {staff_path.relative_to(ROOT)}")

    example = SETTINGS / "restaurant_defaults.example.py"
    print(f"  [OK] Settings template: {example.relative_to(ROOT)}")

    defaults = SETTINGS / "restaurant_defaults.py"
    if not defaults.exists():
        shutil.copy(example, defaults)
        print(f"  [OK] Created {defaults.name} from example (first run only).")
    else:
        print(f"  [*] Kept existing {defaults.name} (not overwritten).")

    auth_path = SETTINGS / "manager_auth.json"
    if not auth_path.exists():
        auth_path.write_text(
            json.dumps(
                {
                    "override_pin": "5555",
                    "pins": {},
                    "_comment": "Optional per-staff PINs: {\"EMP-M01\": \"secret\"}. Values may use sha256:hexdigest.",
                    "note": "Demo only — change PIN and use verify_manager in production.",
                },
                indent=4,
            ),
            encoding="utf-8",
        )
        print(f"  [OK] Created {auth_path.relative_to(ROOT)}")
    else:
        print(f"  [*] Kept existing manager_auth.json")

    log_path = LOGS / "security.log"
    if not log_path.exists():
        log_path.write_text("--- HOSPITALITY OS SECURITY LOG ---\n", encoding="utf-8")
    print(f"  [OK] Security log ready: {log_path.relative_to(ROOT)}")

    print("\n[OK] Environment ready. Run: python launcher.py")


if __name__ == "__main__":
    setup_environment()
