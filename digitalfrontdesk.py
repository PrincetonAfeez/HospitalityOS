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
from models import Person   # Inheriting base attributes (name) from the core model
from validator import get_name, get_email, get_int, get_date, get_time, get_yes_no
from storage import save_to_json  # Guest persistence
from models import Person, Table, Guest, Reservation # Now importing both

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

def handle_arrival(guest_obj, adults, children, floor_map): # FIX: Accept floor_map
    """
    Handles physical arrival, table assignment, and hand-off to POS.
    """
    print(f"\n--- Part B: Guest Arrival ---")
    print(f"Welcome back, {guest_obj.full_name}!")
    
    # 1. Re-Verify Party Size (Common hospitality UX requirement)
    if get_yes_no("Is the party size still the same? (y/n): "):
        total_guests = adults + children # Use original reservation counts
    else:
        # Update counts if the party grew or shrunk
        new_adults = get_int("Updated adult count: ", min_val=1)
        new_kids = get_int("Updated children count: ", allow_zero=True)
        total_guests = new_adults + new_kids
    
    # 2. Safety UX: Explicit alert for the server/kitchen
    if guest_obj.allergies:
        print(f"\n*** KITCHEN ALERT: {', '.join(guest_obj.allergies)} ***")

    # 3. Table Assignment Logic
    if get_yes_no("Do you have a specific table preference? (y/n): "):
        # Manual table selection (validated 1-99)
        table_num = get_int("Enter Table Number (1-99): ", min_val=1, max_val=99)
    else:
        # Automated random assignment
        table_num = random.randint(1, 99)
        print(f"No problem, we have assigned you Table {table_num}.")

    # Commit 34: Smart Table Assignment
    best_table = find_best_table(floor_map, total_guests)
    
    if best_table:
        table_num = best_table.table_id
        best_table.seat_guest(guest_obj.guest_id)
        print(f"✅ Table {table_num} (Capacity: {best_table.capacity}) assigned.")
    else:
        print(f"❌ No available tables for a party of {total_guests}.")
        # To be handled in Commit 35: Waitlist
        return

    digitalpos.run_pos(table_num, guest_obj)
    
    print(f"\nEnjoy your meal! Table {table_num} is ready for {total_guests} guests.")

    # 4. FINAL INTEGRATION: Launch the POS with the specific Table and Guest data
    success = digitalpos.run_pos(table_num, guest_obj)
    if success is False:
        print(f"⚠️  POS session for Table {table_num} ended without completing checkout.")

if __name__ == "__main__":
    main() # Execute the script