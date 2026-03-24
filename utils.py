"""
HospitalityOS v4.0 - Universal Utilities
Architect: Princeton Afeez
Description: Centralized path resolution and system-wide helper functions.
             Ensures the 'Shared Brain' works on Windows, macOS, and Linux.
"""

import os
from pathlib import Path

class PathManager:
    """
    Commit 45: Advanced Path Resolver.
    Uses 'pathlib' for modern, cross-platform compatibility.
    """
    # 1. Establish the absolute Root of the project
    # __file__ refers to utils.py; .resolve().parent gets the folder it sits in.
    BASE_DIR = Path(__file__).resolve().parent
    
    # 2. Define Sub-Directory Map
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = DATA_DIR / "logs"
    SETTINGS_DIR = BASE_DIR / "settings"

    @classmethod
    def _ensure_dirs(cls):
        """Internal helper to guarantee the folder tree exists before writing files."""
        for folder in [cls.DATA_DIR, cls.LOG_DIR, cls.SETTINGS_DIR]:
            folder.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_path(cls, filename: str) -> str:
        """
        Smart Routing: Automatically determines the correct folder based 
        on file extension or naming convention.
        """
        cls._ensure_dirs() # Safety check: create folders if missing
        
        # Route 1: Security and Transaction Logs
        if filename.endswith(".log") or "Z_REPORT" in filename:
            target = cls.LOG_DIR / filename
            
        # Route 2: System Configuration and Defaults
        elif filename.endswith(".py") and filename != "main.py":
            target = cls.SETTINGS_DIR / filename
            
        # Route 3: Standard CSV/JSON Data (Menu, Staff, State)
        elif filename.endswith(".csv") or filename.endswith(".json"):
            target = cls.DATA_DIR / filename
            
        # Route 4: Root Level (scripts)
        else:
            target = cls.BASE_DIR / filename
            
        return str(target) # Return as string for compatibility with open()

# ==============================================================================
# UI HELPERS (Cross-Module)
# ==============================================================================

def clear_terminal():
    """Wipes the screen based on the user's Operating System."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_divider(char="═", length=45):
    """Standardizes UI separators for a consistent 'HospitalityOS' look."""
    print(char * length)