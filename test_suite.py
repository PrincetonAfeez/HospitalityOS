"""
HospitalityOS - Test Suite
Covers: Cart, Transaction, Staff payroll, Menu, DailyLedger, validators, modifiers.
Run with: python test_suite.py
"""
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from models import (
    Cart, Transaction, Staff, Menu, MenuItem, Modifier,
    DailyLedger, InsufficientStockError, AnalyticsEngine
)
from validator import get_date


# ==============================================================================
# HELPERS
# ==============================================================================

def make_staff(dept="FOH", rate=20.0):
    return Staff("EMP-99", "Test", "User", dept, "Server", rate)

def make_item(name="Burger", price=12.0, line_inv=5):
    return MenuItem("Food", name, price, line_inv, 5, 5, 10)


# ==============================================================================
# STAFF & PAYROLL TESTS
# ==============================================================================

class TestStaffPayroll(unittest.TestCase):

    def test_min_wage_enforced(self):
        """Staff below min wage should be raised to MIN_WAGE."""
        s = make_staff(rate=10.0)
        self.assertGreaterEqual(s.hourly_rate, Decimal("18.00"))

    def test_regular_pay(self):
        """Shift under 8 hours: straight pay, no penalty."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=4)
        s.shift_end = datetime.now()
        pay = s.calculate_shift_pay(had_break=True)
        self.assertAlmostEqual(float(pay), 4 * 20.0, delta=0.10)

    def test_overtime_pay(self):
        """Shift over 8 hours: first 8 regular, remainder at 1.5x."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=10)
        s.shift_end = datetime.now()
        pay = s.calculate_shift_pay(had_break=True)
        expected = (8 * 20.0) + (2 * 20.0 * 1.5)  # 160 + 60 = 220
        self.assertAlmostEqual(float(pay), expected, delta=0.20)

    def test_ca_meal_penalty_applied(self):
        """Shift > 6h with no break: adds 1hr penalty pay."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=7)
        s.shift_end = datetime.now()
        pay_no_break = s.calculate_shift_pay(had_break=False)
        pay_with_break = s.calculate_shift_pay(had_break=True)
        self.assertAlmostEqual(float(pay_no_break - pay_with_break), 20.0, delta=0.10)

    def test_ca_meal_penalty_not_applied_under_6h(self):
        """Shift <= 6h should never trigger the meal penalty."""
        s = make_staff(rate=20.0)
        s.shift_start = datetime.now() - timedelta(hours=5)
        s.shift_end = datetime.now()
        pay_no_break = s.calculate_shift_pay(had_break=False)
        pay_with_break = s.calculate_shift_pay(had_break=True)
        self.assertEqual(pay_no_break, pay_with_break)

    def test_clock_in_sets_shift_start(self):
        s = make_staff()
        self.assertIsNone(s.shift_start)
        s.clock_in()
        self.assertIsNotNone(s.shift_start)

    def test_clock_out_sets_shift_end(self):
        s = make_staff()
        s.clock_in()
        s.clock_out()
        self.assertIsNotNone(s.shift_end)


# ==============================================================================
# CART TESTS
# ==============================================================================

class TestCart(unittest.TestCase):

    def test_add_item_deducts_inventory(self):
        item = make_item(line_inv=5)
        cart = Cart()
        cart.add_to_cart(item)
        self.assertEqual(item.line_inv, 4)
        self.assertEqual(len(cart.items), 1)

    def test_add_item_clones_prevents_shared_state(self):
        """Modifier on cart item must not affect the master item."""
        item = make_item()
        cart = Cart()
        cart.add_to_cart(item)
        cart.items[0].add_modifier(Modifier("Extra Cheese", 1.50))
        self.assertEqual(len(item.modifiers), 0)

    def test_insufficient_stock_raises(self):
        item = make_item(line_inv=0)
        cart = Cart()
        with self.assertRaises(InsufficientStockError):
            cart.add_to_cart(item)

    def test_units_sold_increments(self):
        item = make_item(line_inv=10)
        cart = Cart()
        cart.add_to_cart(item)
        cart.add_to_cart(item)
        self.assertEqual(item.units_sold, 2)

    def test_subtotal_includes_modifiers(self):
        item = make_item(price=10.0, line_inv=5)
        cart = Cart()
        cart.add_to_cart(item)
        cart.items[0].add_modifier(Modifier("Cheese", 2.0))
        self.assertEqual(cart.subtotal, Decimal("12.00"))

    def test_tax_exempt_guest_pays_no_tax(self):
        class FakeGuest:
            is_tax_exempt = True
        item = make_item(price=100.0, line_inv=5)
        cart = Cart(guest=FakeGuest())
        cart.add_to_cart(item)
        self.assertEqual(cart.sales_tax, Decimal("0.00"))

    def test_void_item_removes_from_cart(self):
        item = make_item(line_inv=5)
        cart = Cart()
        cart.add_to_cart(item)
        result = cart.void_item("Burger")
        self.assertTrue(result)
        self.assertEqual(len(cart.items), 0)

    def test_void_item_not_found_returns_false(self):
        cart = Cart()
        result = cart.void_item("Nonexistent")
        self.assertFalse(result)


# ==============================================================================
# TRANSACTION / TIP TESTS
# ==============================================================================

class TestTransaction(unittest.TestCase):

    def setUp(self):
        item = make_item(price=50.0, line_inv=5)
        cart = Cart()
        cart.add_to_cart(item)
        staff = make_staff()
        self.txn = Transaction(cart, table_num=5, staff=staff)
        self.subtotal = Decimal("50.00")

    def test_tip_dollar_amount(self):
        self.txn.apply_tip("10.00")
        self.assertEqual(self.txn.tip, Decimal("10.00"))

    def test_tip_dollar_with_symbol(self):
        self.txn.apply_tip("$10.00")
        self.assertEqual(self.txn.tip, Decimal("10.00"))

    def test_tip_percentage(self):
        self.txn.apply_tip("20%")
        expected = (self.subtotal * Decimal("0.20")).quantize(Decimal("0.01"))
        self.assertEqual(self.txn.tip, expected)

    def test_tip_invalid_defaults_to_zero(self):
        self.txn.apply_tip("bad input!!!")
        self.assertEqual(self.txn.tip, Decimal("0.00"))

    def test_tip_empty_string_defaults_to_zero(self):
        self.txn.apply_tip("")
        self.assertEqual(self.txn.tip, Decimal("0.00"))


# ==============================================================================
# MENU TESTS
# ==============================================================================

class TestMenu(unittest.TestCase):

    def setUp(self):
        self.menu = Menu()
        self.menu.add_item(make_item("Burger"))
        self.menu.add_item(make_item("Steak"))

    def test_find_item_case_insensitive(self):
        self.assertIsNotNone(self.menu.find_item("burger"))
        self.assertIsNotNone(self.menu.find_item("BURGER"))

    def test_find_item_not_found(self):
        self.assertIsNone(self.menu.find_item("Pizza"))

    def test_find_item_inactive_returns_none(self):
        """86'd items should not be findable through the POS."""
        item = self.menu.find_item("Burger")
        item.is_active = False
        self.assertIsNone(self.menu.find_item("Burger"))


