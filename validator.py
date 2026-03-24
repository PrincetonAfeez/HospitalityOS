import datetime  # Essential for validating reservation and shift dates
import re        # Regular expressions for strict pattern matching (IDs, Emails)
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation  # High-precision financial math
from models import HospitalityError  # Custom exception for domain-specific errors

# ==============================================================================
# DECORATORS & SECURITY UTILITIES
# ==============================================================================

def sanitize_input(func):
    """
    Commit 21: A middleware-style decorator that automatically cleans strings.
    It prevents shell injection and removes 'noise' before validation logic runs.
    """
    def wrapper(*args, **kwargs):
        # Capture the raw output from the input function
        result = func(*args, **kwargs)
        # If the result is a string, strip whitespace and remove dangerous characters
        if isinstance(result, str):
            # Removes semicolons and backslashes often used in command injection attacks
            return result.strip().replace(";", "").replace("\\", "")
        return result
    return wrapper

def validate_input_safety(user_input: str):
    """
    Commit 24: Explicit blacklist check for forbidden system commands.
    Used for sensitive fields to prevent unauthorized system access.
    """
    forbidden = ["DROP TABLE", "DELETE FROM", "SUDO", "RM -RF"]
    # Check if any forbidden term exists in the uppercase version of the input
    if any(term in user_input.upper() for term in forbidden):
        raise HospitalityError("🚨 SECURITY ALERT: Unauthorized character sequence detected.")

# ==============================================================================
# STRING & IDENTITY VALIDATORS
# ==============================================================================

@sanitize_input
def get_name(prompt):
    """Ensures names follow professional standards (No numbers/special symbols)."""
    # Regex: Starts with letter, allows spaces/hyphens, ends with letter
    name_regex = r"^[A-Za-z][A-Za-z\s\-\']+[A-Za-z]$"
    while True:
        # .title() ensures 'ever flores' becomes 'Ever Flores' for the DB
        name = input(prompt).strip().title()
        if re.fullmatch(name_regex, name):
            return name
        print("❌ Invalid Name: Use letters, hyphens, or apostrophes only.")

def get_staff_id(prompt):
    """Commit 23: Enforces the 'EMP-XXX' organizational ID standard."""
    # Pattern: Requires 'EMP-' prefix followed by exactly 2 to 3 digits
    staff_id_regex = r"^EMP-\d{2,3}$"
    while True:
        # Convert to upper so 'emp-01' is corrected to 'EMP-01' automatically
        staff_id = input(prompt).strip().upper()
        if re.fullmatch(staff_id_regex, staff_id):
            return staff_id
        print("❌ Invalid Format: Use 'EMP-' followed by 2-3 digits (e.g., EMP-01).")

def get_email(prompt):
    """Validates structure for staff notifications or digital receipts."""
    email_regex = r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$"
    while True:
        email = input(prompt).strip().lower()
        if re.fullmatch(email_regex, email):
            return email
        print("❌ Invalid Email: Please use format 'name@domain.com'.")

# ==============================================================================
# NUMERIC & FINANCIAL VALIDATORS
# ==============================================================================

