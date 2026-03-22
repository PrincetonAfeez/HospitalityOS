import os
import re
import datetime 
from decimal import Decimal
from database import load_menu_from_csv, initialize_system_state, save_system_state, validate_staff_login
from models import Cart, ReceiptPrinter, Transaction, Staff, InventoryManager, Modifier 
from validator import get_int, get_name, get_yes_no, get_email, get_float, get_staff_id
from storage import save_to_json

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
        active_server = validate_staff_login(login_id) # Cross-reference CSV/Database
        if active_server:
            print(f"✅ Welcome, {active_server.name}!") # Success feedback
        else:
            print(f"❌ Access Denied: ID '{login_id}' not found.") # Failure feedback
    return active_server # Return the Staff object for session use

def handle_item_addition(menu, cart, sync_callback):
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
        
        cart.add_to_cart(found_item) # Move item into active session cart
        sync_callback(cart) # Update restaurant_state.json via callback
    else:
        print(f"❌ '{item_name}' not found on menu.")
    input("\nPress Enter to continue...")

def handle_item_removal(active_server, cart, sync_callback):
    """Requirement 8: Removes items and logs 'Voids' to security.log."""
    if not cart.items:
        print("Your cart is empty!")
    else:
        item_to_remove = input("Which item would you like to remove? ").strip()
        if cart.remove_from_cart(item_to_remove): # Attempt list removal
            # Security Audit Trail logic
            now = datetime.datetime.now().strftime("%I:%M:%S %p") # Current timestamp
            log_entry = f"[{now}] VOID: {item_to_remove} removed by {active_server.name} ({active_server.staff_id})\n"
            with open("security.log", "a") as f: # Open in Append mode
                f.write(log_entry) # Write the void record
            sync_callback(cart) # Update the Shared Brain immediately
        else:
            print(f"❌ '{item_to_remove}' not found in cart.")
    input("\nPress Enter to continue...")

def process_checkout(active_server, table_num, cart, menu, current_sales):
    """Finalizes transaction, prints receipt, and updates daily totals."""
    if not cart.items:
        print("Cart is empty!")
        return current_sales # Return current sales unchanged
    
    # Initialize Transaction with cart and staff metadata
    txn = Transaction(cart, table_num, staff_id=active_server.staff_id)
    
    print(f"\nSubtotal: ${cart.subtotal:.2f}")
    tip_input = input("Enter tip (e.g., 20% or 10.00): ") # Flexible tip entry
    txn.apply_tip(tip_input) # Logic handled in Transaction model
    
    split_input = input("How many ways to split? (1-10): ") # Payment splitting
    txn.split_count = int(split_input) if split_input.isdigit() else 1
    
    clear_screen()
    ReceiptPrinter.print_bill(txn) # Visual printout
    
    # Persistent Logging for Day 7 Analytics
    save_to_json(txn.to_dict(), "transaction_log.json") # Append to history
    
    # Update Daily Ledger
    new_total = current_sales + cart.subtotal # Add subtotal to daily net
    save_system_state(menu, new_total) # Save to database.py state handler
    
    # Cleanup session
    if os.path.exists("restaurant_state.json"):
        os.remove("restaurant_state.json") # Wipe temporary sync file
        
    input("\nTransaction Complete. Press Enter for New Table...")
    return new_total # Return the updated sales for real-time labor tracking

# ==============================================================================
# MAIN APPLICATION ENGINE
# ==============================================================================

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
            print(" [1] View Menu\n [2] Add Item\n [3] Remove Item\n [4] Checkout\n [5] Prep List\n [Q] Cancel Table")
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
                
            elif choice == 'Q':
                if get_yes_no("Cancel current table order? (y/n): "):
                    if os.path.exists("restaurant_state.json"):
                        os.remove("restaurant_state.json") # Clean up state
                    break # Cancel and return to table entry
            
            clear_screen() # Refresh UI for next action

if __name__ == "__main__":
    main() # Execute the entry point