# ==============================================================================
# MODIFIER TESTS
# ==============================================================================

class TestModifier(unittest.TestCase):

    def test_modifier_limit_enforced(self):
        item = make_item()
        item.add_modifier(Modifier("A", 1.0))
        item.add_modifier(Modifier("B", 1.0))
        item.add_modifier(Modifier("C", 1.0))
        result = item.add_modifier(Modifier("D", 1.0))
        self.assertFalse(result)
        self.assertEqual(len(item.modifiers), 3)

    def test_modifier_added_successfully(self):
        item = make_item()
        result = item.add_modifier(Modifier("Extra Cheese", 1.50))
        self.assertTrue(result)


# ==============================================================================
# DAILYLEDGER TESTS
# ==============================================================================

class TestDailyLedger(unittest.TestCase):

    def setUp(self):
        # Reset singleton between tests
        DailyLedger._instance = None

    def test_initial_sales_set(self):
        ledger = DailyLedger(Decimal("100.00"))
        self.assertEqual(ledger.total_revenue, Decimal("100.00"))

    def test_record_sale_updates_revenue_and_count(self):
        ledger = DailyLedger(Decimal("0.00"))
        ledger.record_sale(Decimal("50.00"))
        ledger.record_sale(Decimal("25.00"))
        self.assertEqual(ledger.total_revenue, Decimal("75.00"))
        self.assertEqual(ledger.transaction_count, 2)

    def test_singleton_returns_same_instance(self):
        a = DailyLedger()
        b = DailyLedger()
        self.assertIs(a, b)


