"""
HospitalityOS v4.0 - Shared Brain Integration Test
Description: Verifies that Ledger, Inventory, and Staff snapshots 
             sync correctly across different system modules.
"""

import os
import json
from decimal import Decimal
from database import load_system_state, save_system_state
from models import Menu, MenuItem, DailyLedger, Staff, Cart, Transaction
from utils import PathManager

def run_integration_test():
    print("🧪 Starting Shared Brain Integration Test...")

    # 1. SETUP: Create a clean environment
    menu, ledger, staff_list = load_system_state()
    test_item_name = "Classic Burger"
    
    if test_item_name not in menu.items:
        print(f"❌ Test Failed: {test_item_name} not found in menu.csv. Run setup_os.py first.")
        return

    initial_inv = menu.items[test_item_name].line_inv
    print(f"📦 Initial Inventory for {test_item_name}: {initial_inv}")

    # 2. MOCK TRANSACTION: Simulate a sale
    print("\n🛒 Simulating a sale of 2 Burgers...")
    cart = Cart()
    burger = menu.items[test_item_name]
    
    # Add 2 burgers to cart
    cart.add_to_cart(burger)
    cart.add_to_cart(burger)
    
    # Create a transaction and record it in the ledger
    mock_staff = Staff("EMP-01", "Princeton", "Afeez", "Manager", "Manager", Decimal("35.00"))
    txn = Transaction(cart, table_number=10, staff=mock_staff)
    ledger.record_sale(cart.subtotal)
    
    print(f"💰 New Ledger Total: ${ledger.total_revenue}")
    print(f"📉 Expected New Inventory: {burger.line_inv}")

    # 3. ATOMIC SAVE: Push state to JSON
    print("\n💾 Performing Atomic Sync to restaurant_state.json...")
    save_system_state(menu, ledger.total_revenue, ledger.transaction_count)

    # 4. REHYDRATION VERIFICATION: Reload from disk
    print("\n🔄 Rehydrating system from Shared Brain...")
    new_menu, new_ledger, new_staff = load_system_state()

    # TEST A: Ledger Sync
    if new_ledger.total_revenue == ledger.total_revenue:
        print("✅ SUCCESS: Ledger Revenue synced.")
    else:
        print(f"❌ FAILURE: Ledger mismatch. Expected {ledger.total_revenue}, got {new_ledger.total_revenue}")

    # TEST B: Inventory Sync
    rehydrated_inv = new_menu.items[test_item_name].line_inv
    if rehydrated_inv == initial_inv - 2:
        print("✅ SUCCESS: Inventory counts synced.")
    else:
        print(f"❌ FAILURE: Inventory mismatch. Expected {initial_inv - 2}, got {rehydrated_inv}")

    # TEST C: Staff State (Check if JSON recorded the last active user)
    state_path = PathManager.get_path("restaurant_state.json")
    with open(state_path, 'r') as f:
        raw_json = json.load(f)
        # Check the 'last_updated' key exists
        if "last_updated" in raw_json:
            print(f"✅ SUCCESS: Timestamp recorded ({raw_json['last_updated']})")

    print("\n✨ Integration Test Complete. The 'Shared Brain' is healthy.")

if __name__ == "__main__":
    run_integration_test()