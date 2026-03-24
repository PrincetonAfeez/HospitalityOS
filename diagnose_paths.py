"""
HospitalityOS v4.0 - Path Diagnostic Utility
Architect: Princeton Afeez
Description: Verifies that the OS can see all critical data files. 
             Checks absolute vs relative path resolution to prevent 'File Not Found' errors.
"""

import os
from pathlib import Path

class PathManager:
    """
    Commit 40: Centralized path resolver to ensure the OS works 
    identically on Windows, Mac, and Linux.
    """
    # Dynamically find the project root folder
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = DATA_DIR / "logs"
    SETTINGS_DIR = BASE_DIR / "settings"

    @classmethod
    def get_path(cls, filename):
        """
        Logic: Routes filenames to their correct sub-directories 
        based on file extension or purpose.
        """
        if filename.endswith(".log"):
            return cls.LOG_DIR / filename
        if filename.endswith(".csv"):
            return cls.DATA_DIR / filename
        if filename.endswith(".json"):
            return cls.DATA_DIR / filename
        if "defaults" in filename:
            return cls.SETTINGS_DIR / filename
        return cls.BASE_DIR / filename

@classmethod
def ensure_directories(cls):
    """Ensures the OS folders exist before the system tries to write to them."""
    for directory in [cls.DATA_DIR, cls.LOG_DIR, cls.SETTINGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

def run_diagnostic():
    """
    Standardizes the verification of the 'Shared Brain' file system.
    """
    print("\n" + "═"*50)
    print(f"║ {'HOSPITALITY OS: PATH DIAGNOSTIC v4.0' :^46} ║")
    print("═"*50)
    
    # 1. Define the 'Vital Signs' (Files the system cannot run without)
    files_to_check = [
        "menu.csv", 
        "staff.csv", 
        "restaurant_state.json", 
        "security.log",
        "restaurant_defaults.py"
    ]
    
    missing_count = 0

    # 2. Iterate and Validate
    for f in files_to_check:
        # Resolve the absolute path
        target_path = PathManager.get_path(f)
        
        # Check physical existence on the storage drive
        exists = os.path.exists(target_path)
        status_icon = "✅ FOUND" if exists else "❌ MISSING"
        
        if not exists:
            missing_count += 1

        print(f"FILE   : {f}")
        print(f"PATH   : {target_path}")
        print(f"STATUS : {status_icon}\n")

    # 3. System Directory Overview
    print("-" * 50)
    print(f"ROOT DIR : {PathManager.BASE_DIR}")
    print(f"DATA DIR : {PathManager.DATA_DIR}")
    print(f"LOGS DIR : {PathManager.LOG_DIR}")
    print("-" * 50)

    # 4. Final Verdict
    if missing_count == 0:
        print("\n✨ SYSTEM HEALTH: OPTIMAL. All paths resolved.")
    else:
        print(f"\n⚠️  SYSTEM HEALTH: DEGRADED. {missing_count} file(s) unreachable.")
        print("💡 TIP: Run 'python setup_os.py' to restore missing files.")
    print("═"*50 + "\n")

if __name__ == "__main__":
    run_diagnostic()