"""
Project: The "Smart" Labor Cost Auditor
Description: A specialized tool for California restaurant managers to audit labor 
             costs, sync sales data, and ensure meal-break compliance.
Features: 
  - Dynamic Staff loading from CSV via RegEx name formatting.
  - Automated/Manual Sales Syncing via inventorymanager.
  - California Meal Break & Overtime (8hr+) logic.
  - Shift logging to CSV for payroll records.
  - Initialization logic (New Service Day vs. Current Shift)
  - Shared Brain (restaurant_state.json) for Inventory & Sales
"""

import sys  # Handles system exits and error management
from datetime import datetime, date, timedelta
import csv  # For reading staff rosters and writing shift logs
import re   # For parsing 'Last, First' name formats
import os   # For handling file paths and directory debugging
import json # Added: To read from the Shared Brain

# Custom Packages & Modules
from validator import get_int, get_float, get_time, get_yes_no  # Centralized input logic
# Removed: import inventorymanager as inv_mgr (Now syncing via JSON)
from settings.restaurant_defaults import * # Debugging: Helpful for identifying pathing issues when running in different environments
print(f"DEBUG: Python is currently looking in: {os.getcwd()}")

# ==============================================================================
# HELPER FUNCTIONS (DATA PARSING & MATH)
# ==============================================================================

def calculate_shift_hours(clock_in, clock_out):
    """
    Calculates the decimal duration between two time objects.
    Logic: Handles graveyard shifts by checking if clock_out is before clock_in.
    Returns: Float (e.g., 8.5)
    """
    today = date.today()
    # Datetime objects are required to perform subtraction (timedeltas)
    start_dt = datetime.combine(today, clock_in)
    end_dt = datetime.combine(today, clock_out)

    # If the end time is numerically lower (e.g., 10pm to 2am), it's the next day
    if end_dt < start_dt:
        end_dt += timedelta(days=1)

    duration = end_dt - start_dt
    # total_seconds / 3600 converts the raw duration into decimal hours
    return duration.total_seconds() / 3600


def log_shift(person, in_time, out_time):
    """
    Appends a finalized shift record to shift_log.csv.
    Logic: Creates the file and header if they do not already exist.
    """
    filename = "shift_log.csv"
    file_exists = os.path.isfile(filename)
    today_date = date.today().strftime("%Y-%m-%d")

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        # Write header only once per file lifecycle
        if not file_exists:
            writer.writerow(["Date", "Name", "Clock_In", "Clock_Out", "Hours", "Pay"])
        
        # Log the critical payroll data
        writer.writerow([
            today_date, 
            person['name'], 
            in_time.strftime("%I:%M %p"), 
            out_time.strftime("%I:%M %p"), 
            f"{person['hours_worked']:.2f}", 
            f"{person['total_pay']:.2f}"
        ])


def format_employee_name(raw_name):
    """
    Standardizes employee names using RegEx.
    Input: "Doe, Jane" -> Output: "Jane Doe"
    """
    # Pattern: Capitalized Word, Comma, Space, Capitalized Word
    pattern = r"^([A-Z][a-z]+),\s+([A-Z][a-z]+)$"
    match = re.search(pattern, raw_name.strip())
    
    if match:
        # Group 2 is First Name, Group 1 is Last Name
        return f"{match.group(2)} {match.group(1)}"
    return raw_name


