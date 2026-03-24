"""
HospitalityOS v4.0 - Digital Front Desk
Architect: Princeton Afeez
Description: Manages the Front-of-House (FOH) intake. Handles reservations, 
             party size calculations, and the transition of guests to the POS.
"""

import uuid   # Used to generate unique 8-character Guest IDs for CRM tracking
import digitalpos # Integration with the POS engine to transition guests to a table
from decimal import Decimal # Ensuring financial precision for loyalty/tax logic
from datetime import datetime

# --- INTERNAL MODULE IMPORTS ---
from validator import (
    get_name, get_email, get_int, get_date, get_time, get_yes_no
)
from database import save_system_state # Persistence trigger
from hospitality_models import (
    Guest, Table, FloorMap, WaitlistManager
)
from models import SecurityLog, DailyLedger

# ==============================================================================
# MAIN ENGINE & LOGIC
# ==============================================================================

def main_front_desk(floor: FloorMap, waitlist: WaitlistManager):
    """
    The central coordinator. Orchestrates the flow from 
    Reservation (Intake) to Arrival (Seating).
    """
    print("\n" + "═"*45)
    print(f"║ {'GUEST INTAKE & RESERVATIONS' :^41} ║")
    print("═"*45)
    
    # 1. Gather Guest Data
    guest_obj = collect_guest_details()
    
    # 2. Transition to Seating Workflow
    handle_arrival(guest_obj, floor, waitlist)

def collect_guest_details():
    """
    UX: Collects and validates all guest information.
    Returns a hydrated Guest object ready for seating.
    """
    print("\n--- NEW RESERVATION ---")
    
    # 1. Collect Identity Information via the 'Input Shield' (validator.py)
    first_name = get_name("First Name: ") 
    last_name = get_name("Last Name: ")   
    email = get_email("Email Address: ")  
    
    # 2. Collect Contact Info (Must be exactly 10 digits for SMS notifications)
    phone = str(get_int("Mobile Number (10 digits): ", min_val=1000000000, max_val=9999999999))
    
    # 3. Collect Party Context
    adults = get_int("Number of Adults: ", min_val=1)
    children = get_int("Number of Children: ", min_val=0)
    total_party = adults + children
    
    # 4. Scheduling (Validated against business hours/dates)
    res_date = get_date("Date (MM/DD/YYYY): ")
    res_time = get_time("Time (11:00-21:00): ")
    
    # 5. Allergy Logic: Multi-item list builder
    allergies = []
    if get_yes_no("Does this party have food allergies? (y/n): "):
        print("Enter allergies one-by-one (Type 'DONE' to finish):")
        while True:
            item = input("> ").strip().title()
            if item.upper() == "DONE": break
            if item: allergies.append(item)

    # 6. Instantiate the Unified Guest Object
    # Use uuid to ensure every guest is unique even with the same name
    generated_id = f"GST-{str(uuid.uuid4())[:8].upper()}"
    new_guest = Guest(generated_id, first_name, last_name, phone, party_size=total_party)
    new_guest.allergies = allergies # Add the extra context
    
    print(f"✅ Reservation created for {new_guest.full_name} ({total_party} pax).")
    return new_guest

def find_best_table(floor: FloorMap, party_size: int) -> Table:
    """
    Algorithm: Finds the 'Best Fit' table.
    Prioritizes available tables that match the party size perfectly to save 
    larger tables for larger parties.
    """
    # Filter for available tables that can fit the party
    candidates = [t for t in floor.tables if t.status == "Available" and t.capacity >= party_size]
    
    if not candidates:
        return None # No room available
    
    # Sort by capacity so we use the smallest sufficient table first
    candidates.sort(key=lambda x: x.capacity)
    return candidates[0]

def handle_arrival(guest_obj: Guest, floor: FloorMap, waitlist: WaitlistManager):
    """
    Handles the physical seating of the guest or waitlist fallback.
    """
    print(f"\n--- SEATING: {guest_obj.full_name.upper()} ---")
    
    # Attempt to find a table
    assigned_table = find_best_table(floor, guest_obj.party_size)

    if assigned_table:
        # 1. Update the Table State
        assigned_table.seat_guest(guest_obj.guest_id)
        
        # 2. Update the Guest State
        guest_obj.is_seated = True
        guest_obj.assigned_table = assigned_table.table_id
        
        # 3. Security Audit
        SecurityLog.log_event("HOST_STATION", "GUEST_SEATED", 
                             f"Guest {guest_obj.guest_id} seated at Table {assigned_table.table_id}")
        
        print(f"✅ Table {assigned_table.table_id} assigned (Capacity: {assigned_table.capacity}).")
        
        # 4. POS Hand-off
        # Transitions the control to the ordering engine
        if get_yes_no("Launch POS for this table now? (y/n): "):
            digitalpos.run_pos(assigned_table.table_id, guest_obj)
    
        # NEW: Trigger persistence so seated guests survive a restart
        floor.save_floor_state() 
        print(f"💾 Floor state persisted to active_tables.json")

    else:
        # FALLBACK: Join the Waitlist if no tables match
        print(f"❌ SORRY: No tables available for a party of {guest_obj.party_size}.")
        if get_yes_no("Would you like to join the waitlist? (y/n): "):
            waitlist.add_to_wait(guest_obj, guest_obj.party_size)
            print("📝 You will be notified when a table opens.")

def cancel_reservation(guest_id: str, floor: FloorMap, waitlist: WaitlistManager):
    """
    Phase 4 (A): Instantly clears a session or waitlist entry.
    """
    # 1. Check if they are already seated
    for table in floor.tables:
        if table.current_guest_id == guest_id:
            table.clear_table() # Status becomes 'Dirty'
            print(f"🧹 Table {table.table_id} cleared. Staff notified for busing.")
            SecurityLog.log_event("FRONT_DESK", "SESSION_KILLED", f"Guest {guest_id} walked out.")
            return True

    # 2. Check the Waitlist
    initial_len = len(waitlist.queue)
    waitlist.queue = [entry for entry in waitlist.queue if entry.guest.guest_id != guest_id]
    
    if len(waitlist.queue) < initial_len:
        print(f"📝 Guest {guest_id} removed from Waitlist.")
        return True

    print("⚠️ Error: Guest ID not found in active sessions.")
    return False

# ==============================================================================
# KITCHEN & SERVICE UTILITIES
# ==============================================================================

def fire_to_kitchen(cart, table_num):
    """
    The 'Fire' command: Sends orders to the KDS (Kitchen Display System).
    """
    if not cart.items:
        print("⚠️ Order is empty. Nothing to fire.")
        return False

    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n🍳 KITCHEN TICKET GENERATED [{timestamp}]")
    print(f"TABLE: {table_num}")
    for item in cart.items:
        mods = f" ({', '.join([m.name for m in item.modifiers])})" if item.modifiers else ""
        print(f" > {item.name}{mods}")
    
    # In a full system, this would push to a 'data/kitchen_queue.json'
    print("✅ Order successfully sent to station printers.")
    return True