import json
import os

def save_to_json(data, filename):
    """Universal helper to save dictionaries or append to JSON lists."""
    try:
        # Task: Handle Log Files (Must always be lists)
        if "log" in filename:
            logs = []
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    try:
                        logs = json.load(f)
                        if not isinstance(logs, list):
                            logs = [logs] # Safety wrap
                    except json.JSONDecodeError:
                        logs = []
            
            logs.append(data)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=4)
        
        # Task: Handle State Files (Direct Overwrite)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"❌ Error saving to {filename}: {e}")
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