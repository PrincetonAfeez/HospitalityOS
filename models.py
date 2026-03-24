"""
HospitalityOS v4.0 - Core Financial & Inventory Models
Architect: Princeton Afeez
Description: Handles the 'Heavy Lifting' of the POS. Manages high-precision 
             financials, inventory deductions, and Labor Law compliance.
"""

import os
import json
import uuid
import copy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

# Standardized imports from settings to ensure system-wide consistency
from settings.restaurant_defaults import (
    GRATUITY_RATE, GRATUITY_THRESHOLD, 
    TAX_RATE, MIN_WAGE, MAX_MODS
)

# ==============================================================================
# SECURITY & BASE IDENTITY
# ==============================================================================

class SecurityLog:
    """Requirement: Objective 4 - Provides an immutable forensic audit trail."""
    @staticmethod
    def log_event(staff_id: str, action: str, details: str) -> None:
        """Captures a timestamped entry of high-risk actions (voids, comps, logins)."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Generate current time
        log_entry = f"[{timestamp}] STAFF: {staff_id} | ACTION: {action} | DETAILS: {details}\n"
        try:
            # Append mode 'a' ensures we never overwrite previous history
            with open("data/logs/security.log", "a") as f:
                f.write(log_entry) # Commit string to the flat file
        except OSError:
            # Silent failure prevents a disk error from crashing the whole POS
            pass 

class Person:
    """Abstract identity model to handle naming conventions across the system."""
    def __init__(self, first_name: str, last_name: str):
        # .strip() removes accidental spaces; .title() ensures 'smith' becomes 'Smith'
        self.first_name = first_name.strip().title()
        self.last_name = last_name.strip().title()

    @property
    def full_name(self):
        """Helper to return a formatted string for receipts and badges."""
        return f"{self.first_name} {self.last_name}"

# ==============================================================================
# MENU & INVENTORY MODELS
# ==============================================================================

class Modifier:
    """Represents a kitchen modification (e.g., 'No Onions' or 'Add Bacon')."""
    def __init__(self, name: str, price: float = 0.00):
        self.name = name.strip().title() # Format the name for the kitchen ticket
        self.price = Decimal(str(price)) # Ensure price is a Decimal for math safety

    def to_dict(self):
        """Converts object to dictionary for JSON persistence."""
        return {"name": self.name, "price": str(self.price)}

class MenuItem:
    """The fundamental data object for every product sold in the restaurant."""
    def __init__(self, name, price, category, walk_in, freezer, par_level=10, line_inv=0, station="Kitchen"):
        self.name = name.strip() # The display name
        self.price = Decimal(str(price)) # Retail price
        self.category = category # Reporting category (e.g., Appetizer)
        self.walk_in_inv = int(walk_in) # Backup stock
        self.freezer_inv = int(freezer) # Frozen stock
        self.par_level = int(par_level) # The reorder threshold
        self.line_inv = int(line_inv) # Items currently on the prep line
        self.station = station.strip().title() # Routing info (e.g., Grill, Bar)
        self.modifiers: List[Modifier] = [] # Container for mods (max 3)
        self.is_active = True # Seasonal toggle
        self.units_sold = 0 # Daily sales counter

    def clone(self) -> 'MenuItem':
        """Deep copies the item so 'Table 1 Burger' mods don't affect 'Table 5 Burger'."""
        return copy.deepcopy(self)

    def to_dict(self):
        """Serializes the item for the 'Shared Brain' JSON state."""
        return {
            "name": self.name,
            "price": str(self.price),
            "line_inv": self.line_inv,
            "modifiers": [m.to_dict() for m in self.modifiers]
        }

# ==============================================================================
# FINANCIAL CORE (CART & TRANSACTION)
# ==============================================================================

