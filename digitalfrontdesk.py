"""
Project: Hospitality OS - Digital Front Desk (v3.0)
Description: This script manages the Front-of-House (FOH) guest experience. 
             It handles the intake of new reservations, calculates party sizes,
             and bridges the data gap to the POS system.
"""

import random # Used for automated table assignment if no preference is given
import uuid   # Used to generate a unique 4-character Guest ID for CRM tracking
import digitalpos # Integration with the POS engine to transition guests to a table
from decimal import Decimal # Ensuring financial precision for loyalty calculations
from validator import get_name, get_email, get_int, get_date, get_time, get_yes_no
from storage import save_to_json  # Guest persistence

from models import (
    Person,
    Guest, 
    Table, 
    WaitlistManager,
    Reservation, 
    SecurityLog, 
    InsufficientStockError
)

# ==============================================================================
# MAIN ENGINE & LOGIC
# ==============================================================================

def main():
    """
    The central coordinator. Orchestrates the flow from 
    Reservation (Part A) to Arrival (Part B).
    """
    print("\n--- Part A: Reservation InTake ---\n")
    
    # Define your actual dining room layout
    floor_map = [Table(101, 2), Table(102, 2), Table(201, 4), Table(202, 4), Table(301, 8)]
    guest_obj, adults, kids = get_resy_details()
    # FIX: Pass floor_map here
    handle_arrival(guest_obj, adults, kids, floor_map)

def get_resy_details():
    """
    UX: Collects and validates all guest information.
    Creates and returns a formal Guest object + party counts.
    """
    print("--- MyRestaurant Reservation System ---")
    
    # 1. Collect Basic Identity Information
    first_name = get_name("First Name: ") # Validates string length
    last_name = get_name("Last Name: ")   # Validates string length
    email = get_email("Email Address: ")  # Validates '@' and '.'
    
    # 2. Collect Contact Info (Must be exactly 10 digits)
    phone = get_int("Mobile (10 digits): ", exact_len=10)
    
    # 3. Collect Party Context (Not stored in the permanent Guest profile)
    adults = get_int("Number of Adults: ", min_val=1)
    children = get_int("Number of Children: ", allow_zero=True)
    
    # 4. Scheduling Data (Validated against business hours)
    date = get_date("Reservation Date (e.g., Oct 12th): ")
    resy_time = get_time("Reservation Time: ", start_hour=11, end_hour=21)
    
    # 5. Allergy Logic: Multi-item list builder
    allergies = []
    if get_yes_no("Are there any food allergies for this party? (y/n): "):
        print("Enter allergies one by one (type 'done' when finished):")
        while True:
            item = input("> ").strip().title() # Standardize to Title Case
            if item.lower() == "done": # Break condition
                break
            if item: # Prevent empty strings
                allergies.append(item)

    # 6. Instantiate the Guest Object (Unified)
    generated_id = f"GST-{str(uuid.uuid4())[:8].upper()}"
    total = adults + children
    current_guest = Guest(generated_id, first_name, last_name, phone, party_size=total, allergies=allergies)

    # 7. Persist guest record to CRM log
    guest_record = {
        "guest_id": current_guest.guest_id,
        "name": current_guest.full_name,
        "phone": current_guest.phone,
        "allergies": current_guest.allergies,
        "loyalty_points": current_guest.loyalty_points,
        "is_tax_exempt": current_guest.is_tax_exempt,
        "party_size": current_guest.party_size, # Added this
        "reservation_date": str(date),
        "reservation_time": str(resy_time)
    }
    save_to_json(guest_record, "guest_log.json")

    total = adults + children
    current_guest = Guest(generated_id, first_name, last_name, phone, party_size=total, allergies=allergies)

    # 8. Confirmation UX
    print(f"\n--- Reservation Confirmed ---")
    print(f"Guest: {current_guest.full_name} | ID: {current_guest.guest_id}")
    print(f"Date: {date} at {resy_time}")

    # Returning the full object plus temporary party counts
    return current_guest, adults, children

def find_best_table(floor_map, party_size):
    """Finds the smallest available table that fits the party."""
    candidates = [t for t in floor_map if t.status == "Available" and t.capacity >= party_size]
    if not candidates:
        return None
    candidates.sort(key=lambda x: x.capacity)
    return candidates[0]

# Initialize a global or session-based waitlist manager
active_waitlist = WaitlistManager()

def clear_and_reassign(table: 'Table', floor_map, waitlist: WaitlistManager):
    """
    Called when a guest checks out. Clears the table and 
    immediately checks if anyone on the waitlist fits.
    """
    table.clear_table() # Status becomes 'Dirty'
    print(f"🧹 Table {table.table_id} is being bussed...")
    
    # Simulate bussing time or manual clear
    table.status = "Available"
    
    # Check if someone waiting can take this table
    next_party = waitlist.get_next_fit(table.capacity)
    if next_party:
        print(f"🔔 NOTIFICATION: Table {table.table_id} is ready for {next_party.guest.full_name}!")
        next_party.is_notified = True
        waitlist.remove_guest(next_party.guest.guest_id)

