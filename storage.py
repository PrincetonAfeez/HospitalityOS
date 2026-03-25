"""
Atomic JSON writes with optional merge-into-array semantics (e.g. feedback.json).
merge_array replaces fragile substring checks on filenames.
"""

import json
import logging
import os
import threading
from typing import Any, Optional

LOG = logging.getLogger(__name__)
_io_lock = threading.Lock()


def atomic_write_json(file_path: str, data: Any) -> bool:
    """
    Write JSON atomically (temp file + os.replace) for restaurant_state, Z-reports, etc.
    """
    temp_path = f"{file_path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, default=str)
        os.replace(temp_path, file_path)
        return True
    except OSError as exc:
        LOG.error("atomic_write_json failed %s: %s", file_path, exc)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return False


def save_to_json(data: Any, filename: str, *, merge_array: bool = False) -> bool:
    """
    Write JSON atomically via temp file + os.replace.
    If merge_array=True, load existing root list (if any), append `data`, save combined list.
    """
    temp_filename = f"{filename}.tmp"

    with _io_lock:
        try:
            payload: Any = data
            if merge_array:
                logs: list = []
                if os.path.exists(filename):
                    with open(filename, "r", encoding="utf-8") as fh:
                        try:
                            logs = json.load(fh)
                            if not isinstance(logs, list):
                                logs = [logs]
                        except json.JSONDecodeError:
                            logs = []
                logs.append(data)
                payload = logs

            with open(temp_filename, "w", encoding="utf-8") as fh:
                if hasattr(payload, "model_dump"):
                    json.dump(payload.model_dump(), fh, indent=4, default=str)
                else:
                    json.dump(payload, fh, indent=4, default=str)

            os.replace(temp_filename, filename)
            return True

        except OSError as exc:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            LOG.error("Storage error for %s: %s", filename, exc)
            print(f"[X] Storage Error for {filename}: {exc}")
            return False


def load_from_json(file_path: str) -> Optional[Any]:
    """Thread-safe read; returns None if missing or corrupt."""
    with _io_lock:
        try:
            if not os.path.exists(file_path):
                return None
            with open(file_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            LOG.warning("Load failed %s: %s", file_path, exc)
            print(f"[!] Load Error: Could not read {file_path}. ({exc})")
            return None
