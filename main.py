"""
HospitalityOS v4.0 - Main Entry Point (Refactored)
Architect: Princeton Afeez
Description: Production-grade POS orchestrator. Features split-phase 
             initialization for enhanced stability and security.
"""

import sys
import os
import re
import atexit
from datetime import datetime
from decimal import Decimal

# Internal Module Imports - Ensuring Shared Brain connectivity
from database import (
    load_system_state, 
    save_system_state, 
    validate_staff_login,
    check_database_integrity
)
from validator import (
    get_int, get_name, get_yes_no, get_staff_id, 
    get_decimal_input, sanitize_input, get_float, get_time
)
from models import (
    Cart, ReceiptPrinter, Transaction, Staff, Menu, 
    MenuEditor, AnalyticsEngine, InventoryManager, FloorMap,
    Modifier, InsufficientStockError, DailyLedger, AdminSession, 
    generate_low_stock_report
)
from storage import save_to_json

# ==============================================================================
# UI & GLOBALS
# ==============================================================================

def clear_screen():
    """Clears terminal console based on OS type (NT for Windows, Posix for Mac/Linux)."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    """Renders a high-visibility status bar for the current active table."""
    print("\n" + "█" * 45)
    print(f"{' HOSPITALITY OS - TABLE ' + str(table_num) :^45}")
    print("█" * 45)
    # Real-time telemetry: shows count of items and formatted currency subtotal
    print(f" Items: {len(cart.items):<15} | Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

# ==============================================================================
# PHASE 1: SYSTEM BOOTSTRAP (SECURITY & DATA HYDRATION)
# ==============================================================================

def system_bootstrap():
    """
    Handles the 'Cold Boot' sequence: File Integrity -> Data Merge -> Security Login.
    Returns: (active_server, menu, ledger) if successful, else (None, None, None).
    """
    clear_screen()
    print("🚀 Initializing Hospitality OS v4.0...")

    # 1. Hardware/File Integrity Check: Verify CSVs exist before trying to read them
    if not check_database_integrity():
        print("🛑 SYSTEM HALTED: Critical database files (.csv) are missing from /data.")
        return None, None, None

    # 2. Data Hydration: Merges menu.csv (Structure) with restaurant_state.json (Live Inventory)
    # This is the 'Shared Brain' restoration point.
    menu, ledger, staff_list = load_system_state()
    
    # 3. Shutdown Hook: Register atexit to ensure data is saved even on unexpected close
    def final_sync():
        print("\n💾 Shutdown signal detected. Performing final Atomic Sync...")
        save_system_state(menu, ledger.total_revenue, ledger.transaction_count)
    atexit.register(final_sync)

    # 4. Security Gate: Multi-attempt Login Guard (RBAC)
    active_server = None
    for attempt in range(1, 6): # Allow 5 attempts before terminal lockout
        print(f"\n[ SECURITY ACCESS - ATTEMPT {attempt}/5 ]")
        login_id = get_staff_id("Scan Badge or Enter Staff ID (e.g., EMP-01): ")
        active_server = validate_staff_login(login_id)
        
        if active_server:
            active_server.clock_in() # Set shift_start timestamp for labor math
            print(f"✅ Access Granted: Welcome, {active_server.full_name}.")
            input("Press Enter to open floor map...")
            return active_server, menu, ledger
            
        remaining = 5 - attempt
        if remaining > 0:
            print(f"❌ ID Not Recognized. {remaining} attempts remaining.")
    
    print("⛔ SECURITY LOCKOUT: Unauthorized access attempt limit reached.")
    return None, None, None

# ==============================================================================
# PHASE 2: OPERATING CYCLE (ACTIVE SERVICE)
# ==============================================================================

def operating_cycle(active_server, menu, ledger):
    """
    Main Event Loop: Manages UI routing between Tables, Manager Panel, and Shutdown.
    """
    # UI Sync Helper: Updates the JSON state file so other modules (Auditor) can see live data
    def sync_ui_state():
        state = {
            "staff_id": active_server.staff_id,
            "staff_name": active_server.full_name,
            "net_sales": str(ledger.total_revenue),
            "last_sync": datetime.now().strftime("%H:%M:%S")
        }
        # Save to JSON for external module visibility
        save_to_json(state, "restaurant_state.json")
        # Save full menu/ledger state for persistence
        save_system_state(menu, ledger.total_revenue, ledger.transaction_count)

    while True:
        clear_screen()
        # Dashboard Header: Always visible shift-sales tracking
        print(f"👤 USER: {active_server.full_name} | 💰 SHIFT REVENUE: ${ledger.total_revenue:.2f}")
        print("═"*45)
        print(" [1] OPEN TABLE / NEW ORDER")
        print(" [2] MANAGER CONTROL PANEL")
        print(" [3] END SHIFT & SHUTDOWN")
        print("═"*45)
        
        choice = input("Action Select > ").strip()

        if choice == "1":
            # Direct to Table Workflow
            table_num = get_int("Table Number (1-50): ", min_val=1, max_val=50)
            table_service_loop(table_num, menu, ledger, active_server, sync_ui_state)

        elif choice == "2":
            # Privilege Check: Only Managers/Admins can access pricing and inventory toggles
            if active_server.role.upper() in ["MANAGER", "ADMIN"]:
                session = AdminSession(active_server, MenuEditor(menu))
                manager_menu(session, ledger)
            else:
                print("❌ ACCESS DENIED: Manager credentials required.")
                input("Press Enter...")

        elif choice == "3":
            # Graceful Exit: Payroll compliance and final report generation
            if perform_graceful_shutdown(active_server, menu, ledger):
                break

# ==============================================================================
# WORKFLOW HELPERS (SUB-FUNCTIONS)
# ==============================================================================

def table_service_loop(table_num, menu, ledger, active_server, sync_callback):
    """Handles the internal logic of a single table session."""
    cart = Cart() # Initialize empty shopping cart for the table
    
    while True:
        clear_screen()
        display_header(table_num, cart)
        
        # Real-time Labor Analysis: Warning if the server's labor cost is exceeding 25% of sales
        if ledger.total_revenue > 0:
            elapsed_hours = Decimal(str((datetime.now() - active_server.shift_start).total_seconds() / 3600))
            estimated_labor = elapsed_hours * active_server.hourly_rate
            labor_pct = (estimated_labor / ledger.total_revenue) * 100
            if labor_pct > 25:
                print(f"⚠️ LABOR ALERT: {labor_pct:.1f}% of sales. High Labor detected.")

        print(" [1] Add Item  [2] Void Item  [3] Checkout  [Q] Back")
        op = input("Table Action > ").strip().upper()
        
        if op == "1":
            handle_item_addition(menu, cart, sync_callback, active_server)
        elif op == "2":
            item_name = input("Exact Item Name to Void: ")
            # Voiding triggers internal inventory restock and staff-level logging
            cart.void_item(item_name, staff=active_server, reason="Manager Request/Error")
        elif op == "3":
            if process_checkout(active_server, table_num, cart, menu, ledger):
                break # Checkout complete, return to main menu
        elif op == "Q":
            break # Exit to main menu without closing table

def handle_item_addition(menu, cart, sync_callback, active_server):
    """Encapsulates Item Lookup, Modifier Logic, and Inventory Checks."""
    item_name = get_name("Enter item name: ")
    found_item = menu.find_item(item_name)
    
    if found_item:
        # Modifier workflow (Phase 1 legacy feature)
        wants_mod = get_yes_no(f"Customize {found_item.name}? (y/n): ")
        if wants_mod:
            mod_text = input("Modifier Name: ").strip()
            mod_cost = get_float("Mod Price: $", min_val=0.0)
        
        try:
            # Add item to cart (this triggers a MenuItem clone for specific modifications)
            cart.add_to_cart(found_item)
            if wants_mod:
                # Modifiers are applied to the most recent item in the cart
                cart.items[-1].add_modifier(Modifier(mod_text, Decimal(str(mod_cost))))
            
            sync_callback() # Trigger JSON state update
            print(f"✅ {found_item.name} added to cart.")
        except InsufficientStockError as e:
            print(f"❌ OUT OF STOCK: {e}")
    else:
        print(f"❓ Item '{item_name}' not found in database.")
    input("Press Enter...")

def process_checkout(active_server, table_num, cart, menu, ledger):
    """Finalizes Transaction, Prints Receipt, and Commits to Ledger."""
    if not cart.items:
        print("🛒 Cart is empty. Cannot checkout.")
        return False

    txn = Transaction(cart, table_num, staff=active_server)

    # Tip Calculation Logic (Validator-driven for % or $ support)
    while True:
        tip_input = input(f"Total: ${cart.subtotal:.2f} | Enter Tip ($ or %): ")
        if txn.apply_tip(tip_input):
            break
        print("Format Error: Use '20%' or '$5.00'.")

    clear_screen()
    ReceiptPrinter.print_bill(txn) # Formatted receipt output

    # Atomic Save: Log transaction first, then update ledger
    if save_to_json(txn.to_dict(), "transaction_log.json"):
        ledger.record_sale(cart.subtotal) # Update singleton ledger revenue
        save_system_state(menu, ledger.total_revenue, ledger.transaction_count)
        input("\n✅ Payment Successful. Press Enter...")
        return True
    else:
        print("🛑 SYSTEM ERROR: Transaction log failure. Payment rejected.")
        return False

def manager_menu(session: AdminSession, ledger: DailyLedger):
    """Secure Administration Loop for price and inventory control."""
    while session.is_active:
        print("\n" + "🔐" + "━"*10 + " MANAGER PANEL " + "━"*10)
        print(" [1] Update Item Price")
        print(" [2] Toggle Item Availability")
        print(" [3] View Analytics Engine")
        print(" [4] Exit Admin Mode")
        
        cmd = input("\nAdmin Action > ").strip()

        if cmd == "1":
            target = input("Item Name: ")
            price = get_decimal_input("New Price: $")
            session.editor.update_price(target, price)
            session.log_action(f"PRICE_UPDATE: {target} to {price}")
        elif cmd == "2":
            target = input("Item Name: ")
            session.editor.toggle_item_status(target)
            session.log_action(f"STATUS_TOGGLE: {target}")
        elif cmd == "3":
            # Commit 42: Real-time Analytics integration
            engine = AnalyticsEngine(ledger, session.editor.menu)
            print("\n📈 PERFORMANCE DATA:")
            for top in engine.get_top_performing_items():
                print(f" - {top.name}: {top.total_sold} units sold")
        elif cmd == "4":
            session.is_active = False

def perform_graceful_shutdown(server, menu, ledger):
    """Final Compliance Audit and Shutdown Sync."""
    print("\n🏁 Finalizing shift data...")
    # CA Compliance Requirement: Manual break verification for the log
    server.had_break = get_yes_no(f"Confirm: Did {server.full_name} take a meal break? (y/n): ")
    server.clock_out()
    
    # Final Inventory Snapshot
    save_system_state(menu, ledger.total_revenue, ledger.transaction_count)
    
    # Generate Low Stock Report (Phase 3 feature)
    low_stock_count = generate_low_stock_report(menu.items)
    if low_stock_count > 0:
        print(f"⚠️ {low_stock_count} items below par! Audit shopping_list.csv.")
    else:
        print("✅ Inventory levels optimal.")
        
    print(f"👋 {server.full_name} logged out. System Safe.")
    return True

# ==============================================================================
# MAIN EXECUTION BLOCK
# ==============================================================================

if __name__ == "__main__":
    try:
        # Step 1: Bootstrap the environment (Integrity -> Hydration -> Login)
        user, live_menu, live_ledger = system_bootstrap()
        
        # Step 2: If authentication passed, enter the operating cycle
        if user:
            operating_cycle(user, live_menu, live_ledger)
            
    except Exception as e:
        # 2026 Emergency Fallback: Log critical error and exit
        print(f"☢️ CRITICAL RUNTIME FAILURE: {e}")
        sys.exit(1)