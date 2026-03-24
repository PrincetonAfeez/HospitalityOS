"""
HospitalityOS v4.0 - Digital POS Bridge
Description: Provides the run_pos() entry point called by the Digital Front Desk.
             Launches a table ordering session with the guest object pre-loaded
             into the cart for tax exemption and loyalty tracking.
"""

from decimal import Decimal
from database import load_menu_from_csv, save_system_state, validate_staff_login, initialize_system_state
from models import (
    Cart, Transaction, Modifier, ReceiptPrinter,
    InsufficientStockError, DailyLedger, save_guest_feedback
)
from validator import get_name, get_int, get_yes_no, get_float, get_staff_id
from storage import save_to_json
from datetime import datetime


def _display_header(table_num, cart):
    """Renders the table status bar."""
    print("\n" + "█" * 45)
    print(f"{' HOSPITALITY OS - TABLE ' + str(table_num) :^45}")
    print("█" * 45)
    print(f" Items: {len(cart.items):<15} | Subtotal: ${cart.subtotal:>8.2f}")
    if cart.guest:
        print(f" Guest: {cart.guest.full_name:<15} | Tax Exempt: {cart.guest.is_tax_exempt}")
    print("-" * 45)


def run_pos(table_num: int, guest=None):
    """
    Launches a POS ordering session for a specific table.
    Called by digitalfrontdesk.py after guest check-in.

    Args:
        table_num: The table number assigned at the front desk.
        guest: Optional Guest object to attach to the cart (enables tax
               exemption and loyalty point tracking).
    """
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"=== POS SESSION - TABLE {table_num} ===")
    if guest:
        print(f"Guest: {guest.full_name} | ID: {guest.guest_id}")
        if guest.allergies:
            print(f"*** ALLERGY ALERT: {', '.join(guest.allergies)} ***")
    print()

    # Load menu and seed ledger from state file if it exists (prevents $0 context when standalone)
    menu = load_menu_from_csv("menu.csv")
    initial_sales = initialize_system_state(menu)
    ledger = DailyLedger(initial_sales)

    # Authenticate the server — max 5 attempts before lockout
    active_server = None
    for attempt in range(1, 6):
        login_id = get_staff_id("Server Staff ID: ")
        active_server = validate_staff_login(login_id)
        if active_server:
            break
        remaining = 5 - attempt
        if remaining:
            print(f"Login failed. {remaining} attempt(s) remaining.")
        else:
            print("Too many failed login attempts. Session locked.")
            return False
    active_server.clock_in()

    # Create cart pre-linked to the guest for tax/loyalty logic
    cart = Cart(guest=guest)

    # --- Order Entry Loop ---
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        _display_header(table_num, cart)
        print(" [1] Add Item  [2] Remove Item  [3] Checkout  [Q] Cancel Table")
        action = input("Table Action > ").strip().upper()

        if action == "1":
            item_name = get_name("Item name: ")
            found = menu.find_item(item_name)
            if found:
                wants_modifier = get_yes_no(f"Add modifiers to {found.name}? (y/n): ")
                mod_name = None
                mod_price = None
                if wants_modifier:
                    mod_name = input("Modifier name: ").strip()
                    mod_price = get_float("Modifier price: $", min_val=0.0)
                try:
                    cart.add_to_cart(found)  # Clone is created here
                    if wants_modifier:
                        # Apply modifier to the clone, not the master item
                        if not cart.items[-1].add_modifier(Modifier(mod_name, mod_price)):
                            print("Modifier limit reached (max 3).")
                    print(f"Added: {found.name}")
                except InsufficientStockError as e:
                    print(f"STOCK ERROR: {e}")
            else:
                print(f"'{item_name}' not found or unavailable.")
            input("\nPress Enter...")

        elif action == "2":
            target = input("Item name to remove: ")
            cart.void_item(target, staff=active_server, reason="Front Desk Correction")

        elif action == "3":
            if not cart.items:
                print("Cannot checkout an empty cart.")
                input("Press Enter...")
                continue

            # Finalize transaction
            txn = Transaction(cart, table_num, staff=active_server)

            # Re-prompt until valid tip format
            while True:
                tip_str = input(f"Subtotal ${cart.subtotal:.2f} | Enter Tip ($ or %): ")
                if txn.apply_tip(tip_str):
                    break
                print("Invalid format. Try '5.00', '$5', or '20%'.")

            os.system('cls' if os.name == 'nt' else 'clear')
            ReceiptPrinter.print_bill(txn)
            
            # Award loyalty points if guest is present
            if guest:
                guest.add_loyalty_points(cart.subtotal)

            # Atomic commit: persist log first, then update ledger
            if save_to_json(txn.to_dict(), "transaction_log.json"):
                ledger.record_sale(cart.subtotal)
                save_system_state(menu, ledger.total_revenue)
            else:
                print("WARNING: Transaction log failed to save. Sale not recorded in ledger.")

            active_server.clock_out()
            input("Payment processed. Press Enter to return to Front Desk...")
            return True

        elif action == "Q":
            active_server.clock_out()
            print("Table session cancelled. Returning to Front Desk.")
            return False

