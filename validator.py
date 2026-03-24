"""
HospitalityOS v4.0 - Input Validation Utility
Architect: Princeton Afeez
Description: The 'System Firewall.' Acts as a mandatory filter for all 
             user inputs to prevent data corruption, floating-point 
             errors, and logic crashes across all modules.
"""

from decimal import Decimal, InvalidOperation # Critical for exact monetary math

def get_staff_id(prompt):
    """
    Pattern Validation: Enforces the 'EMP-XX' corporate naming convention.
    Ensures database keys for staff remain consistent and searchable.
    """
    while True:
        # Normalize input to uppercase to match the 'EMP-' standard regardless of user shift-key usage
        entry = input(prompt).strip().upper()
        # Logic: Must start with prefix and contain at least one character after the hyphen
        if entry.startswith("EMP-") and len(entry) >= 5:
            return entry
        print("⚠️  INVALID FORMAT: Staff IDs must start with 'EMP-' (e.g., EMP-01)")

def get_int(prompt, min_val=0, max_val=None):
    """
    Numeric Sanitization: Converts string inputs to integers with boundary enforcement.
    Prevents 'ValueError' crashes when a user accidentally types a letter.
    """
    while True:
        try:
            # Attempt to cast the raw string input to a whole number
            val = int(input(prompt))
            # Logic: If boundaries are provided, ensure val sits between min and max
            if (min_val is not None and val < min_val) or (max_val is not None and val > max_val):
                range_msg = f"between {min_val} and {max_val}" if max_val else f"at least {min_val}"
                print(f"⚠️  OUT OF RANGE: Please enter a number {range_msg}.")
                continue
            return val # Return validated integer to the calling module
        except ValueError:
            # Triggered if the input cannot be mathematically converted to an int
            print("⚠️  DATA TYPE ERROR: Please enter a whole number (no decimals or letters).")

def get_decimal_input(prompt, allow_negative=False):
    """
    Financial Precision: Forces monetary inputs into a Decimal object.
    Replaces float math (0.1 + 0.2 != 0.3) with precise base-10 arithmetic.
    """
    while True:
        # Sanitization: Strip currency symbols that users often type by habit
        entry = input(prompt).replace("$", "").replace(",", "").strip()
        try:
            val = Decimal(entry)
            # Logic Guard: Unless specifically allowed, money shouldn't be negative
            if not allow_negative and val < 0:
                print("⚠️  VALUE ERROR: Financial entries cannot be negative.")
                continue
            return val
        except (InvalidOperation, ValueError):
            # Triggered if the string contains multiple decimals or non-numeric characters
            print("⚠️  CURRENCY ERROR: Enter a valid price format (e.g., 15.50).")

def get_name(prompt):
    """
    Text Integrity: Ensures names are descriptive and non-empty.
    Prevents the creation of 'Ghost' items or guests with empty strings as IDs.
    """
    while True:
        # Strip leading/trailing whitespace which can break O(1) dictionary lookups
        entry = input(prompt).strip()
        # Logic: Name must be longer than 1 char and not be a disguised number
        if len(entry) > 1 and not entry.isdigit():
            return entry
        print("⚠️  NAME ERROR: Please enter a valid name (at least 2 letters).")

def get_yes_no(prompt):
    """
    Boolean Logic Gate: Standardizes binary choices (y/n) across the OS.
    Reduces code duplication in 'if/else' decision trees.
    """
    while True:
        # Case-insensitive check for user flexibility
        entry = input(prompt).strip().lower()
        if entry in ['y', 'yes', 'true', '1']:
            return True
        if entry in ['n', 'no', 'false', '0']:
            return False
        print("⚠️  CHOICE ERROR: Please respond with 'y' or 'n'.")

def format_currency(amount):
    """
    UX Display Logic: Formats numbers into human-readable currency strings.
    Ensures consistent visual reporting in the GM Dashboard and Receipts.
    """
    # Formatting: Adds a '$', commas for thousands, and forces 2 decimal places
    return f"${float(amount):,.2f}"

def get_verified_high_value(prompt, threshold=100):
    """
    NEW FEATURE: Double-verification for high-risk data entries.
    Triggered when a manager enters a value that significantly impacts the P&L.
    """
    val = get_int(prompt)
    if val >= threshold:
        # Defensive Programming: Force the user to consciously acknowledge the high number
        if not get_yes_no(f"  🚩 ALERT: {val} is a high value. Is this correct? (y/n): "):
            return get_verified_high_value(prompt, threshold) # Recursive retry
    return val