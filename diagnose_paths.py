from utils import PathManager
import os

def run_diagnostic():
    """
    Commit 10: Diagnostic utility to verify absolute path resolution.
    """
    print("--- HOSPITALITY OS PATH DIAGNOSTIC ---")
    
    files_to_check = ["menu.csv", "staff.csv", "restaurant_state.json"]
    
    for f in files_to_check:
        path = PathManager.get_path(f)
        exists = "✅ FOUND" if os.path.exists(path) else "❌ MISSING"
        print(f"{f:<20} : {path}")
        print(f"Status: {exists}\n")

    print(f"Base Directory: {PathManager.BASE_DIR}")
    print(f"Data Directory: {PathManager.DATA_DIR}")

if __name__ == "__main__":
    run_diagnostic()