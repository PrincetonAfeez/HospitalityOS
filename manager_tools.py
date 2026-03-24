"""
HospitalityOS v4.0 - Managerial Tools & Labor Auditor
Architect: Princeton Afeez
Description: Handles sensitive administrative tasks including Z-Reports, 
             labor-to-sales ratios, and master inventory adjustments.
"""

import os
import json
import csv
from datetime import datetime
from decimal import Decimal
from models import SecurityLog, DailyLedger, Staff, MenuItem

# ==========================================================================
# SECURITY DECORATOR (Task 8)
# ==========================================================================

def require_manager_auth(func):
    """
    Intercepts sensitive functions to verify Manager credentials.
    Ensures that high-risk actions (Z-Reports, Voids) are authorized.
    """
    @functools.wraps(func)
    def wrapper(self, manager_id, *args, **kwargs):
        # 1. Identify the staff member attempting the action
        # We look for the staff object in the tool's internal staff_list
        staff_member = next((s for s in self.staff_list if s.staff_id == manager_id), None)
        
        # 2. Check Role (Managers bypass the PIN prompt for their own tools)
        if staff_member and staff_member.role.upper() == "MANAGER":
            return func(self, manager_id, *args, **kwargs)
        
        # 3. Fallback: Request Manager PIN (Hardcoded 5555 for Phase 1)
        print("\n" + "🔒" * 20)
        print(f" SECURITY: AUTH REQUIRED FOR {func.__name__.upper()}")
        print("🔒" * 20)
        
        pin = input("Enter Manager PIN to authorize: ")
        if pin == "5555":
            SecurityLog.log_event(manager_id, "OVERRIDE_GRANTED", f"Action: {func.__name__}")
            return func(self, manager_id, *args, **kwargs)
        else:
            print("❌ ACCESS DENIED: Invalid Manager Credentials.")
            return False
            
    return wrapper

# ==========================================================================
# MAIN TOOLSET
# ==========================================================================

class ManagerTools:
    """Consolidates all administrative and financial auditing functions."""

    def __init__(self, ledger: DailyLedger, menu, staff_list: list[Staff]):
        self.ledger = ledger # Reference to the live daily sales data
        self.menu = menu # Reference to the master menu and inventory
        self.staff_list = staff_list # List of all employees for labor auditing

    # ==========================================================================
    # FINANCIAL AUDITING (Z-REPORTS)
    # ==========================================================================

    # --- PROTECTED ACTION ---
    @require_manager_auth
    def generate_z_report(self, manager_id: str):
        """
        Performs the 'End of Day' close. Archives sales and resets the ledger.
        This is a permanent action that creates a timestamped JSON audit file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M") 
        report_name = f"data/logs/Z_REPORT_{timestamp}.json" 
        
        report_data = {
            "business_date": datetime.now().strftime("%Y-%m-%d"),
            "closed_by": manager_id,
            "total_net_sales": str(self.ledger.total_revenue),
            "transaction_count": self.ledger.transaction_count,
            "average_check": str((self.ledger.total_revenue / self.ledger.transaction_count) 
                                if self.ledger.transaction_count > 0 else 0)
        }

        try:
            with open(report_name, "w") as f:
                json.dump(report_data, f, indent=4)
            
            SecurityLog.log_event(manager_id, "Z_REPORT_GENERATED", f"Report: {report_name}")
            
            self.ledger.total_revenue = Decimal("0.00")
            self.ledger.transaction_count = 0
            
            print(f"✅ Z-Report archived successfully to {report_name}")
            return True
        except Exception as e:
            print(f"❌ Critical Error during Z-Report: {e}")
            return False

    # ==========================================================================
    # LABOR COST ANALYSIS (CA COMPLIANCE)
    # ==========================================================================

    def run_labor_audit(self):
        """
        Calculates total labor expense vs total sales to determine the 'Labor %'.
        This is vital for staying profitable under California wage standards.
        """
        total_labor_cost = Decimal("0.00")
        
        print("\n--- LIVE LABOR AUDIT ---")
        for employee in self.staff_list:
            # Check if employee has clocked out; if not, use current time for estimate
            if employee.shift_start and not employee.shift_end:
                employee.shift_end = datetime.now() 
                
            shift_pay = employee.calculate_shift_pay()
            total_labor_cost += shift_pay
            print(f"👤 {employee.full_name:<18} | Est. Pay: ${shift_pay:>7.2f}")

        # Calculate the impact: (Labor / Sales) * 100
        sales = self.ledger.total_revenue
        labor_pct = (total_labor_cost / sales * 100) if sales > 0 else Decimal("0.00")
        
        print("-" * 40)
        print(f"💰 Total Sales: ${sales:>10.2f}")
        print(f"👷 Total Labor: ${total_labor_cost:>10.2f}")
        print(f"📊 Labor Impact: {labor_pct:>9.2f}%")
        
        # UX Alert: Most restaurants target under 30% labor
        if labor_pct > 30:
            print("⚠️ ALERT: Labor costs are exceeding the 30% profitability threshold!")
        print("-" * 40)

    # ==========================================================================
    # INVENTORY MANAGEMENT
    # ==========================================================================

    def generate_reorder_csv(self):
        """
        Scans 'Shared Brain' inventory levels and creates a CSV for the morning buyer.
        Includes only items that have fallen below their Par levels.
        """
        reorder_file = "data/logs/morning_order.csv"
        low_stock_items = []

        # Iterate through the dictionary-based menu
        for item in self.menu.items.values():
            if item.line_inv < item.par_level:
                qty_needed = item.par_level - item.line_inv
                low_stock_items.append([item.name, item.category, item.line_inv, item.par_level, qty_needed])

        if not low_stock_items:
            print("✅ All inventory levels are healthy. No order needed.")
            return

        # Write to a standard CSV format for Excel/Google Sheets compatibility
        with open(reorder_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Item Name", "Category", "Current Stock", "Par Level", "Order Qty"])
            writer.writerows(low_stock_items)

        print(f"📝 Reorder list generated: {len(low_stock_items)} items saved to {reorder_file}")

    # ==========================================================================
    # SECURITY LOG VIEWER
    # ==========================================================================

    def view_recent_security_logs(self, limit=15):
        """Reads the security log file and displays the most recent audit events."""
        print(f"\n--- SECURITY AUDIT (Last {limit} events) ---")
        try:
            with open("data/logs/security.log", "r") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    print(line.strip())
        except FileNotFoundError:
            print("No security logs found.")
        print("-" * 45)