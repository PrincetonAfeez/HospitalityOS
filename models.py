"""
Project: Hospitality OS - Data Models
Description: This module defines the architectural blueprints for the system. 
             It uses Decimal for financial precision and includes business 
             logic for inventory, tax, and California-compliant labor tracking.
"""
import uuid # Standard library for generating unique, non-sequential transaction IDs
import json # Used for serializing objects into the 'Shared Brain' JSON state
import copy # Essential for deep-copying MenuItems to prevent shared state bugs in carts
from datetime import datetime # Core utility for timestamping sales and clock-ins
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation # Industry standard for financial rounding precision
from typing import List, Optional

from HospitalityOS.settings.restaurant_defaults import GRATUITY_RATE, GRATUITY_THRESHOLD


# Try-Except block to handle missing settings during initial environment setup
try:
    from settings.restaurant_defaults import TAX_RATE, MIN_WAGE, MAX_MODS
except ImportError:
    TAX_RATE = Decimal("0.095")
    MIN_WAGE = Decimal("18.00")
    MAX_MODS = 3

# Type Hinting: Prevents circular imports while allowing IDE autocompletion
from typing import TYPE_CHECKING, List, Optional
if TYPE_CHECKING:
    from digitalfrontdesk import Guest # Only for type hints, not actual code execution

# ==============================================================================
# BASE EXCEPTIONS & SECURITY MODELS
# ==============================================================================

class HospitalityError(Exception):
    """The root exception for the entire OS; allows for broad 'catch-all' safety nets."""
    pass

class InsufficientStockError(HospitalityError):
    """Triggered by InventoryManager when a 'line_inv' hits zero (86'd items)."""
    pass

class TableAssignmentError(HospitalityError):
    """Prevents hosting logic from double-booking a physical table."""
    pass

