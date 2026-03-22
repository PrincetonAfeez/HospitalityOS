import os
import re
import datetime
from decimal import Decimal
from database import load_menu_from_csv, initialize_system_state, save_system_state, validate_staff_login
from models import Cart, Transaction
from validator import get_int, get_name, get_yes_no, get_email, get_float
from storage import save_to_json
from models import Staff, InventoryManager # Needed for Task 10

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
    # 1. Initialize System & Load Shared Brain
    menu = load_menu_from_csv('menu.csv')
    daily_net_sales = initialize_system_state(menu)

    # --- Staff Login ---
    print("--- STAFF LOGIN ---")
    active_server = None
    while not active_server:
        login_id = input("Enter Server ID (e.g., EMP-01): ").strip().upper()
        # For now, we'll simulate a check, but Task 5 will link to CSV
        if login_id.startswith("EMP"):
            active_server = Staff(login_id, "Jane Doe", "Server") # Placeholder
            print(f"Welcome, {active_server.name}!")
        else:
            print("❌ Invalid ID Format. Try again.")
    
        # Inside your main() after login:
        active_server = validate_staff_login(login_id)

        # When saving state (Task 6):
        # Task 6: Prepare the state_data dictionary for the Auditor
        state_data = {
            "staff_id": active_server.staff_id,
            "staff_name": active_server.name,
            "net_sales": float(daily_net_sales),
            "last_updated": datetime.now().strftime("%I:%M %p")
        }

        # Write to the Shared Brain
        save_to_json(state_data, "restaurant_state.json")

    # 2. Intake
    table_num = get_int("Enter Table Number: ", min_val=1)
    cart = Cart()
    clear_screen()
    
    while True:
        display_header(table_num, cart)
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
                mod_name = input("Add a modifier? (e.g., Extra Spicy) or press Enter to skip: ").strip()
                
                if mod_name:
                    # --- Task 7: RegEx Validation ---
                    # Allows letters and spaces only, 2-20 characters
                    if not re.match(r"^[A-Za-z\s]{2,20}$", mod_name):
                        print("❌ Invalid modifier name. Use letters only (2-20 chars).")
                    else:
                        mod_price = get_float(f"Enter price for {mod_name}: ", min_val=0.0)
                        from models import Modifier
                        new_mod = Modifier(mod_name, mod_price)
                        found_item.add_modifier(new_mod)
                
                cart.add_to_cart(found_item)
                                
                # Update safety save with new modifier data
                cart_data = [item.to_dict() for item in cart.items]
                save_to_json(cart_data, "restaurant_state.json")
            else:
                print(f"❌ '{item_name}' not found on menu.")
            input("\nPress Enter to continue...")
                
        elif choice == '3':
            if not cart.items:
                print("Your cart is empty!")
            else:
                item_to_remove = input("Which item would you like to remove? ").strip()
                if cart.remove_from_cart(item_to_remove):
                    # Update the safety save after removal
                    cart_data = [item.to_dict() for item in cart.items]
                    save_to_json(cart_data, "restaurant_state.json")
            input("\nPress Enter to continue...")
                
        elif choice == '4':
            if not cart.items:
                print("Cart is empty!")
                input("\nPress Enter to continue...")
                continue
            
            txn = Transaction(cart, table_num)
            
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