import os
import re
import datetime 
from decimal import Decimal
from database import load_menu_from_csv, initialize_system_state, save_system_state, validate_staff_login
from validator import get_int, get_name, get_yes_no, get_email, get_float, get_staff_id, get_decimal_input,  sanitize_input
from storage import save_to_json
from models import (
    Cart, ReceiptPrinter, Transaction, Staff, MenuEditor, AnalyticsEngine,
    InventoryManager, Modifier, InsufficientStockError, SecurityLog, DailyLedger
)

# ==============================================================================
# UI & UTILITY HELPERS
# ==============================================================================

def clear_screen():
    """Standard utility to refresh the terminal view."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    """Renders the persistent status bar at the top of the order screen."""
    print("\n" + "="*45) # Visual border
    print(f"{'HOSPITALITY OS - TABLE ' + str(table_num):^45}") # Centered Title
    print("="*45) # Visual border
    # Show real-time cart stats to the server
    print(f"Items in Cart: {len(cart.items):<15} Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45) # Section separator

def display_menu(menu_obj):
    """Task 2: Formats and displays the full menu from the loaded CSV."""
    print("\n" + "-"*15 + " CURRENT MENU " + "-"*15)
    for item in menu_obj.items: # Iterate through menu objects
        print(item) # Utilize the __str__ method in MenuItem model
    print("-" * 44)

def display_staff_performance(active_server: Staff):
    """
    Objective 3: UI component for Sales per Labor Hour report.
    In a real scenario, this would load from transaction_log.json.
    """
    # For this demo/commit, we use the active session's sales
    # but the logic is prepared for a full list of Transaction objects
    report = active_server.generate_shift_report(transactions=[]) 
    
    print("\n" + "="*35)
    print(f"{'OFFICIAL SHIFT REPORT':^35}")
    print("="*35)
    print(f"Staff:          {report['staff']}")
    print(f"Hours Worked:   {report['hours_worked']} hrs")
    print(f"Total Sales:    ${report['total_sales']:,.2f}")
    print(f"Sales / Hour:   ${report['sales_per_hour']:,.2f}")
    print("-" * 35)
    
    if report['is_profitable']:
        print("✅ PERFORMANCE: ABOVE TARGET")
    else:
        print("🚩 PERFORMANCE: BELOW TARGET")
    print("="*35)

class AdminSession:
    """Commit 36: Handles the state of an active administrative session."""
    def __init__(self, staff: Staff, editor: MenuEditor):
        self.staff = staff
        self.editor = editor
        self.is_active = True

    def log_action(self, action: str):
        print(f"🔒 [ADMIN LOG] {self.staff.name} performed: {action}")

class AnalyticsEngine:
    """Commit 42: Logic for calculating sales trends and item popularity."""
    def __init__(self, ledger: DailyLedger, menu: Menu):
        self.ledger = ledger
        self.menu = menu

    def get_top_performing_items(self, limit=3):
        # Sorting items based on how much inventory was used
        sorted_items = sorted(self.menu.items, key=lambda x: (x.par_level - x.stock.total), reverse=True)
        return sorted_items[:limit]
    
    def get_reorder_list(self):
        """Commit 43: Returns items that are below 25% of their par level."""
        return [item for item in self.menu.items if item.stock.total < (item.par_level * 0.25)]
    

def manager_menu(session: AdminSession):
    """Commit 37: Dedicated UI loop for restaurant configuration."""
    while session.is_active:
        print("\n--- MANAGER CONTROL PANEL ---")
        print("1. Update Item Price")
        print("2. Toggle Item Availability")
        print("3. Exit Admin Mode")
        
        ledger = DailyLedger()

        choice = input("Select an option: ")
        if choice == "3": session.is_active = False
        # Logic for 1 and 2 will follow in next commits

        if choice == "1":
            name = input("Enter item name: ")
            new_price = get_decimal_input("Enter new price: $")
            session.editor.update_price(name, new_price)
            session.log_action(f"Price Change: {name} to {new_price}")
        elif choice == "2":
            name = input("Enter item name to toggle: ")
            session.editor.toggle_item_status(name)
            session.log_action(f"Status Toggle: {name}")
        if choice == "3":
            from database import save_system_state
            # Assuming 'current_menu' and 'sales' are accessible
            save_system_state(session.editor.menu, ledger.total_revenue)
            session.is_active = False

# ==============================================================================
# CORE WORKFLOW FUNCTIONS
# ==============================================================================

def perform_staff_login():
    """Requirement 4 & 5: Forces a validated login against staff.csv."""
    active_server = None # Initialize empty state
    while not active_server: # Loop until a valid ID is provided
        print("\n" + "="*45)
        print(f"{'STAFF LOGIN REQUIRED':^45}")
        print("="*45)
        login_id = get_staff_id("Enter Staff ID (e.g., EMP-01): ") # RegEx validated input
        active_server = validate_staff_login(login_id)
    if active_server:
        # Changed .name to .full_name to match Commit 1 Refactor
        print(f"✅ Welcome, {active_server.full_name}!") 
    return active_server # Return the Staff object for session use

def handle_item_addition(menu, cart, sync_callback, active_server):
    """Logic for finding items, adding modifiers, and updating the Shared Brain."""
    item_name = get_name("Enter item name exactly: ") # Validated string input
    found_item = menu.find_item(item_name) # Search menu collection
    if found_item:
        # Task 7: Modifier Integration
        mod_prompt = "Add a modifier? (Letters only, 2-20 chars) or Enter to skip: "
        mod_name = input(mod_prompt).strip() # Manual input for optional step
        if mod_name:
            if not re.match(r"^[A-Za-z\s]{2,20}$", mod_name): # Validate Modifier name
                print("❌ Invalid modifier name. Skipping...")
            else:
                mod_p = get_float(f"Enter price for {mod_name}: ", min_val=0.0) # Modifier price
                found_item.add_modifier(Modifier(mod_name, mod_p)) # Attach to item
        
        try:
            # COMMIT 4 BRIDGE: Catch the inventory exception
            cart.add_to_cart(found_item)
            sync_callback(cart)
        except InsufficientStockError as e:
            print(f"\n⚠️ POS ALERT: {e}")
            input("Press Enter to acknowledge...")
    else:
        print(f"❌ '{item_name}' not found on menu.")
    input("\nPress Enter to continue...")

def handle_item_removal(active_server, cart, sync_callback):
    if not cart.items:
        print("Your cart is empty!")
    else:
        item_to_remove = input("Which item would you like to remove? ").strip()
        # COMMIT 5 BRIDGE: Use the new void logic that logs automatically
        if cart.void_item(item_to_remove, staff=active_server, reason="UI Removal"):
            sync_callback(cart)
        else:
            print(f"❌ '{item_to_remove}' not in cart.")
    input("\nPress Enter to continue...")

def process_checkout(active_server, table_num, cart, menu, current_sales):
    """Finalizes transaction, prints receipt, and updates daily totals."""
    if not cart.items:
        print("Cart is empty!")
        return current_sales # Return current sales unchanged
    
    # COMMIT 7 & 8 BRIDGE: Pass the whole 'active_server' object, not just ID
    txn = Transaction(cart, table_num, staff=active_server)
    
    print(f"\nSubtotal: ${cart.subtotal:.2f}")
    tip_input = input("Enter tip (e.g., 20% or 10.00): ")
    txn.apply_tip(tip_input)
    
    split_input = input("How many ways to split? (1-10): ")
    txn.split_count = int(split_input) if split_input.isdigit() else 1
    
    clear_screen()
    # ReceiptPrinter now pulls Server Name from txn.staff.full_name
    ReceiptPrinter.print_bill(txn)
    
    # Save the deep-serialized dictionary to the log
    save_to_json(txn.to_dict(), "transaction_log.json")
    
    new_total = current_sales + cart.subtotal
    save_system_state(menu, new_total)
    
    if os.path.exists("restaurant_state.json"):
        os.remove("restaurant_state.json")
        
    input("\nTransaction Complete. Press Enter for New Table...")
    return new_total # Return the updated sales for real-time labor tracking

# ==============================================================================
# MAIN APPLICATION ENGINE
# ==============================================================================

def print_shift_report(analytics: AnalyticsEngine):
    print("\n" + "█"*40)
    print(f"{'FINAL SHIFT REPORT':^40}")
    print("█"*40)
    print(f"Total Revenue: ${analytics.ledger.total_revenue:.2f}")
    print(f"Total Transactions: {analytics.ledger.transaction_count}")

    from laborcostauditor import LaborAuditor
    auditor = LaborAuditor()
    auditor.sync_with_ledger()
    print(f"Labor Percentage: {auditor.labor_percentage:.1f}%")
    print(f"Labor Status: {'✅ Within Budget' if auditor.is_within_budget else '🚩 Over Budget'}")

    # Final cleanup logic
    auditor.export_payroll(f"payroll_{datetime.now().strftime('%Y%m%d')}.csv")

def main():
    """Primary Controller: Orchestrates the Hospitality OS session."""
    # 1. Boot-up Sequence
    menu = load_menu_from_csv('menu.csv') # Load items from file
    daily_net_sales = initialize_system_state(menu) # Set initial sales state

    # 2. Authentication Phase
    active_server = perform_staff_login() # Enforce login before any operations

    def sync_state(current_cart):
        """Internal helper to package current state for the Auditor Sync."""
        state_snapshot = {
            "staff_id": active_server.staff_id, # Link active server ID
            "staff_name": active_server.name, # Link active server name
            "net_sales": float(daily_net_sales), # Current daily revenue
            "cart": [item.to_dict() for item in current_cart.items], # Serialized items
            "last_updated": datetime.datetime.now().strftime("%I:%M %p") # Time sync
        }
        save_to_json(state_snapshot, "restaurant_state.json") # Write to disk

    # 3. Operations Loop (Multi-Table Support)
    while True:
        print("\n" + "-"*45)
        table_num = get_int("Enter Table Number (or 0 to Quit): ", min_val=0)
        
        if table_num == 0: # Check for exit condition
            print("Exiting System.")
            break

        cart = Cart() # Initialize a fresh cart for the new table
        sync_state(cart) # Push empty state to Shared Brain
        clear_screen()
        
        # 4. Active Order Loop
        while True:
            display_header(table_num, cart) # Render UI
            
            # Requirement 7: Real-Time Labor Alert
            if daily_net_sales > 0:
                # Calculate Labor % based on a fixed $18/hr labor cost example
                labor_pct = (Decimal("18.00") / daily_net_sales) * 100
                if labor_pct > 20: # Trigger alert if above budget
                    print(f"🚩 LABOR WARNING: {labor_pct:.1f}%")
                    print("   Current labor costs exceed 20% of sales target!")
            
            # Action Menu
            print(" [1] View Menu\n [2] Add Item\n [3] Remove Item\n [4] Checkout\n [5] Prep List\n [6] Staff Report\n [Q] Cancel Table")
            choice = input("Selection > ").strip().upper()
            
            if choice == '1':
                display_menu(menu)
                input("\nPress Enter to return...")

            elif choice == '2':
                handle_item_addition(menu, cart, sync_state) # Modifiers & Add

            elif choice == '3':
                handle_item_removal(active_server, cart, sync_state) # Voids & Log

            elif choice == '4':
                # Process checkout and update the cumulative daily sales
                daily_net_sales = process_checkout(active_server, table_num, cart, menu, daily_net_sales)
                break # Return to table selection

            elif choice == '5':
                # Task 10: Inventory Prep Report
                inv_manager = InventoryManager(menu) # Initialize manager with menu data
                prep_list = inv_manager.get_prep_list() # Fetch items below par
                print("\n" + "="*30 + f"\n{'PREP LIST':^30}\n" + "="*30)
                for entry in prep_list:
                    print(f"- {entry['name']:<15} Need: {entry['need']}")
                input("\nPress Enter to return...")
            
            elif choice == '6':
                display_staff_performance(active_server)
                input("\nPress Enter to return...")
                
            elif choice == 'Q':
                if get_yes_no("Cancel current table order? (y/n): "):
                    if os.path.exists("restaurant_state.json"):
                        os.remove("restaurant_state.json") # Clean up state
                    break # Cancel and return to table entry
            
            clear_screen() # Refresh UI for next action

if __name__ == "__main__":
    if __name__ == "__main__":
    try:
        main_loop()
    except Exception as e:
        print(f"☢️ Critical System Failure: {e}")
        # Emergency Save logic
    