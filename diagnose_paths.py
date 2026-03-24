"""
Path diagnostic — delegates to utils.PathManager (single implementation).
"""

import os

from utils import PathManager, RESTAURANT_STATE_NAME, SECURITY_LOG_NAME


def run_diagnostic() -> None:
    print("\n" + "=" * 50)
    print(f"{'HOSPITALITY OS: PATH DIAGNOSTIC v4.0':^50}")
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
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_diagnostic()
