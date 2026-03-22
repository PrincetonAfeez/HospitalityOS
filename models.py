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

# ==============================================================================
# MENU & MODIFIER MODELS
# ==============================================================================

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
    
# ==============================================================================
# CART & FINANCIAL MODELS
# ==============================================================================

class Cart:
    """A temporary container for items in an active customer order."""
    def __init__(self):
        self.items = [] # List of items in the current order
        self.tax_rate = Decimal(str(TAX_RATE)) # Decimal tax rate from settings

    def add_to_cart(self, item: MenuItem):
        """Checks '86' status (inventory) and moves item into the active cart."""
        if item.line_inv > 0: # Check if line stock exists
            self.items.append(item) # Add to session
            item.line_inv -= 1 # Deduct from line stock immediately
            print(f"✅ Added {item.name}. Subtotal: ${self.subtotal:.2f}")
        else:
            print(f"⚠️  CANNOT ADD: {item.name} is 86'd!") # UX feedback
    
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
        """Calculates tax on the subtotal with financial-grade rounding."""
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
    """The base blueprint for any human interacting with the system."""
    def __init__(self, first_name, last_name):
        self.first_name = first_name # Validated string
        self.last_name = last_name # Validated string

    @property
    def full_name(self):
        """Returns the formatted full name for receipts or reports."""
        return f"{self.first_name} {self.last_name}"

class Guest(Person):
    """Represents a customer with a unique ID and hospitality preferences."""
    def __init__(self, guest_id, first_name, last_name, phone, allergies=None):
        super().__init__(first_name, last_name)
        self.guest_id = guest_id # Unique identifier (e.g., GST-101)
        self.phone = phone # Validated 10-digit int
        self.allergies = allergies if allergies else [] # List of strings
        self.loyalty_points = 0 # Tracks rewards for Block 4

class Staff(Person):
    """
    Represents an employee.
    Department: FOH (Front of House) or BOH (Back of House)
    Role: Manager, Server, Chef, Dishwasher, etc.
    """
    def __init__(self, staff_id, first_name, last_name, dept, role):
        super().__init__(first_name, last_name)
        self.staff_id = staff_id # E.g., EMP-01
        self.dept = dept # Must be 'FOH' or 'BOH'
        self.role = role # E.g., 'Manager', 'Server', 'Line Cook'
        self.total_sales = Decimal("0.00") # Only applicable to Sales roles

    def __str__(self):
        """Displays staff details for the Auditor or Manager reports."""
        return f"[{self.staff_id}] {self.full_name} - {self.dept} ({self.role})"

    def calculate_productivity(self, hours_worked):
        """Task 3: Executive Metric - Optimized for Role-specific tracking."""
        if hours_worked <= 0: return Decimal("0.00")
        # Only Servers are measured by personal Sales Per Labor Hour (SPLH)
        if self.role.lower() == "server":
            return (self.total_sales / Decimal(str(hours_worked))).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00") # BOH/Managers contribute to overhead, not direct sales
    

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