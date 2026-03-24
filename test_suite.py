"""
HospitalityOS v4.0 - Full System Integration Test Suite
Unit tests aligned with current Pydantic models (Menu dict, DailyLedger, Cart).
"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from hospitality_models import Guest
from models import (
    AnalyticsEngine,
    Cart,
    DailyLedger,
    InsufficientStockError,
    Menu,
    MenuItem,
    Staff,
    Transaction,
)
from settings.restaurant_defaults import MIN_WAGE


def make_staff(dept: str = "FOH", rate: float = 20.0) -> Staff:
    """Factory: generic server used across payroll and tip tests."""
    return Staff(
        staff_id="EMP-99",
        first_name="Test",
        last_name="User",
        dept=dept,
        role="Server",
        hourly_rate=Decimal(str(rate)),
    )


def make_item(name: str = "Burger", price: float = 12.0, line_inv: int = 5) -> MenuItem:
    """Factory: menu row with enough inventory for typical cart tests."""
    return MenuItem(
        name=name,
        price=Decimal(str(price)),
        category="Test",
        line_inv=line_inv,
        walk_in_inv=5,
        freezer_inv=5,
        par_level=10,
    )


class TestStaffPayroll(unittest.TestCase):
    def test_min_wage_enforced(self) -> None:
        """Hourly rate below MIN_WAGE is bumped up by the field validator."""
        staff = make_staff(rate=10.0)
        self.assertGreaterEqual(staff.hourly_rate, MIN_WAGE)

    def test_overtime_pay_calculation(self) -> None:
        """Ten-hour shift pays 8 regular + 2 at 1.5x when break honored."""
        staff = make_staff(rate=20.0)
        staff.shift_start = datetime.now() - timedelta(hours=10)
        staff.shift_end = datetime.now()
        pay = staff.calculate_shift_pay(had_break=True)
        self.assertEqual(pay, Decimal("220.00"))

    def test_ca_meal_penalty(self) -> None:
        """Seven-hour shift without break adds one hour of pay at base rate."""
        staff = make_staff(rate=20.0)
        staff.shift_start = datetime.now() - timedelta(hours=7)
        staff.shift_end = datetime.now()
        pay_no_break = staff.calculate_shift_pay(had_break=False)
        pay_with_break = staff.calculate_shift_pay(had_break=True)
        self.assertEqual(pay_no_break - pay_with_break, Decimal("20.00"))


class TestCartInventory(unittest.TestCase):
    def test_inventory_deduction_on_add(self) -> None:
        item = make_item(line_inv=10)
        cart = Cart()
        cart.add_to_cart(item)
        self.assertEqual(item.line_inv, 9)

    def test_insufficient_stock_block(self) -> None:
        item = make_item(line_inv=0)
        cart = Cart()
        with self.assertRaises(InsufficientStockError):
            cart.add_to_cart(item)

    def test_tax_exemption_guest(self) -> None:
        guest = Guest(
            guest_id="G-01",
            first_name="Test",
            last_name="Guest",
            phone="555-0101",
            is_tax_exempt=True,
        )
        item = make_item(price=100.0)
        cart = Cart(guest=guest)
        cart.add_to_cart(item)
        self.assertEqual(cart.sales_tax, Decimal("0.00"))


class TestFinancials(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = DailyLedger()

    def test_tip_percentage_logic(self) -> None:
        item = make_item(price=50.0)
        cart = Cart()
        cart.add_to_cart(item)
        txn = Transaction(cart=cart, table_num=1, staff_id=make_staff().staff_id)
        self.assertTrue(txn.apply_tip("20%"))
        self.assertEqual(txn.tip, Decimal("10.00"))

    def test_revenue_accumulation(self) -> None:
        self.ledger.record_sale(Decimal("100.00"))
        self.ledger.record_sale(Decimal("50.00"))
        self.assertEqual(self.ledger.total_revenue, Decimal("150.00"))
        self.assertEqual(self.ledger.transaction_count, 2)


class TestAnalytics(unittest.TestCase):
    def setUp(self) -> None:
        self.menu = Menu()
        self.item_a = make_item("Burger", price=10.0, line_inv=2)
        self.item_b = make_item("Steak", price=50.0, line_inv=20)
        self.menu.add_item(self.item_a)
        self.menu.add_item(self.item_b)

    def test_reorder_logic(self) -> None:
        engine = AnalyticsEngine(DailyLedger(), self.menu)
        reorders = engine.get_reorder_list()
        self.assertIn(self.item_a, reorders)
        self.assertNotIn(self.item_b, reorders)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(f"{'HOSPITALITY OS v4.0 - FINAL INTEGRATION SUITE':^60}")
    print("=" * 60)
    unittest.main(verbosity=2)