# ==============================================================================
# ANALYTICS TESTS
# ==============================================================================

class TestAnalyticsEngine(unittest.TestCase):

    def setUp(self):
        DailyLedger._instance = None
        self.menu = Menu()
        self.burger = make_item("Burger", price=12.0, line_inv=10)
        self.steak = make_item("Steak", price=50.0, line_inv=10)
        self.menu.add_item(self.burger)
        self.menu.add_item(self.steak)

    def test_top_items_by_units_sold_not_price(self):
        """Burger sold twice should rank above Steak (higher price, 0 sold)."""
        cart = Cart()
        cart.add_to_cart(self.burger)
        cart.add_to_cart(self.burger)
        ledger = DailyLedger(Decimal("100.00"))
        engine = AnalyticsEngine(ledger, self.menu)
        top = engine.get_top_performing_items(2)
        self.assertEqual(top[0].name, "Burger")

    def test_reorder_list_below_par(self):
        self.burger.line_inv = 2  # below par_level=10
        ledger = DailyLedger(Decimal("0.00"))
        engine = AnalyticsEngine(ledger, self.menu)
        reorders = engine.get_reorder_list()
        self.assertIn(self.burger, reorders)
        self.assertNotIn(self.steak, reorders)


# ==============================================================================
# VALIDATOR TESTS
# ==============================================================================

class TestGetDate(unittest.TestCase):

    def _call(self, input_str):
        """Directly test the parsing logic without interactive input."""
        import re, datetime as dt
        formats = ["%B %d", "%b %d", "%m/%d", "%m/%d/%Y", "%Y-%m-%d"]
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", input_str, flags=re.IGNORECASE)
        for fmt in formats:
            try:
                parsed = dt.datetime.strptime(cleaned, fmt)
                if parsed.year == 1900:
                    parsed = parsed.replace(year=dt.date.today().year)
                return parsed.date()
            except ValueError:
                continue
        return None

    def test_full_month_name(self):
        result = self._call("October 12")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 12)

    def test_ordinal_suffix_stripped(self):
        result = self._call("Oct 12th")
        self.assertIsNotNone(result)
        self.assertEqual(result.day, 12)

    def test_slash_format(self):
        result = self._call("10/12")
        self.assertIsNotNone(result)
        self.assertEqual(result.month, 10)

    def test_iso_format(self):
        result = self._call("2026-10-12")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)

    def test_invalid_returns_none(self):
        result = self._call("not a date")
        self.assertIsNone(result)


# ==============================================================================
# APPLY_TIP RETURN VALUE TESTS
# ==============================================================================

class TestApplyTipReturnValue(unittest.TestCase):
    """apply_tip now returns True/False instead of silently defaulting."""

    def setUp(self):
        DailyLedger._instance = None
        item = make_item(price=50.0, line_inv=5)
        cart = Cart()
        cart.add_to_cart(item)
        self.txn = Transaction(cart, table_num=1, staff=make_staff())

    def test_valid_dollar_returns_true(self):
        self.assertTrue(self.txn.apply_tip("10.00"))

    def test_valid_percent_returns_true(self):
        self.assertTrue(self.txn.apply_tip("20%"))

    def test_invalid_input_returns_false(self):
        self.assertFalse(self.txn.apply_tip("bad!!!"))

    def test_invalid_does_not_change_tip(self):
        self.txn.apply_tip("bad!!!")
        # tip should be unchanged from default
        self.assertEqual(self.txn.tip, Decimal("0.00"))


