"""
Project: The "Smart" Labor Cost Auditor (Day 6 Integrated Version)
Description: A specialized tool for California restaurant managers to audit labor 
             costs, sync sales data, and ensure meal-break compliance.
             
INTEGRATION FEATURES: 
  - Automated Sales Sync: Pulls real-time net sales from 'restaurant_state.json'.
  - Targeted Auditing: Identifies the active server from the POS login.
  - Productivity Tracking: Calculates individual Sales-Per-Labor-Hour (SPLH).
  - CA Compliance: Automates the $1.00 hour penalty for meal-break violations.
"""

import sys
import csv
import re
import os
import json
from datetime import datetime, date, timedelta
from decimal import Decimal

# Custom Packages & Modules
from HospitalityOS.models import Staff
from validator import get_int, get_float, get_time, get_yes_no
from settings.restaurant_defaults import OVERTIME_LIMIT, MIN_WAGE

# ==============================================================================
# HELPER FUNCTIONS: DATA PARSING & TIME MATH
# ==============================================================================

class ComplianceError(Exception):
    """Raised for impossible labor data or severe CA law violations."""
    pass

class Shift:
    """Requirement 6: Encapsulates time math and CA compliance logic."""
    def __init__(self, clock_in: datetime, clock_out: datetime, break_minutes: int = 0):
        self.clock_in = clock_in
        self.clock_out = clock_out
        self.break_minutes = Decimal(str(break_minutes))
        
    @property
    def raw_hours(self) -> Decimal:
        delta = self.clock_out - self.clock_in
        if self.clock_out < self.clock_in: # Handle graveyard
            delta += timedelta(days=1)
        return Decimal(str(delta.total_seconds() / 3600))

    @property
    def net_hours(self) -> Decimal:
        return self.raw_hours - (self.break_minutes / 60)
    
    @property
    def is_ca_violation(self) -> bool:
        """CA Law: Shift > 6hrs requires 30min break."""
        if self.raw_hours > 6.0 and self.break_minutes < 30:
            return True
        return False

class LaborAuditor:
    """Objective 3: Centralizes labor analysis and POS sync."""
    def __init__(self, target_sales: Decimal = Decimal("0.00")):
        self.net_sales = target_sales
        self.audited_shifts = []

    def sync_with_ledger(self):
        """
        Commit 15: Pulls real-time revenue from the DailyLedger Singleton.
        Eliminates the need for manual JSON file reading.
        """
        from models import DailyLedger
        
        ledger = DailyLedger()
        self.net_sales = ledger.total_revenue
        print(f"🔄 Sync Complete: Auditor is now using current revenue: ${self.net_sales:.2f}")
    
    def add_shift(self, staff: Staff, shift: Shift):
        self.audited_shifts.append({"staff": staff, "shift": shift})
    
    def calculate_ot(self, hours: Decimal) -> Decimal:
        return max(Decimal("0.00"), hours - Decimal(str(OVERTIME_LIMIT)))
            
    def validate_shift(self, shift: Shift):
        if shift.raw_hours > 16: # No legal double-shifts > 16hrs
            raise ComplianceError("Shift exceeds 16-hour safety limit.")
    
    def generate_summary(self):
        print(f"\n{'NAME':<20} | {'HOURS':<8} | {'PAY':<10}")
        for entry in self.audited_shifts:
            s, sh = entry['staff'], entry['shift']
            print(f"{s.full_name:<20} | {sh.net_hours:<8.2f} | ${s.hourly_rate * sh.net_hours:>9.2f}")

    
def calculate_shift_hours(clock_in, clock_out):
    """
    Calculates decimal hours between two time objects.
    Handles graveyard shifts (e.g., 10 PM to 2 AM) by checking if the end 
    time is numerically 'earlier' than the start time.
    """
    today = date.today()
    start_dt = datetime.combine(today, clock_in)
    end_dt = datetime.combine(today, clock_out)

    # If clock-out is before clock-in, assume it happened the next calendar day
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration = end_dt - start_dt
    return duration.total_seconds() / 3600

def format_employee_name(raw_name):
    """
    Standardizes employee names using RegEx.
    Expected Input: 'Doe, Jane' -> Output: 'Jane Doe'
    If the name does not match the pattern, it returns the string untouched.
    """
    pattern = r"^([A-Z][a-z]+),\s+([A-Z][a-z]+)$"
    match = re.search(pattern, raw_name.strip())
    
    if match:
        # Group 2 = First Name, Group 1 = Last Name
        return f"{match.group(2)} {match.group(1)}"
    return raw_name


