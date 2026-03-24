"""
HospitalityOS v4.0 - Master Orchestrator
Boot, login, main menu. Service floor uses digitalpos.run_pos (single ordering engine).
"""

import atexit
import logging
import os
import sys
import time
from datetime import datetime
from typing import Optional

import digitalfrontdesk
import digitalpos
import laborcostauditor

from database import (
    check_database_integrity,
    load_system_state,
    save_system_state,
    validate_staff_login,
)
from hospitality_models import FloorMap, WaitlistManager, walk_in_guest_for_table
from models import DailyLedger, Menu, Staff
from utils import configure_logging, try_configure_utf8_stdout
from validator import format_currency, get_int, get_staff_id, get_yes_no

LOG = logging.getLogger(__name__)


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def system_bootstrap() -> tuple[Optional[Staff], Optional[Menu], Optional[DailyLedger], Optional[FloorMap]]:
    configure_logging()
    try_configure_utf8_stdout()
    clear_screen()
    print("[*] Hospitality OS v4.0 Loading...")

    if not check_database_integrity():
        print("[X] HALT: System files missing. Run setup_os.py first.")
        return None, None, None, None

    menu, ledger, staff_list = load_system_state()
    floor = FloorMap()
    floor.restore_floor_state({})

    atexit.register(lambda: save_system_state(menu, ledger))

    for attempt in range(1, 6):
        print(f"\n[ LOGIN REQUIRED - ATTEMPT {attempt}/5 ]")
        login_id = get_staff_id("Enter Staff ID: ")
        active_staff = validate_staff_login(login_id, staff_list)
        if active_staff:
            active_staff.clock_in()
            print(f"[OK] Welcome, {active_staff.full_name} ({active_staff.role})")
            return active_staff, menu, ledger, floor

    print("[X] ACCESS DENIED: Max attempts reached.")
    return None, None, None, None


def main_loop(user: Staff, menu: Menu, ledger: DailyLedger, floor: FloorMap) -> None:
    waitlist = WaitlistManager()

    while True:
        clear_screen()
        print(
            f"USER: {user.full_name} | SALES: {format_currency(ledger.total_revenue)} "
            f"| TIPS: {format_currency(ledger.total_tips)}"
        )
        print("=" * 45)
        print(" [1] FRONT DESK (Seating & Reservations)")
        print(" [2] SERVICE FLOOR (Table / POS — same engine as host handoff)")
        print(" [3] WAITLIST MANAGEMENT")
        print(" [4] MANAGER OFFICE (Labor & Audit)")
        print(" [5] END SHIFT / LOGOUT")
        print("=" * 45)

        choice = input("Select Action > ").strip()

        if choice == "1":
            digitalfrontdesk.main_front_desk(floor, waitlist, user, menu, ledger)
        elif choice == "2":
            table_id = get_int("Table # (1-20): ", 1, 20)
            party = get_int("Party size: ", 1, 20)
            guest = walk_in_guest_for_table(table_id, party_size=party)
            table_obj = floor.tables[table_id - 1]
            if table_obj.status != "Available":
                print("[!] Table not available. Clear or choose another table.")
                input("Press Enter...")
                continue
            if not table_obj.seat_guest(guest):
                print("[!] Could not seat party (capacity or table state).")
                input("Press Enter...")
                continue
            if digitalpos.run_pos(table_id, guest, menu, ledger, user):
                table_obj.clear_table()
            else:
                print("[*] Session suspended; table left occupied.")
        elif choice == "3":
            print(f"\n--- ACTIVE WAITLIST ({len(waitlist.queue)} parties) ---")
            for i, entry in enumerate(waitlist.queue, 1):
                print(f"{i}. {entry.guest.full_name} (Party: {entry.party_size})")
            input("\nPress Enter to return...")
        elif choice == "4":
            if user.role.upper() == "MANAGER":
                laborcostauditor.main()
            else:
                print("[X] ACCESS DENIED: Manager credentials required.")
                time.sleep(2)
        elif choice == "5":
            if finalize_session(user, menu, ledger):
                break


def finalize_session(user: Staff, menu: Menu, ledger: DailyLedger) -> bool:
    if not get_yes_no(f"Clock out {user.full_name}? (y/n): "):
        return False
    user.had_break = get_yes_no("Did you take your required 30-min meal break? (y/n): ")
    user.clock_out()
    pay = user.calculate_shift_pay()
    print(f"Shift complete. Est. earnings: {format_currency(pay)}")
    save_system_state(menu, ledger, staff_id=user.staff_id)
    return True


if __name__ == "__main__":
    active_user, live_menu, live_ledger, live_floor = system_bootstrap()
    if active_user:
        try:
            main_loop(active_user, live_menu, live_ledger, live_floor)
        except KeyboardInterrupt:
            print("\n[!] Emergency interruption. Saving state...")
            save_system_state(live_menu, live_ledger, staff_id=active_user.staff_id)
            sys.exit(0)
