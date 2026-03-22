import json
import os

def save_to_json(data, filename):
    """Universal helper to save dictionaries to JSON."""
    try:
        # If we are appending to a log, we handle it differently
        if "log" in filename and os.path.exists(filename):
            with open(filename, "r+") as f:
                logs = json.load(f)
                logs.append(data)
                f.seek(0)
                json.dump(logs, f, indent=4)
        else:
            with open(filename, "w") as f:
                json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving to {filename}: {e}")
        return False

def load_from_json(filename):
    """Universal helper to load data from JSON."""
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return json.load(f)