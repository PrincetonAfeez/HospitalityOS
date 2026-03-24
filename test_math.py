"""Quick standalone checks for Cart + Transaction (legacy Day-2 script)."""

from decimal import Decimal

from models import Cart, MenuItem, Modifier, Transaction
from settings.restaurant_defaults import TAX_RATE


def test_financial_engine() -> None:
    print("🧪 Running Day 2 Financial Unit Test...")
    item = MenuItem(
        name="Burger",
        price=Decimal("10.00"),
        category="Mains",
        line_inv=1,
        walk_in_inv=1,
        freezer_inv=1,
        par_level=1,
    )
    cart = Cart()
    cart.add_to_cart(item)

    expected_tax = (cart.subtotal * Decimal(str(TAX_RATE))).quantize(Decimal("0.01"))
    if cart.sales_tax == expected_tax:
        print(f"✅ Tax Calculation Passed: ${cart.sales_tax}")
    else:
        print(f"❌ Tax Calculation Failed: Expected {expected_tax}, got {cart.sales_tax}")

    txn = Transaction(cart=cart, table_num=1, staff_id="EMP-TEST")
    txn.apply_tip("20%")
    if txn.tip == Decimal("2.00"):
        print(f"✅ Tip Calculation Passed: ${txn.tip}")
    else:
        print(f"❌ Tip Calculation Failed: Expected 2.00, got {txn.tip}")


def test_modifier_math() -> None:
    item = MenuItem(
        name="Burger",
        price=Decimal("10.00"),
        category="Mains",
        line_inv=10,
        walk_in_inv=5,
        freezer_inv=5,
        par_level=20,
    )
    item.add_modifier(Modifier(name="Bacon", price=Decimal("2.00")))
    cart = Cart()
    cart.add_to_cart(item)
    expected_subtotal = Decimal("12.00")
    print(f"Calculated Subtotal: {cart.subtotal}")
    assert cart.subtotal == expected_subtotal
    print("✅ Modifier math test passed!")


if __name__ == "__main__":
    test_financial_engine()
    test_modifier_math()
