import os
import re
import datetime # Using the full module import
from decimal import Decimal
from database import load_menu_from_csv, initialize_system_state, save_system_state, validate_staff_login
from models import Cart, Transaction, Staff, InventoryManager # Combined imports
from validator import get_int, get_name, get_yes_no, get_email, get_float, get_staff_id
from storage import save_to_json

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    print("\n" + "="*45)
    print(f"{'HOSPITALITY OS - TABLE ' + str(table_num):^45}")
    print("="*45)
    print(f"Items in Cart: {len(cart.items):<15} Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

def display_menu(menu_obj):
    """Task 2: Dedicated function for menu display"""
    print("\n" + "-"*15 + " CURRENT MENU " + "-"*15)
    # Grouping by category (optional but professional)
    for item in menu_obj.items:
        print(item)
    print("-" * 44)

def view_cart(cart):
    """Task 7: Detailed view of current order"""
    if not cart.items:
        print("\n🛒 Your cart is currently empty.")
    else:
        print("\n--- CURRENT ORDER ---")
        for item in cart.items:
            print(f"- {item.name:<20} ${item.price:>8.2f}")
        print(f"\nSubtotal: ${cart.subtotal:>8.2f}")

def main():
    # 1. Initialize System
    menu = load_menu_from_csv('menu.csv')
    daily_net_sales = initialize_system_state(menu)

    # --- Staff Login ---
    active_server = None
    while not active_server:
        print("\n" + "="*45)
        print(f"{'STAFF LOGIN REQUIRED':^45}")
        print("="*45)
        
        # Task 9: Call the validator instead of raw input
        login_id = get_staff_id("Enter Staff ID (e.g., EMP-01): ")
        
        active_server = validate_staff_login(login_id)

        if active_server:
            print(f"✅ Welcome, {active_server.name}!")
        else:
            print(f"❌ Access Denied: ID '{login_id}' not found in system.")

    def sync_state(current_cart):
        """Bundles staff, sales, and cart into one persistent JSON state."""
        state_snapshot = {
            "staff_id": active_server.staff_id,
            "staff_name": active_server.name,
            "net_sales": float(daily_net_sales),
            "cart": [item.to_dict() for item in current_cart.items],
            # Consistent use of datetime.datetime.now()
            "last_updated": datetime.datetime.now().strftime("%I:%M %p")
        }
        save_to_json(state_snapshot, "restaurant_state.json")

    # Initial login sync
    sync_state(Cart())

    # 2. Intake
    table_num = get_int("Enter Table Number: ", min_val=1)

    cart = Cart()
    clear_screen()
    
    while True:
        display_header(table_num, cart)

        if daily_net_sales > 0:
            labor_cost_pct = (Decimal("18.00") / daily_net_sales) * 100
            if labor_cost_pct > 20:
                print(f"🚩 LABOR WARNING: {labor_cost_pct:.1f}%")
                print("   Current labor costs exceed 20% of sales target!")
        
        print(" [1] View Menu")
        print(" [2] Add Item to Order")
        print(" [3] Remove Item")
        print(" [4] Checkout & Print Receipt")
        print(" [5] Manager Report (Prep List)") # Task 10
        print(" [Q] Quit System")
        print("-" * 45)
        
        choice = input("Selection > ").strip().upper()
        
        if choice == '1':
            display_menu(menu)
            input("\nPress Enter to return...")

        elif choice == '2':
            item_name = get_name("Enter item name exactly: ")
            found_item = menu.find_item(item_name)
            if found_item:
                # Re-inserting the Modifier logic from Task 7
                mod_name = input("Add a modifier? (Letters only, 2-20 chars) or Enter to skip: ").strip()
                if mod_name:
                    if not re.match(r"^[A-Za-z\s]{2,20}$", mod_name):
                        print("❌ Invalid modifier name. Skipping...")
                    else:
                        mod_price = get_float(f"Enter price for {mod_name}: ", min_val=0.0)
                        from models import Modifier
                        found_item.add_modifier(Modifier(mod_name, mod_price))
                
                cart.add_to_cart(found_item)
                sync_state(cart) # Keep the Shared Brain updated
            else:
                print(f"❌ '{item_name}' not found on menu.")
            input("\nPress Enter to continue...")
                
        elif choice == '3': # COMBINED AND FIXED
            if not cart.items:
                print("Your cart is empty!")
            else:
                item_to_remove = input("Which item would you like to remove? ").strip()
                if cart.remove_from_cart(item_to_remove):
                    # Task 8: Security Logging
                    now = datetime.datetime.now().strftime("%I:%M:%S %p")
                    log_entry = f"[{now}] VOID: {item_to_remove} removed by {active_server.name} ({active_server.staff_id})\n"
                    with open("security.log", "a") as f:
                        f.write(log_entry)
                    
                    sync_state(cart) # Sync staff AND cart
                else:
                    print(f"❌ '{item_to_remove}' not found in cart.")
            input("\nPress Enter to continue...")
                
        elif choice == '4':
            if not cart.items:
                print("Cart is empty!")
                input("\nPress Enter to continue...")
                continue
            
            txn = Transaction(cart, table_num, staff_id=active_server.staff_id)
            
            print(f"\nSubtotal: ${cart.subtotal:.2f}")
            tip_input = input("Enter tip (e.g., 20% or 10.00): ")
            txn.apply_tip(tip_input)
            
            split_input = input("How many ways to split? (1-10): ")
            txn.split_count = int(split_input) if split_input.isdigit() else 1
            
            clear_screen()
            txn.generate_receipt()
            
            # --- TASK 7: PERMANENT LOG ---
            # Append this specific transaction to the permanent history
            save_to_json(txn.to_dict(), "transaction_log.json")
            
            daily_net_sales += cart.subtotal
            save_system_state(menu, daily_net_sales)
            
            # Clear the safety save since the transaction is finished
            if os.path.exists("restaurant_state.json"):
                os.remove("restaurant_state.json")
                
            input("\nTransaction Complete. Press Enter to exit...")
            break

        elif choice == '5':
            # --- TASK 10: MANAGER REPORT ---
            inv_manager = InventoryManager(menu)
            prep_list = inv_manager.get_prep_list()
            print("\n" + "="*30)
            print(f"{'PREP LIST / PAR GAPS':^30}")
            print("="*30)
            if not prep_list:
                print("All items at or above par!")
            for entry in prep_list:
                print(f"- {entry['name']:<15} Need: {entry['need']}")
            input("\nPress Enter to return...")
            
        elif choice == 'Q':
            print("Exiting System.")
            break
        
        clear_screen()

if __name__ == "__main__":
    main()