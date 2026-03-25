"""
HospitalityOS v4.0 - Core Financial & Inventory Models
------------------------------------------------------
This module is the "financial brain": menu catalog, cart math, transactions,
staff payroll helpers, and the daily sales ledger. Data classes use Pydantic v2
so fields are validated automatically when you construct objects.
"""

import logging
import uuid  # Standard library: generates unique transaction IDs
import copy  # Standard library: deep copies menu items when they go into a cart
from datetime import datetime  # Used for transaction timestamps and shift times
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation  # Exact money math (no float drift)
from typing import Any, List, Optional  # Type hints make IDE help and tests clearer

from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils import PathManager, SECURITY_LOG_NAME, configure_logging, get_run_id

LOG = logging.getLogger(__name__)
configure_logging()

# Business constants (tax %, gratuity rules, etc.) live in one settings file
from settings.restaurant_defaults import (
    GRATUITY_RATE,
    GRATUITY_THRESHOLD,
    MAX_MODS,
    MIN_WAGE,
    TAX_RATE,
)


# ==============================================================================
# CUSTOM ERRORS — named exceptions make tests and UI messages clearer
# ==============================================================================


class InsufficientStockError(ValueError):
    """
    Raised when the POS tries to sell an item but line inventory is zero.
    Subclassing ValueError means older 'except ValueError' blocks still catch it.
    """

    pass  # No extra body; the class name documents the failure mode


# ==============================================================================
# SECURITY AUDIT LOG — append-only text file for sensitive actions
# ==============================================================================