def load_staff(filename):
    """
    Reads the staff roster and prepares data for the audit.
    Converts strings to floats and standardizes names via RegEx.
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, filename)

    staff_list = []
    try:
        with open(full_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Strip whitespace from keys/values to prevent DictReader errors
                row = {k.strip(): v.strip() for k, v in row.items()}
                row['name'] = format_employee_name(row['name'])
                row['hourly_rate'] = float(row['hourly_rate'])
                staff_list.append(row)
        return staff_list
    except FileNotFoundError:
        print(f"❌ Error: {filename} not found. Ensure it is in the project root.")
        sys.exit()


def log_shift(person, in_time, out_time):
    """
    Writes the finalized audit record to a CSV for payroll processing.
    Ensures a header is created if the file is new.
    """
    filename = "shift_log.csv"
    file_exists = os.path.isfile(filename)
    today_date = date.today().strftime("%Y-%m-%d")

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Name", "Clock_In", "Clock_Out", "Hours", "Pay"])
        
        writer.writerow([
            today_date, 
            person['name'], 
            in_time.strftime("%I:%M %p"), 
            out_time.strftime("%I:%M %p"), 
            f"{person['hours_worked']:.2f}", 
            f"{person['total_pay']:.2f}"
        ])

# ==============================================================================
# AUDIT PHASE 1: INITIALIZATION & SYNC
# ==============================================================================

def fetch_pos_sync_data(json_file):
    """
    Extracts sales and active staff data from the POS 'Shared Brain'.
    This is the core of the Day 6 automation logic.
    """
    if not os.path.exists(json_file):
        print(f"⚠️  Notice: {json_file} missing. POS data not synchronized.")
        return 0.0, None
    
    try:
        with open(json_file, "r") as f:
            state = json.load(f)
            sales = float(state.get("net_sales", 0.0))
            active_id = state.get("staff_id", None)
            print(f"✅ Sync Successful: Active ID [{active_id}] loaded.")
            return sales, active_id
    except Exception as e:
        print(f"⚠️  Sync Warning: Could not parse JSON. {e}")
        return 0.0, None


def initialize_audit():
    """
    Prepares the audit environment. 
    Handles the transition from POS data to the Labor Auditor roster.
    """
    print("\n" + "="*45)
    print(f"{'AUDITOR SALES SYNC':^45}")
    print("="*45)
    
    # 1. Automated Sync
    net_sales, active_id = fetch_pos_sync_data("restaurant_state.json")

    # 2. Manual Fallback (If POS hasn't run or sales are $0)
    if net_sales <= 0:
        print("⚠️  No automated sales data found.")
        if get_yes_no("Would you like to enter sales manually? (y/n): "):
            net_sales = get_float("  Enter total net sales for shift: $", min_val=0.01)
        else:
            print("❌ Audit aborted: Sales required for labor calculation.")
            sys.exit()

    # 3. Roster Loading & Targeted Filtering
    staff_roster = load_staff("staff.csv")
    if active_id:
        # Task 5: Only audit the person who was actually logged into the POS
        staff_roster = [s for s in staff_roster if s['staff_id'] == active_id]
        if staff_roster:
            print(f"🎯 Target Found: Auditing {staff_roster[0]['name']}...")
        else:
            print(f"🚩 Alert: POS ID {active_id} not found in staff roster.")

    return staff_roster, net_sales

# ==============================================================================
# AUDIT PHASE 2: INDIVIDUAL PROCESSING
# ==============================================================================

def collect_staff_times(name):
    """Handles the user-interface loop for time clock entry."""
    while True:
        in_t = get_time(f"  Enter Clock-In (e.g., 11am): ")
        out_t = get_time(f"  Enter Clock-Out (e.g., 5:30pm): ")
        hrs = calculate_shift_hours(in_t, out_t)
        
        print(f"  > Total Shift Duration: {hrs:.2f} hours")
        if get_yes_no(f"  Confirm these times for {name}? (y/n): "):
            return in_t, out_t, hrs


def check_ca_compliance(total_hours):
    """
    Applies California Meal-Break Law Logic.
    Shifts > 6 hours MUST have at least a 30-minute (0.50) unpaid break.
    """
    is_violation = False
    break_time = 0.0
    
    if get_yes_no(f"  Did they take a meal break? (y/n): "):
        while True:
            break_time = float(get_float(f"  How long was the break? (e.g., 0.50): ", min_val=0))
            if break_time < total_hours:
                break
            print(f"    ❌ Error: Break cannot be longer than the shift itself.")
        
        if total_hours > 6.00 and break_time < 0.50:
            is_violation = True
    elif total_hours > 6.00:
        is_violation = True 
        
    return break_time, is_violation


def process_staff_member(person):
    """
    Executes the full audit for a single employee.
    Calculates pay, overtime, and meal-period penalties.
    """
    print(f"\n--- AUDITING: {person['name']} ---")

    # 1. Time Collection
    in_time, out_time, raw_hours = collect_staff_times(person['name'])

    # 2. Compliance Verification
    break_time, is_violation = check_ca_compliance(raw_hours)

    # 3. Pay Calculus
    pay_hours = raw_hours - break_time 
    over_time = max(0, pay_hours - OVERTIME_LIMIT) # OVERTIME_LIMIT usually 8.0
    reg_hours = min(pay_hours, OVERTIME_LIMIT)      
    
    # Penalty Logic: 1 hour of base pay for non-compliance
    penalty_pay = person['hourly_rate'] if is_violation else 0.0
    
    total_pay = (reg_hours * person['hourly_rate']) + \
                (over_time * person['hourly_rate'] * 1.5) + penalty_pay

    # Update person record
    person.update({
        "hours_worked": pay_hours, 
        "over_time": over_time,
        "is_violation": is_violation, 
        "total_pay": total_pay, 
        "penalty_pay": penalty_pay
    })
    
    # Permanent logging
    log_shift(person, in_time, out_time)
    return person

# ==============================================================================
# AUDIT PHASE 3: REPORTING & KPIS
# ==============================================================================

def display_dept_report(dept_name, staff, net_sales):
    """
    Generates the department-specific view of the audit.
    Task 3: Displays individual Productivity based on sales sync.
    """
    print(f"\n--- {dept_name} STAFF LIST ---")
    print(f"{'Name':<18} | {'Pay':<8} | {'Hours':<6}")
    print("-" * 40)
    
    wages, hours, penalties, ot_prem = 0.0, 0.0, 0.0, 0.0
    
    for p in staff:
        if p['dept'] == dept_name:
            # Individual Productivity Metric
            productivity = net_sales / p['hours_worked'] if p['hours_worked'] > 0 else 0
            
            print(f"{p['name']:<18} | ${p['total_pay']:>7.2f} | {p['hours_worked']:>5.2f}")
            print(f"  📊 Productivity: ${productivity:.2f}/hr")
            
            if p['is_violation']:
                print(f"  🚩 CA PENALTY APPLIED: Meal-break violation.")

            # Aggregate department metrics
            wages += p['total_pay']
            hours += p['hours_worked']
            penalties += p['penalty_pay']
            ot_prem += (p['over_time'] * p['hourly_rate'] * 0.5)

    return wages, hours, penalties, ot_prem


def generate_full_reports(staff, net_sales, formatted_date):
    """
    Final Phase: Aggregates all data into the Manager Dashboard.
    Compares performance against restaurant targets.
    """
    print(f"\n{'='*65}\n{'OFFICIAL LABOR AUDIT: ' + formatted_date:^65}\n{'='*65}")

    # 1. Run Department Reports
    boh_w, boh_h, boh_p, boh_ot = display_dept_report("BOH", staff, net_sales)
    foh_w, foh_h, foh_p, foh_ot = display_dept_report("FOH", staff, net_sales)

    # 2. Executive Aggregates
    total_wages = boh_w + foh_w
    total_hours = boh_h + foh_h
    labor_pct = (total_wages / net_sales) * 100 if net_sales > 0 else 0
    splh = net_sales / total_hours if total_hours > 0 else 0 
        
    # 3. Manager Dashboard UX
    print(f"\n{'='*65}\n{'EXECUTIVE MANAGER DASHBOARD':^65}\n{'='*65}")
    print(f"{'Net Sales Sync':<25} | ${net_sales:>10.2f}")
    print(f"{'Overall Labor %':<25} | {labor_pct:>11.2f}%")
    print(f"{'Productivity (SPLH)':<25} | ${splh:>10.2f}")
    print(f"{'Overtime Premiums':<25} | ${ (boh_ot + foh_ot) :>10.2f}")
    print(f"{'Compliance Penalties':<25} | ${ (boh_p + foh_p) :>10.2f}")
    print("-" * 65)

    # 4. Actionable Insights
    if labor_pct > 20:
        print(f"👉 LABOR ALERT: System is {labor_pct - 20:.1f}% over the 20% target.")
    if (boh_p + foh_p) > 0:
        print(f"👉 COMPLIANCE ALERT: Break violations detected. Review schedules.")


def main():
    """Primary Controller for the Auditor application."""
    # Generate timestamped date header
    now = datetime.now()
    formatted_date = now.strftime("%B %d, %Y")
    
    # Phase 1: Initialize (JSON Sync & Roster Prep)
    staff_roster, net_sales = initialize_audit()

    # Phase 2: Processing Loop (Hours, Breaks, Pay)
    updated_staff = []
    for person in staff_roster:
        updated_person = process_staff_member(person)
        updated_staff.append(updated_person)

    # Phase 3: Final Reports (KPIs & Labor Analysis)
    generate_full_reports(updated_staff, net_sales, formatted_date)


if __name__ == "__main__":
    main()