"""
HospitalityOS v4.0 - Labor Cost & Compliance Auditor
----------------------------------------------------
Interactive payroll scratchpad: pulls net sales from restaurant_state.json,
walks each staff row for clock times, estimates pay + CA meal-break flags,
then prints labor %, optional COGS from audit_history.log, and prime cost.
"""

import csv  # Append shift rows and read the roster export
import json  # Load shared-brain JSON for sales + last clerk id
import os  # File existence checks
import re  # Tidy "Last, First" strings for display
import sys  # Hard-stop when sales are unknown and user declines manual entry
from datetime import date, datetime, timedelta  # Combine dates with clock times
from decimal import Decimal  # Keep wage totals out of float error bands

from models import DailyLedger
from settings.restaurant_defaults import OVERTIME_LIMIT
from utils import PathManager, RESTAURANT_STATE_NAME, configure_logging, print_divider, try_configure_utf8_stdout
from validator import get_float, get_int, get_time, get_yes_no  # Numeric/time prompts


class ComplianceError(Exception):
    """Reserved hook if you later want to abort audits on illegal data."""

    pass


class Shift:
    """Wrap clock-in/out datetimes plus unpaid break minutes."""

    def __init__(self, clock_in: datetime, clock_out: datetime, break_minutes: int = 0) -> None:
        self.clock_in = clock_in
        self.clock_out = clock_out
        self.break_minutes = Decimal(str(break_minutes))

    @property
    def raw_hours(self) -> Decimal:
        """Elapsed hours, adding a day if graveyard shift wraps midnight."""
        delta = self.clock_out - self.clock_in
        if self.clock_out < self.clock_in:
            delta += timedelta(days=1)
        return Decimal(str(delta.total_seconds() / 3600))

    @property
    def net_hours(self) -> Decimal:
        """Paid-time approximation = on-clock minus unpaid meal."""
        return self.raw_hours - (self.break_minutes / Decimal("60"))

    @property
    def is_ca_violation(self) -> bool:
        """Demo rule: >6h on clock needs >=30 minutes recorded break."""
        six = Decimal("6")
        thirty = Decimal("30")
        return bool(self.raw_hours > six and self.break_minutes < thirty)


def format_employee_name(raw_name: str) -> str:
    """Swap 'Last, First' pattern to 'First Last' when the regex matches."""
    pattern = r"^([A-Z][a-z]+),\s+([A-Z][a-z]+)$"
    match = re.search(pattern, raw_name.strip())
    if match:
        return f"{match.group(2)} {match.group(1)}"
    return raw_name


