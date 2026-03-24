"""
HospitalityOS v4.0 - System Launcher & Bootloader
-------------------------------------------------
Splash screen, folder preflight, then hands off to main.system_bootstrap().
Run from the project root so imports like `import main` resolve.
"""

import os
import time
from datetime import datetime

from utils import configure_logging, try_configure_utf8_stdout


def render_splash() -> None:
    """Print ASCII banner + boot timestamp for front-of-house polish."""
    os.system("cls" if os.name == "nt" else "clear")
    print(
        r"""
    __  ______  __________  __________  __________    _________  __ 
   / / / / __ \/ ___/ __ \/  _/_  __/ /_  __/ __ \  / ___/ __ \/ / 
  / /_/ / / / /\__ \/ /_/ // /  / /     / / / / / /  \__ \/ / / / /  
 / __  / /_/ /___/ / ____// /  / /     / / / /_/ /  ___/ / /_/ /_/   
/_/ /_/\____//____/_/   /___/ /_/     /_/  \____/  /____/\____/(_)   
                                                                     
    >> RESTAURANT OPERATING SYSTEM [V4.0.26]
    >> ARCHITECT: PRINCETON AFEEZ
    """
    )
    print("═" * 65)
    print(f" SYSTEM BOOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65)


def pre_flight_check() -> bool:
    """Verify critical folders and module files exist beside this script."""
    required_folders = ["data", "data/logs", "settings"]
    required_modules = ["models.py", "hospitality_models.py", "main.py"]

    print("🔍 Initializing Pre-Flight Check...")
    time.sleep(0.5)

    for folder in required_folders:
        if not os.path.exists(folder):
            print(f" ⚠️  ERROR: Missing directory /{folder}")
            return False
        print(f" ✅ Directory /{folder} ... OK")

    for module in required_modules:
        if not os.path.isfile(module):
            print(f" ⚠️  ERROR: Missing core module: {module}")
            return False
        print(f" ✅ Module {module:<22} ... OK")

    print("\n🚀 All Systems Nominal. Engaging POS Interface...")
    time.sleep(1)
    return True


def start_pos() -> None:
    """Import main lazily so splash + check run before heavy model loading."""
    try:
        import main as pos_main

        active_user, menu, ledger, floor = pos_main.system_bootstrap()
        if active_user:
            pos_main.main_loop(active_user, menu, ledger, floor)
        else:
            print("\n👋 System Shutdown: No active user session.")
    except Exception as exc:
        print(f"\n🛑 CRITICAL SYSTEM FAILURE: {exc}")
        input("\nPress Enter to view crash logs and exit...")


if __name__ == "__main__":
    configure_logging()
    try_configure_utf8_stdout()
    render_splash()
    if pre_flight_check():
        start_pos()
    else:
        print("\n❌ SYSTEM HALTED: Environment Incomplete.")
        print("💡 TIP: Run 'python setup_os.py' to repair the directory structure.")
        input("\nPress Enter to close...")
