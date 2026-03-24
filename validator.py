"""
HospitalityOS v4.0 - Input Validation Utility
---------------------------------------------
Central place for input() loops so every module shares the same rules for
IDs, money, dates, and y/n prompts — fewer crashes from bad typing.
"""

from datetime import date, datetime, time  # Calendar math used by FOH and labor tools
from decimal import Decimal, InvalidOperation  # Money must stay out of binary floats
from typing import Any, List, Optional, Type  # Health-check helper typing

from pydantic import BaseModel, ValidationError  # Optional batch validation against models


def get_staff_id(prompt: str) -> str:
    """Loop until input resembles EMP-01 style IDs used in staff.csv."""
    while True:
        entry = input(prompt).strip().upper()
        if entry.startswith("EMP-") and len(entry) >= 5:
            return entry
        print("⚠️  INVALID FORMAT: Staff IDs must start with 'EMP-' (e.g., EMP-01)")


def get_int(prompt: str, min_val: int = 0, max_val: Optional[int] = None) -> int:
    """Parse int; optionally clamp to min/max inclusive."""
    while True:
        try:
            val = int(input(prompt))
            too_low = min_val is not None and val < min_val
            too_high = max_val is not None and val > max_val
            if too_low or too_high:
                label = f"between {min_val} and {max_val}" if max_val is not None else f"at least {min_val}"
                print(f"⚠️  OUT OF RANGE: Please enter a number {label}.")
                continue
            return val
        except ValueError:
            print("⚠️  DATA TYPE ERROR: Please enter a whole number (no decimals or letters).")


def get_decimal_input(prompt: str, allow_negative: bool = False) -> Decimal:
    """Return Decimal for dollars; strip $ and commas first."""
    while True:
        entry = input(prompt).replace("$", "").replace(",", "").strip()
        try:
            val = Decimal(entry)
            if not allow_negative and val < 0:
                print("⚠️  VALUE ERROR: Financial entries cannot be negative.")
                continue
            return val
        except (InvalidOperation, ValueError):
            print("⚠️  CURRENCY ERROR: Enter a valid price format (e.g., 15.50).")


def get_float(prompt: str, min_val: Optional[float] = None) -> float:
    """Labor auditor helper: quick float with optional floor check."""
    while True:
        try:
            val = float(input(prompt).strip().replace(",", ""))
            if min_val is not None and val < min_val:
                print(f"⚠️ Enter a value of at least {min_val}.")
                continue
            return val
        except ValueError:
            print("⚠️ Enter a valid decimal number.")


def get_name(prompt: str) -> str:
    """Require at least two characters and refuse pure digit 'names'."""
    while True:
        entry = input(prompt).strip()
        if len(entry) > 1 and not entry.isdigit():
            return entry
        print("⚠️  NAME ERROR: Please enter a valid name (at least 2 letters).")


def get_email(prompt: str) -> str:
    """Minimal sanity check: one @ and a dot after it (not RFC-perfect)."""
    while True:
        entry = input(prompt).strip().lower()
        if "@" in entry:
            domain = entry.split("@", 1)[1]
            if "." in domain and len(domain) > 2:
                return entry
        print("⚠️  EMAIL ERROR: Expect name@domain.com style addresses.")


def get_yes_no(prompt: str) -> bool:
    """Normalize many truthy/falsey words to a strict bool."""
    while True:
        entry = input(prompt).strip().lower()
        if entry in ("y", "yes", "true", "1"):
            return True
        if entry in ("n", "no", "false", "0"):
            return False
        print("⚠️  CHOICE ERROR: Please respond with 'y' or 'n'.")


def parse_date_string(raw: str) -> Optional[date]:
    """Return date for MM/DD/YYYY or None if the string does not match."""
    try:
        return datetime.strptime(raw.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def get_date(prompt: str) -> date:
    """Keep asking until parse_date_string succeeds (shared with tests)."""
    while True:
        parsed = parse_date_string(input(prompt).strip())
        if parsed:
            return parsed
        print("⚠️  DATE ERROR: Use MM/DD/YYYY.")


def get_time(prompt: str) -> time:
    """Parse a few human patterns into datetime.time for shift audits."""
    formats = ("%H:%M", "%I:%M %p", "%I:%M%p", "%H%M")
    while True:
        raw = input(prompt).strip()
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        print("⚠️  TIME ERROR: Try 16:30, 4:30 PM, or 1630.")


def format_currency(amount: Any) -> str:
    """Pretty money string without turning Decimals into noisy floats."""
    quantized = Decimal(str(amount)).quantize(Decimal("0.01"))
    return f"${quantized:,.2f}"


def get_verified_high_value(prompt: str, threshold: int = 100) -> int:
    """Ask twice when a big integer could be a typo."""
    val = get_int(prompt)
    if val >= threshold and not get_yes_no(f"  🚩 ALERT: {val} is a high value. Is this correct? (y/n): "):
        return get_verified_high_value(prompt, threshold)
    return val


def run_system_health_check(data_list: List[dict], model_class: Type[BaseModel]) -> List[BaseModel]:
    """Instantiate model_class per dict row; skip rows that fail ValidationError."""
    validated: List[BaseModel] = []
    print(f"🔍 Running Health Check on {model_class.__name__}...")
    for entry in data_list:
        try:
            validated.append(model_class(**entry))
        except ValidationError as exc:
            print(f"❌ DATA CORRUPTION DETECTED: {exc}")
    print(f"✅ Cleaned {len(validated)} records.")
    return validated
