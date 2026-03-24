"""
HospitalityOS v4.0 - Labor Cost & Compliance Auditor
Architect: Princeton Afeez
Description: A specialized California-compliant labor tool. Automates 
             overtime math, meal-break penalties, and productivity KPIs (SPLH).
"""

import sys     # Used for clean exits during critical path errors
import csv     # Essential for reading staff records and exporting payroll
import re      # Powers the 'RegEx Name Shield' for standardizing employee strings
import os      # Handles low-level file path existence checks
import json    # Parses the POS 'Shared Brain' for sales synchronization
from datetime import datetime, date, timedelta # Core logic for time-clock math
from decimal import Decimal # Ensuring financial precision for wages and tax

# --- INTERNAL MODULE IMPORTS ---
from utils import PathManager, print_divider # v4.0 Centralized Path/UI Logic
from models import Staff, DailyLedger        # Data structures for Employees and Revenue
from validator import get_int, get_float, get_time, get_yes_no # Input shielding
from settings.restaurant_defaults import OVERTIME_LIMIT, MIN_WAGE # Global constants

# ==============================================================================
# HELPER CLASSES: COMPLIANCE & TIME MATH
# ==============================================================================

class ComplianceError(Exception):
    """Custom exception raised for severe CA labor law violations or data errors."""
    pass

class Shift:
    """Requirement 6: Encapsulates complex time math and CA break logic."""
    def __init__(self, clock_in: datetime, clock_out: datetime, break_minutes: int = 0):
        # Store the raw datetime objects for the start and end of work
        self.clock_in = clock_in
        self.clock_out = clock_out
        # Convert break minutes to Decimal to prevent float drift in payroll
        self.break_minutes = Decimal(str(break_minutes))
        
    @property
    def raw_hours(self) -> Decimal:
        """Calculates total duration, handling midnight crossovers (Graveyard)."""
        delta = self.clock_out - self.clock_in
        # If clock_out is 2 AM and clock_in was 10 PM, the delta is negative; add a day.
        if self.clock_out < self.clock_in: 
            delta += timedelta(days=1)
        # Convert total seconds into a Decimal hour representation
        return Decimal(str(delta.total_seconds() / 3600))

    @property
    def net_hours(self) -> Decimal:
        """Subtracts unpaid break time from the total shift duration."""
        return self.raw_hours - (self.break_minutes / 60)
    
    @property
    def is_ca_violation(self) -> bool:
        """CA LAW: Any shift over 6.0 hours MUST have a 30-minute unpaid break."""
        if self.raw_hours > 6.0 and self.break_minutes < 30:
            return True # Flag for the $1.00 hour penalty
        return False

# ==============================================================================
# DATA PARSING & REGEX UTILITIES
# ==============================================================================

def format_employee_name(raw_name):
    """
    Standardizes names using RegEx. 
    Pattern: 'Last, First' -> 'First Last'
    """
    # Look for: Start of string, Word, Comma, Space, Word, End of string
    pattern = r"^([A-Z][a-z]+),\s+([A-Z][a-z]+)$"
    match = re.search(pattern, raw_name.strip())
    
    if match:
        # Swap Group 2 (First) and Group 1 (Last) for the display name
        return f"{match.group(2)} {match.group(1)}"
    return raw_name # Return original if pattern doesn't match

def load_staff_roster():
    """Reads the staff.csv using v4.0 PathManager and applies RegEx formatting."""
    # Resolve the absolute path to the staff database
    full_path = PathManager.get_path("staff.csv")
    staff_list = []
    
    try:
        with open(full_path, "r", encoding="utf-8") as file:
            # Use DictReader to treat the first row as keys (staff_id, name, etc.)
            reader = csv.DictReader(file)
            for row in reader:
                # Cleanup whitespace and format the name via RegEx
                row = {k.strip(): v.strip() for k, v in row.items()}
                row['name'] = format_employee_name(row['name'])
                # Convert rate to float for interim math (Decimal conversion happens in Shift)
                row['hourly_rate'] = float(row['hourly_rate'])
                staff_list.append(row)
        return staff_list
    except FileNotFoundError:
        print(f"❌ CRITICAL: staff.csv missing at {full_path}")
        sys.exit()

# ==============================================================================
# AUDIT PHASE 1: INITIALIZATION & POS SYNC
# ==============================================================================

