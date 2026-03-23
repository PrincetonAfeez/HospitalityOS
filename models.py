"""
Project: Hospitality OS - Data Models
Description: This module defines the architectural blueprints for the system. 
             It uses Decimal for financial precision and includes business 
             logic for inventory, tax, and California-compliant labor tracking.
"""

from datetime import datetime # For timestamping transactions
from decimal import Decimal, ROUND_HALF_UP # For professional financial rounding
# Import the globally defined Tax Rate (e.g., 0.08 for 8%)
from settings.restaurant_defaults import TAX_RATE 

# NEW: Import Guest only for type hinting to avoid circular dependency
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from digitalfrontdesk import Guest

# ==============================================================================
# MENU & MODIFIER MODELS
# ==============================================================================

class HospitalityError(Exception):
    """Base exception for HospitalityOS v4.0"""
    pass

class InsufficientStockError(HospitalityError):
    """Raised when an item's line inventory is 0 or less."""
    pass

class Modifier:
    """Represents an add-on item like 'Extra Cheese' or 'Sub Salad'."""
    def __init__(self, name: str, price: float = 0.00):
        self.name = name # The name of the modification
        # Convert to string first to ensure Decimal handles the float accurately
        self.price = Decimal(str(price)) 

    def __str__(self):
        """Returns a string representation for the cart view."""
        return f" +{self.name} (${self.price:.2f})"
    
    def to_dict(self):
        """Serializes the modifier for the 'Shared Brain' JSON state."""
        return {"name": self.name, "price": str(self.price)}
    
class MenuItem:
    """The base object for every product sold in the restaurant."""
    def __init__(self, category, name, price, line_inv, walk_in, freezer, par):
        self.category = category # E.g., 'Appetizer', 'Entree'
        self.name = name # E.g., 'Burger'
        self.price = Decimal(str(price)) # Base retail price
        self.line_inv = int(line_inv) # Stock currently on the cooking line
        self.walk_in_inv = int(walk_in) # Stock in the refrigerator
        self.freezer_inv = int(freezer) # Stock in the freezer
        self.par_level = int(par) # Minimum stock required on the line
        self.modifiers = [] # Collection to hold up to 3 Modifier objects
        self.kitchen_notes = "" # Custom string for special prep instructions
    
    def add_modifier(self, mod: 'Modifier'):
        """Task 8: Enforces a business limit of 3 modifiers per item."""
        if len(self.modifiers) < 3: # Check current count
            self.modifiers.append(mod) # Add the object
            print(f"✨ Added modifier: {mod.name}") # Visual confirmation
        else:
            print(f"⚠️ Limit reached! Cannot add '{mod.name}'.") # UX feedback

    @property
    def total_inventory(self):
        """Calculates combined stock levels across all three storage areas."""
        return self.line_inv + self.walk_in_inv + self.freezer_inv

    def to_dict(self):
        """Converts the item into a dictionary for JSON data persistence."""
        return {
            "category": self.category,
            "name": self.name,
            "price": str(self.price), # String conversion for JSON compatibility
            "modifiers": [m.to_dict() for m in self.modifiers], # Nested list
            "notes": self.kitchen_notes,
            "line_inv": self.line_inv,
            "walk_in_inv": self.walk_in_inv,
            "freezer_inv": self.freezer_inv,
            "par_level": self.par_level,
            "total_inventory": self.total_inventory # Computed total
        }

    def __str__(self):
        """Standardizes the visual alignment for the POS menu display."""
        return f"[{self.category:10}] {self.name:25} ${self.price:>6.2f}"

class Menu:
    """A search-optimized collection of MenuItem objects."""
    def __init__(self):
        self.items = [] # The primary item registry

    def add_item(self, item: MenuItem):
        """Appends a new MenuItem to the internal registry list."""
        self.items.append(item)

    def find_item(self, name: str) -> MenuItem:
        """Locates an item by name using a case-insensitive search logic."""
        for item in self.items: # Loop through registry
            if item.name.lower() == name.lower(): # Match normalized strings
                return item # Return the matching object
        return None # Return None if no match is found
    
