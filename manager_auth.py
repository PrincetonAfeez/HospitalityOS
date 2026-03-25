"""
Manager override: verify Staff ID exists in staff.csv with MANAGER role/dept and PIN.
PIN defaults and optional per-staff PINs live in settings/manager_auth.json (created by setup_os).
"""

import hashlib
import json
import os
from typing import Any, Dict, Tuple

from utils import PathManager

_FAILED_PIN: Dict[str, int] = {}
MAX_FAILED_PINS = 5


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


def _is_manager_row(row: dict[str, str]) -> bool:
    dept = (row.get("dept") or "").strip().upper()
    role = (row.get("role") or row.get("dept") or "").strip().upper()
    return dept == "MANAGER" or role == "MANAGER"


def _expected_pin(manager_id: str, cfg: Dict[str, Any]) -> str:
    mid = manager_id.strip().upper()
    pins = cfg.get("pins") or {}
    for k, v in pins.items():
        if str(k).strip().upper() == mid:
            return str(v).strip()
    return str(cfg.get("override_pin", "5555")).strip()


def _pin_matches(entered: str, stored: str) -> bool:
    entered = entered.strip()
    stored = stored.strip()
    if stored.lower().startswith("sha256:"):
        want = stored.split(":", 1)[1].strip().lower()
        got = hashlib.sha256(entered.encode("utf-8")).hexdigest()
        return got == want
    return entered == stored


def verify_manager_override(manager_id: str, pin: str) -> Tuple[bool, str]:
    """
    True if manager_id is listed as MANAGER in staff.csv and PIN matches config.
    Optional per-staff PINs in manager_auth.json pins; override_pin fallback.
    PIN values may be sha256:<hexdigest> for non-plaintext storage.
    """
    mid = manager_id.strip().upper()
    if not mid:
        return False, "Manager staff ID required."

    if _FAILED_PIN.get(mid, 0) >= MAX_FAILED_PINS:
        return False, "Too many failed PIN attempts for this ID. Restart the application."

    cfg = load_auth_config()
    expected = _expected_pin(mid, cfg)

    for row in _staff_rows():
        sid = row.get("staff_id", "").strip().upper()
        if sid != mid:
            continue
        if not _is_manager_row(row):
            return False, "That staff ID is not a manager in staff.csv."
        if not _pin_matches(pin, expected):
            _FAILED_PIN[mid] = _FAILED_PIN.get(mid, 0) + 1
            return False, "Invalid manager PIN."
        _FAILED_PIN[mid] = 0
        return True, mid

    return False, "Manager staff ID not found in staff.csv."
