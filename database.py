import sys  # System-specific parameters and functions
import os  # Operating system interfaces (for clear_screen)
import re  # Regular expression operations for input validation
from datetime import datetime  # Date and time handling for logs/reports
from decimal import Decimal  # Precise arithmetic for financial data

# ------------------------------------------------------------------------------
# INTERNAL MODULE IMPORTS
# ------------------------------------------------------------------------------
from database import (
    load_menu_from_csv,       # Loads MenuItem objects from CSV
    initialize_system_state,  # Handles 'New Day' vs 'Continue' logic
    save_system_state,        # Writes current state to JSON
    validate_staff_login,     # Authenticates user against staff.csv
    check_database_integrity  # Verifies required files exist
)
from validator import (
    get_int,            # Validates integer input within ranges
    get_name,           # Validates names (alphabetic/hyphenated)
    get_yes_no,         # Returns Boolean for y/n prompts
    get_staff_id,       # Validates 'EMP-XX' format via RegEx
    get_decimal_input,  # Converts $ or % inputs to Decimals
    get_float           # Validates float inputs for prices/math
)
from models import (
    Cart,             # Manages items currently being ordered
    ReceiptPrinter,   # Formats and prints ASCII bills
    Transaction,      # Represents a finalized, paid order
    Staff,            # Model for employee data/permissions
    Menu,             # Collection of MenuItem objects
    MenuEditor,       # Controller for administrative menu changes
    AnalyticsEngine,  # Logic for top sellers and reorder lists
    Modifier,         # Represents item add-ons (e.g., 'Extra Cheese')
    InsufficientStockError, # Custom Exception for inventory failures
    DailyLedger,      # Singleton to track total shift revenue
    AdminSession      # Manages state of a logged-in manager
)
from storage import save_to_json # Standardized JSON writer

# ==============================================================================
# UI & UTILITY HELPERS
# ==============================================================================

