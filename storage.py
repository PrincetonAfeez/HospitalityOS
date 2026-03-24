import json
import os

def save_to_json(data, filename):
    """
    Commit 12: Refactored with Atomic Persistence.
    Uses a temporary file and os.replace to prevent data corruption.
    """
    temp_filename = f"{filename}.tmp"
    try:
        # 1. Prepare the data payload
        if "log" in filename:
            logs = []
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = [logs]
                    except json.JSONDecodeError:
                        logs = []
            logs.append(data)
            payload = logs
        else:
            payload = data

        # 2. Write to a temporary file first (The "Atomic" part)
        with open(temp_filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

        # 3. Rename temp file to actual filename (OS-level atomic swap)
        os.replace(temp_filename, filename)
        return True

    except Exception as e:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        print(f"❌ Atomic Save Error for {filename}: {e}")
        return False

def load_from_json(filename):
    """Universal helper to load data from JSON."""
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None