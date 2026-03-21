import os
from decimal import Decimal
from database import load_menu_from_csv
from models import Cart, Transaction

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_header(table_num):
    print("\n" + "="*45)
    print(f"{'HOSPITALITY OS - TABLE ' + str(table_num):^45}")
    print("="*45)

def main():
    # 1. Initialize System
    # In a later task, we will add the "New Service Day" check here
    menu = load_menu_from_csv('menu.csv')
    cart = Cart()
    
    table_num = input("Enter Table Number: ")
    clear_screen()
    
    while True:
        display_header(table_num)
        print(f"Items in Cart: {len(cart.items):<15} Subtotal: ${cart.subtotal:>8.2f}")
        print("-" * 45)
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
            input("\nPress Enter to return to menu...")
            clear_screen()
                
        elif choice == '2':
            item_name = input("Enter item name exactly: ").strip()
            found_item = menu.find_item(item_name)
            if found_item:
                cart.add_to_cart(found_item)
            else:
                print(f"❌ '{item_name}' not found on menu.")
                
        elif choice == '3':
            # This is a placeholder - we will add Remove logic in Task 5
            print("Remove feature coming in Task 5!")
                
        elif choice == '4':
            if not cart.items:
                print("Cart is empty!")
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
            break
        
        clear_screen()

if __name__ == "__main__":
    main()