def load_staff_roster() -> list:
    """Read staff.csv into dict rows with float hourly_rate for quick math."""
    full_path = PathManager.get_path("staff.csv")
    staff_list: list = []
    try:
        with open(full_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                row = {k.strip(): v.strip() for k, v in row.items()}
                row["name"] = format_employee_name(row["name"])
                row["hourly_rate"] = float(row["hourly_rate"])
                staff_list.append(row)
        return staff_list
    except FileNotFoundError:
        print(f"[X] CRITICAL: staff.csv missing at {full_path}")
        sys.exit(1)


def initialize_audit():
    """Hydrate ledger from JSON (if present) then optionally filter roster by staff_id."""
    print_divider("=")
    print(f"{'AUDITOR: SALES & STAFF SYNCHRONIZATION':^45}")
    print_divider("=")

    ledger = DailyLedger()
    state_path = PathManager.get_path(RESTAURANT_STATE_NAME)
    active_id = None
    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
            ledger.total_revenue = Decimal(str(state.get("total_revenue", "0")))
            ledger.total_tips = Decimal(str(state.get("total_tips", "0")))
            ledger.transaction_count = int(state.get("transaction_count", 0))
            active_id = state.get("staff_id")

    net_sales: Decimal = ledger.total_revenue
    if net_sales <= 0:
        print("⚠️  No automated revenue data found in Ledger.")
        if get_yes_no("Enter sales manually? (y/n): "):
            net_sales = Decimal(str(get_float("  Net Sales: $", min_val=0.01)))
        else:
            print("❌ Audit Aborted: Sales data required for KPI calculation.")
            sys.exit(1)

    staff_roster = load_staff_roster()
    if active_id:
        filtered = [s for s in staff_roster if s["staff_id"] == active_id]
        if filtered:
            print(f"🎯 Target Sync: Active ID [{active_id}] - {filtered[0]['name']}")
            return filtered, net_sales

    return staff_roster, net_sales


def process_staff_member(person: dict, net_sales: Decimal) -> dict:
    """Prompt for one roster row's clocks; mutate dict with hours/pay/violation."""
    print(f"\n--- AUDITING: {person['name']} (ID: {person['staff_id']}) ---")

    in_t = get_time("  Clock-In: ")
    out_t = get_time("  Clock-Out: ")
    has_break = get_yes_no("  Did they take a meal break? (y/n): ")
    break_m = get_int("  Break Minutes (e.g. 30): ", min_val=0) if has_break else 0

    today = date.today()
    in_dt = datetime.combine(today, in_t)
    out_dt = datetime.combine(today, out_t)
    shift_obj = Shift(in_dt, out_dt, break_m)

    pay_hours = shift_obj.net_hours
    ot_cap = Decimal(str(OVERTIME_LIMIT))
    reg_hours = min(pay_hours, ot_cap)
    ot_hours = max(Decimal("0"), pay_hours - ot_cap)

    rate = Decimal(str(person["hourly_rate"]))
    penalty_pay = rate if shift_obj.is_ca_violation else Decimal("0.0")
    total_pay = (reg_hours * rate) + (ot_hours * rate * Decimal("1.5")) + penalty_pay
    productivity = net_sales / pay_hours if pay_hours > 0 else Decimal("0")

    person.update(
        {
            "hours": pay_hours,
            "pay": total_pay,
            "violation": shift_obj.is_ca_violation,
            "splh": productivity,
            "penalty": penalty_pay,
        }
    )
    log_shift_to_csv(person, in_t, out_t)
    return person


def log_shift_to_csv(person: dict, in_t, out_t) -> None:
    """Append a summarized shift line under data/logs/shift_log.csv."""
    path = PathManager.get_path("shift_log.csv")
    exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Date", "Name", "In", "Out", "Hours", "Pay", "Violation"])
        writer.writerow(
            [
                date.today(),
                person["name"],
                in_t.strftime("%H:%M"),
                out_t.strftime("%H:%M"),
                f"{person['hours']:.2f}",
                f"{person['pay']:.2f}",
                person["violation"],
            ]
        )


def get_cogs_from_inventory() -> Decimal:
    """Best-effort parse of the last NET line written by inventorymanager."""
    path = PathManager.get_path("audit_history.log")
    if not os.path.exists(path):
        return Decimal("0.00")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return Decimal("0.00")
    last_audit = lines[-1]
    try:
        val = last_audit.split("NET: $")[1].split(" |")[0]
        return Decimal(val)
    except (IndexError, ValueError):
        return Decimal("0.00")


def generate_dashboard(staff: list, net_sales: Decimal) -> None:
    """
    Single consolidated GM view: labor lines plus COGS + prime cost (no duplicate defs).
    """
    print_divider("=")
    print(f"{'HOSPITALITY OS: GM EXECUTIVE DASHBOARD':^45}")
    print_divider("=")

    total_wages = sum(p["pay"] for p in staff)
    total_hours = sum(p["hours"] for p in staff)
    total_penalties = sum(p["penalty"] for p in staff)
    cogs = get_cogs_from_inventory()

    labor_pct = (total_wages / net_sales) * 100 if net_sales > 0 else Decimal("0")
    cogs_pct = (cogs / net_sales) * 100 if net_sales > 0 else Decimal("0")
    prime_cost_pct = labor_pct + cogs_pct

    print(f" 💰 NET SALES:           ${net_sales:>10.2f}")
    print(f" 🥩 COGS (Inventory):    ${cogs:>10.2f} ({cogs_pct:.1f}%)")
    print(f" 👥 LABOR COST:          ${total_wages:>10.2f} ({labor_pct:.1f}%)")
    print(f" ⏱️  TOTAL HOURS:         {total_hours:>10.2f} hrs")
    print(f" ⚖️  COMPLIANCE PEN.:    ${total_penalties:>10.2f}")
    print_divider("-")
    print(f" 🚀 PRIME COST TOTAL:    {prime_cost_pct:>10.2f}%")
    print_divider("-")

    if labor_pct > 30:
        print(f"🚩 ALERT: Labor is high! ({labor_pct:.1f}%) Target is < 30%.")
    if prime_cost_pct > 65:
        print("🚩 PROFIT ALERT: Prime cost exceeds 65%. Reduce waste or labor.")
    elif prime_cost_pct < 55 and prime_cost_pct > 0:
        print("✨ EXCELLENT: Prime cost looks strong today.")
    if any(p["violation"] for p in staff):
        print("🚩 LEGAL: CA meal-break penalties were applied in this run.")

    print("\n✅ Audit Complete. Shift logs archived under data/logs/.")


def main() -> None:
    configure_logging()
    try_configure_utf8_stdout()
    print(
        "\n*** LABOR AUDITOR — TRAINING / DEMO ONLY ***\n"
        "Not legal payroll, tax, or labor law advice. Verify with a qualified professional.\n"
    )
    roster, sales = initialize_audit()
    audited = [process_staff_member(p, sales) for p in roster]
    generate_dashboard(audited, sales)


if __name__ == "__main__":
    main()