def get_int(prompt, min_val=None, max_val=None, allow_zero=False, exact_len=None):
    """Robust integer collector with range and zero-state protection."""
    while True:
        val_str = input(prompt).strip()
        if not val_str:
            print("❌ Input Required: This field cannot be empty.")
            continue
        try:
            val = int(val_str)
            if exact_len is not None and len(val_str) != exact_len:
                print(f"❌ Error: Must be exactly {exact_len} digits.")
                continue
            # Check for zero if the business logic requires a positive count
            if val == 0 and not allow_zero:
                print("❌ Invalid: Value cannot be zero.")
                continue
            # Range validation logic
            if min_val is not None and val < min_val:
                print(f"❌ Error: Minimum allowed is {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"❌ Error: Maximum allowed is {max_val}.")
                continue
            return val
        except ValueError:
            print("❌ Input Error: Please enter a whole number.")

def clean_currency(val_str: str) -> str:
    """Commit 22: Strips UI formatting ($ or ,) so math logic receives raw digits."""
    return val_str.replace("$", "").replace(",", "").strip()

def get_decimal_input(prompt):
    """Collects and validates a decimal/currency input. Strips $ and , formatting."""
    while True:
        try:
            raw = input(prompt).strip()
            val = Decimal(clean_currency(raw))
            if val < 0:
                print("❌ Error: Value cannot be negative.")
                continue
            return val
        except (InvalidOperation, ValueError):
            print("❌ Format Error: Enter a valid amount (e.g., 12.50).")

def get_float(prompt, min_val=None):
    """Financial input collector that converts all strings to Decimal objects."""
    while True:
        try:
            raw = input(prompt)
            # Use Decimal to avoid floating-point binary errors (e.g., 0.1 + 0.2 != 0.3)
            val = Decimal(clean_currency(raw))
            if min_val is not None and val < Decimal(str(min_val)):
                print(f"❌ Error: Value must be at least {min_val}.")
                continue
            return val
        except (InvalidOperation, ValueError):
            print("❌ Format Error: Enter a valid price (e.g., 12.50).")

def get_tip_logic(prompt, subtotal):
    """
    Commit 25: Context-aware tip validator.
    Detects if the user typed a % or a dollar amount and calculates accordingly.
    """
    while True:
        raw_input = input(prompt).strip()
        if not raw_input:
            print("❌ Tip Required: Enter 0 for no tip.")
            continue
        try:
            # Case 1: Percentage Calculation
            if "%" in raw_input:
                percent = Decimal(raw_input.replace("%", ""))
                # Safety check for unusually high tips (e.g., 500%)
                if percent > 100 and not get_yes_no(f"⚠️ Tip is {percent}%. Is this correct? "):
                    continue
                # Calculate percentage and round to nearest cent
                return (subtotal * (percent / 100)).quantize(Decimal("0.01"), ROUND_HALF_UP)
            
            # Case 2: Direct Dollar Amount
            val = Decimal(raw_input.replace("$", ""))
            if val >= 0:
                # Round to nearest cent
                return val.quantize(Decimal("0.01"), ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            print("❌ Format Error: Enter a percentage (15%) or dollar amount ($5).")

# ==============================================================================
# DATE, TIME & BOOLEAN UTILITIES
# ==============================================================================

def get_yes_no(prompt):
    """Standardized boolean picker for UX flow control."""
    while True:
        ans = input(prompt).strip().lower()
        if ans in ['y', 'yes']: return True
        if ans in ['n', 'no']: return False
        print("❌ Please answer 'yes' or 'no'.")

def get_date(prompt):
    """
    Flexible date validator. Accepts common formats:
    'Oct 12', 'Oct 12th', '10/12', '10/12/2026', '2026-10-12'
    Returns a datetime.date object.
    """
    formats = ["%B %d", "%b %d", "%m/%d", "%m/%d/%Y", "%Y-%m-%d"]
    while True:
        raw = input(prompt).strip()
        # Strip ordinal suffixes: 12th -> 12, 3rd -> 3
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw, flags=re.IGNORECASE)
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.datetime.strptime(cleaned, fmt)
                # For formats without a year, default to current year
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.date.today().year)
                break
            except ValueError:
                continue
        if parsed:
            return parsed.date()
        print("❌ Format Error: Try 'Oct 12', '10/12', or '2026-10-12'.")

def get_time(prompt, start_hour=None, end_hour=None):
    """Forgiving time validator: accepts '11', '11:15', '11pm', or '11.15'."""
    while True:
        # Standardize periods to colons for parsing
        t_str = input(prompt).strip().lower().replace(".", ":")
        if t_str.isdigit(): t_str += ":00" # Auto-format '11' to '11:00'
        
        # Test against multiple common time formats for high UX flexibility
        formats = ["%H:%M", "%I:%M%p", "%I%p", "%I:%M %p"]
        parsed_time = None
        for fmt in formats:
            try:
                parsed_time = datetime.datetime.strptime(t_str, fmt).time()
                break
            except ValueError: continue
        
        if parsed_time:
            if start_hour and parsed_time.hour < start_hour:
                print(f"❌ Closed: We open at {start_hour}:00.")
                continue
            if end_hour and parsed_time.hour >= end_hour:
                print(f"❌ Closed: We close at {end_hour}:00.")
                continue
            return parsed_time
        print("❌ Format Error: Try '11am', '11:15', or '23:00'.")

def format_currency(value: Decimal) -> str:
    """Commit 25: Standardizes financial output for all Receipt/UI components."""
    return f"${value:,.2f}"