class SecurityLog:
    """Requirement: Objective 4 - Provides an immutable audit trail for forensic review."""
    LOG_FILE = "security.log"

    @staticmethod
    def log_event(staff_id: str, action: str, details: str) -> None:
        """Writes a timestamped security entry to a flat file for admin audit."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Human-readable time
        log_entry = f"[{timestamp}] STAFF: {staff_id} | ACTION: {action} | DETAILS: {details}\n"
        
        try:
            with open(SecurityLog.LOG_FILE, "a") as f: # Append mode to preserve history
                f.write(log_entry) # Commit to disk
        except OSError as e:
            print(f"[SECURITY WARNING] Audit trail could not be written: {e}")
        print(f"[SECURITY] Event Logged: {action}") # Real-time console feedback


class Person:
    """Abstract base class to handle common identity logic (DRY Principle)."""
    def __init__(self, first_name: str, last_name: str):
        self.first_name = first_name.strip().title() # Auto-correct casing
        self.last_name = last_name.strip().title() # Auto-correct casing

    @property
    def full_name(self):
        """Convenience property for printing receipts and employee badges."""
        return f"{self.first_name} {self.last_name}"
    
# ==============================================================================
# GUEST MODEL (Domain: Front Desk)
# ==============================================================================
      
class Guest(Person):
    """
    Requirement 7-8, 40, 42: Guest Identity Logic.
    Centralized here to keep the core models.py focused on Staff and Inventory.
    """
    def __init__(self, guest_id: str, first_name: str, last_name: str, phone: int, party_size=2, allergies: list[str] = None) -> None:
        # Initialize the 'Person' base class (Commit 1 logic)
        super().__init__(first_name, last_name)
        
        self.guest_id: str = guest_id 
        self.phone: int = phone 
        self.allergies: list[str] = allergies if allergies else [] 
        self.loyalty_points: int = 0 
        self.is_tax_exempt: bool = False
        self.party_size = max(1, int(party_size))
        self.is_seated = False
        self.assigned_table = None
        self.is_tax_exempt = False # Default to False for everyone 

    def to_dict(self):
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "party_size": self.party_size,
            "is_seated": self.is_seated
        }
        
    def add_loyalty_points(self, bill_subtotal: Decimal) -> None:
        """Task 8: Award 1 point per $10 of spend using floor division."""
        points_earned = int(bill_subtotal // 10)
        self.loyalty_points += points_earned
        print(f"⭐ Loyalty: {self.full_name} earned {points_earned} points.")

    def toggle_tax_exempt(self) -> None:
        """Task 40: Manual override for tax-exempt entities."""
        self.is_tax_exempt = not self.is_tax_exempt
        status = "ENABLED" if self.is_tax_exempt else "DISABLED"
        print(f"Tax Exempt status for {self.full_name}: {status}")

    def get_discount_multiplier(self, percentage):
        """Task 42: Math helper to apply percentages (e.g., 20% -> 0.8)."""
        discount = Decimal(str(percentage)) / 100 # Convert to decimal ratio
        return (Decimal("1.00") - discount) # Return the remaining multiplier

    def toggle_tax_exempt(self) -> None:
        """
        Commit 40: Manual override for tax-exempt entities.
        Requires verification of ID/Form at the table.
        """
        self.is_tax_exempt = not self.is_tax_exempt
        status = "ENABLED" if self.is_tax_exempt else "DISABLED"
        print(f"Tax Exempt status for {self.full_name}: {status}")
        # Log this for audit purposes (High-risk action)
        SecurityLog.log_event("MANAGER_OVERRIDE", "TAX_EXEMPT_TOGGLE", f"Guest {self.guest_id} set to {status}")

class Reservation:
    """
    Commit 33: The Reservation Engine.
    Links a guest to a future time slot.
    """
    def __init__(self, guest: Guest, res_date, res_time, table_id=None):
        self.guest = guest
        self.res_date = res_date # datetime.date object
        self.res_time = res_time # datetime.time object
        self.table_id = table_id # Assigned at booking or arrival
        self.is_confirmed = True

    def __repr__(self):
        return f"Res: {self.guest.last_name} | {self.res_date} @ {self.res_time}"

class WaitlistEntry:
    """Represents a party waiting for a table."""
    def __init__(self, guest: 'Guest', party_size: int, quoted_mins: int):
        self.guest = guest
        self.party_size = party_size
        self.arrival_time = datetime.now()
        self.quoted_wait = quoted_mins
        self.is_notified = False

    @property
    def current_wait_time(self) -> int:
        """Calculates how many minutes the guest has actually been waiting."""
        delta = datetime.now() - self.arrival_time
        return int(delta.total_seconds() // 60)

class WaitlistManager:
    """Handles the queue when the restaurant is at capacity."""
    def __init__(self):
        self.queue: List[WaitlistEntry] = []

    def add_to_waitlist(self, guest: 'Guest', party_size: int):
        # Basic logic: 10 mins per party already waiting
        estimated_wait = len(self.queue) * 10 
        entry = WaitlistEntry(guest, party_size, estimated_wait)
        self.queue.append(entry)
        print(f"📝 {guest.full_name} added to waitlist. Est. wait: {estimated_wait} mins.")
        return entry

    def get_next_fit(self, capacity: int) -> Optional[WaitlistEntry]:
        """Finds the first party in the queue that fits an available table capacity."""
        for entry in self.queue:
            if entry.party_size <= capacity:
                return entry
        return None

    def remove_guest(self, guest_id: str):
        self.queue = [e for e in self.queue if e.guest.guest_id != guest_id]

class Table:
    """
    Commit 31: Physical Asset Model.
    Tracks seating capacity and real-time availability.
    """
    def __init__(self, table_id: int, capacity: int):
        self.table_id = table_id
        self.capacity = capacity
        self.status = "Available"  # Available, Occupied, Dirty, Reserved
        self.current_guest_id = None

    def seat_guest(self, guest_id: str):
        if self.status == "Available":
            self.status = "Occupied"
            self.current_guest_id = guest_id
            return True
        return False

    def clear_table(self):
        """Transition to Dirty after a guest leaves."""
        self.status = "Dirty"
        self.current_guest_id = None

    def to_dict(self):
        return {
            "table_id": self.table_id,
            "capacity": self.capacity,
            "status": self.status,
            "guest_id": self.current_guest_id
        }
    
    def __repr__(self):
        return f"Table {self.table_id} ({self.capacity}-top)"

# ==============================================================================
# MENU & MODIFIER MODELS
# ==============================================================================

class Modifier:
    """Represents an add-on item that modifies the base price and name of a dish."""
    def __init__(self, name: str, price: float = 0.00):
        self.name = name.strip().title() # Normalize text (e.g., 'extra cheese')
        self.price = Decimal(str(price)) # Force Decimal for financial safety

    def __str__(self):
        """Standardizes how the modifier looks on the Receipt/Cart UI."""
        return f" +{self.name} (${self.price:.2f})"
    
    def to_dict(self):
        """Converts object to JSON-serializable format for persistence."""
        return {"name": self.name, "price": str(self.price)}

class MenuItem:
    """The granular data object for every SKU sold in the restaurant."""
    def __init__(self, name, price, category, walk_in, freezer, par_level=10, line_inv=0, station="Kitchen"):
        self.category = category # Category for sales reporting (e.g., 'Liquor')
        self.name = name.strip() # The display name for the POS
        self.price = Decimal(str(price)) if Decimal(str(price)) > 0 else Decimal("0.00")
        self.category = category # Base retail cost
        self.walk_in_inv = int(walk_in) # Backup stock in refrigeration
        self.freezer_inv = int(freezer) # Long-term storage stock
        self.par_level = max(0, par_level)  # The 'Reorder Point' for prep lists
        self.line_inv = max(0, line_inv) # Immediate stock available to the chef
        self.modifiers: List[Modifier] = [] # List limited to 3 items per business rules
        self.kitchen_notes = "" # Special prep instructions (e.g., 'Allergy')
        self.is_active = True # Soft-delete flag for seasonal items
        self.units_sold: int = 0 # Tracks actual sales volume for analytics
        self.station = station.strip().title() # e.g., 'Grill', 'Salad', 'Bar'
        self.order_time: Optional[datetime] = None # Tracked when sent to KDS

    def add_modifier(self, mod: Modifier):
        """Enforces the modifier cap (MAX_MODS from settings) to limit order complexity."""
        if len(self.modifiers) < MAX_MODS:
            self.modifiers.append(mod)
            return True
        return False

    def is_low_stock(self) -> bool:
        """
        Commit 14: Returns True if line inventory is 
        below 25% of the designated Par Level.
        """
        if self.par_level <= 0:
            return False
        return self.line_inv < (self.par_level * 0.25)

    def get_inventory_status(self) -> str:
        """
        Commit 14: Returns a human-readable status 
        label for the kitchen display.
        """
        if self.line_inv <= 0:
            return "86'D (OUT)"
        if self.is_low_stock():
            return "CRITICAL LOW"
        if self.line_inv < self.par_level:
            return "UNDER PAR"
        return "STOCKED"

    @property
    def total_inventory(self):
        """Computed property summing all storage locations for a macro view."""
        return self.line_inv + self.walk_in_inv + self.freezer_inv

    def clone(self) -> 'MenuItem':
        """Deep copies the item so modifying a Burger in Table 1 doesn't affect Table 2."""
        return copy.deepcopy(self)

    def to_dict(self):
        """Deep serialization including nested modifiers for the 'Shared Brain'."""
        return {
            "name": self.name,
            "price": str(self.price),
            "modifiers": [m.to_dict() for m in self.modifiers],
            "line_inv": self.line_inv
        }