def load_staff(filename):
    """
    Locates and reads the staff CSV file.
    Logic: Uses absolute pathing to prevent 'File Not Found' errors in sub-directories.
    Returns: List of dictionaries containing staff data.
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, filename)

    staff_list = []
    try:
        with open(full_path, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Process name and convert numerical strings to actual floats
                row['name'] = format_employee_name(row['name'])
                row['hourly_rate'] = float(row['hourly_rate'])
                staff_list.append(row)
        return staff_list
    except FileNotFoundError:
        print(f"❌ Error: Could not find {filename}. Ensure it is in the script folder.")
        sys.exit()

# ==============================================================================
# AUDIT PHASES (LOGIC CONTROLLERS)
# ==============================================================================

def initialize_audit():
    """
    Phase 1: Environment Setup.
    Attempts to pull sales from the Shared Brain (restaurant_state.json). 
    If it fails, prompts for manual entry.
    """
    print("🚀 Initializing Shift Audit: Syncing with Shared Brain...")
    json_file = "restaurant_state.json"
    net_sales = 0.0

    try:
        # UPDATED: Pulling directly from the JSON State created by the POS
        if os.path.exists(json_file):
            with open(json_file, "r") as f:
                state = json.load(f)
                net_sales = state.get("net_sales", 0.0)
        else:
            print(f"⚠️  Notice: {json_file} not found. POS has not run yet.")
    except Exception as e:
        print(f"⚠️  Sync Warning: Could not automate sales data via JSON. {e}")

    # Fallback logic if the data bridge is empty or broken
    if net_sales is None or net_sales <= 0:
        print("\n⚠️  NOTICE: No automated sales data found.")
        if get_yes_no("Would you like to enter sales manually? (y/n): "):
            net_sales = get_float("  Enter total net sales for the shift: $", min_val=0.01)
        else:
            print("❌ Audit aborted: Cannot calculate labor without sales revenue.")
            sys.exit()

    print(f"\n✅ SALES SYNC COMPLETE: ${net_sales:,.2f} loaded.")
    staff = load_staff("staff.csv")
    return staff, net_sales


def process_staff_member(person):
    """
    Phase 2: Individual Data Entry & Compliance Check.
    Handles the 'Fat-Finger' guardrails for hours and break violations.
    """
    print(f"\nProcessing: {person['name']} ({person['dept']})")

    # 1. HOURS COLLECTION (LOOPED FOR CONFIRMATION)
    while True:
        in_time = get_time(f"  Enter Clock-In (e.g., 9am): ")
        out_time = get_time(f"  Enter Clock-Out (e.g., 5:30pm): ")
        raw_hours = calculate_shift_hours(in_time, out_time)

        # Soft validation: Warns but does not block high hour entries
        warning = " 🚩 (CAUTION: HIGH HOURS)" if raw_hours > 14.00 else ""
        print(f"  > Total Shift Duration: {raw_hours:.2f} hours{warning}")
        
        if get_yes_no(f"  Confirm these times for {person['name']}? (y/n): "):
            break

    # 2. CALIFORNIA BREAK COMPLIANCE
    break_time = 0.0
    is_violation = False
    
    # Check if a break occurred
    if get_yes_no(f"  Did they take a meal break? (y/n): "):
        while True:
            break_time = get_float(f"  How long was the break? (e.g., 0.50): ", min_val=0)
            if break_time >= raw_hours or break_time > 1.30:
                print(f"    ❌ Error: Invalid break duration.")
            else:
                break
        
        # CA Rule: Shifts > 6 hours require AT LEAST 30 mins (0.50)
        if raw_hours > 6.00 and break_time < 0.50:
            is_violation = True
    else:
        # CA Rule: Shifts > 6 hours MUST take a break
        if raw_hours > 6.00:
            is_violation = True 

    # 3. PAYROLL CALCULATIONS
    pay_hours = raw_hours - break_time  # Deduct unpaid meal break
    over_time = max(0, pay_hours - OVERTIME_LIMIT)  # Calculate OT hours (usually > 8)
    reg_hours = min(pay_hours, OVERTIME_LIMIT)      # Regular hours capped at OT limit
    
    # California Penalty: 1 hour of base pay for meal period violations
    penalty_pay = person['hourly_rate'] if is_violation else 0.0
    
    # Calculate Total Payroll Impact
    total_pay = (reg_hours * person['hourly_rate']) + \
                (over_time * person['hourly_rate'] * 1.5) + penalty_pay

    # Inject results into the person dictionary for reporting
    person.update({
        "hours_worked": pay_hours,
        "over_time": over_time,
        "is_violation": is_violation,
        "total_pay": total_pay,
        "penalty_pay": penalty_pay
    })
    
    # Commit the individual record to the log
    log_shift(person, in_time, out_time)
    return person


def generate_full_reports(staff, net_sales, formatted_date):
    """
    Phase 3: Aggregation & Final Dashboard.
    Calculates department totals and evaluates performance against targets.
    """
    total_foh_wages = 0.0
    total_boh_wages = 0.0
    total_hours = 0.0
    total_ot_costs = 0.0
    total_penalty_costs = 0.0

    print(f"\n{'='*65}\n{'OFFICIAL LABOR AUDIT':^65}\n{'='*65}")

    # Process by Department for organized viewing
    for dept in ["BOH", "FOH"]:
        print(f"\n--- {dept} STAFF LIST ---")
        print(f"{'Name':<18} | {'Wage':<6} | {'Hours':<6} | {'Total Pay':>10}")
        print("-" * 55)
        
        for p in staff:
            if p['dept'] == dept:
                # Minimum Wage Check (California Compliance)
                if p['hourly_rate'] < MIN_WAGE:
                    print(f"🚩 UNDERPAID ALERT: {p['name']} is below {MIN_WAGE}!")
                
                # Print row
                print(f"{p['name']:<18} | ${p['hourly_rate']:<5.2f} | {p['hours_worked']:<6.2f} | ${p['total_pay']:>9.2f}")
                
                # Update global metrics
                total_hours += p['hours_worked']
                total_penalty_costs += p['penalty_pay']
                total_ot_costs += (p['over_time'] * p['hourly_rate'] * 0.5) # The extra 0.5 premium
                
                if dept == "BOH": total_boh_wages += p['total_pay']
                else: total_foh_wages += p['total_pay']
        
        # Dept-specific Labor % Metrics
        dept_total = total_boh_wages if dept == "BOH" else total_foh_wages
        pct = (dept_total / net_sales) * 100 if net_sales > 0 else 0
        target = BOH_TARGET if dept == "BOH" else FOH_TARGET
        status = "✅ OK" if pct <= target else "⚠️  OVER BUDGET"

        print(f"Total {dept} Cost: ${dept_total:,.2f} ({pct:.2f}% of Sales) | {status}")

    # --- EXECUTIVE MANAGER DASHBOARD ---
    total_wages = total_foh_wages + total_boh_wages
    labor_percentage = (total_wages / net_sales) * 100 if net_sales > 0 else 0
    splh = net_sales / total_hours if total_hours > 0 else 0  # Sales Per Labor Hour
        
    print(f"\n{'='*65}\n{'EXECUTIVE MANAGER DASHBOARD':^65}\n{'='*65}")
    total_target = BOH_TARGET + FOH_TARGET
    l_status = '✅ OK' if labor_percentage <= total_target else '❌ OVER'
    
    print(f"{'Overall Labor %':<25} | {labor_percentage:>11.2f}% | {l_status}")
    print(f"{'Productivity (SPLH)':<25} | ${splh:>10.2f} | {'📢 Alert' if splh < 65 else '✅ OK'}")
    print(f"{'Overtime Premium Cost':<25} | ${total_ot_costs:>10.2f} | 🕒")
    print(f"{'Compliance Penalty Cost':<25} | ${total_penalty_costs:>10.2f} | ⚖️")

    # Final Action Items (Guidance for the Manager)
    print("-" * 65 + "\nACTION ITEMS:")
    if labor_percentage > 20:
        goal_gap = (total_wages / 0.20) - net_sales
        print(f"  👉 Labor high. Increase sales by ${goal_gap:,.2f} to hit 20% goal.")
    
    violators = [p['name'] for p in staff if p['is_violation']]
    if violators: 
        print(f"  👉 Compliance: Review breaks with {', '.join(violators)}.")


def main():
    """
    Primary Controller. 
    Coordinates the initialization, processing loop, and final reporting.
    """
    # Generate Date Header
    now = datetime.now()
    day = now.day
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    formatted_date = now.strftime(f"%A, %B {day}{suffix}, at %I:%M %p")
    
    # Phase 1: Initialize
    staff_roster, net_sales = initialize_audit()

    # Phase 2: Processing Loop
    updated_staff = []
    for person in staff_roster:
        # Process individual data entry and store result
        updated_person = process_staff_member(person)
        updated_staff.append(updated_person)

    # Phase 3: Final Analysis
    generate_full_reports(updated_staff, net_sales, formatted_date)


if __name__ == "__main__":
    main()