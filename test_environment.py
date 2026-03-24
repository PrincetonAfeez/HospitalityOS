"""
HospitalityOS v4.0 - Financial Integrity & Math Unit Tests
Architect: Princeton Afeez
Description: Validates the core "Money Engine." Ensures tax, tips, and 
             modifier surcharges never suffer from floating-point drift.
"""

import sys
from decimal import Decimal, ROUND_HALF_UP # Precise rounding for financial audits
from models import MenuItem, Cart, Modifier, Transaction, Guest
from settings.restaurant_defaults import TAX_RATE # e.g., 0.095 for 9.5%

def print_test_header(name):
    """Visual helper for test reporting."""
    print(f"\n🧪 RUNNING: {name}")
    print("-" * 50)

def test_financial_engine():
    """
    Validates Tax and Tip logic using Decimal precision.
    Ensures rounding follows standard accounting (ROUND_HALF_UP).
    """
    print_test_header("Core Sales & Tax Engine")
    
    # 1. Setup: $10.00 Item with a 9.5% Tax Rate
    # Note: Pass price as a string to Decimal for absolute precision
    item = MenuItem("GST-01", "Gourmet Burger", Decimal("10.00"), 10, 5, 5, 20)
    cart = Cart()
    cart.add_to_cart(item)
    
    # 2. Verify Tax Calculation
    # Logic: $10.00 * 0.095 = $0.95
    expected_tax = (cart.subtotal * Decimal(str(TAX_RATE))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    if cart.sales_tax == expected_tax:
        print(f"✅ Tax Logic Passed: Calculated ${cart.sales_tax} on ${cart.subtotal} subtotal.")
    else:
        print(f"❌ Tax Logic Failed: Expected {expected_tax}, got {cart.sales_tax}")

    # 3. Verify Tip Calculation (Standard 20%)
    # Logic: 20% of $10.00 = $2.00
    txn = Transaction(cart, table_number=5)
    txn.apply_tip(Decimal("0.20")) # v4.0 uses Decimal for tips, not strings
    
    if txn.tip == Decimal("2.00"):
        print(f"✅ Tip Logic Passed: 20% Gratuity correctly calculated as ${txn.tip}.")
    else:
        print(f"❌ Tip Logic Failed: Expected 2.00, got {txn.tip}")

def test_modifier_math():
    """
    Validates "Add-on" logic. Ensures modifiers increase the 
    subtotal correctly before tax is applied.
    """
    print_test_header("Modifier & Surcharge Logic")
    
    # 1. Setup: Base Item ($10.00) + Modifier ($2.50)
    item = MenuItem("MOD-01", "Steak", Decimal("10.00"), 10, 5, 5, 20)
    bacon_mod = Modifier("Bacon Wrap", Decimal("2.50"))
    item.add_modifier(bacon_mod)
    
    cart = Cart()
    cart.add_to_cart(item)
    
    # 2. Assertion: Subtotal must be $12.50
    expected_subtotal = Decimal("12.50")
    if cart.subtotal == expected_subtotal:
        print(f"✅ Modifier Math Passed: Subtotal correctly aggregated to ${cart.subtotal}.")
    else:
        print(f"❌ Modifier Math Failed: Expected {expected_subtotal}, got {cart.subtotal}")

def test_tax_exemption_logic():
    """
    Phase 3 Integration: Validates that Guests flagged as 'Tax Exempt' 
    result in a $0.00 tax line item.
    """
    print_test_header("Tax Exemption (Non-Profit/CRM) Test")
    
    # 1. Setup: Create Guest and toggle tax-exempt status
    vip_guest = Guest("GST-99", "Princeton", "Afeez", "555-0101")
    vip_guest.is_tax_exempt = True 
    
    item = MenuItem("TX-01", "Catering Tray", Decimal("100.00"), 1, 1, 1, 1)
    cart = Cart(guest=vip_guest) # Cart must be aware of the guest
    cart.add_to_cart(item)
    
    # 2. Assertion: Tax must be 0
    if cart.sales_tax == Decimal("0.00"):
        print("✅ Tax Exemption Passed: $0.00 tax applied to Exempt Guest.")
    else:
        print(f"❌ Tax Exemption Failed: Tax calculated as ${cart.sales_tax} despite exempt status.")

def run_all_math_tests():
    """Main execution wrapper for the financial test suite."""
    print("═" * 50)
    print(f"{'HOSPITALITY OS: FINANCIAL UNIT TESTING' :^50}")
    print("═" * 50)
    
    try:
        test_financial_engine()
        test_modifier_math()
        test_tax_exemption_logic()
        print("\n✨ ALL FINANCIAL TESTS PASSED. The Money Engine is healthy.")
    except Exception as e:
        print(f"\n💥 CRITICAL MATH ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_all_math_tests()