class Menu:
    """
    Commit 15: Enhanced Lookup Logic.
    Distinguishes between missing items and 86'd (inactive) items.
    """
    def __init__(self):
        self.items = {} 

    def add_item(self, item: MenuItem):
        clean_name = item.name.strip().lower()
        if clean_name in self.items:
            print(f"⚠️ Warning: {item.name} already exists. This will overwrite existing data.")
        
        self.items[clean_name] = item

    def find_item(self, name: str, include_inactive: bool = False) -> Optional[MenuItem]:
        """
        Commit 15: Flexible lookup. By default, hides 86'd items
        unless include_inactive is set to True (for Admin/Chef views).
        """
        if not name:
            return None
            
        target = name.strip().lower()
        item = self.items.get(target)
        
        if item:
            if not item.is_active and not include_inactive:
                return None # Still hides from Guest/Server by default
            return item
        return None

    def get_active_menu(self) -> List[MenuItem]:
        """Commit 15: Helper to return only items currently for sale."""
        return [i for i in self.items.values() if i.is_active]

    def validate_integrity(self):
        """
        Commit 30: Database Integrity Check.
        Scans all loaded items for logical errors and repairs them.
        Returns a count of repairs made.
        """
        repairs = 0
        for item in self.items.values():
            # Rule 1: Inventory cannot be below zero
            if item.line_inv < 0:
                item.line_inv = 0
                repairs += 1
            
            # Rule 2: Prices must be Decimal and non-negative
            if not isinstance(item.price, Decimal) or item.price < 0:
                item.price = Decimal("0.00")
                repairs += 1
                
        if repairs > 0:
            print(f"🛠️ Integrity Check: {repairs} data points repaired for stability.")
        else:
            print("✅ Integrity Check: Data healthy.")
        return repairs
    
