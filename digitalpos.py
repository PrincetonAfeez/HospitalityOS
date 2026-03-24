"""
HospitalityOS v4.0 - Point of Sale (POS) Interface
Architect: Princeton Afeez
Description: The primary interface used by servers at the table. 
             Handles ordering, modifiers, and payment processing.
"""

import os
from decimal import Decimal
from datetime import datetime

# --- INTERNAL MODULE IMPORTS ---
from validator import (
    get_int, get_name, get_yes_no, format_currency
)
from models import (
    Cart, Transaction, MenuItem, SecurityLog, Modifier
)
from settings.restaurant_defaults import MAX_MODS

# ==============================================================================
# CORE POS EXECUTION
# ==============================================================================

def run_pos(table_num, guest_obj, menu_brain, daily_ledger, current_staff):
    """
    The main loop for an active table session.
    """
    # 1. Initialize the session-specific Cart
    active_cart = Cart(guest=guest_obj)
    
    # --- TASK: OPTIMIZE LOOKUP (Commit 1) ---
    # Convert list-based menu to a dictionary for O(1) access
    # Assuming menu_brain has an attribute 'items' or similar
    menu_lookup = {item.name.lower(): item for item in menu_brain.items}
    
    while True:
        draw_pos_header(table_num, guest_obj, active_cart)
        
        print(" [1] Add Food/Drink")
        print(" [2] Add Modifier (Sub/Add)")
        print(" [3] View Bill / Print Prep")
        print(" [4] Process Payment & Close")
        print(" [Q] Suspend Session (Save for later)")
        print("═"*45)
        
        choice = input("Select Action > ").strip().upper()

        if choice == "1":
            # Optimized lookup logic
            query = get_name("Enter Item Name: ").lower()
            
            # O(1) Dictionary Access vs Previous O(n) Search
            master_item = menu_lookup.get(query)
            
            if master_item:
                try:
                    active_cart.add_to_cart(master_item)
                    print(f"✅ {master_item.name} added to Table {table_num}.")
                except Exception as e:
                    print(f"❌ ERROR: {e}")
            else:
                print("❓ Item not found in current Menu.")
            input("\nPress Enter...")

        elif choice == "2":
            apply_modifier_workflow(active_cart)

        elif choice == "3":
            display_current_bill(active_cart)
            input("\nPress Enter to return...")

        elif choice == "4":
            if process_checkout(active_cart, table_num, daily_ledger, current_staff):
                return True 
        
        elif choice == "Q":
            print(f"💾 Session for Table {table_num} suspended.")
            return False

# ==============================================================================
# WORKFLOW HELPERS
# ==============================================================================

def draw_pos_header(table_num, guest, cart):
    """Renders the top-level HUD for the server."""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("═"*45)
    print(f" TABLE: {table_num} | GUEST: {guest.full_name}")
    print(f" PARTY: {guest.party_size} | TOTAL: {format_currency(cart.grand_total)}")
    print("═"*45)

def apply_modifier_workflow(cart):
    """Handles the addition of special instructions to the last item added."""
    if not cart.items:
        print("⚠️  Add an item to the cart first!")
        return

    # Targeting the most recently added item (the 'active' item)
    target_item = cart.items[-1]
    
    if len(target_item.modifiers) >= MAX_MODS:
        print(f"⚠️  MAX MODS REACHED: Limit is {MAX_MODS} per item.")
        return

    mod_name = get_name(f"Modifier for {target_item.name}: ")
    mod_price = Decimal("0.00")
    
    # Check if this is a premium modifier (e.g., 'Add Avocado')
    if get_yes_no("Is there an upcharge for this mod? (y/n): "):
        mod_price = Decimal(input("Upcharge Amount: "))

    new_mod = Modifier(mod_name, float(mod_price))
    target_item.modifiers.append(new_mod)
    print(f"📝 Added '{mod_name}' to {target_item.name}.")

def display_current_bill(cart):
    """Generates a detailed breakdown of items, taxes, and potential gratuity."""
    print("\n--- PRE-CHECK REVIEW ---")
    for item in cart.items:
        print(f" {item.name:<25} {format_currency(item.price):>10}")
        for mod in item.modifiers:
            if mod.price > 0:
                print(f"  + {mod.name:<23} {format_currency(mod.price):>10}")
            else:
                print(f"  + {mod.name}")
    
    print("-" * 40)
    print(f" Subtotal:        {format_currency(cart.subtotal):>10}")
    print(f" Tax:             {format_currency(cart.sales_tax):>10}")
    
    # Auto-Gratuity Display logic
    if cart.auto_gratuity > 0:
        print(f" Auto-Grat (18%): {format_currency(cart.auto_gratuity):>10}")
    
    print(f" GRAND TOTAL:     {format_currency(cart.grand_total):>10}")

def process_checkout(cart, table_num, ledger, staff):
    """
    Refactored checkout logic to include Loyalty rewards and Guest feedback.
    """
    if not cart.items:
        print("⚠️  Cannot checkout an empty table.")
        return False

    display_current_bill(cart)
    guest = cart.guest

    # --- TASK 5: LOYALTY REDEMPTION ---
    if guest and guest.loyalty_points >= 500:
        print(f"\n⭐ LOYALTY ALERT: {guest.full_name} has {guest.loyalty_points} points.")
        if get_yes_no("Redeem 500 points for a $10.00 discount? (y/n): "):
            # Deduct points; the cart's grand_total property handles the math 
            # (via the apply_loyalty_discount logic in hospitality_models.py)
            guest.loyalty_points -= 500
            print("✅ Discount applied. Recalculating totals...")
            display_current_bill(cart)

    if get_yes_no("\nProceed to Final Payment? (y/n): "):
        # Create the immutable transaction record
        # Note: Using staff.staff_id as per Pydantic refactor in Commit 2
        txn = Transaction(cart=cart, table_num=table_num, staff_id=staff.staff_id)
        
        tip_input = input("Enter Tip Amount (e.g. 5.00 or 20%): ")
        txn.apply_tip(tip_input)
        
        # 1. Update the Daily Ledger
        ledger.record_sale(cart.grand_total)
        
        # 2. Log for security audit
        SecurityLog.log_event(staff.staff_id, "PAYMENT_PROCESSED", 
                             f"Table {table_num} | Total: {format_currency(cart.grand_total + txn.tip)}")

        # --- TASK 1: GUEST FEEDBACK PROMPT ---
        print("\n" + "═"*45)
        print(f" THANK YOU, {guest.full_name.upper()}!")
        if get_yes_no("Would the guest like to leave a quick rating? (y/n): "):
            rating = get_int("Rate your experience (1-5): ", min_val=1, max_val=5)
            comment = input("Any comments? (Optional): ").strip()
            
            # Use the method added in hospitality_models.py
            guest.record_feedback(rating, comment)
            print("🙏 Thank you! Feedback has been saved.")
        
        # Award points for this meal (100 base + 1 per $10 spent)
        guest.add_loyalty_points(cart.grand_total)
        
        print("\n✅ PAYMENT SUCCESSFUL. Receipt archived.")
        return True
    
    return False