class SecurityLog:
    """
    Objective 4: Centralized security audit trail.
    Tracks high-sensitivity actions like Voids and Discounts.
    """
    LOG_FILE = "security.log"

    @staticmethod
    def log_event(staff_id: str, action: str, details: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] STAFF: {staff_id} | ACTION: {action} | DETAILS: {details}\n"
        
        # Ensure we use a safe pathing approach later, but for now:
        with open(SecurityLog.LOG_FILE, "a") as f:
            f.write(log_entry)
        print(f"🔒 Security Event Logged: {action}")

# ==============================================================================
# CART & FINANCIAL MODELS
# ==============================================================================

class Cart:
    def __init__(self, guest=None):
        self.items: list[MenuItem] = []
        self.guest = guest
        self.tax_rate = Decimal(str(TAX_RATE))

    def add_to_cart(self, item: MenuItem) -> None:
        """
        Objective 2: Validate inventory BEFORE adding to cart.
        Raises InsufficientStockError if item is 86'd.
        """
        if item.line_inv <= 0:
            # The 'Error Bridge': Raise instead of print
            raise InsufficientStockError(f"Inventory Failure: {item.name} is 86'd and cannot be sold.")
        
        self.items.append(item)
        item.line_inv -= 1
        print(f"✅ Added {item.name}. Subtotal: ${self.subtotal:.2f}")

    def remove_from_cart(self, item_name: str):
        """Removes an item and replenishes the line inventory automatically."""
        for i, item in enumerate(self.items): # Search the cart
            if item.name.lower() == item_name.lower(): # Match name
                item.line_inv += 1 # Restore the deducted stock
                self.items.pop(i) # Remove from list
                print(f"🗑️ Removed {item.name}. (Stock Restored)") # UX feedback
                return True # Signal successful removal
        print(f"❌ '{item_name}' not in cart.") # UX feedback
        return False

    def void_item(self, item_name: str, staff: Staff, reason: str = "Not Specified") -> bool:
        """Requirement 41: Logs voids with mandatory staff attribution."""
        for i, item in enumerate(self.items):
            if item.name.lower() == item_name.lower():
                self.items.pop(i)
                item.line_inv += 1 # Replenish stock
                
                # Use the new SecurityLog class
                SecurityLog.log_event(
                    staff_id=staff.staff_id,
                    action="VOID",
                    details=f"Item: {item.name} | Reason: {reason}"
                )
                return True
        return False
    
    @property
    def subtotal(self) -> Decimal:
        """Aggregates the total cost of all items including their modifiers."""
        total = Decimal("0.00") # Initialize sum
        for item in self.items: # Loop through cart
            total += item.price # Add base price
            # Sum up modifier prices using a generator expression
            total += sum((m.price for m in item.modifiers), Decimal("0.00"))
        return total # Return combined sum
    
    @property
    def sales_tax(self) -> Decimal:
        """Requirement 40: Calculates tax, checking if Guest is tax-exempt."""
        if self.guest and self.guest.is_tax_exempt:
            return Decimal("0.00")
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @property
    def grand_total(self) -> Decimal:
        """The pre-tip total amount (Subtotal + Tax)."""
        return self.subtotal + self.sales_tax

