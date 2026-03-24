"""
Manager override: verify Staff ID exists in staff.csv with MANAGER role/dept and PIN.
PIN defaults live in settings/manager_auth.json (created by setup_os).
"""

import json
import os
from typing import Any, Dict, Tuple

from utils import PathManager


def _default_auth_config() -> Dict[str, Any]:
    return {"override_pin": "5555", "_comment": "Training/demo only — replace for production."}


def load_auth_config() -> Dict[str, Any]:
    path = PathManager.get_path("manager_auth.json")
    if not os.path.isfile(path):
        return _default_auth_config()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if "override_pin" not in data:
            data["override_pin"] = _default_auth_config()["override_pin"]
        return data
    except (json.JSONDecodeError, OSError):
        return _default_auth_config()


def _staff_rows() -> list[dict[str, str]]:
    path = PathManager.get_path("staff.csv")
    if not os.path.isfile(path):
        return []
    import csv

    with open(path, "r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def verify_manager_override(manager_id: str, pin: str) -> Tuple[bool, str]:
    """
    True if manager_id is listed as MANAGER in staff.csv and pin matches config.
    """
    mid = manager_id.strip().upper()
    cfg = load_auth_config()
    expected = str(cfg.get("override_pin", "5555")).strip()

    for row in _staff_rows():
        sid = row.get("staff_id", "").strip().upper()
        if sid != mid:
            continue
        dept = row.get("dept", "").strip().upper()
        if dept != "MANAGER":
            return False, "That staff ID is not a manager in staff.csv."
        if pin.strip() != expected:
            return False, "Invalid manager PIN."
        return True, mid

    if mid:
        return False, "Manager staff ID not found in staff.csv."
    return False, "Manager staff ID required."
