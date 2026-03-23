from decimal import Decimal
from models import MenuItem, Cart, Modifier, Transaction
from settings.restaurant_defaults import TAX_RATE

def test_financial_engine():
    print("🧪 Running Day 2 Financial Unit Test...")
    
    # 1. Setup a fake item ($10.00)
    item = MenuItem("Test", "Burger", "10.00", 1, 1, 1, 1)
    cart = Cart()
    cart.add_to_cart(item)
    
    # 2. Test Tax (Should be $0.95 based on your 9.5% setting)
    expected_tax = Decimal("0.95")
    if cart.sales_tax == expected_tax:
        print(f"✅ Tax Calculation Passed: ${cart.sales_tax}")
    else:
        print(f"❌ Tax Calculation Failed: Expected {expected_tax}, got {cart.sales_tax}")

    # 3. Test Tip (20% of $10.00 should be $2.00)
    txn = Transaction(cart, 1)
    txn.apply_tip("20%")
    if txn.tip == Decimal("2.00"):
        print(f"✅ Tip Calculation Passed: ${txn.tip}")
    else:
        print(f"❌ Tip Calculation Failed: Expected 2.00, got {txn.tip}")

def test_modifier_math():
    # 1. Setup
    item = MenuItem("Test", "Burger", 10.00, 10, 5, 5, 20)
    mod = Modifier("Bacon", 2.00)
    item.add_modifier(mod)
    
    cart = Cart()
    cart.add_to_cart(item)
    
    # 2. Assertions
    expected_subtotal = Decimal("12.00")
    print(f"Calculated Subtotal: {cart.subtotal}")
    assert cart.subtotal == expected_subtotal
    print("✅ Modifier math test passed!")

if __name__ == "__main__":
    test_modifier_math()
    
if __name__ == "__main__":
    test_financial_engine()