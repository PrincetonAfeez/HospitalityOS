"""
HospitalityOS v4.0 - Storage Engine
Refactor: Combined Atomic File Swapping with Threading Locks for 100% Data Integrity.
"""

import json
import os
import threading
from typing import Any, Optional

# --- GLOBAL LOCK ---
# Prevents multiple threads from accessing the filesystem simultaneously
_io_lock = threading.Lock()

def save_to_json(data: Any, filename: str) -> bool:
    """
    Thread-safe & Atomic write operation.
    Uses a Lock to prevent race conditions and os.replace to prevent corruption.
    """
    temp_filename = f"{filename}.tmp"
    
    with _io_lock: # Ensure only one thread enters this block
        try:
            # 1. Prepare the data payload (Existing Log logic)
            payload = data
            if "log" in filename:
                logs = []
                if os.path.exists(filename):
                    with open(filename, "r", encoding="utf-8") as f:
                        try:
                            logs = json.load(f)
                            if not isinstance(logs, list): logs = [logs]
                        except json.JSONDecodeError:
                            logs = []
                logs.append(data)
                payload = logs

            # 2. Write to a temporary file (Atomic Safety)
            # Check for Pydantic model conversion
            with open(temp_filename, "w", encoding="utf-8") as f:
                if hasattr(payload, "model_dump"):
                    json.dump(payload.model_dump(), f, indent=4, default=str)
                else:
                    json.dump(payload, f, indent=4, default=str)

            # 3. OS-level atomic swap
            os.replace(temp_filename, filename)
            return True

        except Exception as e:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            print(f"❌ Storage Error for {filename}: {e}")
            return False

def load_from_json(file_path: str) -> Optional[Any]:
    """
    Thread-safe read operation.
    """
    with _io_lock: # Prevent reading while another thread is mid-swap
        try:
            if not os.path.exists(file_path):
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Load Error: Could not read {file_path}. (Error: {e})")
            return None