def handle_arrival(guest_obj, adults, children, floor_map):
    # ... (previous verification and allergy logic) ...
    total_guests = adults + children
    
    # [Rest of Table Assignment Logic]
    assigned_table = find_best_table(floor_map, total_guests)

    if assigned_table:
        # 1. Update the Table Object
        # This calls the method in models.py to set status to 'Occupied'
        assigned_table.seat_guest(guest_obj.guest_id)
        
        # Commit 45: Persistence Trigger
        # floor_map is your list of Table objects
        from models import save_table_session
        save_table_session(floor_map) 
        
        print(f"✅ Session persisted to active_tables.json")
        
        # 2. Update the Guest Object
        # Links the Guest to the table for receipt/service tracking
        guest_obj.is_seated = True
        guest_obj.assigned_table = assigned_table.table_id
        
        table_num = assigned_table.table_id
        print(f"✅ Table {table_num} (Capacity: {assigned_table.capacity}) assigned.")
        print(f"Server Alert: {guest_obj.full_name} is now seated at Table {table_num}.")
        
        # 3. Security Audit
        # Records who sat the guest and where (Objective 4 compliance)
        SecurityLog.log_event("HOST_STATION", "GUEST_SEATED", f"Guest: {guest_obj.guest_id} -> Table: {table_num}")

        # 4. Launch POS
        print(f"\nEnjoy your meal! Table {table_num} is ready.")
        success = digitalpos.run_pos(table_num, guest_obj)
        
        if not success:
             print(f"⚠️ POS session for Table {table_num} ended without checkout.")
    else:
        # ... (Waitlist logic we discussed previously) ...
        print(f"❌ No available tables for {total_guests} guests.")
        if get_yes_no("Would you like to join the waitlist? (y/n): "):
            active_waitlist.add_to_waitlist(guest_obj, total_guests)
        
        # Commit 35: Waitlist Fallback
        if get_yes_no("Would you like to join the waitlist? (y/n): "):
            active_waitlist.add_to_waitlist(guest_obj, total_guests)
            print("We will notify you as soon as a table opens up.")
        else:
            print("Understood. Have a wonderful day!")
    

def run_shift_close(manager_staff, daily_ledger, floor_map):
    """
    Commit 36: Standardized Close-out Procedure.
    1. Check for open tables.
    2. Print final stats.
    3. Archive data.
    4. Reset Ledger.
    """
    print(f"\n{'='*40}")
    print(f"{'SHIFT CLOSE INITIATED':^40}")
    print(f"{'='*40}")

    # 1. Validation: Ensure no guests are still seated
    open_tables = [t for t in floor_map if t.status == "Occupied"]
    if open_tables:
        print(f"⚠️  ABORT: Table(s) {', '.join(str(t.table_id) for t in open_tables)} are still occupied!")
        return False

    # 2. Print Summary for Manager review
    avg = daily_ledger.total_revenue / daily_ledger.transaction_count if daily_ledger.transaction_count > 0 else 0
    print(f"Final Revenue:  ${daily_ledger.total_revenue:.2f}")
    print(f"Total Sales:    {daily_ledger.transaction_count}")
    print(f"Avg. Check:     ${avg:.2f}")

    # 3. Archive and Reset
    if get_yes_no("Proceed with Final Z-Report and Archive? (y/n): "):
        success = daily_ledger.archive_shift_data(manager_staff.staff_id)
        if success:
            daily_ledger.reset() # Clears the singleton for tomorrow
            print("\n✅ Shift closed successfully. Data archived.")
            return True
    
    print("\n❌ Shift close cancelled.")
    return False

def close_restaurant_shift(manager_staff, ledger, floor_map):
    """The 'End of Day' procedure."""
    print("\n--- INITIATING SHIFT CLOSE-OUT ---")
    
    # 1. Check for 'Ghost Guests' (Unpaid tables)
    open_tables = [t for t in floor_map if t.status == "Occupied"]
    if open_tables:
        print("🛑 ERROR: Cannot close shift. The following tables are still occupied:")
        for t in open_tables:
            print(f"  - Table {t.table_id}")
        return False

    # 2. Final Archive
    confirm = input("Confirm Z-Report and Revenue Reset? (y/n): ").lower()
    if confirm == 'y':
        if ledger.archive_shift_data(manager_staff.staff_id):
            ledger.reset() # Using the reset method we built in Commit 30
            print("✅ Shift data archived. Ledger reset to $0.00.")
            SecurityLog.log_event(manager_staff.staff_id, "SYSTEM_RESET", "Day ended successfully.")
            return True
    
    print("Shift close aborted.")
    return False

def handle_split_payment(cart, ledger):
    """
    Commit 37: UI Controller for splitting checks.
    """
    print("\n--- SPLIT CHECK INTERFACE ---")
    print("1. Split Evenly (2-6 ways)")
    print("2. Split by Items (Seat-based)")
    choice = input("Select split type: ")

    if choice == "1":
        count = int(input("How many ways? "))
        amounts = cart.split_evenly(count)
        for i, amt in enumerate(amounts):
            print(f"Payment {i+1}: ${amt}")
            ledger.record_transaction(amt)
        cart.items = [] # Clear original cart once all shares are "paid"

    elif choice == "2":
        while cart.items:
            print("\nRemaining Items:")
            for idx, item in enumerate(cart.items):
                print(f"{idx}: {item.name} (${item.price})")
            
            indices = input("Enter item numbers for this sub-check (comma separated): ")
            idx_list = [int(i.strip()) for i in indices.split(",")]
            
            sub_cart = cart.split_by_items(idx_list)
            print(f"Sub-total for this guest: ${sub_cart.grand_total}")
            ledger.record_transaction(sub_cart.grand_total)
            # Repeat until cart.items is empty
            
def finalize_order_to_kitchen(cart, table_num, kds):
    """
    Commit 38: The 'Fire' command.
    Sends items to KDS and prepares the cart for the next round of drinks/food.
    """
    if not cart.items:
        print("❌ Cannot fire an empty order.")
        return

    kds.route_order(cart, table_num)
    
    # Optional: Mark items as 'fired' so they aren't sent twice
    # For now, we assume the cart is cleared for 'rounds' of service
    print(f"✅ Order fired for Table {table_num}.")            

if __name__ == "__main__":
    main() # Execute the script