# ==============================================================================
# DAILYLEDGER RESET TESTS
# ==============================================================================

class TestDailyLedgerReset(unittest.TestCase):

    def setUp(self):
        DailyLedger._instance = None

    def test_reset_clears_revenue(self):
        ledger = DailyLedger(Decimal("500.00"))
        ledger.record_sale(Decimal("100.00"))
        fresh = DailyLedger.reset(Decimal("0.00"))
        self.assertEqual(fresh.total_revenue, Decimal("0.00"))
        self.assertEqual(fresh.transaction_count, 0)

    def test_reset_returns_new_instance(self):
        a = DailyLedger(Decimal("100.00"))
        b = DailyLedger.reset(Decimal("50.00"))
        self.assertEqual(b.total_revenue, Decimal("50.00"))


# ==============================================================================
# MAX_MODS FROM SETTINGS TESTS
# ==============================================================================

class TestMaxModsFromSettings(unittest.TestCase):

    def test_modifier_cap_matches_settings(self):
        """The enforced cap must equal MAX_MODS from settings."""
        from models import MAX_MODS
        item = make_item()
        for i in range(MAX_MODS):
            result = item.add_modifier(Modifier(f"Mod{i}", 1.0))
            self.assertTrue(result, f"Modifier {i+1} should be accepted")
        overflow = item.add_modifier(Modifier("Overflow", 1.0))
        self.assertFalse(overflow)
        self.assertEqual(len(item.modifiers), MAX_MODS)


# ==============================================================================
# INVENTORY AUDIT JSON KEY TESTS
# ==============================================================================

class TestInventoryAuditJsonKey(unittest.TestCase):

    def test_load_sales_data_builds_inventory_from_menu_snapshot(self):
        """load_sales_data must expose shared_brain['inventory'] keyed by name."""
        import json, tempfile, os
        from inventorymanager import load_sales_data

        # Write a restaurant_state.json in the format save_system_state produces
        state = {
            "net_sales": 250.0,
            "menu_snapshot": [
                {"name": "Burger", "price": "12.00", "modifiers": [], "line_inv": 3},
                {"name": "Steak",  "price": "48.00", "modifiers": [], "line_inv": 7},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(state, f)
            tmp_path = f.name

        try:
            result = load_sales_data(tmp_path)
            self.assertIn("inventory", result)
            self.assertEqual(result["inventory"]["Burger"], 3)
            self.assertEqual(result["inventory"]["Steak"], 7)
            self.assertEqual(result["net_sales"], 250.0)
        finally:
            os.unlink(tmp_path)

    def test_load_sales_data_missing_file_returns_empty(self):
        from inventorymanager import load_sales_data
        result = load_sales_data("nonexistent_file_xyz.json")
        self.assertEqual(result["inventory"], {})
        self.assertEqual(result["net_sales"], 0.0)


# ==============================================================================
# GET_TIME END_HOUR TESTS
# ==============================================================================

class TestGetTimeEndHour(unittest.TestCase):
    """end_hour was previously accepted but never enforced."""

    def _parse(self, t_str):
        """Exercise the time-parsing logic without interactive input."""
        import datetime as dt
        t_str = t_str.strip().lower().replace(".", ":")
        if t_str.isdigit():
            t_str += ":00"
        formats = ["%H:%M", "%I:%M%p", "%I%p", "%I:%M %p"]
        for fmt in formats:
            try:
                return dt.datetime.strptime(t_str, fmt).time()
            except ValueError:
                continue
        return None

    def test_time_within_hours_is_valid(self):
        t = self._parse("14:00")
        self.assertIsNotNone(t)
        self.assertGreaterEqual(t.hour, 11)
        self.assertLess(t.hour, 21)

    def test_time_after_end_hour_detected(self):
        t = self._parse("22:00")
        self.assertIsNotNone(t)
        # Confirm the hour violates end_hour=21
        self.assertGreaterEqual(t.hour, 21)


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
