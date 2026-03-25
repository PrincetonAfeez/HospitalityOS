"""
HospitalityOS v4.0 - Universal Utilities
Path resolution, logging bootstrap, UTF-8 console hints, and run correlation ID.
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("hospitalityos.utils")

# Correlates audit lines and log messages within one process (see docs/observability.md).
_run_id: Optional[str] = None


def init_run_context() -> str:
    """Generate and store a run_id once per process; safe to call multiple times."""
    global _run_id
    if _run_id is None:
        _run_id = uuid.uuid4().hex[:12]
    return _run_id


def get_run_id() -> str:
    """Return current run_id, initializing if needed (e.g. tests calling SecurityLog directly)."""
    return init_run_context()

# Standard basenames — use with PathManager.get_path(...) everywhere (no hardcoded paths).
SECURITY_LOG_NAME = "security.log"
ACTIVE_TABLES_NAME = "active_tables.json"
FEEDBACK_JSON_NAME = "feedback.json"
MANAGER_AUTH_NAME = "manager_auth.json"
RESTAURANT_STATE_NAME = "restaurant_state.json"
# Operational CSVs kept under data/logs/ (not inventory/menu exports)
LOG_CSV_NAMES = frozenset({"shift_log.csv", "morning_order.csv"})


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent-ish basic logging for POS / launcher processes."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def try_configure_utf8_stdout() -> None:
    """Reduce UnicodeEncodeError on Windows cp1252 consoles when printing emoji."""
    stdout = getattr(sys, "stdout", None)
    if stdout and hasattr(stdout, "reconfigure"):
        try:
            stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError) as exc:
            LOG.debug("stdout reconfigure skipped: %s", exc)


class PathManager:
    """
    Resolves data/, data/logs/, and settings/ from the repo root (directory of this file).
    """

    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = DATA_DIR / "logs"
    SETTINGS_DIR = BASE_DIR / "settings"

    @classmethod
    def _ensure_dirs(cls) -> None:
        for folder in (cls.DATA_DIR, cls.LOG_DIR, cls.SETTINGS_DIR):
            folder.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_path(cls, filename: str) -> str:
        """
        Route by basename only (ignore directory prefixes) for consistent resolution.
        """
        cls._ensure_dirs()
        base = os.path.basename(filename.strip())

        if base == MANAGER_AUTH_NAME:
            target = cls.SETTINGS_DIR / base
        elif base in LOG_CSV_NAMES:
            target = cls.LOG_DIR / base
        elif base.endswith(".log") or "Z_REPORT" in base:
            target = cls.LOG_DIR / base
        elif base.endswith(".py") and base != "main.py":
            target = cls.SETTINGS_DIR / base
        elif base.endswith(".csv") or base.endswith(".json"):
            target = cls.DATA_DIR / base
        else:
            target = cls.BASE_DIR / base

        return str(target)


def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_divider(char: str = "=", length: int = 45) -> None:
    """ASCII-friendly divider (default '=') for all consoles."""
    print(char * length)
