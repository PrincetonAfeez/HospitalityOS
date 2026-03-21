from database import load_menu_from_csv
from models import Cart

def main():
    # 1. Initialize System
    menu = load_menu_from_csv('menu.csv')
    cart = Cart()
    
    print("\n--- Welcome to Hospitality OS ---")
    
    # 2. Simple Command Loop
    while True:
        print("\nOptions: [1] View Menu [2] Add to Order [3] View Cart [4] Checkout [Q] Quit")
        choice = input("Select an option: ").strip().upper()
        
        if choice == '1':
            for item in menu.items:
                print(item)
                
        elif choice == '2':
            item_name = input("Enter the name of the item to add: ")
            found_item = menu.find_item(item_name)
            if found_item:
                cart.add_to_cart(found_item)
            else:
                print("Item not found.")
                
        elif choice == '3':
            print(f"\nCurrent Cart: {len(cart.items)} items")
            print(f"Subtotal: ${cart.subtotal:.2f}")
            
        elif choice == 'Q':
            break

if __name__ == "__main__":
    main()