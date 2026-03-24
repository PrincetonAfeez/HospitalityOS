"""
HospitalityOS v4.0 - Guest & Floor Models
Refactor: Integrated Pydantic and added Milestone/No-Show Tracking.
"""

import os
import json
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator

# Inheriting from our newly refactored Pydantic Person model
from models import Person, SecurityLog
# Use our thread-safe storage for the feedback logic
from storage import save_to_json

# In your main boot sequence or launcher
waitlist = WaitlistManager()

# ==============================================================================
# GUEST & LOYALTY (PHASE 3: GUEST 360)
# ==============================================================================

class Guest(Person):
    """
    Enhanced Guest profile with Milestone alerts and Reliability tracking.
    """
    guest_id: str
    phone: str
    party_size: int = Field(default=2, ge=1)
    
    # --- CRM DATA POINTS (Commit 4) ---
    loyalty_points: int = 0
    total_spent: Decimal = Field(default=Decimal("0.00"))
    allergies: List[str] = []
    preferences: List[str] = []
    is_vip: bool = False
    
    # New Milestone Fields
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    
    # New Reliability Tracking
    no_show_count: int = Field(default=0, ge=0)
    
    # --- STATUS FLAGS ---
    is_tax_exempt: bool = False 
    is_seated: bool = False 
    assigned_table: Optional[int] = None

    @property
    def is_frequent_noshow(self) -> bool:
        """Requirement: Flag guests with 3+ no-shows for host alerts."""
        return self.no_show_count >= 3

    def add_loyalty_points(self, bill_amount: Decimal):
        """Awards points and automates VIP tagging ($1000+)."""
        points_earned = 100 + int(bill_amount // 10)
        self.loyalty_points += points_earned
        self.total_spent += bill_amount
        
        if self.total_spent > 1000 and not self.is_vip:
            self.is_vip = True
            
    def apply_loyalty_discount(self, bill_total: Decimal) -> Decimal:
        """Every 500 points = $10 discount."""
        if self.loyalty_points >= 500:
            self.loyalty_points -= 500
            return max(Decimal("0.00"), bill_total - Decimal("10.00"))
        return bill_total

    def record_feedback(self, rating: int, comment: str):
        """Captures post-checkout experience using thread-safe storage."""
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "guest_id": self.guest_id,
            "guest_name": self.full_name,
            "rating": rating,
            "comment": comment
        }
        # Use the thread-safe save logic from Commit 3
        save_to_json(feedback_entry, "data/feedback.json")

# ==============================================================================
# FLOOR & QUEUE MANAGEMENT
# ==============================================================================

class Table(BaseModel):
    """Represents a physical table in the dining room."""
    table_id: int
    capacity: int
    status: str = "Available" # Available, Occupied, Dirty, Reserved
    current_guest_id: Optional[str] = None

    def seat_guest(self, guest: Guest):
        if self.status == "Available" and guest.party_size <= self.capacity:
            self.status = "Occupied"
            self.current_guest_id = guest.guest_id
            guest.is_seated = True
            guest.assigned_table = self.table_id
            return True
        return False

    def clear_table(self):
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

                    """
HospitalityOS v4.0 - Waitlist Logic
Requirement: Task 4 - Automated No-Show tagging and queue management.
"""

class WaitlistEntry(BaseModel):
    """Represents a single party waiting for a table."""
    guest: Guest
    party_size: int
    entry_time: datetime = Field(default_factory=datetime.now)

class WaitlistManager(BaseModel):
    """The master controller for the FOH queue."""
    queue: List[WaitlistEntry] = []

    def add_to_wait(self, guest: Guest):
        """Adds a guest to the digital queue."""
        entry = WaitlistEntry(guest=guest, party_size=guest.party_size)
        self.queue.append(entry)
        print(f"📝 {guest.full_name} added to waitlist (Position: {len(self.queue)})")

    def seat_from_waitlist(self, guest_id: str, table: Any):
        """Standard flow: Guest arrived and is being seated."""
        for entry in self.queue:
            if entry.guest.guest_id == guest_id:
                table.seat_guest(entry.guest)
                self.queue.remove(entry)
                return True
        return False

    def mark_as_no_show(self, guest_id: str):
        """
        TASK 4: Increments the guest's no-show counter and removes them.
        This triggers the 'is_frequent_noshow' alert in DigitalFrontDesk.
        """
        for entry in self.queue:
            if entry.guest.guest_id == guest_id:
                # 1. Update the counter on the Guest object
                entry.guest.no_show_count += 1
                
                # 2. Log for security audit
                SecurityLog.log_event("FRONT_DESK", "NO_SHOW_RECORDED", 
                                     f"Guest {entry.guest.full_name} missed their slot. Total: {entry.guest.no_show_count}")
                
                print(f"⚠️ {entry.guest.full_name} marked as No-Show. Total misses: {entry.guest.no_show_count}")
                
                # 3. Remove from active queue
                self.queue.remove(entry)
                return True
        return False