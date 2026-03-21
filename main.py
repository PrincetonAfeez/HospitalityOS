import os
from decimal import Decimal
from database import load_menu_from_csv, initialize_system_state, save_system_state
from models import Cart, Transaction
from validator import get_int, get_name, get_yes_no, get_email, get_float

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num, cart):
    print("\n" + "="*45)
    print(f"{'HOSPITALITY OS - TABLE ' + str(table_num):^45}")
    print("="*45)
    print(f"Items in Cart: {len(cart.items):<15} Subtotal: ${cart.subtotal:>8.2f}")
    print("-" * 45)

def main():
    # 1. Initialize System & Load Shared Brain
    menu = load_menu_from_csv('menu.csv')
    daily_net_sales = initialize_system_state(menu)
    
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
        print(" [Q] Quit System")
        print("-" * 45)
        
        choice = input("Selection > ").strip().upper()
        
        if choice == '1':
            print("\n--- CURRENT MENU ---")
            for item in menu.items:
                print(item)
            input("\nPress Enter to return...")
                
        elif choice == '2':
            item_name = input("Enter item name exactly: ").strip()
            found_item = menu.find_item(item_name)
            if found_item:
                cart.add_to_cart(found_item)
            else:
                print(f"❌ '{item_name}' not found on menu.")
            input("\nPress Enter to continue...")
                
        elif choice == '3':
            # FEATURE ACTIVATED: Using the remove logic from models.py
            if not cart.items:
                print("Your cart is empty!")
            else:
                item_to_remove = input("Which item would you like to remove? ").strip()
                cart.remove_from_cart(item_to_remove)
            input("\nPress Enter to continue...")
                
        elif choice == '4':
            if not cart.items:
                print("Cart is empty!")
                input("\nPress Enter to continue...")
                continue
            
            # Initialize Transaction
            txn = Transaction(cart, table_num)
            
            # Tip Logic
            print(f"\nSubtotal: ${cart.subtotal:.2f}")
            tip_input = input("Enter tip (e.g., 20% or 10.00): ")
            txn.apply_tip(tip_input)
            
            # Split Logic
            split_input = input("How many ways to split? (1-10): ")
            txn.split_count = int(split_input) if split_input.isdigit() else 1
            
            # Final Print
            clear_screen()
            txn.generate_receipt()
            
            # FEATURE RESTORED: Update the Shared Brain (JSON)
            daily_net_sales += cart.subtotal
            save_system_state(menu, daily_net_sales)
            
            input("\nTransaction Complete. Press Enter to exit...")
            break
            
        elif choice == 'Q':
            print("Exiting System.")
            break
        
        clear_screen()

if __name__ == "__main__":
    main()