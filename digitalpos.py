"""
HospitalityOS v4.0 - Point of Sale (POS) Interface
--------------------------------------------------
Table-side ordering: dictionary menu lookup, modifiers, loyalty redemption,
and checkout that feeds the DailyLedger + SecurityLog.
"""

import os  # Terminal clear for HUD redraws
from decimal import Decimal  # Modifier upcharges and money display

from manager_tools import require_manager_auth  # Manager-gated void/comp tools

from hospitality_models import Guest  # Guest-aware cart (tax / gratuity flags)
from models import Cart, DailyLedger, Menu, Modifier, SecurityLog, Staff, Transaction
from settings.restaurant_defaults import MAX_MODS  # Cap modifiers per line
from validator import format_currency, get_int, get_name, get_yes_no, get_decimal_input


def run_pos(
    table_num: int,
    guest_obj: Guest,
    menu_brain: Menu,
    daily_ledger: DailyLedger,
    current_staff: Staff,
) -> bool:
    """
    Main ordering loop for one seated party. Returns True after paid close.
    Suspend returns False so the host can resume later.
    """
    active_cart = Cart(guest=guest_obj)
    menu_lookup = {item.name.lower(): item for item in menu_brain.items.values()}

    while True:
        draw_pos_header(table_num, guest_obj, active_cart)
        print(" [1] Add Food/Drink")
        print(" [2] Add Modifier (Sub/Add)")
        print(" [3] View Bill / Print Prep")
        print(" [4] Process Payment & Close")
        print(" [Q] Suspend Session (Save for later)")
        print("═" * 45)

        choice = input("Select Action > ").strip().upper()
        if choice == "1":
            query = get_name("Enter Item Name: ")
            master_item = menu_brain.find_item(query) or menu_lookup.get(query.lower())
            if master_item:
                try:
                    active_cart.add_to_cart(master_item)
                    print(f"✅ {master_item.name} added to Table {table_num}.")
                except Exception as exc:
                    print(f"❌ ERROR: {exc}")
            else:
                print("❓ Item not found in current Menu.")
            input("\nPress Enter...")
        elif choice == "2":
            apply_modifier_workflow(active_cart)
        elif choice == "3":
            display_current_bill(active_cart)
            input("\nPress Enter to return...")
        elif choice == "4":
            if process_checkout(active_cart, table_num, daily_ledger, current_staff):
                return True
        elif choice == "Q":
            print(f"💾 Session for Table {table_num} suspended.")
            return False


def draw_pos_header(table_num: int, guest: Guest, cart: Cart) -> None:
    """Top banner: party context + running grand total."""
    os.system("cls" if os.name == "nt" else "clear")
    print("═" * 45)
    print(f" TABLE: {table_num} | GUEST: {guest.full_name}")
    print(f" PARTY: {guest.party_size} | TOTAL: {format_currency(cart.grand_total)}")
    print("═" * 45)


def apply_modifier_workflow(cart: Cart) -> None:
    """Attach a Modifier model to the most recently added line item."""
    if not cart.items:
        print("⚠️  Add an item to the cart first!")
        return
    target_item = cart.items[-1]
    if len(target_item.modifiers) >= MAX_MODS:
        print(f"⚠️  MAX MODS REACHED: Limit is {MAX_MODS} per item.")
        return

    mod_name = get_name(f"Modifier for {target_item.name}: ")
    mod_price = Decimal("0.00")
    if get_yes_no("Is there an upcharge for this mod? (y/n): "):
        mod_price = get_decimal_input("Upcharge Amount: ")
    new_mod = Modifier(name=mod_name, price=mod_price)
    target_item.modifiers.append(new_mod)
    print(f"📝 Added '{mod_name}' to {target_item.name}.")