class SecurityLog:
    """
    Append-only audit file resolved via PathManager (single location — no cwd fallback).
    """

    @staticmethod
    def log_event(staff_id: str, action: str, details: str, manager_id: str = "SYSTEM") -> None:
        """Build one log line and append it to data/logs/security.log."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rid = get_run_id()[:8]
        log_entry = (
            f"[{timestamp}] RUN:{rid} | STAFF: {staff_id:<8} | AUTH: {manager_id:<8} | "
            f"ACTION: {action:<15} | MSG: {details}\n"
        )
        log_path = PathManager.get_path(SECURITY_LOG_NAME)
        try:
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(log_entry)
        except OSError as exc:
            LOG.error("Security log write failed: %s", exc)


# ==============================================================================
# PEOPLE — shared name handling for staff and guests (Guest subclasses this)
# ==============================================================================


class Person(BaseModel):
    """Base identity: first + last name, normalized to Title Case."""

    first_name: str
    last_name: str

    @field_validator("first_name", "last_name")
    @classmethod
    def format_name(cls, value: str) -> str:
        """Strip stray spaces and use Title Case so 'john DOE' matches 'John Doe'."""
        return value.strip().title()

    @property
    def full_name(self) -> str:
        """Single string for receipts and UI headers."""
        return f"{self.first_name} {self.last_name}"


# ==============================================================================
# MENU — modifiers and line items (inventory + pricing)
# ==============================================================================


class Modifier(BaseModel):
    """A priced add-on (extra cheese, side upgrade, etc.)."""

    name: str
    price: Decimal = Field(default=Decimal("0.00"))

    @field_validator("name")
    @classmethod
    def format_mod_name(cls, value: str) -> str:
        """Keep modifier labels consistent in the kitchen printout."""
        return value.strip().title()


class MenuItem(BaseModel):
    """One row from menu.csv plus runtime fields like units_sold."""

    name: str
    price: Decimal
    category: str
    walk_in_inv: int = Field(default=0, ge=0)
    freezer_inv: int = Field(default=0, ge=0)
    par_level: int = Field(default=10)
    line_inv: int = Field(default=0, ge=0)
    station: str = Field(default="Kitchen")
    modifiers: List[Modifier] = Field(default_factory=list)
    is_active: bool = True
    units_sold: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def clone(self) -> "MenuItem":
        """Return an independent copy so cart line items do not alias inventory rows."""
        return copy.deepcopy(self)

    def add_modifier(self, mod: Modifier) -> None:
        """
        Convenience for tests and POS: append a modifier and respect MAX_MODS.
        """
        if len(self.modifiers) >= MAX_MODS:  # Business rule from settings
            raise ValueError(f"Maximum {MAX_MODS} modifiers per item.")
        self.modifiers.append(mod)


# ==============================================================================
# MENU CATALOG — all items keyed by name for fast lookup
# ==============================================================================


class Menu(BaseModel):
    """
    In-memory representation of menu.csv. Keys are item names; values are MenuItem.
    """

    items: dict[str, MenuItem] = Field(default_factory=dict)

    def add_item(self, item: MenuItem) -> None:
        """Register one item; name becomes the dictionary key."""
        self.items[item.name] = item

    def list_item_candidates(self, name: str, include_inactive: bool = False) -> List[MenuItem]:
        """All menu rows matching fuzzy rules (exact, case, substring, tokens) — may be multiple."""
        key = name.strip()
        if not key:
            return []

        def ok(it: MenuItem) -> bool:
            return include_inactive or it.is_active

        seen: set[str] = set()
        out: List[MenuItem] = []

        def add(it: MenuItem) -> None:
            if it.name not in seen and ok(it):
                seen.add(it.name)
                out.append(it)

        lowered = key.lower()
        if key in self.items:
            add(self.items[key])
        for sn, it in self.items.items():
            if sn.lower() == lowered:
                add(it)
        for sn, it in self.items.items():
            if lowered in sn.lower():
                add(it)
        tokens = [t for t in lowered.split() if len(t) > 1]
        if tokens:
            for it in self.items.values():
                if ok(it) and all(t in it.name.lower() for t in tokens):
                    add(it)
        return out

    def find_item(self, name: str, include_inactive: bool = False) -> Optional[MenuItem]:
        """
        Unique match only; if multiple candidates exist, returns None (use POS disambiguation).
        """
        cands = self.list_item_candidates(name, include_inactive=include_inactive)
        if len(cands) == 1:
            return cands[0]
        return None


# ==============================================================================
# CART & TRANSACTION — guest check math
# ==============================================================================


class Cart(BaseModel):
    """
    Running check for one table session. Items list holds clones sold from MenuItem.
    loyalty_discount reduces the taxable subtotal after redemption (dollars).
    """

    items: List[MenuItem] = Field(default_factory=list)
    guest: Optional[Any] = None
    tax_rate: Decimal = Field(default=Decimal(str(TAX_RATE)))
    gratuity_rate: Decimal = Field(default=Decimal(str(GRATUITY_RATE)))
    loyalty_discount: Decimal = Field(default=Decimal("0.00"), ge=0)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_to_cart(self, master_item: MenuItem) -> None:
        """Decrement master inventory, bump units_sold, append a clone to this cart."""
        if master_item.line_inv <= 0:
            raise InsufficientStockError(f"86 ALERT: {master_item.name} is out of stock!")
        master_item.line_inv -= 1
        master_item.units_sold += 1
        self.items.append(master_item.clone())

    def void_item(self, item_name: str, staff: Any, reason: str) -> bool:
        """Remove first line matching name (case-insensitive) and write SecurityLog VOID."""
        needle = item_name.strip().lower()
        for idx, it in enumerate(self.items):
            if it.name.lower() == needle:
                removed = self.items.pop(idx)
                SecurityLog.log_event(staff.staff_id, "VOID", f"{removed.name} | {reason}")
                print(f"🗑️ Removed {removed.name}")
                return True
        print("❓ Item not in cart.")
        return False

    @property
    def subtotal(self) -> Decimal:
        """Sum of line prices plus their modifiers before tax/discount."""
        total = Decimal("0.00")
        for item in self.items:
            total += item.price
            total += sum(m.price for m in item.modifiers)
        return total

    @property
    def taxable_subtotal(self) -> Decimal:
        """Subtotal after loyalty dollar discount (never below zero)."""
        return max(Decimal("0.00"), self.subtotal - self.loyalty_discount)

    @property
    def sales_tax(self) -> Decimal:
        """Tax on taxable_subtotal; guests can be flagged tax-exempt on the Guest model."""
        if self.guest and getattr(self.guest, "is_tax_exempt", False):
            return Decimal("0.00")
        return (self.taxable_subtotal * self.tax_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)

    @property
    def auto_gratuity(self) -> Decimal:
        """Large-party automatic gratuity uses the original subtotal (common POS behavior)."""
        party_size = getattr(self.guest, "party_size", 1) if self.guest else 1
        if party_size >= GRATUITY_THRESHOLD:
            return (self.subtotal * self.gratuity_rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
        return Decimal("0.00")

    @property
    def grand_total(self) -> Decimal:
        """What the guest owes before tip: discounted subtotal + tax + auto-grat."""
        return self.taxable_subtotal + self.sales_tax + self.auto_gratuity


class Transaction(BaseModel):
    """Immutable-style record of one closed check (tip stored separately)."""

    txn_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    cart: Cart
    table_num: int
    staff_id: str
    tip: Decimal = Field(default=Decimal("0.00"))
    timestamp: datetime = Field(default_factory=datetime.now)

    def apply_tip(self, amount: Any) -> bool:
        """
        Accept '20%', '$5', 5, or Decimal('0.20') where 0.20 means 20% of pre-tax subtotal.
        Returns True if parsing succeeded.
        """
        try:
            # Decimal instance: values in (0,1] are treated as a fraction (20% = 0.20)
            if isinstance(amount, Decimal):
                if Decimal("0") < amount <= Decimal("1"):
                    self.tip = (self.cart.subtotal * amount).quantize(Decimal("0.01"))
                else:
                    self.tip = amount.quantize(Decimal("0.01"))
                return True
            amount_str = str(amount).strip()
            clean = amount_str.replace("$", "").replace("%", "").strip()
            if "%" in amount_str:
                self.tip = (self.cart.subtotal * (Decimal(clean) / 100)).quantize(Decimal("0.01"))
            else:
                self.tip = Decimal(clean).quantize(Decimal("0.01"))
            return True
        except (InvalidOperation, ValueError, TypeError):
            return False


# ==============================================================================
# DAILY LEDGER — rolling totals for the business day
# ==============================================================================


class DailyLedger(BaseModel):
    """
    Net sales (pre-tip check totals), tip pool, and transaction count.
    Persisted in restaurant_state.json — tips tracked separately for labor reporting clarity.
    """

    total_revenue: Decimal = Field(default=Decimal("0.00"))
    total_tips: Decimal = Field(default=Decimal("0.00"))
    transaction_count: int = Field(default=0)

    def record_sale(self, amount: Any, tip: Optional[Any] = None) -> None:
        """Add check total to revenue; optional tip accumulated for reporting (not same as revenue)."""
        self.total_revenue += Decimal(str(amount))
        self.transaction_count += 1
        if tip is not None:
            self.total_tips += Decimal(str(tip))


# ==============================================================================
# ANALYTICS — simple GM helpers (reorder list)
# ==============================================================================


class AnalyticsEngine:
    """
    Lightweight reporting: compares each MenuItem.line_inv to par_level.
    """

    def __init__(self, ledger: DailyLedger, menu: Menu) -> None:
        self.ledger = ledger  # Reserved for future KPIs that use sales + inventory
        self.menu = menu

    def get_reorder_list(self) -> List[MenuItem]:
        """Return items below par; uses ledger to flag demo/session context in logs."""
        low: List[MenuItem] = []
        for item in self.menu.items.values():
            if item.line_inv < item.par_level:
                low.append(item)
        if low and self.ledger.total_revenue == Decimal("0.00"):
            LOG.info(
                "Reorder list: %s items below par while ledger net sales is $0 (demo / new session).",
                len(low),
            )
        return low


# ==============================================================================
# STAFF & PAYROLL HELPERS
# ==============================================================================


class Staff(Person):
    """Employee record loaded from staff.csv plus live shift clock times."""

    staff_id: str
    dept: str
    role: str
    hourly_rate: Decimal
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None
    had_break: bool = True

    @field_validator("hourly_rate", mode="before")
    @classmethod
    def enforce_min_wage(cls, value: Any) -> Decimal:
        """Clamp hourly_rate to at least MIN_WAGE in settings (CA compliance demo)."""
        rate = Decimal(str(value))
        return max(rate, MIN_WAGE)

    @field_validator("dept")
    @classmethod
    def format_dept(cls, value: str) -> str:
        """Normalize department labels to upper case for comparisons."""
        return value.upper()

    def clock_in(self) -> None:
        """Mark shift start time to now."""
        self.shift_start = datetime.now()

    def clock_out(self) -> None:
        """Mark shift end time to now."""
        self.shift_end = datetime.now()

    def calculate_shift_pay(self, had_break: Optional[bool] = None) -> Decimal:
        """
        TRAINING / DEMO ONLY — not legal payroll advice. Simplified OT + meal premium model.
        Regular pay up to 8h, then 1.5x; optional CA-style meal premium if >6h and no break.
        If had_break is None, uses self.had_break (lets tests pass explicit True/False).
        """
        if not self.shift_start or not self.shift_end:
            return Decimal("0.00")
        took_break = self.had_break if had_break is None else had_break
        delta = self.shift_end - self.shift_start
        hrs = Decimal(str(delta.total_seconds() / 3600)).quantize(Decimal("0.01"))
        if hrs <= 8:
            pay = hrs * self.hourly_rate
        else:
            pay = (Decimal("8") * self.hourly_rate) + ((hrs - Decimal("8")) * self.hourly_rate * Decimal("1.5"))
        if hrs > 6 and not took_break:
            pay += self.hourly_rate
        return pay.quantize(Decimal("0.01"), ROUND_HALF_UP)

    @classmethod
    def from_dict(cls, data: dict) -> "Staff":
        """Rebuild Staff from a plain dict (JSON import helper)."""
        return cls(
            staff_id=data["staff_id"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            dept=data["dept"],
            role=data["role"],
            hourly_rate=Decimal(str(data["hourly_rate"])),
        )
