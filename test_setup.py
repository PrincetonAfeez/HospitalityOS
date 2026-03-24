"""
Shared-brain integration test — skips if seed data missing (no brittle failure on empty repo).
"""

import json
import os
import unittest
from decimal import Decimal

from database import load_system_state, save_system_state
from models import Cart, Staff
from utils import PathManager, RESTAURANT_STATE_NAME


class TestSharedBrainIntegration(unittest.TestCase):
    """Uses real data/menu.csv when Classic Burger exists."""

    def setUp(self) -> None:
        self.menu_path = PathManager.get_path("menu.csv")
        if not os.path.isfile(self.menu_path):
            self.skipTest("data/menu.csv missing — run setup_os.py")

    def test_load_save_roundtrip(self) -> None:
        menu, ledger, _ = load_system_state()
        if "Classic Burger" not in menu.items:
            self.skipTest("Classic Burger not in menu — seed data differs")

        test_item = "Classic Burger"
        initial_inv = menu.items[test_item].line_inv

        cart = Cart()
        burger = menu.items[test_item]
        cart.add_to_cart(burger)
        cart.add_to_cart(burger)

        mock_staff = Staff(
            staff_id="EMP-01",
            first_name="Princeton",
            last_name="Afeez",
            dept="Manager",
            role="Manager",
            hourly_rate="35.00",
        )
        ledger.record_sale(cart.grand_total, tip=Decimal("5.00"))

        save_system_state(menu, ledger, staff_id=mock_staff.staff_id)

        new_menu, new_ledger, _ = load_system_state()

        self.assertEqual(new_ledger.total_revenue, ledger.total_revenue)
        self.assertEqual(new_ledger.total_tips, ledger.total_tips)
        self.assertEqual(new_menu.items[test_item].line_inv, initial_inv - 2)

        state_path = PathManager.get_path(RESTAURANT_STATE_NAME)
        with open(state_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertIn("last_updated", raw)
        self.assertIn("total_tips", raw)


if __name__ == "__main__":
    unittest.main()