def clear_screen():
    """Cleans the terminal window to provide a 'Software' feel, not a script."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    """Renders a persistent status bar with real-time cart telemetry."""
    print("\n" + "█" * 45)  # Visual boundary
    print(f"{' HOSPITALITY OS - TABLE ' + str(table_num) :^45}") # Centered text
    print("█" * 45)
    # Real-time stats help the server track order progress at a glance
    print(f" Items in Cart: {len(cart.items):<10} | Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

# ==============================================================================
# ADMINISTRATIVE CONTROL LOGIC
# ==============================================================================

def manager_menu(session: AdminSession, ledger: DailyLedger):
    """Secure UI loop for managers to modify system configuration mid-shift."""
    while session.is_active:
        print("\n" + "🔐" + "━"*10 + " MANAGER PANEL " + "━"*10)
        print(" [1] Update Item Price")      # Direct price modification
        print(" [2] Toggle Item Availability") # Hide/Show items
        print(" [3] Run Analytics Report")    # Top sellers/Stock alerts
        print(" [4] Exit Admin Mode")
        
        choice = input("\nSelect Admin Action > ").strip()

        if choice == "1":
            name = input("Target Item Name: ")
            new_p = get_decimal_input("Set New Price: $")
            session.editor.update_price(name, new_p) # Backend update
            session.log_action(f"PRICE_UPDATE: {name} to {new_p}") # Audit trail

        elif choice == "2":
            name = input("Item Name to Toggle: ")
            session.editor.toggle_item_status(name) # Flips is_active boolean
            session.log_action(f"STATUS_TOGGLE: {name}")

        elif choice == "3":
            # Analytics engine crunches ledger and menu data
            engine = AnalyticsEngine(ledger, session.editor.menu)
            print(f"\n📈 SHIFT REVENUE: ${ledger.total_revenue:.2f}")
            print("🚀 TOP ITEMS:", [i.name for i in engine.get_top_performing_items()])
            alerts = engine.get_reorder_list()
            if alerts:
                print("🚩 LOW STOCK:", [i.name for i in alerts])

        elif choice == "4":
            print("💾 Finalizing admin changes...")
            save_system_state(session.editor.menu, ledger.total_revenue) # Atomic save
            session.is_active = False # Break the admin loop

# ==============================================================================
# CORE TRANSACTION WORKFLOW
# ==============================================================================

def handle_item_addition(menu, cart, sync_callback, active_server):
    """Handles item search, modifier logic, and inventory deduction."""
    item_name = get_name("Enter item name: ") # Sanitized input
    found_item = menu.find_item(item_name)    # Search the Menu object
    
    if found_item:
        # Prompt for optional modifiers (Requirement 7)
        if get_yes_no(f"Add modifiers to {found_item.name}? (y/n): "):
            m_name = input("Modifier Name: ").strip()
            m_price = get_float("Modifier Price: ", min_val=0.0)
            found_item.add_modifier(Modifier(m_name, m_price)) # Attach to item
        
        try:
            cart.add_to_cart(found_item) # Deducts inventory and adds to cart
            sync_callback(cart) # Updates the JSON 'Shared Brain'
            print(f"✅ {found_item.name} added to cart.")
        except InsufficientStockError as e:
            print(f"⚠️ POS ALERT: {e}") # Triggers if line/walk-in inv is 0
    else:
        print(f"❌ Item '{item_name}' not found on menu.")
    input("\nPress Enter to continue...")

def process_checkout(active_server, table_num, cart, menu, ledger):
    """Finalizes order, calculates tips, prints bill, and updates ledger."""
    if not cart.items:
        print("❌ Cannot checkout an empty cart.")
        return

    # Create transaction object linking cart, table, and staff
    txn = Transaction(cart, table_num, staff=active_server)
    
    # Financial input with automatic percentage/dollar detection
    tip_str = input(f"Subtotal: ${cart.subtotal:.2f} | Enter Tip ($ or %): ")
    txn.apply_tip(tip_str)
    
    clear_screen()
    ReceiptPrinter.print_bill(txn) # Formatted ASCII output
    
    # Log detailed JSON for future accounting
    save_to_json(txn.to_dict(), "transaction_log.json")
    
    # Update global shift sales
    ledger.total_revenue += cart.subtotal
    save_system_state(menu, ledger.total_revenue) # Sync state to disk
    input("\n✅ Transaction Finalized. Press Enter for next table...")

# ==============================================================================
# MAIN APPLICATION ENGINE
# ==============================================================================

def main_loop():
    """The master controller orchestrating the entire POS lifecycle."""
    
    # Step 1: Pre-flight health check
    if not check_database_integrity():
        return # Terminate if files are missing

    # Step 2: Initialize Persistence and Global State
    menu = load_menu_from_csv("menu.csv")
    initial_sales = initialize_system_state(menu) # Ask user: New or Continue?
    ledger = DailyLedger(initial_sales) # Instantiate Singleton Ledger
    
    # Step 3: Authentication Barrier
    active_server = None
    while not active_server:
        clear_screen()
        print("🔐 HOSPITALITY OS v4.0 - SECURE LOGIN")
        l_id = get_staff_id("Staff ID (EMP-XX): ") # RegEx validation
        active_server = validate_staff_login(l_id) # CSV lookup

    # Closure: Internal helper to sync local cart state to shared brain
    def sync_state(current_cart):
        state_data = {
            "staff": active_server.full_name,
            "net_sales": float(ledger.total_revenue),
            "cart_items": len(current_cart.items),
            "updated_at": datetime.now().strftime("%H:%M:%S")
        }
        save_to_json(state_data, "restaurant_state.json")

    # Step 4: Primary Operations Loop
    while True:
        clear_screen()
        # Top-level status board
        print(f"USER: {active_server.full_name} | ROLE: {active_server.dept}")
        print(f"SHIFT SALES: ${ledger.total_revenue:.2f}")
        print("\n" + "═"*30)
        print(f"{'MAIN MENU':^30}")
        print("═"*30)
        print(" [1] Open Table / New Order")
        print(" [2] Manager Control Panel")
        print(" [3] System Shutdown")
        
        main_choice = input("\nPOS Select > ").strip()

        if main_choice == "1":
            t_num = get_int("Enter Table #: ", min_val=1)
            cart = Cart() # Fresh cart for every table
            
            while True: # Sub-loop for active table
                clear_screen()
                display_header(t_num, cart)
                
                # Dynamic Labor Alert (Requirement 7)
                if ledger.total_revenue > 0:
                    # Mock calculation: Sales / Theoretical Labor Cost
                    labor_ratio = (Decimal("25.00") / ledger.total_revenue) * 100
                    if labor_ratio > 30: # 30% is a standard industry danger zone
                        print(f"🚩 LABOR WARNING: {labor_ratio:.1f}% (High)")

                print(" [1] Add Item  [2] Void Item  [3] Checkout  [Q] Back")
                action = input("Table Action > ").strip().upper()
                
                if action == "1":
                    handle_item_addition(menu, cart, sync_state, active_server)
                elif action == "2":
                    target = input("Name of item to void: ")
                    # Voiding logs the action for security (Commit 5)
                    cart.void_item(target, staff=active_server, reason="User Correction")
                    sync_state(cart)
                elif action == "3":
                    process_checkout(active_server, t_num, cart, menu, ledger)
                    break # Return to Main Menu
                elif action == "Q":
                    break # Discard/Hold table and go back

        elif main_choice == "2":
            # RBAC Gatekeeping: Only Managers can enter
            if active_server.dept.upper() == "MANAGER":
                editor = MenuEditor(menu) # Initialize controller
                session = AdminSession(active_server, editor)
                manager_menu(session, ledger)
            else:
                print("❌ ACCESS DENIED: Manager credentials required.")
                input("Press Enter...")

        elif main_choice == "3":
            # Graceful Shutdown: Saves final state before closing
            print("💾 Saving final shift state... System Closing.")
            save_system_state(menu, ledger.total_revenue)
            break # Terminate the main_loop

# Standard Python entry point boilerplate
if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        # Protects data if user hits Ctrl+C
        print("\n\n⚠️ Keyboard Interrupt detected. State preserved.")
    except Exception as e:
        # Global safety net to prevent unhandled crashes
        print(f"☢️  CRITICAL SYSTEM FAILURE: {e}")