class Transaction:
    """The final financial record representing a paid bill."""
    def __init__(self, cart: Cart, table_num: int, staff_id: str = "OFFLINE"):
        self.cart = cart # Full Cart object reference
        self.table_num = table_num # Associated table number
        self.staff_id = staff_id # ID of the server who closed the bill
        self.tip = Decimal("0.00") # Start tip at zero
        self.split_count = 1 # Start split at one person

    @property
    def final_total(self) -> Decimal:
        """The absolute bottom line: Cart total plus the added tip."""
        return self.cart.grand_total + self.tip

    @property
    def per_person(self) -> Decimal:
        """Calculates the amount due per guest for split-check scenarios."""
        return (self.final_total / Decimal(str(self.split_count))).quantize(Decimal("0.01"), ROUND_HALF_UP)

    def apply_tip(self, amount: str):
        """Parses user input to apply a percentage (20%) or flat ($5) tip."""
        try:
            clean_amt = amount.replace("%", "").replace("$", "") # Strip symbols
            if "%" in amount: # If input was a percentage
                percent = Decimal(clean_amt) / 100 # Convert to decimal
                self.tip = (self.cart.subtotal * percent).quantize(Decimal("0.01"), ROUND_HALF_UP)
            else: # If input was a flat dollar amount
                self.tip = Decimal(clean_amt).quantize(Decimal("0.01"), ROUND_HALF_UP)
            return True # Success
        except: # Handle non-numeric input gracefully
            print("❌ Invalid tip format.")
            return False
    
    def to_dict(self):
        """Serializes the entire transaction for the permanent 'transaction_log.json'."""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Current time
            "staff_id": self.staff_id, # Server ID
            "table_num": self.table_num, # Table ID
            "items": [item.to_dict() for item in self.cart.items], # Deep copy of items
            "financials": { # Dictionary of string-converted Decimals
                "subtotal": str(self.cart.subtotal),
                "tax": str(self.cart.sales_tax),
                "tip": str(self.tip),
                "grand_total": str(self.final_total)
            },
            "split_count": self.split_count # Number of payers
        }

# ==============================================================================
# UI & REPORTING MODELS
# ==============================================================================

class ReceiptPrinter:
    """A specialized class to handle visual receipt formatting (UX)."""
    @staticmethod
    def print_bill(txn: Transaction):
        """Static method to generate a professional receipt in the console."""
        print("\n" + "="*35)
        print(f"{'HOSPITALITY OS RECEIPT':^35}") # Header
        print(f"{'Table: ' + str(txn.table_num):^35}") # Metadata
        print(f"{'Server: ' + txn.staff_id:^35}") # Metadata
        print("="*35)
        
        for item in txn.cart.items: # Iterate through cart items
            print(f"1x {item.name:<20} ${item.price:>8.2f}") # Base item line
            for mod in item.modifiers: # Nested modifier loop
                print(f"   + {mod.name:<17} ${mod.price:>8.2f}") # Modifier line
            if item.kitchen_notes: # Check for notes
                print(f"     (Note: {item.kitchen_notes})") # Note line

        print("-" * 35) # Visual separator
        print(f"Subtotal:            ${txn.cart.subtotal:>8.2f}")
        tax_pct = int(txn.cart.tax_rate * 100) # Convert rate to integer display
        print(f"Tax ({tax_pct}%):           ${txn.cart.sales_tax:>8.2f}")
        print(f"Tip:                 ${txn.tip:>8.2f}")
        print("-" * 35) # Visual separator
        print(f"TOTAL:               ${txn.final_total:>8.2f}")
        
        if txn.split_count > 1: # Conditional split display
            print(f"Each ({txn.split_count} ways):      ${txn.per_person:>8.2f}")
        print("="*35 + "\n") # Footer