# ==============================================================================
# LABOR & STAFF MODELS
# ==============================================================================

class KDSManager:
    """Requirement: Objective 12 - Digital Ticket Routing."""
    def __init__(self):
        self.active_tickets = [] # List of 'tickets' (dicts or objects)

    def route_order(self, cart: 'Cart', table_num: int):
        """
        Commit 38: Breaks a cart into station-specific tickets.
        Ensures the Bar doesn't see Salad orders and vice-versa.
        """
        timestamp = datetime.now()
        stations_involved = {item.station for item in cart.items}
        
        for station in stations_involved:
            station_items = [i for i in cart.items if i.station == station]
            ticket = {
                "ticket_id": str(uuid.uuid4())[:6].upper(),
                "table": table_num,
                "station": station,
                "items": [i.name for i in station_items],
                "time_in": timestamp,
                "status": "Pending"
            }
            self.active_tickets.append(ticket)
            print(f"📠 KDS: Ticket sent to {station} for Table {table_num}")

    def get_station_view(self, station_name: str):
        """Returns only tickets for a specific screen (e.g., the Bar tablet)."""
        return [t for t in self.active_tickets if t["station"] == station_name.title()]

class Staff(Person):
    """Represents an employee with CA labor-compliant payroll logic."""
    def __init__(self, staff_id, first_name, last_name, dept, role, hourly_rate):
        super().__init__(first_name, last_name)
        self.staff_id = staff_id
        self.dept = dept.upper()
        self.role = role.title()
        self._hourly_rate = Decimal("16.00")
        self.hourly_rate = hourly_rate # Uses your existing setter logic
        
        # State Tracking
        self.is_clocked_in = False 
        self.shift_start: Optional[datetime] = None
        self.shift_end: Optional[datetime] = None
        self.had_break: bool = True  # Set by manager at clock-out; defaults True for safety

    @property
    def hourly_rate(self) -> Decimal:
        """Getter for the hourly wage."""
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float):
        """Requirement 14: Automated Guardrail for CA Minimum Wage (from settings)."""
        val = Decimal(str(value))
        self._hourly_rate = max(val, MIN_WAGE)  # Enforce floor from settings

    def clock_in(self):
        """Initializes the labor session."""
        self.is_clocked_in = True
        self.shift_start = datetime.now()
        print(f"⏰ {self.first_name} {self.last_name} [ID: {self.staff_id}] clocked in.")

    def to_dict(self):
        """Enables the 'Shared Brain' to save staff state."""
        return {
            "staff_id": self.staff_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "dept": self.dept,
            "role": self.role,
            "hourly_rate": str(self.hourly_rate),
            "is_clocked_in": self.is_clocked_in
        }

    def clock_out(self):
        """Finalizes the labor session."""
        self.is_clocked_in = False
        self.shift_end = datetime.now() # Capture exact current time

    def get_total_hours(self) -> Decimal:
        """Calculates total hours as a Decimal for precise payroll calculation."""
        if not self.shift_start or not self.shift_end:
            return Decimal("0.00") # Return zero if shift is incomplete
        delta = self.shift_end - self.shift_start # Subtract timestamps
        return Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"))

    def calculate_shift_pay(self, had_break: bool = True) -> Decimal:
        """Requirement 19/20: Overtime (1.5x after 8h) and CA Meal Penalty logic.

        Args:
            had_break: True if employee took an adequate 30-min break. CA law
                       requires a meal period for shifts exceeding 6 hours;
                       failure triggers a 1-hour penalty at the regular rate.
        """
        hrs = self.get_total_hours()
        if hrs <= 8:
            base_pay = hrs * self.hourly_rate
        else:
            base_pay = (8 * self.hourly_rate) + ((hrs - 8) * self.hourly_rate * Decimal("1.5"))

        # CA Meal Penalty: only applies if shift > 6h AND no adequate break taken
        if hrs > 6 and not had_break:
            base_pay += self.hourly_rate
        return base_pay.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @classmethod
    def from_dict(cls, data):
        """Reconstructs Staff object from saved JSON data."""
        staff = cls(
            data["staff_id"], 
            data["first_name"], 
            data["last_name"], 
            data["dept"], 
            data["role"], 
            Decimal(data["hourly_rate"])
        )
        staff.is_clocked_in = data.get("is_clocked_in", False)
        return staff
    
