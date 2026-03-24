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
    from digitalfrontdesk import Guest

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
    def __init__(self, category, name, price, line_inv, walk_in, freezer, par):
        self.category = category # Category for sales reporting (e.g., 'Liquor')
        self.name = name # The display name for the POS
        self.price = Decimal(str(price)) # Base retail cost
        self.line_inv = int(line_inv) # Immediate stock available to the chef
        self.walk_in_inv = int(walk_in) # Backup stock in refrigeration
        self.freezer_inv = int(freezer) # Long-term storage stock
        self.par_level = int(par) # The 'Reorder Point' for prep lists
        self.modifiers: List[Modifier] = [] # List limited to 3 items per business rules
        self.kitchen_notes = "" # Special prep instructions (e.g., 'Allergy')
        self.is_active = True # Soft-delete flag for seasonal items
        self.units_sold: int = 0 # Tracks actual sales volume for analytics

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

# ==============================================================================
# LABOR & STAFF MODELS
# ==============================================================================

class Person:
    """Abstract base class to handle common identity logic (DRY Principle)."""
    def __init__(self, first_name: str, last_name: str):
        self.first_name = first_name.strip().title() # Auto-correct casing
        self.last_name = last_name.strip().title() # Auto-correct casing

    @property
    def full_name(self):
        """Convenience property for printing receipts and employee badges."""
        return f"{self.first_name} {self.last_name}"

class Staff(Person):
    """Represents an employee with CA labor-compliant payroll logic."""
    def __init__(self, staff_id, first_name, last_name, dept, role, hourly_rate):
        super().__init__(first_name, last_name) # Initialize Person attributes
        self.staff_id = staff_id # Unique employee identifier (e.g., EMP-01)
        self.dept = dept.upper() # FOH or BOH normalization
        self.role = role.title() # Job title normalization
        self._hourly_rate = Decimal("16.00") # Default starting point
        self.hourly_rate = hourly_rate # Triggers the setter for compliance check
        self.shift_start: Optional[datetime] = None # Stores clock-in time
        self.shift_end: Optional[datetime] = None # Stores clock-out time
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
        """Initializes the labor session for productivity tracking."""
        self.shift_start = datetime.now() # Capture exact current time

    def clock_out(self):
        """Finalizes the labor session."""
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

# ==============================================================================
# CART & TRANSACTION MODELS
# ==============================================================================

class Cart:
    """The temporary holding area for an active table order."""
    def __init__(self, guest=None):
        """
        Commit 16 (Merged): Preserves guest and tax logic 
        while preparing for atomic stock validation.
        """
        self.items: List[MenuItem] = [] 
        self.guest = guest 
        self.tax_rate = Decimal(str(TAX_RATE))
        self.is_finalized = False # Useful for Phase 3 (Payments)

    def add_item(self, item: MenuItem) -> bool:
        """
        Commit 16: Pre-flight stock check.
        Only adds if item is active and line_inv > 0.
        """
        if not item.is_active or item.line_inv <= 0:
            print(f"❌ Cannot add {item.name}: Out of Stock.")
            return False
        
        self.items.append(item)
        return True

    def calculate_total(self) -> Decimal:
        """Updated to use your Decimal tax_rate logic."""
        subtotal = sum(item.price for item in self.items)
        return Decimal(str(subtotal)) * (1 + self.tax_rate)

    def checkout(self) -> bool:
        """
        Commit 16: Atomic Checkout.
        Deducts inventory and clears cart in one movement.
        """
        if not self.items:
            return False
            
        for item in self.items:
            item.line_inv -= 1
            item.units_sold += 1
            
        self.items = [] 
        return True
    
    def add_to_cart(self, item: MenuItem):
        """Validates inventory and clones the item to prevent 'Shared State' bugs."""
        if item.line_inv <= 0:
            raise InsufficientStockError(f"86 ALERT: {item.name} is out of stock!")
        
        cloned_item = item.clone() # Create a private copy of the MenuItem
        self.items.append(cloned_item) # Add the copy to the cart
        item.line_inv -= 1 # Deduct from the master menu inventory
        item.units_sold += 1 # Track sales volume on the master item for analytics

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
    def grand_total(self) -> Decimal:
        """The final pre-tip cost: Subtotal + Sales Tax."""
        return self.subtotal + self.sales_tax

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
        print(f"  {'Tip:':<28} ${txn.tip:>6.2f}")
        total = txn.cart.grand_total + txn.tip
        print("=" * 42)
        print(f"  {'TOTAL:':<28} ${total:>6.2f}")
        print("=" * 42 + "\n")


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