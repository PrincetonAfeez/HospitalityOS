"""
HospitalityOS v4.0 - Digital Front Desk
Architect: Princeton Afeez
Description: Manages the Front-of-House (FOH) intake. Handles reservations, 
             party size calculations, and the transition of guests to the POS.
"""

import uuid   # Used to generate unique 8-character Guest IDs for CRM tracking
import digitalpos # Integration with the POS engine to transition guests to a table
from decimal import Decimal # Ensuring financial precision for loyalty/tax logic
from datetime import date, datetime

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

def trigger_guest_alerts(guest: Guest):
    """
    Scans the guest profile for milestones and operational warnings.
    """
    today = date.today()
    alerts = []

    # 1. Birthday Check (Month & Day match)
    if guest.birthday and guest.birthday.month == today.month and guest.birthday.day == today.day:
        alerts.append("🎂 BIRTHDAY TODAY: Offer complimentary dessert!")

    # 2. Anniversary Check
    if guest.anniversary and guest.anniversary.month == today.month and guest.anniversary.day == today.day:
        alerts.append("🥂 ANNIVERSARY: Offer champagne toast!")

    # 3. Reliability Warning (Task 4)
    if guest.is_frequent_noshow:
        alerts.append("⚠️ ATTENTION: Frequent No-Show (Credit Card Guarantee Required)")

    # 4. VIP Status
    if guest.is_vip:
        alerts.append("💎 VIP GUEST: Priority seating and Manager greeting requested.")

    if alerts:
        print("\n" + "█" * 60)
        print(f"  ALERTS FOR {guest.full_name.upper()}")
        for msg in alerts:
            print(f"  >> {msg}")
        print("█" * 60 + "\n")

# ==============================================================================
# UPDATED COLLECTION LOGIC
# ==============================================================================

def collect_guest_details() -> Guest:
    """
    Refactored to capture Birthday/Anniversary and return a Pydantic Guest object.
    """
    print("\n--- NEW RESERVATION ---")
    first_name = get_name("First Name: ") 
    last_name = get_name("Last Name: ")   
    phone = str(get_int("Mobile Number (10 digits): ", min_val=1000000000, max_val=9999999999))
    
    adults = get_int("Number of Adults: ", min_val=1)
    children = get_int("Number of Children: ", min_val=0)
    total_party = adults + children
    
    # --- TASK 3: Capture Milestone Data ---
    bday = None
    if get_yes_no("Is there a Birthday on file? (y/n): "):
        bday = get_date("Enter Birthday (MM/DD/YYYY): ")

    anniv = None
    if get_yes_no("Is there an Anniversary on file? (y/n): "):
        anniv = get_date("Enter Anniversary (MM/DD/YYYY): ")

    allergies = []
    if get_yes_no("Any food allergies? (y/n): "):
        print("Enter allergies (Type 'DONE' to finish):")
        while True:
            item = input("> ").strip().title()
            if item.upper() == "DONE": break
            if item: allergies.append(item)

    # Instantiate via Pydantic (No manual __init__ needed)
    generated_id = f"GST-{str(uuid.uuid4())[:8].upper()}"
    
    return Guest(
        guest_id=generated_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        party_size=total_party,
        birthday=bday,
        anniversary=anniv,
        allergies=allergies
    )

def handle_arrival(guest_obj: Guest, floor: FloorMap, waitlist):
    """
    Enhanced seating workflow with automated alerts.
    """
    # TRIGGER ALERTS IMMEDIATELY UPON ARRIVAL
    trigger_guest_alerts(guest_obj)

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