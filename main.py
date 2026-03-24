"""
HospitalityOS v4.0 - Master Orchestrator
Architect: Princeton Afeez
Description: The primary execution loop. Coordinates between the financial 
             engine (models.py) and the physical floor state (hospitality_models.py).
"""

import sys
import os
import atexit
import time
from datetime import datetime
from decimal import Decimal
import digitalfrontdesk
import laborcostauditor

# --- INTERNAL MODULE IMPORTS ---
# database.py handles CSV/JSON disk I/O
from database import (
    load_system_state, 
    save_system_state, 
    validate_staff_login,
    check_database_integrity
)
# validator.py ensures all user input is sanitized and typed
from validator import (
    get_int, get_name, get_yes_no, get_staff_id, 
    get_decimal_input, format_currency
)
# models.py contains the 'Financial Brain'
from models import (
    Cart, Transaction, Staff, MenuItem, 
    SecurityLog, DailyLedger
)
# hospitality_models.py contains the 'Physical Floor'
from hospitality_models import (
    FloorMap, Table, Guest, WaitlistManager
)

# ==============================================================================
# UI TERMINAL UTILITIES
# ==============================================================================

def clear_screen():
    """Wipes the terminal clean for a fresh UI draw; handles both Windows and Unix."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_table_header(table_num, cart):
    """Renders the active 'Heads-Up Display' (HUD) for a specific table session."""
    print("\n" + "═" * 45)
    print(f"║ {'TABLE ' + str(table_num) + ' SESSION' :^41} ║")
    print("═" * 45)
    # Displays real-time item count and current running subtotal
    print(f" Items: {len(cart.items):<12} | Current Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

# ==============================================================================
# SYSTEM INITIALIZATION (BOOTSTRAP)
# ==============================================================================

def system_bootstrap():
    """
    The 'Cold Boot' sequence: 
    1. Integrity Check -> 2. Data Hydration -> 3. Security Login.
    """
    clear_screen()
    print("✨ Hospitality OS v4.0 Loading...")

    # Verification: Ensure menu.csv and staff.csv exist before proceeding
    if not check_database_integrity():
        print("🛑 HALT: System files missing. Run setup_os.py first.")
        return None, None, None, None

    # Hydration: Pull the 'Shared Brain' state from disk into live objects
    menu, ledger, staff_list = load_system_state()
    floor = FloorMap() # Initialize the physical table layout
    floor.restore_floor_state() # Re-seat guests if the system previously crashed

    # Atomic Shutdown: Ensures sales are saved even if the user closes the window
    atexit.register(lambda: save_system_state(menu, ledger.total_revenue, ledger.transaction_count))

    # Security Login Loop (5 Attempts)
    for attempt in range(1, 6):
        print(f"\n[ LOGIN REQUIRED - ATTEMPT {attempt}/5 ]")
        login_id = get_staff_id("Enter Staff ID: ")
        active_staff = validate_staff_login(login_id)
        
        if active_staff:
            active_staff.clock_in() # Start the labor timer for CA compliance
            print(f"✅ Welcome, {active_staff.full_name} ({active_staff.role})")
            return active_staff, menu, ledger, floor
            
    print("⛔ ACCESS DENIED: Max attempts reached.")
    return None, None, None, None

# ==============================================================================
# MAIN OPERATING LOOP
# ==============================================================================

def main_loop(user, menu, ledger, floor):
    """
    v4.0 Updated Operating Loop: 
    Now coordinates across Front Desk, POS, and Labor modules.
    """
    # Initialize the waitlist for the session
    waitlist = WaitlistManager() 

    while True:
        clear_screen()
        print(f"👤 USER: {user.full_name} | 💰 TOTAL SALES: {format_currency(ledger.total_revenue)}")
        print("═"*45)
        print(" [1] 🛋️  FRONT DESK (Seating & Reservations)") # UPDATED
        print(" [2] 🍔 SERVICE FLOOR (Open Table / POS)")    # UPDATED
        print(" [3] 📝 WAITLIST MANAGEMENT")
        print(" [4] 📊 MANAGER OFFICE (Labor & Audit)")      # NEW
        print(" [5] 🚪 END SHIFT / LOGOUT")
        print("═"*45)
        
        choice = input("Select Action > ").strip()

        if choice == "1":
            # PHASE 4: Launch Digital Front Desk
            # This handles party size, guest details, and seating
            digitalfrontdesk.main_front_desk(floor, waitlist)
        
        elif choice == "2":
            # POS Workflow
            table_id = get_int("Table # (1-20): ", 1, 20)
            order_workflow(table_id, menu, ledger, user, floor)

        elif choice == "3":
            # Waitlist Logic
            print(f"\n--- ACTIVE WAITLIST ({len(waitlist.queue)} parties) ---")
            for i, entry in enumerate(waitlist.queue, 1):
                print(f"{i}. {entry.guest.full_name} (Party: {entry.party_size})")
            input("\nPress Enter to return...")

        elif choice == "4":
            # PHASE 4: Launch Labor Auditor
            # Only allow if the user is a 'Manager'
            if user.role.upper() == "MANAGER":
                laborcostauditor.main()
            else:
                print("⛔ ACCESS DENIED: Manager credentials required.")
                time.sleep(2)

        elif choice == "5":
            if finalize_session(user, menu, ledger):
                break

# ==============================================================================
# WORKFLOW MODULES
# ==============================================================================

def order_workflow(table_id, menu, ledger, staff, floor):
    """Manages the lifecycle of an active table order."""
    cart = Cart() # Create a fresh shopping cart for this session
    table_obj = floor.tables[table_id - 1] # Get the specific Table object
    
    while True:
        clear_screen()
        display_table_header(table_id, cart)
        
        # CA LABOR ALERT: If server has been on for 4+ hours without a break recorded
        if (datetime.now() - staff.shift_start).total_seconds() > 14400:
            print("⚠️ LABOR ALERT: Shift exceeds 4 hours. Ensure break is taken.")

        print(" [1] Add Item  [2] Void Item  [3] Pay & Close  [Q] Exit Table")
        cmd = input("Command > ").strip().upper()

        if cmd == "1":
            # Add item logic (cloning and inventory deduction)
            item_name = get_name("Item Name: ")
            master_item = menu.find_item(item_name)
            if master_item:
                try:
                    cart.add_to_cart(master_item) # Deducts line_inv immediately
                    print(f"✅ {master_item.name} added.")
                except Exception as e:
                    print(f"❌ {e}") # Handles '86' (Out of Stock) alerts
            else:
                print("❓ Item not found.")
            input("...")

        elif cmd == "2":
            # Secure voiding (requires security logging)
            item_to_void = input("Item to Void: ")
            if cart.void_item(item_to_void, staff, "Server Error"):
                # Inventory restoration would happen here in a full-scale DB
                pass
            input("...")

        elif cmd == "3":
            # Checkout: Transaction logging and Ledger update
            if checkout_workflow(cart, table_id, staff, ledger):
                table_obj.clear_table() # Set status to 'Dirty'
                break # Return to Main Menu

        elif cmd == "Q":
            break # Exit back to floor without closing the bill

def checkout_workflow(cart, table_num, staff, ledger):
    """Finalizes the bill, applies tips, and commits to the Daily Ledger."""
    if not cart.items:
        print("🛒 Cart is empty.")
        return False

    txn = Transaction(cart, table_num, staff)
    
    # Tip Input Loop
    while True:
        tip_in = input(f"Total: ${cart.grand_total:.2f} | Add Tip ($ or %): ")
        if txn.apply_tip(tip_in):
            break
        print("Invalid format. Try '$5' or '20%'.")

    # Financial Sync: Update the DailyLedger (Singleton)
    ledger.record_sale(cart.grand_total)
    
    # Audit: Log the transaction ID for the manager report
    SecurityLog.log_event(staff.staff_id, "CHECKOUT", f"Table {table_num} | Total: ${txn.cart.grand_total + txn.tip:.2f}")
    
    print("\n✅ Transaction Complete. Receipt Printed to Log.")
    input("Press Enter...")
    return True

def show_floor_status(floor):
    """Renders a visual status of all tables."""
    print("\n--- FLOOR STATUS ---")
    for t in floor.tables:
        print(f"Table {t.table_id:02}: {t.status:<12} (Cap: {t.capacity})")
    input("\nPress Enter...")

def finalize_session(user, menu, ledger):
    """Handles secure logout and California compliance checks."""
    confirm = get_yes_no(f"Clock out {user.full_name}? (y/n): ")
    if confirm:
        # Compliance: Manual verification of the meal break for payroll
        user.had_break = get_yes_no("Did you take your required 30-min meal break? (y/n): ")
        user.clock_out()
        
        # Calculate final shift earnings for the employee's visibility
        pay = user.calculate_shift_pay()
        print(f"💰 Shift Complete. Est. Earnings: {format_currency(pay)}")
        
        # Final Sync: Write all memory data to CSV/JSON before closing
        save_system_state(menu, ledger.total_revenue, ledger.transaction_count)
        return True
    return False

# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    # 1. Initialize System
    active_user, live_menu, live_ledger, live_floor = system_bootstrap()
    
    # 2. Start Operations if login was successful
    if active_user:
        try:
            main_loop(active_user, live_menu, live_ledger, live_floor)
        except KeyboardInterrupt:
            # Catch Ctrl+C to ensure a safe state save before crashing
            print("\n⚠️ Emergency Interruption. Saving state...")
            save_system_state(live_menu, live_ledger.total_revenue, live_ledger.transaction_count)
            sys.exit(0)