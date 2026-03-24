"""
HospitalityOS v4.0 - Main Entry Point
Architect: Princeton Afeez
Description: A production-grade POS system featuring Atomic Persistence, 
Labor Compliance Auditing, and Role-Based Access Control (RBAC).
"""

import sys
import os
import re
from datetime import datetime
from decimal import Decimal

# Internal Module Imports
from database import (
    load_menu_from_csv, 
    initialize_system_state, 
    save_system_state, 
    validate_staff_login,
    check_database_integrity
)
from validator import (
    get_int, get_name, get_yes_no, get_staff_id, 
    get_decimal_input, sanitize_input, get_float
)
from models import (
    Cart, ReceiptPrinter, Transaction, Staff, Menu, 
    MenuEditor, AnalyticsEngine, InventoryManager, 
    Modifier, InsufficientStockError, DailyLedger, AdminSession
)
from storage import save_to_json

# ==============================================================================
# UI & VISUAL UTILITIES
# ==============================================================================

def clear_screen():
    """Clears the terminal to keep the UX focused and professional."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    """Renders a persistent status bar with real-time cart telemetry."""
    print("\n" + "█" * 45)
    print(f"{' HOSPITALITY OS - TABLE ' + str(table_num) :^45}")
    print("█" * 45)
    print(f" Items: {len(cart.items):<15} | Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

# ==============================================================================
# ADMINISTRATIVE & ANALYTICS UI
# ==============================================================================

def manager_menu(session: AdminSession, ledger: DailyLedger):
    """
    Commit 37: The secure 'Back-Office' loop.
    Allows price adjustments and inventory toggles without file editing.
    """
    while session.is_active:
        print("\n" + "🔐" + "━"*10 + " MANAGER PANEL " + "━"*10)
        print(" [1] Update Item Price")
        print(" [2] Toggle Seasonal Availability")
        print(" [3] Run Shift-End Analytics")
        print(" [4] Exit Admin Mode")
        
        choice = input("\nAdmin Action > ").strip()

        if choice == "1":
            name = input("Target Item Name: ")
            new_price = get_decimal_input("Set New Price: $")
            session.editor.update_price(name, new_price)
            session.log_action(f"PRICE_CHANGE: {name} to {new_price}")

        elif choice == "2":
            name = input("Item Name to Toggle: ")
            session.editor.toggle_item_status(name)
            session.log_action(f"AVAILABILITY_TOGGLE: {name}")

        elif choice == "3":
            # Commit 42: Real-time analytics engine
            analytics = AnalyticsEngine(ledger, session.editor.menu)
            print("\n📈 TOP SELLERS:", [i.name for i in analytics.get_top_performing_items()])
            alerts = analytics.get_reorder_list()
            if alerts:
                print("🚩 REORDER REQUIRED:", [i.name for i in alerts])

        elif choice == "4":
            print("Saving administrative changes...")
            save_system_state(session.editor.menu, ledger.total_revenue)
            session.is_active = False

# ==============================================================================
# TRANSACTION WORKFLOW
# ==============================================================================

def handle_item_addition(menu, cart, sync_callback, active_server):
    """Handles item lookup, modifier attachment, and inventory validation."""
    item_name = get_name("Enter item name: ")
    found_item = menu.find_item(item_name)
    
    if found_item:
        wants_modifier = get_yes_no(f"Add modifiers to {found_item.name}? (y/n): ")
        mod_name = None
        mod_price = None
        if wants_modifier:
            mod_name = input("Modifier (e.g., 'Extra Cheese'): ").strip()
            mod_price = get_float("Mod Price: ", min_val=0.0)

        try:
            cart.add_to_cart(found_item)  # Clone is created here
            if wants_modifier:
                # Apply modifier to the clone (cart.items[-1]), not the master item
                if not cart.items[-1].add_modifier(Modifier(mod_name, mod_price)):
                    print("Modifier limit reached (max 3).")
            sync_callback(cart) # Update 'Shared Brain'
            print(f"✅ Added {found_item.name}")
        except InsufficientStockError as e:
            print(f"⚠️ STOCK ERROR: {e}")
    else:
        print(f"❌ '{item_name}' not found.")
    input("\nPress Enter...")

def process_checkout(active_server, table_num, cart, menu, ledger):
    """Finalizes the sale, logs the transaction, and updates the Ledger."""
    if not cart.items:
        return

    txn = Transaction(cart, table_num, staff=active_server)

    # Re-prompt until a valid tip format is entered
    while True:
        tip_val = input(f"Subtotal ${cart.subtotal:.2f} | Enter Tip ($ or %): ")
        if txn.apply_tip(tip_val):
            break
        print("Invalid format. Try '5.00', '$5', or '20%'.")

    clear_screen()
    ReceiptPrinter.print_bill(txn)

    # Atomic commit: persist log first, then update ledger
    if save_to_json(txn.to_dict(), "transaction_log.json"):
        ledger.record_sale(cart.subtotal)
        save_system_state(menu, ledger.total_revenue)
    else:
        print("WARNING: Transaction log failed to save. Sale not recorded in ledger.")
    input("\nPayment Processed. Press Enter for next table...")

# ==============================================================================
# MAIN SYSTEM ENGINE
# ==============================================================================

def main_loop():
    """
    The Orchestrator. Connects Database, Models, and Validators 
    into a single, high-stability event loop.
    """
    if not check_database_integrity():
        return

    # Initialize Persistence
    menu = load_menu_from_csv("menu.csv")
    initial_sales = initialize_system_state(menu)
    ledger = DailyLedger(initial_sales)
    
    # Login Guard — max 5 attempts before lockout
    active_server = None
    for attempt in range(1, 6):
        login_id = get_staff_id("Enter Staff ID to unlock POS: ")
        active_server = validate_staff_login(login_id)
        if active_server:
            break
        remaining = 5 - attempt
        if remaining:
            print(f"Login failed. {remaining} attempt(s) remaining.")
        else:
            print("Too many failed login attempts. System locked.")
            return
    active_server.clock_in()

    def sync_state(current_cart):
        """Helper to keep the 'Shared Brain' JSON in sync with the current session."""
        state = {
            "staff_name": active_server.full_name,
            "staff_id": active_server.staff_id,
            "net_sales": float(ledger.total_revenue),
            "cart_count": len(current_cart.items),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        save_to_json(state, "restaurant_state.json")

    while True:
        clear_screen()
        print(f"Logged in: {active_server.full_name} | Shift Sales: ${ledger.total_revenue:.2f}")
        print("\n" + "═"*30)
        print("  HOSPITALITY OS MAIN MENU")
        print("═"*30)
        print(" [1] Open Table / New Order")
        print(" [2] Manager Control Panel")
        print(" [3] System Shutdown")
        
        main_choice = input("\nSelect > ").strip()

        if main_choice == "1":
            table_num = get_int("Table Number: ", min_val=1)
            cart = Cart()  # Walk-in flow; no guest object by default
            
            while True:
                clear_screen()
                display_header(table_num, cart)
                
                # Labor Warning — real-time estimate based on server's elapsed shift
                if ledger.total_revenue > 0 and active_server.shift_start:
                    elapsed = Decimal(str(
                        (datetime.now() - active_server.shift_start).total_seconds() / 3600
                    ))
                    estimated_labor = elapsed * active_server.hourly_rate
                    labor_pct = (estimated_labor / ledger.total_revenue) * 100
                    if labor_pct > 25:
                        print(f"LABOR ALERT: {labor_pct:.1f}% of sales.")

                print(" [1] Add Item  [2] Remove  [3] Checkout  [Q] Back")
                op = input("Action > ").strip().upper()
                
                if op == "1":
                    handle_item_addition(menu, cart, sync_state, active_server)
                elif op == "2":
                    item_name = input("Item to remove: ")
                    cart.void_item(item_name, staff=active_server, reason="User Error")
                elif op == "3":
                    process_checkout(active_server, table_num, cart, menu, ledger)
                    break
                elif op == "Q":
                    break

        elif main_choice == "2":
            if active_server.dept.upper() == "MANAGER":
                editor = MenuEditor(menu)
                session = AdminSession(active_server, editor)
                manager_menu(session, ledger)
            else:
                print("❌ ERROR: Manager credentials required.")
                input("Press Enter...")

        elif main_choice == "3":
            print("Performing Atomic Shutdown...")
            active_server.had_break = get_yes_no(f"Did {active_server.full_name} take a meal break? (y/n): ")
            active_server.clock_out()
            save_system_state(menu, ledger.total_revenue)
            break

if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        print(f"☢️ CRITICAL SYSTEM FAILURE: {e}")
        # In a real environment, we'd trigger an emergency log here.