def apply_tax_exemption(cart, manager_staff):
    """
    Commit 40: Manager-only flow to exempt a check from tax.
    """
    if not cart.guest:
        print("❌ Error: No guest profile linked to this cart.")
        return

    print(f"Current Guest: {cart.guest.full_name}")
    confirm = input("Verify Tax-Exempt ID and proceed? (y/n): ")
    
    if confirm.lower() == 'y':
        cart.guest.toggle_tax_exempt()
        print(f"✅ Tax removed. New Total: ${cart.grand_total}")
    else:
        print("Action cancelled.")

def manager_comp_flow(cart, manager):
    """UI for applying discounts/comps."""
    print("\n--- MANAGER COMP INTERFACE ---")
    for i, item in enumerate(cart.items):
        print(f"{i}: {item.name} (${item.price})")
    
    idx = int(input("Select item index to COMP: "))
    reason = input("Enter reason (e.g., 'Kitchen Error', 'Employee Meal'): ")
    
    cart.apply_comp(idx, manager.staff_id, reason)

def process_checkout(table, guest, ledger, floor_map):
    """
    Hospitality OS: Final Checkout Controller.
    Handles payment, robust tip parsing, loyalty points, and guest feedback.
    """
    cart = table.current_cart
    print(f"\n" + "="*30)
    print(f"      CHECKOUT: TABLE {table.table_id}      ")
    print("="*30)
    print(f"Guest: {guest.full_name}")
    print(f"Subtotal:      ${cart.subtotal:>10.2f}")
    print(f"Tax:           ${cart.sales_tax:>10.2f}")
    
    if cart.auto_gratuity > 0:
        print(f"Auto-Grat (18%): ${cart.auto_gratuity:>10.2f}")
        
    print(f"TOTAL DUE:     ${cart.grand_total:>10.2f}")
    print("-" * 30)

    # 1. Payment Method Selection
    method = input("Payment Method (Cash/Card): ").strip().title()
    
    # 2. Initialize Transaction Object
    from models import Transaction
    txn = Transaction(cart, method)
    
    # 3. Robust Tip Loop (Using your custom logic)
    while True:
        tip_input = input("Enter Tip (e.g., '5.00' or '20%'): ").strip()
        if txn.apply_tip(tip_input):
            break
        print("❌ Invalid format. Please use '5.00' or '20%'.")

    print(f"Final Total (incl. tip): ${txn.final_total:.2f}")

    # 4. Finalize Financials & Record to Ledger
    payment_success = False
    try:
        ledger.record_transaction(txn.final_total)
        payment_success = True
        print(f"\n✅ Payment Processed. Transaction ID: {txn.transaction_id}")
    except Exception as e:
        print(f"❌ Critical Error recording transaction: {e}")

    # 5. The Feedback Loop (Commit 42 / Phase 3 - Item B)
    if payment_success:
        # Loyalty Points: 1 point per $10 spent (Phase 3 - Item C)
        points_earned = int(txn.final_total // 10)
        guest.loyalty_points += points_earned
        print(f"✨ Loyalty Update: +{points_earned} points (Total: {guest.loyalty_points})")

        print(f"\nThank you for dining with us, {guest.full_name}!")
        try:
            stars = int(input("How was your experience today? (1-5 stars): "))
            if 1 <= stars <= 5:
                note = input("Any additional comments? ")
                # Import utility from models.py
                from models import save_guest_feedback
                save_guest_feedback(guest.guest_id, stars, note)
            else:
                print("Rating out of range. Skipping feedback.")
        except ValueError:
            print("Invalid input. Skipping feedback.")

    # 6. Table Cleanup
    table.clear_table() # Sets status to 'Dirty' for the busser
    
    # Commit 45: Update persistence after guest leaves
    from models import save_table_session
    # Assuming floor_map is available in your global scope or passed in
    save_table_session(floor_map)  

    return txn

def display_gm_dashboard(ledger, staff_list):
    """The 'Executive View' terminal dashboard."""
    report = ledger.generate_gm_report(staff_list)
    
    print("\n" + "="*40)
    print(f"       EXECUTIVE GM DASHBOARD        ")
    print(f"       Date: {datetime.now().strftime('%Y-%m-%d')} ")
    print("="*40)
    print(f"Gross Sales:         ${report['total_sales']:>10.2f}")
    print(f"Labor Expenses:      ${report['total_labor']:>10.2f}")
    print(f"Labor Cost %:         {report['labor_percentage']:>10}%")
    print(f"Total Transactions:   {report['transaction_count']:>10}")
    print("-" * 40)
    
    if report['labor_percentage'] > 30:
        print("⚠️ ALERT: Labor is high (>30%). Consider cutting staff.")
    elif report['total_sales'] > 0:
        print("✅ Efficiency: Prime Cost within healthy range.")
    print("="*40)