class Cart:
    """The active shopping container for a table session."""
    def __init__(self, guest=None):
        self.items: List[MenuItem] = [] # List of MenuItem clones
        self.guest = guest # The Guest object associated with this bill
        self.tax_rate = Decimal(str(TAX_RATE)) # Global tax from settings
        self.gratuity_rate = Decimal(str(GRATUITY_RATE)) # Global grat rate

    def add_to_cart(self, master_item: MenuItem):
        """Validates stock, decrements inventory, and adds a clone to the bill."""
        if master_item.line_inv <= 0:
            # Stop the transaction if the kitchen is out of stock
            raise Exception(f"86 ALERT: {master_item.name} is out of stock!")
        
        master_item.line_inv -= 1 # Deduct from the master 'Shared Brain'
        master_item.units_sold += 1 # Increment sales data
        self.items.append(master_item.clone()) # Add the independent copy to cart

    @property
    def subtotal(self) -> Decimal:
        """Calculates the sum of all items plus their specific modifiers."""
        total = Decimal("0.00")
        for item in self.items:
            total += item.price # Add base item price
            total += sum(m.price for m in item.modifiers) # Add each modifier's price
        return total

    @property
    def sales_tax(self) -> Decimal:
        """Calculates tax; returns 0.00 if the guest is flagged as Tax Exempt."""
        if self.guest and getattr(self.guest, 'is_tax_exempt', False):
            return Decimal("0.00")
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def auto_gratuity(self) -> Decimal:
        """Calculates 18% gratuity if party size meets the threshold (e.g., 6+)."""
        if self.guest and getattr(self.guest, 'party_size', 1) >= GRATUITY_THRESHOLD:
            return (self.subtotal * self.gratuity_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00")

    @property
    def grand_total(self) -> Decimal:
        """The total amount due: Subtotal + Tax + Auto-Gratuity."""
        return self.subtotal + self.sales_tax + self.auto_gratuity

class Transaction:
    """The immutable historical record generated at checkout."""
    def __init__(self, cart: Cart, table_num: int, staff: 'Staff'):
        self.txn_id = str(uuid.uuid4())[:8].upper() # Create a unique 8-char receipt ID
        self.cart = cart # Capture the cart snapshot
        self.table_num = table_num # Record the table location
        self.staff = staff # Attributed employee for commission/audits
        self.tip = Decimal("0.00") # Start with zero tip
        self.timestamp = datetime.now() # Record precise checkout time

    def apply_tip(self, amount_str: str) -> bool:
        """Parses a string input (e.g., '$5' or '20%') and sets the tip value."""
        try:
            clean = amount_str.replace("$", "").replace("%", "").strip()
            if "%" in amount_str:
                self.tip = (self.cart.subtotal * (Decimal(clean) / 100)).quantize(Decimal("0.01"))
            else:
                self.tip = Decimal(clean).quantize(Decimal("0.01"))
            return True
        except:
            return False # Return False to trigger a retry in the UI

    def to_dict(self):
        """Serializes transaction data for the permanent daily log."""
        return {
            "txn_id": self.txn_id,
            "staff": self.staff.full_name,
            "subtotal": str(self.cart.subtotal),
            "tax": str(self.cart.sales_tax),
            "tip": str(self.tip),
            "total": str(self.cart.grand_total + self.tip),
            "timestamp": self.timestamp.isoformat()
        }

# ==============================================================================
# LABOR & STAFF
# ==============================================================================

class Staff(Person):
    """Employee model featuring CA-compliant labor math."""
    def __init__(self, staff_id, first_name, last_name, dept, role, hourly_rate):
        super().__init__(first_name, last_name) # Call parent name logic
        self.staff_id = staff_id # Unique Employee ID
        self.dept = dept.upper() # e.g., FOH or BOH
        self.role = role.title() # e.g., Server or Manager
        self.hourly_rate = Decimal(str(hourly_rate)) # Base pay rate
        self.shift_start: Optional[datetime] = None # Timestamped at login
        self.shift_end: Optional[datetime] = None # Timestamped at logout
        self.had_break = True # Compliance flag for meal breaks

    def clock_in(self):
        """Sets the start of the labor session."""
        self.shift_start = datetime.now()

    def clock_out(self):
        """Sets the end of the labor session."""
        self.shift_end = datetime.now()

    def calculate_shift_pay(self) -> Decimal:
        """Calculates pay including 1.5x OT after 8 hours and meal penalties."""
        if not self.shift_start or not self.shift_end:
            return Decimal("0.00")
        
        delta = self.shift_end - self.shift_start # Find duration
        hrs = Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"))
        
        # Calculate Base vs Overtime pay
        if hrs <= 8:
            pay = hrs * self.hourly_rate
        else:
            pay = (8 * self.hourly_rate) + ((hrs - 8) * self.hourly_rate * Decimal("1.5"))
            
        # California Labor Law: 1 hour penalty pay if shift > 6h and no break was taken
        if hrs > 6 and not self.had_break:
            pay += self.hourly_rate
            
        return pay.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @classmethod
    def from_dict(cls, data):
        """Rebuilds a Staff object from saved JSON data."""
        return cls(data["staff_id"], data["first_name"], data["last_name"], 
                   data["dept"], data["role"], data["hourly_rate"])