class Person:
    """
    The base blueprint for any human interacting with the system.
    Requirement: DRY Principle - Centralize identity logic.
    """
    def __init__(self, first_name: str, last_name: str) -> None:
        self.first_name: str = first_name.strip().title()
        self.last_name: str = last_name.strip().title()

    @property
    def full_name(self) -> str:
        """Returns the formatted full name for receipts or reports."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        """Technical representation for debugging."""
        return f"<{self.__class__.__name__}: {self.full_name}>"
    
class Staff(Person):
    """
    Represents an employee with role-based logic and CA labor compliance.
    Requirement: Task 14 & 20 - Wage Guardrails and Shift Tracking.
    """
    def __init__(self, staff_id: str, first_name: str, last_name: str, dept: str, role: str, hourly_rate: float):
        super().__init__(first_name, last_name)
        self.staff_id = staff_id
        self.dept = dept.upper()  # Normalize to 'FOH' or 'BOH'
        self.role = role.title()
        
        # This triggers the @hourly_rate.setter logic below
        self.hourly_rate = hourly_rate 
        
        self.total_sales = Decimal("0.00")
        self.shift_start = None
        self.shift_end = None

    @property
    def hourly_rate(self) -> Decimal:
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value: float) -> None:
        """Requirement 14: CA Min Wage Guardrail (2026 Standard: $16.00)"""
        min_wage = Decimal("16.00")
        input_wage = Decimal(str(value))
        
        if input_wage < min_wage:
            print(f"⚠️ COMPLIANCE ALERT: {value} is below CA Min Wage. Corrected to {min_wage}.")
            self._hourly_rate = min_wage
        else:
            self._hourly_rate = input_wage

    def __str__(self) -> str:
        return f"[{self.staff_id}] {self.full_name} - {self.role} ({self.dept})"
    

    def calculate_productivity(self, hours_worked):
        """Task 3: Executive Metric - Optimized for Role-specific tracking."""
        if hours_worked <= 0: return Decimal("0.00")
        # Only Servers are measured by personal Sales Per Labor Hour (SPLH)
        if self.role.lower() == "server":
            return (self.total_sales / Decimal(str(hours_worked))).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00") # BOH/Managers contribute to overhead, not direct sales
    
    def clock_in(self):
        """Requirement 16: Records the exact start of the shift."""
        self.shift_start = datetime.now()
        print(f"⏰ {self.full_name} clocked in at {self.shift_start.strftime('%I:%M %p')}")

    def clock_out(self):
        """Requirement 17: Records the end of the shift."""
        self.shift_end = datetime.now()
        print(f"🏁 {self.full_name} clocked out at {self.shift_end.strftime('%I:%M %p')}")

    def get_total_hours(self):
        """Requirement 18: Calculates duration between clock-in and clock-out."""
        if not self.shift_start or not self.shift_end:
            return Decimal("0.00")
        delta = self.shift_end - self.shift_start
        # Convert total seconds to decimal hours (e.g., 8.5)
        return Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    def calculate_shift_pay(self):
        """Requirement 19 & 20: CA Overtime (1.5x after 8h) and Meal Penalty logic."""
        hours = self.get_total_hours()
        rate = self.hourly_rate
        total_pay = Decimal("0.00")

        # Overtime Logic (1.5x after 8 hours)
        if hours > 8:
            regular_hours = Decimal("8.00")
            ot_hours = hours - 8
            total_pay = (regular_hours * rate) + (ot_hours * rate * Decimal("1.5"))
        else:
            total_pay = hours * rate

        # Meal Break Penalty (If shift > 5 hours, add 1 hour of pay if break was missed)
        if hours > 5:
            total_pay += rate # Adding 1 hour 'Penalty' pay per CA law
            
        return total_pay.quantize(Decimal("0.01"), ROUND_HALF_UP)
    
    def to_csv_row(self):
        """Requirement 21: Formats shift data for payroll CSV exports."""
        return {
            "staff_id": self.staff_id,
            "name": self.full_name,
            "dept": self.dept,
            "role": self.role,
            "hours_worked": str(self.get_total_hours()),
            "hourly_rate": str(self.hourly_rate),
            "gross_pay": str(self.calculate_shift_pay()),
            "timestamp": datetime.now().strftime("%Y-%m-%d")
        }
    
    @property
    def hourly_rate(self):
        return self._hourly_rate

    @hourly_rate.setter
    def hourly_rate(self, value):
        """Requirement 14: CA Min Wage Guardrail (Adjust as per 2026 laws)"""
        min_wage = Decimal("16.00") 
        if Decimal(str(value)) < min_wage:
            print(f"⚠️ Warning: {value} is below CA Min Wage. Adjusting to {min_wage}.")
            self._hourly_rate = min_wage
        else:
            self._hourly_rate = Decimal(str(value))

class InventoryManager:
    """Logic engine to analyze stock gaps and prep requirements."""
    def __init__(self, menu):
        self.menu = menu # Reference to the loaded menu collection

    def get_prep_list(self):
        """Task 5: Business intelligence - Identifies items below par levels."""
        prep_list = [] # Initialize results
        for item in self.menu.items: # Loop through menu
            if item.line_inv < item.par_level: # Check for inventory gap
                gap = item.par_level - item.line_inv # Calculate missing units
                prep_list.append({ # Add data dictionary to list
                    "name": item.name,
                    "current": item.line_inv,
                    "par": item.par_level,
                    "need": gap
                })
        return prep_list # Return the actionable data