def display_current_bill(cart: Cart) -> None:
    """Line-by-line preview including tax, auto-grat, loyalty discount line."""
    print("\n--- PRE-CHECK REVIEW ---")
    for item in cart.items:
        print(f" {item.name:<25} {format_currency(item.price):>10}")
        for mod in item.modifiers:
            if mod.price > 0:
                print(f"  + {mod.name:<23} {format_currency(mod.price):>10}")
            else:
                print(f"  + {mod.name}")
    if cart.loyalty_discount > 0:
        print(f" {'Loyalty discount':<25} -{format_currency(cart.loyalty_discount):>9}")
    print("-" * 40)
    print(f" Subtotal:        {format_currency(cart.subtotal):>10}")
    print(f" Tax:             {format_currency(cart.sales_tax):>10}")
    if cart.auto_gratuity > 0:
        print(f" Auto-Grat (18%): {format_currency(cart.auto_gratuity):>10}")
    print(f" GRAND TOTAL:     {format_currency(cart.grand_total):>10}")


def process_checkout(cart: Cart, table_num: int, ledger: DailyLedger, staff: Staff) -> bool:
    """Confirm bill, optional loyalty burn, tips, ledger + CRM updates."""
    if not cart.items:
        print("⚠️  Cannot checkout an empty table.")
        return False

    display_current_bill(cart)
    guest = cart.guest

    if guest and guest.loyalty_points >= 500:
        print(f"\n⭐ LOYALTY ALERT: {guest.full_name} has {guest.loyalty_points} points.")
        if get_yes_no("Redeem 500 points for a $10.00 discount? (y/n): "):
            before = cart.subtotal
            after = guest.apply_loyalty_discount(before)
            cart.loyalty_discount = before - after
            print("✅ Discount applied. Recalculating totals...")
            display_current_bill(cart)

    if not get_yes_no("\nProceed to Final Payment? (y/n): "):
        return False

    txn = Transaction(cart=cart, table_num=table_num, staff_id=staff.staff_id)
    tip_input = input("Enter Tip Amount (e.g. 5.00 or 20%): ")
    if not txn.apply_tip(tip_input):
        print("⚠️ Tip not applied — invalid format.")

    ledger.record_sale(cart.grand_total, tip=txn.tip)
    SecurityLog.log_event(
        staff.staff_id,
        "PAYMENT_PROCESSED",
        f"Table {table_num} | Total: {format_currency(cart.grand_total + txn.tip)}",
    )

    print("\n" + "═" * 45)
    gname = guest.full_name.upper() if guest else "GUEST"
    print(f" THANK YOU, {gname}!")
    if guest and get_yes_no("Would the guest like to leave a quick rating? (y/n): "):
        rating = get_int("Rate your experience (1-5): ", min_val=1, max_val=5)
        comment = input("Any comments? (Optional): ").strip()
        guest.record_feedback(rating, comment)
        print("🙏 Thank you! Feedback has been saved.")

    if guest:
        guest.add_loyalty_points(cart.grand_total)
    print("\n✅ PAYMENT SUCCESSFUL. Receipt archived.")
    return True


@require_manager_auth
def void_item(current_staff: Staff, cart: Cart, item_index: int, authorized_by: str = "N/A") -> None:
    """Pop by index after manager decorator approves caller."""
    if 0 <= item_index < len(cart.items):
        item = cart.items.pop(item_index)
        SecurityLog.log_event(current_staff.staff_id, "VOID", f"Item: {item.name}", manager_id=authorized_by)
        print(f"🗑️ Voided {item.name}")


@require_manager_auth
def comp_entire_table(current_staff: Staff, cart: Cart, authorized_by: str = "N/A") -> None:
    """Zero the cart after manager approval."""
    details = f"Value: {cart.grand_total}"
    cart.items.clear()
    SecurityLog.log_event(current_staff.staff_id, "COMP_TABLE", details, manager_id=authorized_by)
    print("🎁 Table has been comped.")


@require_manager_auth
def manual_inventory_adjust(current_staff: Staff, item, new_amount: int, authorized_by: str = "N/A") -> None:
    """Direct line inventory overwrite for miscount corrections."""
    old_val = item.line_inv
    item.line_inv = new_amount
    SecurityLog.log_event(
        current_staff.staff_id,
        "INV_ADJUST",
        f"{item.name}: {old_val}->{new_amount}",
        manager_id=authorized_by,
    )
    print("📦 Inventory updated.")
