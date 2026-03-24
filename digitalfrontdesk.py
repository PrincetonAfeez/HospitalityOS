"""
HospitalityOS v4.0 - Digital Front Desk
---------------------------------------
Host workflow: collect Guest, show alerts, best-fit table, optional handoff
to the richer digitalpos session, then persist floor JSON.
"""

import uuid  # Random guest ids like GST-XXXXXXXX
from datetime import date  # Compare month/day for birthdays

import digitalpos  # Table-side ordering UI used after seating

from database import save_system_state  # Optional sync after seating (inventory unaffected here)
from hospitality_models import FloorMap, Guest, Table, WaitlistManager  # Floor + queue types
from models import DailyLedger, Menu, SecurityLog, Staff  # Domain + current clerk for POS
from validator import get_email, get_int, get_name, get_yes_no  # Typed console input


def main_front_desk(
    floor: FloorMap,
    waitlist: WaitlistManager,
    staff: Staff,
    menu: Menu,
    ledger: DailyLedger,
) -> None:
    """Print header, build one Guest, then route to seating or waitlist."""
    print("\n" + "═" * 45)
    print(f"║ {'GUEST INTAKE & RESERVATIONS':^41} ║")
    print("═" * 45)

    guest_obj = collect_guest_details()
    handle_arrival(guest_obj, floor, waitlist, staff, menu, ledger)


def find_best_table(floor: FloorMap, party_size: int) -> Table | None:
    """Pick smallest table that still fits the party to preserve large tops."""
    candidates = [t for t in floor.tables if t.status == "Available" and t.capacity >= party_size]
    if not candidates:
        return None
    candidates.sort(key=lambda t: t.capacity)
    return candidates[0]


def trigger_guest_alerts(guest: Guest) -> None:
    """Print a banner if birthday, anniversary, VIP, or no-show risk applies."""
    today = date.today()
    alerts: list[str] = []

    if guest.birthday and guest.birthday.month == today.month and guest.birthday.day == today.day:
        alerts.append("🎂 BIRTHDAY TODAY: Offer complimentary dessert!")
    if guest.anniversary and guest.anniversary.month == today.month and guest.anniversary.day == today.day:
        alerts.append("🥂 ANNIVERSARY: Offer champagne toast!")
    if guest.is_frequent_noshow:
        alerts.append("⚠️ ATTENTION: Frequent No-Show (Credit Card Guarantee Required)")
    if guest.is_vip:
        alerts.append("💎 VIP GUEST: Priority seating and Manager greeting requested.")

    if alerts:
        print("\n" + "█" * 60)
        print(f"  ALERTS FOR {guest.full_name.upper()}")
        for msg in alerts:
            print(f"  >> {msg}")
        print("█" * 60 + "\n")


def collect_guest_details() -> Guest:
    """Prompt for minimal PMS fields and return a validated Guest instance."""
    print("\n--- NEW RESERVATION ---")
    first_name = get_name("First Name: ")
    last_name = get_name("Last Name: ")
    phone = str(get_int("Mobile Number (10 digits): ", min_val=1000000000, max_val=9999999999))
    guest_email = None
    if get_yes_no("Add email for opt-in / receipts? (y/n): "):
        guest_email = get_email("Email: ")
    adults = get_int("Number of Adults: ", min_val=1)
    children = get_int("Number of Children: ", min_val=0)
    total_party = adults + children

    birthday = None
    if get_yes_no("Is there a Birthday on file? (y/n): "):
        birthday = get_date_simple("Enter Birthday (MM/DD/YYYY): ")

    anniversary = None
    if get_yes_no("Is there an Anniversary on file? (y/n): "):
        anniversary = get_date_simple("Enter Anniversary (MM/DD/YYYY): ")

    allergies: list[str] = []
    if get_yes_no("Any food allergies? (y/n): "):
        print("Enter allergies (Type 'DONE' to finish):")
        while True:
            item = input("> ").strip().title()
            if item.upper() == "DONE":
                break
            if item:
                allergies.append(item)

    gid = f"GST-{str(uuid.uuid4())[:8].upper()}"
    return Guest(
        guest_id=gid,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=guest_email,
        party_size=total_party,
        birthday=birthday,
        anniversary=anniversary,
        allergies=allergies,
    )


def get_date_simple(prompt: str) -> date:
    """Parse MM/DD/YYYY using validator.parse_date or loop until valid."""
    from validator import parse_date_string

    while True:
        raw = input(prompt).strip()
        parsed = parse_date_string(raw)
        if parsed:
            return parsed
        print("⚠️ Use MM/DD/YYYY with slashes.")


def handle_arrival(
    guest_obj: Guest,
    floor: FloorMap,
    waitlist: WaitlistManager,
    staff: Staff,
    menu: Menu,
    ledger: DailyLedger,
) -> None:
    """Seat or queue the guest; optionally launch POS with full menu + ledger context."""
    trigger_guest_alerts(guest_obj)
    print(f"\n--- SEATING: {guest_obj.full_name.upper()} ---")

    assigned_table = find_best_table(floor, guest_obj.party_size)
    if assigned_table:
        assigned_table.seat_guest(guest_obj)
        SecurityLog.log_event(
            staff.staff_id,
            "GUEST_SEATED",
            f"Guest {guest_obj.guest_id} seated at Table {assigned_table.table_id}",
        )
        print(f"✅ Table {assigned_table.table_id} assigned (Capacity: {assigned_table.capacity}).")

        if get_yes_no("Launch POS for this table now? (y/n): "):
            digitalpos.run_pos(assigned_table.table_id, guest_obj, menu, ledger, staff)

        floor.save_floor_state()
        save_system_state(menu, ledger, staff_id=staff.staff_id)
        print("💾 Floor state persisted to active_tables.json")
    else:
        print(f"❌ SORRY: No tables available for a party of {guest_obj.party_size}.")
        if get_yes_no("Would you like to join the waitlist? (y/n): "):
            waitlist.add_to_wait(guest_obj)
            print("📝 You will be notified when a table opens.")


def cancel_reservation(guest_id: str, floor: FloorMap, waitlist: WaitlistManager) -> bool:
    """Walk tables then waitlist to remove a guest session by id string."""
    for table in floor.tables:
        if table.current_guest_id == guest_id:
            table.clear_table()
            print(f"🧹 Table {table.table_id} cleared. Staff notified for busing.")
            SecurityLog.log_event("FRONT_DESK", "SESSION_KILLED", f"Guest {guest_id} walked out.")
            return True

    before = len(waitlist.queue)
    waitlist.queue = [e for e in waitlist.queue if e.guest.guest_id != guest_id]
    if len(waitlist.queue) < before:
        print(f"📝 Guest {guest_id} removed from Waitlist.")
        return True

    print("⚠️ Error: Guest ID not found in active sessions.")
    return False


def fire_to_kitchen(cart, table_num: int) -> bool:
    """Pretty-print a pretend KDS ticket for training demos."""
    if not cart.items:
        print("⚠️ Order is empty. Nothing to fire.")
        return False

    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n🍳 KITCHEN TICKET GENERATED [{ts}]")
    print(f"TABLE: {table_num}")
    for item in cart.items:
        mods = f" ({', '.join(m.name for m in item.modifiers)})" if item.modifiers else ""
        print(f" > {item.name}{mods}")
    print("✅ Order successfully sent to station printers.")
    return True
