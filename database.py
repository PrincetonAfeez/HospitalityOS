"""
HospitalityOS v4.0 - Database & Persistence Layer
Loads menu.csv and staff.csv into Pydantic objects, and reads/writes
restaurant_state.json so totals and inventory survive restarts.
"""

import csv
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from models import DailyLedger, Menu, MenuItem, Staff
from storage import atomic_write_json
from utils import PathManager, configure_logging, RESTAURANT_STATE_NAME

LOG = logging.getLogger(__name__)
configure_logging()


def check_database_integrity() -> bool:
    """Require menu.csv and staff.csv under PathManager data dir."""
    required_files = ["menu.csv", "staff.csv"]
    for filename in required_files:
        path = PathManager.get_path(filename)
        if not os.path.exists(path):
            LOG.warning("Missing required file %s at %s", filename, path)
            print(f"[X] CRITICAL ERROR: Missing {filename} at {path}")
            return False
    return True


def validate_staff_login(login_id: str, staff_list: List[Staff]) -> Optional[Staff]:
    """Return Staff row for EMP-xx ID or None."""
    normalized = login_id.strip().upper()
    for member in staff_list:
        if member.staff_id.upper() == normalized:
            return member
    return None


def load_system_state() -> tuple[Menu, DailyLedger, List[Staff]]:
    """Hydrate Menu, DailyLedger (revenue + tips + txns), and Staff list."""
    menu = Menu()
    staff_list: List[Staff] = []

    menu_path = PathManager.get_path("menu.csv")
    staff_path = PathManager.get_path("staff.csv")
    state_path = PathManager.get_path(RESTAURANT_STATE_NAME)

    try:
        with open(menu_path, mode="r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                item = MenuItem(
                    name=row["name"],
                    price=Decimal(str(row["unit_price"])),
                    category=row["category"],
                    walk_in_inv=int(row["walk_in_inv"]),
                    freezer_inv=int(row["freezer_inv"]),
                    par_level=int(row["par_level"]),
                    line_inv=int(row["line_inv"]),
                )
                if item.name in menu.items:
                    LOG.warning("Duplicate menu name %r — last row wins", item.name)
                menu.add_item(item)
    except (OSError, KeyError, ValueError) as exc:
        LOG.exception("Menu load failed")
        print(f"[!] Menu Load Error: {exc}")

    if not menu.items:
        LOG.warning("Menu catalog is empty after load — check menu.csv")

    try:
        with open(staff_path, mode="r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row_num, row in enumerate(reader, start=2):
                try:
                    last_name, first_name = row["name"].split(", ", 1)
                    dept_label = row["dept"].strip()
                    member = Staff(
                        staff_id=row["staff_id"].strip(),
                        first_name=first_name.strip(),
                        last_name=last_name.strip(),
                        dept=dept_label,
                        role=dept_label,
                        hourly_rate=row["hourly_rate"],
                    )
                    staff_list.append(member)
                except (KeyError, ValueError) as exc:
                    LOG.warning("Skipping staff row %s: %s", row_num, exc)
                    continue
    except (OSError, KeyError, ValueError) as exc:
        LOG.exception("Staff load failed")
        print(f"[!] Staff Load Error: {exc}")

    ledger = DailyLedger()
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as fh:
            state = json.load(fh)
            ledger.total_revenue = Decimal(str(state.get("total_revenue", "0.00")))
            ledger.total_tips = Decimal(str(state.get("total_tips", "0.00")))
            ledger.transaction_count = int(state.get("transaction_count", 0))
            for name, qty in state.get("inventory_snapshot", {}).items():
                found = menu.find_item(name, include_inactive=True)
                if found:
                    found.line_inv = int(qty)

    return menu, ledger, staff_list


def save_system_state(
    menu: Menu,
    ledger: DailyLedger,
    staff_id: Optional[str] = None,
) -> None:
    """Persist ledger (revenue, tips, txn count), inventory snapshot, metadata."""
    state_path = PathManager.get_path(RESTAURANT_STATE_NAME)
    inventory_snapshot = {item.name: item.line_inv for item in menu.items.values()}
    state_data = {
        "timestamp": str(os.path.getmtime(PathManager.get_path("menu.csv"))),
        "last_updated": datetime.now().isoformat(),
        "total_revenue": str(ledger.total_revenue),
        "total_tips": str(ledger.total_tips),
        "transaction_count": ledger.transaction_count,
        "inventory_snapshot": inventory_snapshot,
    }
    if staff_id:
        state_data["staff_id"] = staff_id

    if atomic_write_json(state_path, state_data):
        LOG.info("Saved system state to %s", state_path)
        print(f"[*] System state synced to: {state_path}")
    else:
        LOG.error("Failed to save system state to %s", state_path)
        print(f"[X] Failed to save system state")