# ==============================================================================
# CART & TRANSACTION MODELS
# ==============================================================================

class Ledger:
    """
    Commit 17: The Financial Authority.
    Tracks all revenue and transaction history for the session.
    """
    def __init__(self, initial_revenue: Decimal = Decimal("0.00"), initial_count: int = 0):
        self.total_revenue = initial_revenue
        self.transaction_count = initial_count
        self.history = [] # Optional: to store individual transaction IDs

    def record_transaction(self, amount: Decimal):
        """
        Commit 17: Updates the ledger with a new sale.
        """
        if amount > 0:
            self.total_revenue += amount
            self.transaction_count += 1
            return True
        return False

    def get_report(self):
        """Returns a snapshot of current earnings."""
        return {
            "total_revenue": float(self.total_revenue),
            "transactions": self.transaction_count,
            "average_check": float(self.total_revenue / self.transaction_count) if self.transaction_count > 0 else 0
        }
    
    def print_daily_summary(self):
        """
        Commit 25: Standardized Financial Reporting.
        Uses Validator's currency formatting for a clean UI.
        """
        # Note: You may need to import format_currency from validator
        from validator import format_currency 
        
        print("\n" + "="*30)
        print("   HOSPITALITY OS: SHIFT REPORT   ")
        print("="*30)
        print(f"Total Revenue:   {format_currency(self.total_revenue):>10}")
        print(f"Transactions:    {self.transaction_count:>10}")
        
        if self.transaction_count > 0:
            avg = self.total_revenue / self.transaction_count
            print(f"Avg. Check:      {format_currency(avg):>10}")
        
        print("="*30 + "\n")
        
