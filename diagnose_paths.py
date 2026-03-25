"""
Path diagnostic and lightweight health check — delegates to PathManager.
Run: python diagnose_paths.py
See docs/observability.md for RUN ID and audit fields.
"""

import csv
import json
import os

from utils import PathManager, RESTAURANT_STATE_NAME, SECURITY_LOG_NAME


def _check_csv_headers(path: str, required: set[str], label: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if not reader.fieldnames:
                issues.append(f"{label}: no header row")
                return issues
            missing = required - {h.strip() for h in reader.fieldnames if h}
            if missing:
                issues.append(f"{label}: missing columns {sorted(missing)}")
    except OSError as exc:
        issues.append(f"{label}: cannot read ({exc})")
    return issues


def _check_json_state(path: str) -> list[str]:
    issues: list[str] = []
    if not os.path.exists(path):
        return issues
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            issues.append("restaurant_state.json: root must be an object")
            return issues
        if "inventory_snapshot" in data and not isinstance(data["inventory_snapshot"], dict):
            issues.append("restaurant_state.json: inventory_snapshot must be an object")
    except json.JSONDecodeError as exc:
        issues.append(f"restaurant_state.json: invalid JSON ({exc})")
    except OSError as exc:
        issues.append(f"restaurant_state.json: read error ({exc})")
    return issues


def run_diagnostic() -> None:
    print("\n" + "=" * 50)
    print(f"{'HOSPITALITY OS: PATH & HEALTH DIAGNOSTIC v4.0':^50}")
    print("=" * 50)

    files_to_check = [
        "menu.csv",
        "staff.csv",
        RESTAURANT_STATE_NAME,
        SECURITY_LOG_NAME,
        "restaurant_defaults.py",
    ]

    missing_count = 0
    for fname in files_to_check:
        target_path = PathManager.get_path(fname)
        exists = os.path.exists(target_path)
        mark = "[OK]" if exists else "[MISSING]"
        if not exists:
            missing_count += 1
        print(f"FILE: {fname}\nPATH: {target_path}\nSTATUS: {mark}\n")

    print("-" * 50)
    print(f"ROOT: {PathManager.BASE_DIR}")
    print(f"DATA: {PathManager.DATA_DIR}")
    print(f"LOGS: {PathManager.LOG_DIR}")
    print("-" * 50)

    if missing_count == 0:
        print("\n[OK] All checked paths resolve.")
    else:
        print(f"\n[!] {missing_count} file(s) missing — run setup_os.py")

    menu_path = PathManager.get_path("menu.csv")
    staff_path = PathManager.get_path("staff.csv")
    state_path = PathManager.get_path(RESTAURANT_STATE_NAME)

    schema_issues: list[str] = []
    schema_issues.extend(
        _check_csv_headers(
            menu_path,
            {"category", "name", "unit_price", "line_inv", "walk_in_inv", "freezer_inv", "par_level"},
            "menu.csv",
        )
    )
    schema_issues.extend(
        _check_csv_headers(staff_path, {"staff_id", "name", "dept", "hourly_rate"}, "staff.csv")
    )
    schema_issues.extend(_check_json_state(state_path))

    if schema_issues:
        print("\n[SCHEMA / DATA WARNINGS]")
        for line in schema_issues:
            print(f"  - {line}")
    else:
        print("\n[OK] CSV headers and restaurant_state JSON look usable.")

    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_diagnostic()
