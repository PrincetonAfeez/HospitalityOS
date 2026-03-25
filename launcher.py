"""
HospitalityOS v4.0 - System Launcher & Bootloader
-------------------------------------------------
Splash screen, folder preflight, then hands off to main.system_bootstrap().
Run from the project root so imports like `import main` resolve.
"""

import os
import time
from datetime import datetime

from utils import PathManager, configure_logging, try_configure_utf8_stdout


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
    """Verify critical folders and module files exist under repo root (PathManager)."""
    root = PathManager.BASE_DIR
    required_folders = [root / "data", root / "data" / "logs", root / "settings"]
    required_modules = [root / "models.py", root / "hospitality_models.py", root / "main.py"]

    print("🔍 Initializing Pre-Flight Check...")
    time.sleep(0.5)

    for folder in required_folders:
        if not folder.exists():
            print(f" ⚠️  ERROR: Missing directory {folder.relative_to(root)}")
            return False
        print(f" ✅ Directory {folder.relative_to(root)} ... OK")

    for module in required_modules:
        if not module.is_file():
            print(f" ⚠️  ERROR: Missing core module: {module.name}")
            return False
        print(f" ✅ Module {module.name:<22} ... OK")

    print("\n🚀 All Systems Nominal. Engaging POS Interface...")
    time.sleep(1)
    return True


def start_pos() -> None:
    """Import main lazily so splash + check run before heavy model loading."""
    try:
        import main as pos_main

        session = pos_main.system_bootstrap()
        if session and session.user:
            pos_main.main_loop(session)
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