class Cart:
    """The temporary holding area for an active table order."""
    def __init__(self, guest=None):
        self.items: List[MenuItem] = [] 
        self.guest = guest 
        self.gratuity_rate = Decimal(str(GRATUITY_RATE)) # Added for Commit 39
        self.is_finalized = False

    def add_item(self, item: MenuItem) -> bool:
        """
        Unified Add Logic: Validates stock, clones for safety, 
        and deducts inventory immediately.
        """
        if not item.is_active or item.line_inv <= 0:
            # Raise exception so the UI can catch it and alert the server
            raise InsufficientStockError(f"86 ALERT: ❌ {item.name} is Out of Stock.")
        
        # 1. Create a private copy so modifications don't affect other tables
        cloned_item = item.clone() 
        
        # 2. Record the sale on the master item
        item.line_inv -= 1 
        item.units_sold += 1 
        
        # 3. Add the clone to this specific cart
        self.items.append(cloned_item)
        return True

    def checkout(self, ledger: 'Ledger') -> bool:
        """Finalizes the transaction and records revenue."""
        if not self.items:
            raise HospitalityError("Cannot checkout an empty cart.")
            
        final_total = self.grand_total # Uses the property you defined
        ledger.record_transaction(final_total)
        
        self.items = [] 
        self.is_finalized = True
        return True

    def calculate_total(self) -> Decimal:
        """Updated to use your Decimal tax_rate logic."""
        subtotal = sum(item.price for item in self.items)
        return Decimal(str(subtotal)) * (1 + self.tax_rate)

    def void_item(self, name: str, staff=None, reason: str = "") -> bool:
        """Removes the first matching item from the cart and logs the action."""
        for item in self.items:
            if item.name.lower() == name.lower():
                self.items.remove(item)
                if staff:
                    SecurityLog.log_event(staff.staff_id, "VOID_ITEM", f"{item.name} | {reason}")
                print(f"Voided: {item.name}")
                return True
        print(f"Item '{name}' not found in cart.")
        return False

    def split_by_items(self, item_indices: List[int]) -> 'Cart':
        """
        Commit 37: Extracts specific items by index and returns a new Cart.
        Useful for 'I'm paying for the appetizers and my drink' logic.
        """
        new_cart = Cart(guest=self.guest)
        # Sort indices in reverse to prevent list shifting issues during removal
        for index in sorted(item_indices, reverse=True):
            if 0 <= index < len(self.items):
                item = self.items.pop(index)
                new_cart.items.append(item)
        
        return new_cart

    def split_evenly(self, divisor: int) -> List[Decimal]:
        """
        Commit 37: Simple math split. Returns a list of totals.
        Example: $100 total split 3 ways -> [33.34, 33.33, 33.33]
        """
        if divisor <= 0: return [self.grand_total]
        
        total = self.grand_total
        share = (total / divisor).quantize(Decimal("0.01"), ROUND_HALF_UP)
        
        shares = [share] * divisor
        # Adjust for penny-rounding discrepancies
        difference = total - sum(shares)
        shares[0] += difference 
        
        return shares
    
    def apply_comp(self, item_index: int, manager_id: str, reason: str):
        """
        Commit 41: 100% discount (Comp) for a specific item.
        Tracks the manager who authorized it and the reason.
        """
        if 0 <= item_index < len(self.items):
            item = self.items[item_index]
            original_price = item.price
            item.price = Decimal("0.00") # The 'Comp' action
            
            log_msg = f"Item {item.name} (${original_price}) COMPED by {manager_id}. Reason: {reason}"
            SecurityLog.log_event(manager_id, "ITEM_COMP", log_msg)
            print(f"✅ {item.name} has been comped.")
            return True
        return False
    
    @property
    def subtotal(self) -> Decimal:
        """Aggregates prices of all items plus their nested modifiers."""
        total = Decimal("0.00")
        for item in self.items:
            total += item.price # Add base item price
            total += sum(m.price for m in item.modifiers) # Add all modifier prices
        return total

    @property
    def sales_tax(self) -> Decimal:
        """Calculates tax with a check for tax-exempt guest status."""
        if self.guest and getattr(self.guest, 'is_tax_exempt', False):
            return Decimal("0.00") # Return zero tax for exempt organizations
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def sales_tax(self) -> Decimal:
        """
        Commit 40: Conditional tax calculation.
        Returns 0 if the associated guest is tax-exempt.
        """
        if self.guest and getattr(self.guest, 'is_tax_exempt', False):
            return Decimal("0.00")
        
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def grand_total(self) -> Decimal:
        """The final pre-tip cost: Subtotal + Sales Tax."""
        return self.subtotal + self.sales_tax

    @property
    def auto_gratuity(self) -> Decimal:
        """
        Commit 39: Calculates 18% gratuity if party size >= threshold.
        Note: Gratuity is usually calculated on the subtotal BEFORE tax.
        """
        if self.guest and self.guest.party_size >= GRATUITY_THRESHOLD:
            return (self.subtotal * self.gratuity_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00")

    @property
    def grand_total(self) -> Decimal:
        """Updated to include auto-gratuity in the final sum."""
        return self.subtotal + self.sales_tax + self.auto_gratuity
    
class Transaction:
    """The immutable historical record of a completed sale."""
    def __init__(self, cart: Cart, table_num: int, staff: Staff):
        self.txn_id = str(uuid.uuid4())[:8].upper() # Human-friendly short ID
        self.cart = cart # Associated cart data
        self.table_num = table_num # Source table location
        self.staff = staff # Attributed employee
        self.tip = Decimal("0.00") # Initialized tip
        self.timestamp = datetime.now() # Capture moment of sale

    def apply_tip(self, amount_str: str) -> bool:
        """Parses tip input. Returns True on success, False if format is invalid."""
        try:
            is_percent = "%" in amount_str  # Check BEFORE stripping symbols
            clean = amount_str.replace("$", "").replace("%", "").strip()
            if is_percent:
                self.tip = (self.cart.subtotal * (Decimal(clean) / 100)).quantize(Decimal("0.01"))
            else:
                self.tip = Decimal(clean).quantize(Decimal("0.01"))
            return True
        except (ValueError, InvalidOperation):
            return False

    def to_dict(self):
        """Serializes the entire transaction including financials for the JSON log."""
        return {
            "txn_id": self.txn_id,
            "staff": self.staff.full_name,
            "total": str(self.cart.grand_total + self.tip),
            "timestamp": self.timestamp.isoformat()
        }

# ==============================================================================
# FINANCIAL & UTILITY MODELS
# ==============================================================================

class DailyLedger:
    """Singleton: The single source of truth for the restaurant's daily revenue."""
    _instance = None

    def __new__(cls, initial_sales=Decimal("0.00")):
        if cls._instance is None:
            cls._instance = super(DailyLedger, cls).__new__(cls)
        return cls._instance

    def __init__(self, initial_sales=Decimal("0.00")):
        if not hasattr(self, '_initialized'):
            self.total_revenue = Decimal(str(initial_sales))
            self.transaction_count = 0
            self._initialized = True

    @classmethod
    def reset(cls, initial_sales: Decimal = Decimal("0.00")) -> 'DailyLedger':
        """Destroys the current singleton and returns a fresh ledger. Call at new-day start."""
        cls._instance = None
        return cls(initial_sales)

    def record_sale(self, amount: Decimal):
        """Adds a finalized sale to the daily running total."""
        self.total_revenue += amount
        self.transaction_count += 1

    def archive_shift_data(self, staff_id: str) -> bool:
        """
        Commit 36: Standard 'Z-Report' logic. 
        Exports daily revenue to an immutable JSON file before resetting.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"z_report_{timestamp}.json"
        
        report = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "closed_by": staff_id,
            "total_revenue": str(self.total_revenue),
            "total_transactions": self.transaction_count,
            "average_check": str((self.total_revenue / self.transaction_count).quantize(Decimal("0.01"))) if self.transaction_count > 0 else "0.00"
        }

        try:
            with open(filename, "w") as f:
                json.dump(report, f, indent=4)
            SecurityLog.log_event(staff_id, "Z_REPORT_GENERATED", f"File: {filename}")
            return True
        except Exception as e:
            print(f"❌ Archive Failed: {e}")
            return False

class InventoryManager:
    """Commit 7: Update loop to handle dictionary-based menu."""
    def get_prep_list(self):
        prep_list = []
        # Changed from 'for item in self.menu.items'
        for item in self.menu.items.values():
            if not item.is_active:
                continue
            if item.line_inv < item.par_level:
                prep_list.append({
                    "name": item.name,
                    "need": item.par_level - item.line_inv
                })
        return prep_list # Return actionable data for the chef

# ==============================================================================
# RECEIPT, ADMIN & ANALYTICS MODELS
# ==============================================================================

class ReceiptPrinter:
    """Formats and prints an ASCII bill for a completed transaction."""

    @staticmethod
    def print_bill(txn: 'Transaction'):
        """Renders a structured receipt to the terminal."""
        print("\n" + "=" * 42)
        print(f"{'HOSPITALITY OS':^42}")
        print(f"{'RECEIPT':^42}")
        print("=" * 42)
        print(f" Table: {txn.table_num:<22} TXN: {txn.txn_id}")
        print(f" Server: {txn.staff.full_name}")
        print(f" Time: {txn.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 42)
        for item in txn.cart.items:
            mod_total = sum(m.price for m in item.modifiers)
            line_total = item.price + mod_total
            print(f"  {item.name:<26} ${line_total:>6.2f}")
            for mod in item.modifiers:
                print(f"    {str(mod).strip()}")
        print("-" * 42)
        print(f"  {'Subtotal:':<28} ${txn.cart.subtotal:>6.2f}")
        print(f"  {'Tax:':<28} ${txn.cart.sales_tax:>6.2f}")

        if txn.cart.auto_gratuity > 0:
            print(f"  {'Auto-Gratuity (18%):':<28} ${txn.cart.auto_gratuity:>6.2f}")

        print(f"  {'Tip:':<28} ${txn.tip:>6.2f}")
        total = txn.cart.grand_total + txn.tip
        print("=" * 42)
        print(f"  {'TOTAL:':<28} ${total:>6.2f}")
        print("=" * 42 + "\n")
        # Commit 39: Show Auto-Gratuity if applicable



class MenuEditor:
    """Administrative controller for live menu modifications."""

    def __init__(self, menu: Menu):
        self.menu = menu

    def update_price(self, name: str, new_price: Decimal):
        """Updates the price of a named menu item."""
        item = self.menu.find_item(name)
        if item:
            item.price = Decimal(str(new_price))
            print(f"Price updated: {item.name} -> ${item.price:.2f}")
        else:
            print(f"Item '{name}' not found on menu.")

    def toggle_item_status(self, name: str):
        """Flips the is_active flag to show or hide a seasonal item."""
        item = self.menu.find_item(name)
        if item:
            item.is_active = not item.is_active
            status = "available" if item.is_active else "unavailable (86'd)"
            print(f"{item.name} is now {status}.")
        else:
            print(f"Item '{name}' not found on menu.")


class AnalyticsEngine:
    """Analyzes ledger and menu data to surface actionable insights."""

    def __init__(self, ledger: 'DailyLedger', menu: Menu):
        self.ledger = ledger
        self.menu = menu

    def get_top_performing_items(self, n: int = 5) -> List[MenuItem]:
        # Changed from 'self.menu.items' to 'self.menu.items.values()'
        active = [i for i in self.menu.items.values() if i.is_active]
        return sorted(active, key=lambda x: x.units_sold, reverse=True)[:n]

    def get_reorder_list(self) -> List[MenuItem]:
        # Changed to dictionary values
        return [i for i in self.menu.items.values() if i.line_inv < i.par_level]

# Also update MenuEditor's loops if any exist, but it primarily 
# uses find_item(), which we already fixed in Commit 5.

def save_guest_feedback(guest_id, rating, comments=""):
    """
    Commit 42: Phase 3 - Item B.
    Captures guest ratings (1-5) and persists to feedback.json.
    """
    feedback_file = os.path.join(os.path.dirname(__file__), "feedback.json")
    new_entry = {
        "guest_id": guest_id,
        "timestamp": datetime.now().isoformat(),
        "rating": rating,
        "comments": comments
    }
    
    # Load existing or start new list
    data = []
    if os.path.exists(feedback_file):
        with open(feedback_file, "r") as f:
            data = json.load(f)
            
    data.append(new_entry)
    
    with open(feedback_file, "w") as f:
        json.dump(data, f, indent=4)
    print("🌟 Feedback saved. Thank you!")

class AdminSession:
    """Manages the state and audit trail of a logged-in manager session."""

    def __init__(self, staff: Staff, editor: MenuEditor):
        self.staff = staff
        self.editor = editor
        self.is_active = True
        self._action_log: List[str] = []

    def log_action(self, action: str):
        """Records an admin action to both the in-memory log and the security file."""
        entry = f"{datetime.now().strftime('%H:%M:%S')} | {self.staff.full_name} | {action}"
        self._action_log.append(entry)
        SecurityLog.log_event(self.staff.staff_id, "ADMIN_ACTION", action)
    
    def view_audit_log(self, lines: int = 20):
        """Displays the last N lines of the security audit trail."""
        print(f"\n--- SECURITY AUDIT TRAIL (Last {lines} events) ---")
        try:
            with open(SecurityLog.LOG_FILE, "r") as f:
                content = f.readlines()
                for line in content[-lines:]:
                    print(line.strip())
        except FileNotFoundError:
            print("No security log found yet.")
        print("-" * 45)