def initialize_audit():
    """Bridges the gap between POS Sales (Shared Brain) and Labor Analysis."""
    print_divider("═")
    print(f"{'AUDITOR: SALES & STAFF SYNCHRONIZATION':^45}")
    print_divider("═")
    
    # 1. Sync with the DailyLedger Singleton (v4.0 Shared Brain)
    ledger = DailyLedger()
    net_sales = ledger.total_revenue
    
    # 2. Check for the Active POS Staff ID in the state file
    state_path = PathManager.get_path("restaurant_state.json")
    active_id = None
    if os.path.exists(state_path):
        with open(state_path, "r") as f:
            state = json.load(f)
            # Find which staff member was logged in when the shift ended
            active_id = state.get("staff_id", None)

    # 3. Manual Fallback if Ledger is empty
    if net_sales <= 0:
        print("⚠️  No automated revenue data found in Ledger.")
        if get_yes_no("Enter sales manually? (y/n): "):
            net_sales = Decimal(str(get_float("  Net Sales: $", min_val=0.01)))
        else:
            print("❌ Audit Aborted: Sales data required for KPI calculation.")
            sys.exit()

    # 4. Load and Filter Roster
    staff_roster = load_staff_roster()
    if active_id:
        # TASK 5: Targeted Audit - Prioritize the person logged into the POS
        filtered = [s for s in staff_roster if s['staff_id'] == active_id]
        if filtered:
            print(f"🎯 Target Sync: Active ID [{active_id}] - {filtered[0]['name']}")
            return filtered, net_sales

    return staff_roster, net_sales

# ==============================================================================
# AUDIT PHASE 2: COMPLIANCE PROCESSING
# ==============================================================================

def process_staff_member(person, net_sales):
    """Calculates pay, overtime, productivity (SPLH), and CA penalties."""
    print(f"\n--- AUDITING: {person['name']} (ID: {person['staff_id']}) ---")

    # 1. Collect Times (Validator ensures correct '11am' format)
    in_t = get_time(f"  Clock-In: ")
    out_t = get_time(f"  Clock-Out: ")
    
    # 2. Collect Break Info for CA Compliance
    has_break = get_yes_no("  Did they take a meal break? (y/n): ")
    break_m = get_int("  Break Minutes (e.g. 30): ", min_val=0) if has_break else 0

    # 3. Instantiate the Shift Logic Engine
    today = date.today()
    in_dt = datetime.combine(today, in_t)
    out_dt = datetime.combine(today, out_t)
    shift_obj = Shift(in_dt, out_dt, break_m)

    # 4. Pay Calculus (Reg vs OT)
    pay_hours = shift_obj.net_hours
    reg_hours = min(pay_hours, Decimal(str(OVERTIME_LIMIT)))
    ot_hours = max(0, pay_hours - Decimal(str(OVERTIME_LIMIT)))
    
    # 5. CA Penalty Logic ($1.00 hour base pay for violation)
    penalty_pay = Decimal(str(person['hourly_rate'])) if shift_obj.is_ca_violation else Decimal("0.0")
    
    # 6. Final Wage Math
    total_pay = (reg_hours * Decimal(str(person['hourly_rate']))) + \
                (ot_hours * Decimal(str(person['hourly_rate'])) * Decimal("1.5")) + \
                penalty_pay

    # 7. Productivity KPI: Sales Per Labor Hour (SPLH)
    productivity = net_sales / pay_hours if pay_hours > 0 else 0

    # Update the record dictionary
    person.update({
        "hours": pay_hours, "pay": total_pay, 
        "violation": shift_obj.is_ca_violation, "splh": productivity,
        "penalty": penalty_pay
    })
    
    # Trigger the log save via PathManager
    log_shift_to_csv(person, in_t, out_t)
    return person

def log_shift_to_csv(person, in_t, out_t):
    """Permanently archives the shift to data/logs/shift_log.csv."""
    path = PathManager.get_path("shift_log.csv")
    exists = os.path.isfile(path)
    
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["Date", "Name", "In", "Out", "Hours", "Pay", "Violation"])
        writer.writerow([
            date.today(), person['name'], in_t.strftime("%H:%M"), 
            out_t.strftime("%H:%M"), f"{person['hours']:.2f}", 
            f"{person['pay']:.2f}", person['violation']
        ])

