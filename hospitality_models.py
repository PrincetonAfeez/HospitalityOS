"""
HospitalityOS v4.0 - Guest & Floor Models
Architect: Princeton Afeez
Description: Handles the physical mapping of the restaurant. 
             Manages seating, reservations, and guest loyalty data.
"""

import os
import json
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from models import Person, SecurityLog

# ==============================================================================
# GUEST & LOYALTY
# ==============================================================================

class Guest(Person):
    """Represents a customer with preferences and tax-exempt status tracking."""
    def __init__(self, guest_id: str, first_name: str, last_name: str, phone: str, party_size=2):
        super().__init__(first_name, last_name) # Initialize name logic
        self.guest_id = guest_id # Unique identifier (e.g., Phone number)
        self.phone = phone # Contact info
        self.party_size = int(party_size) # Size of the group
        self.loyalty_points = 0 # Reward tracker
        self.is_tax_exempt = False # Toggle for Non-Profits/Entities
        self.is_seated = False # Status flag for the FloorMap
        self.assigned_table = None # Table ID link

    def add_loyalty_points(self, amount: Decimal):
        """Awards 1 point for every $10 spent."""
        points = int(amount // 10)
        self.loyalty_points += points
        print(f"⭐ Loyalty: {self.full_name} earned {points} points.")

    def toggle_tax_exempt(self):
        """Switches tax status and logs the event for administrative audit."""
        self.is_tax_exempt = not self.is_tax_exempt
        status = "ENABLED" if self.is_tax_exempt else "DISABLED"
        SecurityLog.log_event("MANAGER", "TAX_TOGGLE", f"Guest {self.guest_id} set to {status}")

# ==============================================================================
# FLOOR & TABLE MANAGEMENT
# ==============================================================================

class Table:
    """Represents a physical table in the dining room."""
    def __init__(self, table_id: int, capacity: int):
        self.table_id = table_id # The number on the table
        self.capacity = capacity # Max guests allowed
        self.status = "Available" # Available, Occupied, Dirty, Reserved
        self.current_guest_id = None # Link to the seated guest

    def seat_guest(self, guest_id: str):
        """Changes status to Occupied and links the guest ID."""
        if self.status == "Available":
            self.status = "Occupied"
            self.current_guest_id = guest_id
            return True
        return False

    def clear_table(self):
        """Resets table status for the next party."""
        self.status = "Dirty" # Requires cleaning before 'Available'
        self.current_guest_id = None

class FloorMap:
    """The master controller for all physical tables in the restaurant."""
    def __init__(self, table_count=20):
        # Dynamically create tables: half 2-tops, half 4-tops
        self.tables: List[Table] = []
        for i in range(1, table_count + 1):
            cap = 4 if i > (table_count // 2) else 2
            self.tables.append(Table(i, cap))

    def save_floor_state(self):
        """Persists the current seating chart to a JSON file."""
        path = "data/active_tables.json"
        # Only save tables that aren't empty
        active_data = [t.__dict__ for t in self.tables if t.status != "Available"]
        with open(path, "w") as f:
            json.dump(active_data, f, indent=4)

    def restore_floor_state(self):
        """Reads the JSON file to re-seat guests after a system restart."""
        path = "data/active_tables.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                saved = json.load(f)
                for data in saved:
                    # Match the saved ID to the live table object
                    table = next((t for t in self.tables if t.table_id == data['table_id']), None)
                    if table:
                        table.status = data['status']
                        table.current_guest_id = data['current_guest_id']

# ==============================================================================
# QUEUE MANAGEMENT
# ==============================================================================

class WaitlistEntry:
    """A record of a party waiting for an available table."""
    def __init__(self, guest: Guest, party_size: int, quoted_mins: int):
        self.guest = guest # The Guest object
        self.party_size = party_size # How many people
        self.arrival_time = datetime.now() # When they walked in
        self.quoted_wait = quoted_mins # The host's estimate

class WaitlistManager:
    """Orchestrates the queue and wait-time estimations."""
    def __init__(self):
        self.queue: List[WaitlistEntry] = []

    def add_to_wait(self, guest: Guest, party_size: int):
        """Calculates an estimate (10m per party ahead) and adds to queue."""
        est = len(self.queue) * 10
        self.queue.append(WaitlistEntry(guest, party_size, est))
        print(f"📝 {guest.full_name} added to wait. Est: {est} mins.")