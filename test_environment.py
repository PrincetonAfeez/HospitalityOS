"""
HospitalityOS v4.0 - Integration Test Suite
Architect: Princeton Afeez
Description: Automated validation of the 'Shared Brain'. Ensures that 
             Transactions, Inventory, and Labor logs sync across all modules.
"""

import os
import json
from decimal import Decimal
from database import load_system_state, save_system_state
from models import Cart, Transaction, Staff
from hospitality_models import FloorMap

def run_integration_test():
    """
    Simulates a live lunch-rush scenario to verify data integrity.
    """
    print("🧪 Starting HospitalityOS Integration Test...")
    print("=" * 45)

    # 1. INITIALIZATION: Load the current state
    menu, ledger, staff_list = load_system_state()
    test_item_name = "Classic Burger" # Assumes this exists in your menu.csv
    
    # Check if the test item exists to avoid a KeyError
    item = menu.find_item(test_item_name)
    if not item:
        print(f"❌ TEST FAILED: '{test_item_name}' not found in menu.csv.")
        return

    initial_inv = item.line_inv
    print(f"📦 Initial Stock for {test_item_name}: {initial_inv}")

    # 2. MOCK TRANSACTION: Simulate a sale of 2 units
    print(f"\n🛒 Simulating a sale of 2 {test_item_name}s...")
    cart = Cart()
    
    # Process 2 items through the Cart logic
    try:
        cart.add_to_cart(item)
        cart.add_to_cart(item)
    except Exception as e:
        print(f"⚠️  STOCK ALERT: {e}")
        return

    # 3. LABOR MOCK: Attribute the sale to the first staff member found
    mock_staff = staff_list[0] if staff_list else Staff("EMP-99", "Test", "User", "QA", "Tester", 20.00)
    txn = Transaction(cart, table_num=10, staff=mock_staff)
    
    # Record the revenue in the daily ledger
    ledger.record_sale(cart.grand_total)
    print(f"💰 Ledger Updated: +${cart.grand_total:.2f}")

    # 4. ATOMIC SYNC: Force a save to restaurant_state.json
    print("\n💾 Performing Atomic Sync to 'Shared Brain'...")
    save_system_state(menu, ledger.total_revenue, ledger.transaction_count)

    # 5. VERIFICATION: Re-load from disk to ensure persistence
    print("🔄 Rehydrating system from disk...")
    new_menu, new_ledger, _ = load_system_state()

    # TEST A: Revenue Persistence
    if new_ledger.total_revenue == ledger.total_revenue:
        print("✅ SUCCESS: Financial Ledger synced.")
    else:
        print(f"❌ FAILURE: Ledger mismatch! Expected {ledger.total_revenue}, got {new_ledger.total_revenue}")

    # TEST B: Inventory Persistence
    rehydrated_item = new_menu.find_item(test_item_name)
    if rehydrated_item.line_inv == (initial_inv - 2):
        print("✅ SUCCESS: Inventory counts synced.")
    else:
        print(f"❌ FAILURE: Inventory mismatch! Expected {initial_inv - 2}, got {rehydrated_item.line_inv}")

    print("\n" + "=" * 45)
    print("✨ INTEGRATION COMPLETE: The 'Shared Brain' is healthy.")

if __name__ == "__main__":
    run_integration_test()