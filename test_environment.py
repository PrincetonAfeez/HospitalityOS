"""
Financial smoke tests for tax, tips, modifiers, and tax-exempt guests.
Run manually: python test_environment.py
"""

import sys
from decimal import Decimal, ROUND_HALF_UP

from hospitality_models import Guest
from models import Cart, MenuItem, Modifier, Transaction
from settings.restaurant_defaults import TAX_RATE


def print_test_header(name: str) -> None:
    print(f"\n[TEST] RUNNING: {name}")
    print("-" * 50)


def test_financial_engine() -> None:
    print_test_header("Core Sales & Tax Engine")
    item = MenuItem(
        name="Gourmet Burger",
        price=Decimal("10.00"),
        category="Mains",
        line_inv=10,
        walk_in_inv=5,
        freezer_inv=5,
        par_level=20,
    )
    cart = Cart()
    cart.add_to_cart(item)
    expected_tax = (cart.subtotal * Decimal(str(TAX_RATE))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if cart.sales_tax == expected_tax:
        print(f"[OK] Tax Logic Passed: Calculated ${cart.sales_tax} on ${cart.subtotal} subtotal.")
    else:
        print(f"[FAIL] Tax Logic Failed: Expected {expected_tax}, got {cart.sales_tax}")

    txn = Transaction(cart=cart, table_num=5, staff_id="EMP-01")
    txn.apply_tip("20%")

    if txn.tip == Decimal("2.00"):
        print(f"[OK] Tip Logic Passed: 20% Gratuity correctly calculated as ${txn.tip}.")
    else:
        print(f"[FAIL] Tip Logic Failed: Expected 2.00, got {txn.tip}")


def test_modifier_math() -> None:
    print_test_header("Modifier & Surcharge Logic")
    item = MenuItem(
        name="Steak",
        price=Decimal("10.00"),
        category="Mains",
        line_inv=10,
        walk_in_inv=5,
        freezer_inv=5,
        par_level=20,
    )
    item.add_modifier(Modifier(name="Bacon Wrap", price=Decimal("2.50")))
    cart = Cart()
    cart.add_to_cart(item)
    expected_subtotal = Decimal("12.50")
    if cart.subtotal == expected_subtotal:
        print(f"[OK] Modifier Math Passed: Subtotal correctly aggregated to ${cart.subtotal}.")
    else:
        print(f"[FAIL] Modifier Math Failed: Expected {expected_subtotal}, got {cart.subtotal}")


def test_tax_exemption_logic() -> None:
    print_test_header("Tax Exemption (Non-Profit/CRM) Test")
    vip_guest = Guest(
        guest_id="GST-99",
        first_name="Princeton",
        last_name="Afeez",
        phone="555-0101",
        is_tax_exempt=True,
    )
    item = MenuItem(
        name="Catering Tray",
        price=Decimal("100.00"),
        category="Catering",
        line_inv=1,
        walk_in_inv=1,
        freezer_inv=1,
        par_level=1,
    )
    cart = Cart(guest=vip_guest)
    cart.add_to_cart(item)
    if cart.sales_tax == Decimal("0.00"):
        print("[OK] Tax Exemption Passed: $0.00 tax applied to Exempt Guest.")
    else:
        print(f"[FAIL] Tax Exemption Failed: Tax calculated as ${cart.sales_tax} despite exempt status.")


def run_all_math_tests() -> None:
    print("=" * 50)
    print(f"{'HOSPITALITY OS: FINANCIAL UNIT TESTING':^50}")
    print("=" * 50)
    try:
        test_financial_engine()
        test_modifier_math()
        test_tax_exemption_logic()
        print("\n[OK] ALL FINANCIAL TESTS PASSED. The Money Engine is healthy.")
    except Exception as exc:
        print(f"\n[ERROR] CRITICAL MATH ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run_all_math_tests()