# ==============================================================================
# AUDIT PHASE 3: MANAGER DASHBOARD
# ==============================================================================

def generate_dashboard(staff, net_sales):
    """Renders the Final KPI Report with actionable insights."""
    print_divider("═")
    print(f"{'EXECUTIVE LABOR DASHBOARD':^45}")
    print_divider("═")

    total_wages = sum(p['pay'] for p in staff)
    total_hours = sum(p['hours'] for p in staff)
    labor_pct = (total_wages / net_sales) * 100 if net_sales > 0 else 0
    total_penalties = sum(p['penalty'] for p in staff)

    print(f" Net Sales (Sync):       ${net_sales:>10.2f}")
    print(f" Total Labor Cost:       ${total_wages:>10.2f}")
    print(f" Labor Percentage:       {labor_pct:>10.2f}%")
    print(f" Total Shift Hours:      {total_hours:>10.2f} hrs")
    print(f" Compliance Penalties:   ${total_penalties:>10.2f}")
    print_divider("-")

    # Actionable Logic
    if labor_pct > 30:
        print(f"🚩 ALERT: Labor is high! ({labor_pct:.1f}%) Target is < 30%.")
    if total_penalties > 0:
        print(f"🚩 COMPLIANCE: Meal-break violations found. Check schedules.")
    
    print(f"\n✅ Audit Complete. Shift logs archived to /data/logs/")

def main():
    """Primary Controller for the Labor Auditor application."""
    # 1. Initialize and Sync
    roster, sales = initialize_audit()

    # 2. Process Staff
    audited_staff = []
    for p in roster:
        updated = process_staff_member(p, sales)
        audited_staff.append(updated)

    # 3. Final Report
    generate_dashboard(audited_staff, sales)

def get_cogs_from_inventory():
    """
    PHASE 4 (13): Bridges InventoryManager to LaborAuditor.
    Pulls the 'Total Sold Value' (Cost of Goods Sold) from the nightly audit.
    """
    path = PathManager.get_path("audit_history.log")
    if os.path.exists(path):
        with open(path, "r") as f:
            lines = f.readlines()
            if lines:
                # Logic: Pull the last line of the audit log and extract 'NET'
                # In a production environment, we'd use a structured JSON daily report
                last_audit = lines[-1]
                try:
                    # Simple parse: looking for the value after 'NET: $'
                    val = last_audit.split("NET: $")[1].split(" |")[0]
                    return Decimal(val)
                except (IndexError, ValueError):
                    return Decimal("0.00")
    return Decimal("0.00")

def generate_dashboard(staff, net_sales):
    """
    PHASE 4 (13): Renders the 'Executive View' - Sales vs. Labor vs. COGS.
    """
    print_divider("═")
    print(f"{'HOSPITALITY OS: GM EXECUTIVE DASHBOARD':^45}")
    print_divider("═")

    # 1. Financial Aggregation
    total_wages = sum(p['pay'] for p in staff)
    cogs = get_cogs_from_inventory()
    
    # 2. KPI Calculations
    labor_pct = (total_wages / net_sales) * 100 if net_sales > 0 else 0
    cogs_pct = (cogs / net_sales) * 100 if net_sales > 0 else 0
    prime_cost_pct = labor_pct + cogs_pct

    # 3. Visual Reporting
    print(f" 💰 NET SALES:           ${net_sales:>10.2f}")
    print(f" 🥩 COGS (Inventory):    ${cogs:>10.2f} ({cogs_pct:.1f}%)")
    print(f" 👥 LABOR COST:          ${total_wages:>10.2f} ({labor_pct:.1f}%)")
    print_divider("-")
    print(f" 🚀 PRIME COST TOTAL:    {prime_cost_pct:>10.2f}%")
    print_divider("-")

    # 4. Actionable Insights (Phase 4 Goal)
    if prime_cost_pct > 65:
        print("🚩 PROFIT ALERT: Prime cost exceeds 65%. Reduce waste or labor.")
    elif prime_cost_pct < 55:
        print("✨ EXCELLENT: Operation is highly profitable today.")
    
    if any(p['violation'] for p in staff):
        print("🚩 LEGAL: CA Meal-Break Penalties were applied to today's payroll.")

    print(f"\n✅ Monday Master To-Do List: ALL PHASES COMPLETE.")
    
if __name__ == "__main__":
    main()