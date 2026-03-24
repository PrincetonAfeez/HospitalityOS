"""
HospitalityOS v4.0 - System Launcher & Bootloader
Architect: Princeton Afeez
Description: The master entry point. Performs a pre-flight hardware/software 
             check and renders the professional startup UI.
"""

import os
import time
import sys
from datetime import datetime

def render_splash():
    """
    Renders the ASCII Art logo and system versioning. 
    Provides a professional UX for the staff upon opening the terminal.
    """
    os.system('cls' if os.name == 'nt' else 'clear') # Start with a clean slate
    
    # ASCII Art Logo: Designed for a standard 80-character terminal width
    print(r"""
    __  ______  __________  __________  __________    _________  __ 
   / / / / __ \/ ___/ __ \/  _/_  __/ /_  __/ __ \  / ___/ __ \/ / 
  / /_/ / / / /\__ \/ /_/ // /  / /     / / / / / /  \__ \/ / / / /  
 / __  / /_/ /___/ / ____// /  / /     / / / /_/ /  ___/ / /_/ /_/   
/_/ /_/\____//____/_/   /___/ /_/     /_/  \____/  /____/\____/(_)   
                                                                     
    >> RESTAURANT OPERATING SYSTEM [V4.0.26]
    >> ARCHITECT: PRINCETON AFEEZ
    """)
    print("═" * 65)
    # Dynamic timestamping for the boot log
    print(f" SYSTEM BOOT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 65)

def pre_flight_check():
    """
    Verifies that the "Shared Brain" environment is intact.
    Checks for required directories and critical Python modules.
    """
    required_folders = ['data', 'data/logs', 'settings'] # Base architecture
    required_modules = ['models.py', 'hospitality_models.py', 'main.py'] # Core logic
    
    print("🔍 Initializing Pre-Flight Check...")
    time.sleep(0.5) # Slight pause for visual UX feedback

    # 1. Check Directory Structure
    for folder in required_folders:
        if not os.path.exists(folder):
            print(f" ⚠️  ERROR: Missing directory /{folder}")
            return False
        print(f" ✅ Directory /{folder} ... OK")

    # 2. Check Logic Modules
    for module in required_modules:
        if not os.path.isfile(module):
            print(f" ⚠️  ERROR: Missing core module: {module}")
            return False
        print(f" ✅ Module {module:<22} ... OK")

    print("\n🚀 All Systems Nominal. Engaging POS Interface...")
    time.sleep(1) # Allow user to see the success state
    return True

def start_pos():
    """
    Executes the main.py script. This hand-off ensures that if 
    the POS crashes, the launcher can potentially log the error.
    """
    try:
        # Import main inside the function to prevent global scope pollution
        import main
        # Trigger the bootstrap sequence defined in main.py
        active_user, live_menu, live_ledger, live_floor = main.system_bootstrap()
        
        if active_user:
            # Transfer control to the main operating loop
            main.main_loop(active_user, live_menu, live_ledger, live_floor)
        else:
            print("\n👋 System Shutdown: No active user session.")
            
    except Exception as e:
        # Emergency Error Catch: Prevents the terminal from closing instantly on crash
        print(f"\n🛑 CRITICAL SYSTEM FAILURE: {e}")
        input("\nPress Enter to view crash logs and exit...")

# ==============================================================================
# EXECUTION ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    render_splash() # Show the logo
    
    if pre_flight_check():
        start_pos() # Launch the POS
    else:
        # Instructions for the user if the environment is broken
        print("\n❌ SYSTEM HALTED: Environment Incomplete.")
        print("💡 TIP: Run 'python setup_os.py' to repair the directory structure.")
        input("\nPress Enter to close...")