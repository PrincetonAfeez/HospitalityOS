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
from typing import List, Optional, Dict
# Assuming these exist in your core models
from models import Person, SecurityLog

# ==============================================================================
# GUEST & LOYALTY (PHASE 3: GUEST 360)
# ==============================================================================

class Guest(Person):
    """
    Represents a customer with deep preference tracking and 
    automated loyalty tiering.
    """
    def __init__(self, guest_id: str, first_name: str, last_name: str, phone: str, party_size=2):
        # Initialize the base Person attributes (names, email logic)
        super().__init__(first_name, last_name) 
        self.guest_id = guest_id      # Unique ID (Database Key)
        self.phone = phone            # Primary contact for SMS alerts
        self.party_size = int(party_size) 
        
        # --- PHASE 3: CRM DATA POINTS ---
        self.loyalty_points = 0       # Current points balance
        self.total_spent = Decimal("0.00") # Lifetime value (LTV)
        self.allergies: List[str] = [] # Critical safety data
        self.preferences: List[str] = [] # "Window seat", "Quiet table", etc.
        self.is_vip = False           # Flag for high-spenders/regulars
        
        # --- STATUS FLAGS ---
        self.is_tax_exempt = False 
        self.is_seated = False 
        self.assigned_table = None 

    def add_loyalty_points(self, bill_amount: Decimal):
        """
        Logic Gate: Awards 100 points per booking + 1 point per $10.
        Automates VIP tagging based on spending thresholds ($1000+).
        """
        # Base points for showing up + points for spend
        points_earned = 100 + int(bill_amount // 10)
        self.loyalty_points += points_earned
        self.total_spent += bill_amount
        
        # PHASE 3 (D): Automated VIP Tagging
        if self.total_spent > 1000 and not self.is_vip:
            self.is_vip = True
            print(f"🎊 STATUS UPGRADE: {self.full_name} is now a VIP!")
            
        print(f"⭐ Loyalty: {self.full_name} earned {points_earned} pts. (Total: {self.loyalty_points})")

    def apply_loyalty_discount(self, bill_total: Decimal) -> Decimal:
        """
        Logic: Every 500 points = $10 discount.
        Returns the new total after deducting points.
        """
        if self.loyalty_points >= 500:
            discount = Decimal("10.00")
            self.loyalty_points -= 500
            print(f"🎟️ Loyalty Applied: $10.00 off for {self.full_name}.")
            return max(Decimal("0.00"), bill_total - discount)
        return bill_total

    def record_feedback(self, rating: int, comment: str):
        """
        PHASE 3 (B): Captures post-checkout experience to feedback.json.
        """
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "guest_id": self.guest_id,
            "guest_name": self.full_name,
            "rating": rating, # 1-5 Scale
            "comment": comment
        }
        
        path = "data/feedback.json"
        existing_data = []
        
        # Load existing feedback to append
        if os.path.exists(path):
            with open(path, "r") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []
        
        existing_data.append(feedback_entry)
        with open(path, "w") as f:
            json.dump(existing_data, f, indent=4)
        print(f"💬 Feedback recorded for {self.full_name}.")

# ==============================================================================
# FLOOR & QUEUE MANAGEMENT
# ==============================================================================

class Table:
    """Represents a physical table in the dining room."""
    def __init__(self, table_id: int, capacity: int):
        self.table_id = table_id 
        self.capacity = capacity 
        self.status = "Available" # Available, Occupied, Dirty, Reserved
        self.current_guest_id = None 

    def seat_guest(self, guest: Guest):
        """Seats a guest and updates their status flags."""
        if self.status == "Available" and guest.party_size <= self.capacity:
            self.status = "Occupied"
            self.current_guest_id = guest.guest_id
            guest.is_seated = True
            guest.assigned_table = self.table_id
            return True
        return False

    def clear_table(self):
        """Preps table for the 'Dirty' cycle before it can be reused."""
        self.status = "Dirty"
        self.current_guest_id = None

class FloorMap:
    """The master controller for all physical tables in the restaurant."""
    def __init__(self, table_count=20):
        self.tables: List[Table] = []
        # Dynamic layout: 2-tops for first half, 4-tops for second half
        for i in range(1, table_count + 1):
            cap = 4 if i > (table_count // 2) else 2
            self.tables.append(Table(i, cap))

    def save_floor_state(self):
        """PHASE 4 (10): Ensures seated guests survive a restart."""
        path = "data/active_tables.json"
        # Serialize only tables currently in use
        active_data = [t.__dict__ for t in self.tables if t.status != "Available"]
        with open(path, "w") as f:
            json.dump(active_data, f, indent=4)

    def restore_floor_state(self, guest_list: Dict[str, Guest]):
        """Restores the seating chart and re-links Guest objects to tables."""
        path = "data/active_tables.json"
        if os.path.exists(path):
            with open(path, "r") as f:
                try:
                    saved = json.load(f)
                    for data in saved:
                        table = next((t for t in self.tables if t.table_id == data['table_id']), None)
                        if table:
                            table.status = data['status']
                            table.current_guest_id = data['current_guest_id']
                            # Re-link the Guest status if they exist in the master list
                            if table.current_guest_id in guest_list:
                                g = guest_list[table.current_guest_id]
                                g.is_seated = True
                                g.assigned_table = table.table_id
                except json.JSONDecodeError:
                    print("⚠️ Error: active_tables.json is corrupt. Starting with empty floor.")