"""
HospitalityOS v4.0 - Managerial Tools
Z-reports, labor snapshot helpers, reorder CSV — paths via PathManager.
"""

import csv
import functools
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional, TypeVar

from manager_auth import verify_manager_override
from models import DailyLedger, SecurityLog, Staff
from storage import atomic_write_json
from utils import PathManager, SECURITY_LOG_NAME

F = TypeVar("F", bound=Callable[..., Any])


def require_manager_auth(func: F) -> F:
    """
    If first arg is ManagerTools, require PIN + manager ID from staff.csv.
    If first arg is Staff and role is MANAGER, allow.
    Otherwise Staff must present manager override.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not args:
            return func(*args, **kwargs)

        first = args[0]
        cls_name = getattr(first, "__class__", type(first)).__name__

        def prompt_and_verify() -> Optional[str]:
            print("\n[!] SECURITY:", func.__name__.replace("_", " ").upper())
            print("[!] MANAGER AUTHORIZATION REQUIRED")
            m_id = input("Manager Staff ID: ").strip()
            m_pin = input("Manager PIN: ").strip()
            ok, msg = verify_manager_override(m_id, m_pin)
            if not ok:
                print(f"[X] {msg}")
                return None
            print(f"[OK] Override granted for {m_id}.")
            return m_id

        if cls_name == "ManagerTools":
            m_id = prompt_and_verify()
            if m_id is None:
                return None
            return func(*args, **kwargs, authorized_by=m_id)

        current_staff = first
        if hasattr(current_staff, "role") and str(current_staff.role).upper() == "MANAGER":
            return func(*args, **kwargs)

        m_id = prompt_and_verify()
        if m_id is None:
            return None
        return func(*args, **kwargs, authorized_by=m_id)

    return wrapper  # type: ignore[return-value]


class ManagerTools:
    """Administrative tasks bound to live ledger, menu, and staff roster."""

    def __init__(self, ledger: DailyLedger, menu: Any, staff_list: list[Staff]) -> None:
        self.ledger = ledger
        self.menu = menu
        self.staff_list = staff_list

    @require_manager_auth
    def generate_z_report(self, manager_id: str, authorized_by: str = "SYSTEM") -> bool:
        """Archive sales snapshot then reset ledger totals (training/demo close)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_name = PathManager.get_path(f"Z_REPORT_{timestamp}.json")

        report_data = {
            "business_date": datetime.now().strftime("%Y-%m-%d"),
            "closed_by": manager_id,
            "authorized_by": authorized_by,
            "total_net_sales": str(self.ledger.total_revenue),
            "total_tips_pooled": str(self.ledger.total_tips),
            "transaction_count": self.ledger.transaction_count,
            "average_check": str(
                (self.ledger.total_revenue / self.ledger.transaction_count)
                if self.ledger.transaction_count > 0
                else 0
            ),
        }

        if not atomic_write_json(report_name, report_data):
            print("[X] Z-Report write failed")
            return False

        SecurityLog.log_event(manager_id, "Z_REPORT_GENERATED", f"Report: {report_name}")

        self.ledger.total_revenue = Decimal("0.00")
        self.ledger.total_tips = Decimal("0.00")
        self.ledger.transaction_count = 0

        print(f"[OK] Z-Report archived to {report_name}")
        return True

    def run_labor_audit(self) -> None:
        """TRAINING / DEMO — estimated labor vs sales (not legal payroll)."""
        total_labor_cost = Decimal("0.00")

        print("\n--- LIVE LABOR AUDIT (training estimate) ---")
        for employee in self.staff_list:
            if employee.shift_start and not employee.shift_end:
                employee.shift_end = datetime.now()

            shift_pay = employee.calculate_shift_pay()
            total_labor_cost += shift_pay
            print(f"  {employee.full_name:<18} | Est. Pay: ${shift_pay:>7.2f}")

        sales = self.ledger.total_revenue
        labor_pct = (total_labor_cost / sales * 100) if sales > 0 else Decimal("0.00")

        print("-" * 40)
        print(f"  Total Sales: ${sales:>10.2f}")
        print(f"  Total Labor: ${total_labor_cost:>10.2f}")
        print(f"  Labor %:     {labor_pct:>9.2f}%")
        if labor_pct > 30:
            print("[!] Labor above rough 30% demo threshold.")
        print("-" * 40)

    def generate_reorder_csv(self) -> None:
        """Items under line par -> morning_order.csv in logs folder."""
        reorder_file = PathManager.get_path("morning_order.csv")
        low_stock_items: list[list[Any]] = []

        for item in self.menu.items.values():
            if item.line_inv < item.par_level:
                qty_needed = item.par_level - item.line_inv
                low_stock_items.append([item.name, item.category, item.line_inv, item.par_level, qty_needed])

        if not low_stock_items:
            print("[OK] All inventory levels at/above par.")
            return

        with open(reorder_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Item Name", "Category", "Current Stock", "Par Level", "Order Qty"])
            writer.writerows(low_stock_items)

        print(f"[*] Reorder CSV: {len(low_stock_items)} rows -> {reorder_file}")

    def view_recent_security_logs(self, limit: int = 15) -> None:
        """Tail the security log via PathManager."""
        print(f"\n--- SECURITY AUDIT (last {limit}) ---")
        path = PathManager.get_path(SECURITY_LOG_NAME)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
                for line in lines[-limit:]:
                    print(line.strip())
        except OSError:
            print("No security log found.")
        print("-" * 45)
