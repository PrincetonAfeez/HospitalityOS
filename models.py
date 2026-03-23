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
from decimal import Decimal, ROUND_HALF_UP # Industry standard for financial rounding precision

# Try-Except block to handle missing settings during initial environment setup
try:
    from settings.restaurant_defaults import TAX_RATE 
except ImportError:
    TAX_RATE = 0.08  # Default fallback if the settings file is not yet created

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
        
        with open(SecurityLog.LOG_FILE, "a") as f: # Append mode to preserve history
            f.write(log_entry) # Commit to disk
        print(f"🔒 Security Event Logged: {action}") # Real-time console feedback

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

    def add_modifier(self, mod: Modifier):
        """Enforces the 'Rule of Three' to prevent order complexity and over-charging."""
        if len(self.modifiers) < 3:
            self.modifiers.append(mod) # Append the object to the list
            return True
        return False # Signal failure if limit reached

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
    """The primary registry for all MenuItem objects."""
    def __init__(self):
        self.items: List[MenuItem] = [] # Internal storage list

    def add_item(self, item: MenuItem):
        """Appends a new dish to the live menu registry."""
        self.items.append(item)

    def find_item(self, name: str) -> Optional[MenuItem]:
        """Case-insensitive search utility for the POS search bar."""
        for item in self.items:
            if item.name.lower() == name.lower():
                return item # Return reference to the actual object
        return None

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

    @property
    def hourly_rate(self) -> Decimal:
        """Getter for the hourly wage."""
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float):
        """Requirement 14: Automated Guardrail for 2026 CA Minimum Wage ($16.00)."""
        val = Decimal(str(value)) # Standardize input to Decimal
        self._hourly_rate = max(val, Decimal("16.00")) # Enforce floor price

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

    def calculate_shift_pay(self) -> Decimal:
        """Requirement 19/20: Overtime (1.5x after 8h) and CA Meal Penalty logic."""
        hrs = self.get_total_hours() # Get work duration
        if hrs <= 8:
            base_pay = hrs * self.hourly_rate # Regular time
        else:
            # Split pay into regular and time-and-a-half segments
            base_pay = (8 * self.hourly_rate) + ((hrs - 8) * self.hourly_rate * Decimal("1.5"))
        
        # Meal Penalty: Add 1 hour of pay if the shift exceeded 5 hours (CA Law)
        if hrs > 5:
            base_pay += self.hourly_rate
        return base_pay.quantize(Decimal("0.01"), ROUND_HALF_UP)

# ==============================================================================
# CART & TRANSACTION MODELS
# ==============================================================================

class Cart:
    """The temporary holding area for an active table order."""
    def __init__(self, guest=None):
        self.items: List[MenuItem] = [] # Active items in the cart
        self.guest = guest # Reference to the Guest object (if seated)
        self.tax_rate = Decimal(str(TAX_RATE)) # Global tax constant

    def add_to_cart(self, item: MenuItem):
        """Validates inventory and clones the item to prevent 'Shared State' bugs."""
        if item.line_inv <= 0:
            raise InsufficientStockError(f"86 ALERT: {item.name} is out of stock!")
        
        cloned_item = item.clone() # Create a private copy of the MenuItem
        self.items.append(cloned_item) # Add the copy to the cart
        item.line_inv -= 1 # Deduct from the master menu inventory

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

    def apply_tip(self, amount_str: str):
        """Parses user input for percentage ('20%') or dollar ('5.00') amounts."""
        try:
            clean = amount_str.replace("$", "").replace("%", "") # Strip UI symbols
            if "%" in amount_str:
                # Percentage of the subtotal
                self.tip = (self.cart.subtotal * (Decimal(clean) / 100)).quantize(Decimal("0.01"))
            else:
                # Flat dollar amount
                self.tip = Decimal(clean).quantize(Decimal("0.01"))
        except:
            self.tip = Decimal("0.00") # Fallback for invalid input

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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DailyLedger, cls).__new__(cls)
            cls._instance.total_revenue = Decimal("0.00") # Reset revenue to zero
            cls._instance.transaction_count = 0 # Reset count to zero
        return cls._instance

    def record_sale(self, amount: Decimal):
        """Adds a finalized sale to the daily running total."""
        self.total_revenue += amount
        self.transaction_count += 1

class InventoryManager:
    """Business Intelligence tool to identify prep needs and stock gaps."""
    def __init__(self, menu: Menu):
        self.menu = menu # Link to the master menu

    def get_prep_list(self):
        """Compares current stock against Par Levels to generate a 'To-Do' list."""
        prep_list = []
        for item in self.menu.items:
            if item.line_inv < item.par_level:
                prep_list.append({
                    "name": item.name,
                    "need": item.par_level - item.line_inv # Calculate discrepancy
                })
        return prep_list # Return actionable data for the chef