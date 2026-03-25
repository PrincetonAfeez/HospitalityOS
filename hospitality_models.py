"""
HospitalityOS v4.0 - Guest & Floor Models
-----------------------------------------
Guests (CRM), physical Table state, waitlist queue, and JSON persistence
so occupied tables can be rebuilt after a crash (best-effort without a DB).
"""

from __future__ import annotations  # Lets us type-hint Table before the class is defined if needed

import json  # Serialize table layouts to data/active_tables.json
import os  # Check saved JSON path exists
from datetime import date, datetime  # Guest milestones and waitlist timestamps
from decimal import Decimal  # Guest lifetime spend and loyalty math
from typing import Any, Dict, List, Optional  # Containers used across FOH logic

from pydantic import BaseModel, Field

from models import Person, SecurityLog  # Shared Person + audit logger
from storage import save_to_json  # Atomic feedback.json writes
from utils import PathManager, ACTIVE_TABLES_NAME, FEEDBACK_JSON_NAME


# ==============================================================================
# GUEST PROFILE — loyalty, tax flags, reliability counters
# ==============================================================================


class Guest(Person):
    """Guest extends Person with phone, party size, and CRM fields."""

    guest_id: str
    phone: str
    email: Optional[str] = None
    party_size: int = Field(default=2, ge=1)
    loyalty_points: int = 0
    total_spent: Decimal = Field(default=Decimal("0.00"))
    allergies: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    is_vip: bool = False
    birthday: Optional[date] = None
    anniversary: Optional[date] = None
    no_show_count: int = Field(default=0, ge=0)
    is_tax_exempt: bool = False
    is_seated: bool = False
    assigned_table: Optional[int] = None
    is_walk_in: bool = False

    @property
    def is_frequent_noshow(self) -> bool:
        """Hosts get warned after three recorded no-shows."""
        return self.no_show_count >= 3

    def add_loyalty_points(self, bill_amount: Decimal) -> None:
        """Award points from the closed check; auto-VIP over $1000 lifetime."""
        points_earned = 100 + int(bill_amount // 10)
        self.loyalty_points += points_earned
        self.total_spent += bill_amount
        if self.total_spent > 1000 and not self.is_vip:
            self.is_vip = True

    def apply_loyalty_discount(self, bill_total: Decimal) -> Decimal:
        """Spend 500 points to take $10 off bill_total; returns new total owed."""
        if self.loyalty_points >= 500:
            self.loyalty_points -= 500
            return max(Decimal("0.00"), bill_total - Decimal("10.00"))
        return bill_total

    def record_feedback(self, rating: int, comment: str) -> None:
        """Append one JSON object into data/feedback.json via the storage helper."""
        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "guest_id": self.guest_id,
            "guest_name": self.full_name,
            "rating": rating,
            "comment": comment,
        }
        save_to_json(feedback_entry, PathManager.get_path(FEEDBACK_JSON_NAME), merge_array=True)


# ==============================================================================
# TABLES & FLOOR MAP
# ==============================================================================


class Table(BaseModel):
    """One physical table: capacity, status, and optional seated guest id."""

    table_id: int
    capacity: int
    status: str = "Available"
    current_guest_id: Optional[str] = None

    def seat_guest(self, guest: Guest) -> bool:
        """Mark occupied if size fits; updates guest flags when successful."""
        if self.status == "Available" and guest.party_size <= self.capacity:
            self.status = "Occupied"
            self.current_guest_id = guest.guest_id
            guest.is_seated = True
            guest.assigned_table = self.table_id
            return True
        return False

    def clear_table(self) -> None:
        """After payment or reset, table needs bussing."""
        self.status = "Dirty"
        self.current_guest_id = None


class FloorMap:
    """Creates a fixed table_count layout and persists non-available tables to JSON."""

    def __init__(self, table_count: int = 20) -> None:
        self.tables: List[Table] = []
        for i in range(1, table_count + 1):
            cap = 4 if i > (table_count // 2) else 2
            self.tables.append(Table(table_id=i, capacity=cap))

    def save_floor_state(self) -> None:
        """Write every not-available table using Pydantic's JSON-safe dict (not raw __dict__)."""
        path = PathManager.get_path(ACTIVE_TABLES_NAME)
        active_data = [t.model_dump(mode="json") for t in self.tables if t.status != "Available"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(active_data, fh, indent=4)

    def restore_floor_state(self, guest_list: Optional[Dict[str, Guest]] = None) -> None:
        """
        Reload statuses from disk. guest_list maps guest_id -> Guest for deep linking;
        pass {} or None when no CRM session tracked guests yet.
        """
        registry = guest_list or {}
        path = PathManager.get_path(ACTIVE_TABLES_NAME)
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as fh:
            try:
                saved = json.load(fh)
            except json.JSONDecodeError:
                print("⚠️ Error: active_tables.json is corrupt. Starting with empty floor.")
                return
        for data in saved:
            table = next((t for t in self.tables if t.table_id == data["table_id"]), None)
            if not table:
                continue
            table.status = data["status"]
            table.current_guest_id = data.get("current_guest_id")
            gid = table.current_guest_id
            if gid and gid in registry:
                g = registry[gid]
                g.is_seated = True
                g.assigned_table = table.table_id


# ==============================================================================
# WAITLIST — FIFO-style queue of WaitlistEntry rows
# ==============================================================================


class WaitlistEntry(BaseModel):
    """One party waiting for a table with a timestamp for fairness tooling."""

    guest: Guest
    party_size: int
    entry_time: datetime = Field(default_factory=datetime.now)


class WaitlistManager(BaseModel):
    """add / seat / no-show helpers for the front host."""

    queue: List[WaitlistEntry] = Field(default_factory=list)

    def add_to_wait(self, guest: Guest) -> None:
        """Append a WaitlistEntry cloned from the guest's current party_size."""
        entry = WaitlistEntry(guest=guest, party_size=guest.party_size)
        self.queue.append(entry)
        print(f"📝 {guest.full_name} added to waitlist (Position: {len(self.queue)})")

    def seat_from_waitlist(self, guest_id: str, table: Table) -> bool:
        """Seat first matching guest_id and drop them from the queue."""
        for entry in self.queue:
            if entry.guest.guest_id == guest_id:
                table.seat_guest(entry.guest)
                self.queue.remove(entry)
                return True
        return False

    def mark_as_no_show(self, guest_id: str) -> bool:
        """Increment guest's counter, audit-log, and remove from queue."""
        for entry in self.queue:
            if entry.guest.guest_id == guest_id:
                entry.guest.no_show_count += 1
                SecurityLog.log_event(
                    "FRONT_DESK",
                    "NO_SHOW_RECORDED",
                    f"Guest {entry.guest.full_name} missed their slot. Total: {entry.guest.no_show_count}",
                )
                print(f"⚠️ {entry.guest.full_name} marked as No-Show. Total misses: {entry.guest.no_show_count}")
                self.queue.remove(entry)
                return True
        return False


def walk_in_guest_for_table(table_id: int, party_size: int = 1) -> Guest:
    """Synthetic guest when servers open a table from the main menu (no front-desk record)."""
    return Guest(
        guest_id=f"WALK-T{table_id:02d}",
        first_name="Walk",
        last_name=f"In Table {table_id}",
        phone="0000000000",
        party_size=party_size,
        is_walk_in=True,
    )
