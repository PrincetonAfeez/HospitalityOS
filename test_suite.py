"""
HospitalityOS v4.0 - Full System Integration Test Suite
Architect: Princeton Afeez
Description: The final validation layer. Covers Payroll, Inventory, 
             Financial Math, Analytics, and Input Validation.
"""
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

# --- CORE IMPORTS ---
from models import (
    Cart, Transaction, Staff, Menu, MenuItem, Modifier,
    DailyLedger, InsufficientStockError, AnalyticsEngine, Guest
)
from validator import get_date
from settings.restaurant_defaults import TAX_RATE, MIN_WAGE, MAX_MODS

# ==============================================================================
# TEST FIXTURES & HELPERS
# ==============================================================================

def make_staff(dept="FOH", rate=20.0):
    return Staff("EMP-99", "Test", "User", dept, "Server", Decimal(str(rate)))

def make_item(name="Burger", price=12.0, line_inv=5):
    return MenuItem("FOOD-01", name, Decimal(str(price)), line_inv, 5, 5, 10)

# ==============================================================================
# LABOR & COMPLIANCE (PHASE 4)
# ==============================================================================

class TestStaffPayroll(unittest.TestCase):

    def test_min_wage_enforced(self):
        """Logic: Staff rates below MIN_WAGE must be automatically corrected."""
        # Using 10.0 to trigger the floor check
        s = make_staff(rate=10.0) 
        self.assertGreaterEqual(s.hourly_rate, Decimal(str(MIN_WAGE)))

    def test_overtime_pay_calculation(self):
        """Logic: 8 hours @ Reg, 2 hours @ 1.5x."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=10)
        s.shift_end = datetime.now()
        pay = s.calculate_shift_pay(had_break=True)
        # (8 * 20) + (2 * 30) = 220
        self.assertEqual(pay, Decimal("220.00"))

    def test_ca_meal_penalty(self):
        """CA Law: +1 hour pay if shift > 6h and no break taken."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=7)
        s.shift_end = datetime.now()
        # No break: should include $20 penalty
        pay_no_break = s.calculate_shift_pay(had_break=False)
        # Break taken: regular pay
        pay_with_break = s.calculate_shift_pay(had_break=True)
        self.assertEqual(pay_no_break - pay_with_break, Decimal("20.00"))

# ==============================================================================
# CART & INVENTORY (PHASE 2)
# ==============================================================================

class TestCartInventory(unittest.TestCase):

    def test_inventory_deduction_on_add(self):
        item = make_item(line_inv=10)
        cart = Cart()
        cart.add_to_cart(item)
        self.assertEqual(item.line_inv, 9)

    def test_insufficient_stock_block(self):
        """Logic: System must prevent sales of 86'd items."""
        item = make_item(line_inv=0)
        cart = Cart()
        with self.assertRaises(InsufficientStockError):
            cart.add_to_cart(item)

    def test_tax_exemption_guest(self):
        """CRM Integration: Tax-exempt guests must result in $0.00 tax."""
        guest = Guest("G-01", "Test", "Guest", "555-0101")
        guest.is_tax_exempt = True
        item = make_item(price=100.0)
        cart = Cart(guest=guest)
        cart.add_to_cart(item)
        self.assertEqual(cart.sales_tax, Decimal("0.00"))

# ==============================================================================
# FINANCIALS & TIPS (PHASE 1)
# ==============================================================================

class TestFinancials(unittest.TestCase):

    def setUp(self):
        # Reset Singleton
        DailyLedger._instance = None
        self.ledger = DailyLedger()

    def test_tip_percentage_logic(self):
        item = make_item(price=50.0)
        cart = Cart()
        cart.add_to_cart(item)
        txn = Transaction(cart, table_num=1, staff=make_staff())
        txn.apply_tip("20%") # 20% of 50 = 10
        self.assertEqual(txn.tip, Decimal("10.00"))

    def test_revenue_accumulation(self):
        self.ledger.record_sale(Decimal("100.00"))
        self.ledger.record_sale(Decimal("50.00"))
        self.assertEqual(self.ledger.total_revenue, Decimal("150.00"))
        self.assertEqual(self.ledger.transaction_count, 2)

# ==============================================================================
# ANALYTICS & GM DASHBOARD (PHASE 4)
# ==============================================================================

class TestAnalytics(unittest.TestCase):

    def setUp(self):
        self.menu = Menu()
        self.item_a = make_item("Burger", price=10.0, line_inv=2) # Below Par
        self.item_b = make_item("Steak", price=50.0, line_inv=20) # Above Par
        self.menu.add_item(self.item_a)
        self.menu.add_item(self.item_b)

    def test_reorder_logic(self):
        """Verify the 'Low Stock' alert for the GM."""
        engine = AnalyticsEngine(DailyLedger(), self.menu)
        reorders = engine.get_reorder_list()
        self.assertIn(self.item_a, reorders)
        self.assertNotIn(self.item_b, reorders)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "═"*60)
    print(f"║ {'HOSPITALITY OS v4.0 - FINAL INTEGRATION SUITE' :^56} ║")
    print("═"*60)
    unittest.main(verbosity=2)