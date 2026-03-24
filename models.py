"""
HospitalityOS v4.0 - Core Financial & Inventory Models
Refactor: Integrated Pydantic for robust data schema validation.
"""

import uuid
import copy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Any
from pydantic import BaseModel, Field, validator, ConfigDict

# Standardized imports from settings
from settings.restaurant_defaults import (
    GRATUITY_RATE, GRATUITY_THRESHOLD, 
    TAX_RATE, MIN_WAGE, MAX_MODS
)

# ==============================================================================
# BASE MODELS & IDENTITY
# ==============================================================================

class SecurityLog:
    """
    Requirement: Commit 11 - Forensic Dual-Signature Logging.
    Ensures accountability by linking every sensitive action to two individuals.
    """
    @staticmethod
    def log_event(staff_id: str, action: str, details: str, manager_id: str = "SYSTEM"):
        """
        Records an audit entry in the security.log file.
        Format: [Timestamp] STAFF: {ID} | AUTH: {MGR_ID} | ACTION: {TYPE} | MSG: {DETAILS}
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Dual-signature string construction
        log_entry = (
            f"[{timestamp}] STAFF: {staff_id:<8} | AUTH: {manager_id:<8} | "
            f"ACTION: {action:<15} | MSG: {details}\n"
        )
        
        # In HospitalityOS, we log to data/logs/security.log for persistence
        log_path = "data/logs/security.log"
        
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except FileNotFoundError:
            # Fallback for local root if data directory isn't initialized
            with open("security.log", "a", encoding="utf-8") as f:
                f.write(log_entry)

class Person(BaseModel):
    """Base identity model with automatic formatting."""
    first_name: str
    last_name: str

    @validator('first_name', 'last_name')
    def format_name(cls, v):
        return v.strip().title()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

# ==============================================================================
# MENU & INVENTORY MODELS
# ==============================================================================

class Modifier(BaseModel):
    name: str
    price: Decimal = Field(default=Decimal("0.00"))

    @validator('name')
    def format_mod_name(cls, v):
        return v.strip().title()

class MenuItem(BaseModel):
    name: str
    price: Decimal
    category: str
    walk_in_inv: int = Field(default=0, ge=0)
    freezer_inv: int = Field(default=0, ge=0)
    par_level: int = Field(default=10)
    line_inv: int = Field(default=0, ge=0) # Logic: Cannot be less than 0
    station: str = Field(default="Kitchen")
    modifiers: List[Modifier] = []
    is_active: bool = True
    units_sold: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def clone(self) -> 'MenuItem':
        return copy.deepcopy(self)

# ==============================================================================
# FINANCIAL CORE
# ==============================================================================

class Cart(BaseModel):
    items: List[MenuItem] = []
    guest: Optional[Any] = None # Using Any until hospitality_models is refactored
    tax_rate: Decimal = Field(default=Decimal(str(TAX_RATE)))
    gratuity_rate: Decimal = Field(default=Decimal(str(GRATUITY_RATE)))

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_to_cart(self, master_item: MenuItem):
        if master_item.line_inv <= 0:
            raise ValueError(f"86 ALERT: {master_item.name} is out of stock!")
        
        master_item.line_inv -= 1
        master_item.units_sold += 1
        self.items.append(master_item.clone())

    @property
    def subtotal(self) -> Decimal:
        total = Decimal("0.00")
        for item in self.items:
            total += item.price
            total += sum(m.price for m in item.modifiers)
        return total

    @property
    def sales_tax(self) -> Decimal:
        if self.guest and getattr(self.guest, 'is_tax_exempt', False):
            return Decimal("0.00")
        return (self.subtotal * self.tax_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def auto_gratuity(self) -> Decimal:
        party_size = getattr(self.guest, 'party_size', 1) if self.guest else 1
        if party_size >= GRATUITY_THRESHOLD:
            return (self.subtotal * self.gratuity_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00")

    @property
    def grand_total(self) -> Decimal:
        return self.subtotal + self.sales_tax + self.auto_gratuity

class Transaction(BaseModel):
    txn_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    cart: Cart
    table_num: int
    staff_id: str # Simplified to ID for flat storage
    tip: Decimal = Field(default=Decimal("0.00"))
    timestamp: datetime = Field(default_factory=datetime.now)

    def apply_tip(self, amount_str: str) -> bool:
        try:
            clean = amount_str.replace("$", "").replace("%", "").strip()
            if "%" in amount_str:
                self.tip = (self.cart.subtotal * (Decimal(clean) / 100)).quantize(Decimal("0.01"))
            else:
                self.tip = Decimal(clean).quantize(Decimal("0.01"))
            return True
        except:
            return False

# ==============================================================================
# LABOR & STAFF
# ==============================================================================

class Staff(Person):
    staff_id: str
    dept: str
    role: str
    hourly_rate: Decimal
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None
    had_break: bool = True

    @validator('dept')
    def format_dept(cls, v):
        return v.upper()

    def clock_in(self):
        self.shift_start = datetime.now()

    def clock_out(self):
        self.shift_end = datetime.now()

    def calculate_shift_pay(self) -> Decimal:
        if not self.shift_start or not self.shift_end:
            return Decimal("0.00")
        
        delta = self.shift_end - self.shift_start
        hrs = Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"))
        
        if hrs <= 8:
            pay = hrs * self.hourly_rate
        else:
            pay = (8 * self.hourly_rate) + ((hrs - 8) * self.hourly_rate * Decimal("1.5"))
            
        if hrs > 6 and not self.had_break:
            pay += self.hourly_rate
            
        return pay.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @classmethod
    def from_dict(cls, data):
        """Rebuilds a Staff object from saved JSON data."""
        return cls(data["staff_id"], data["first_name"], data["last_name"], 
                   data["dept"], data["role"], data["hourly_rate"])