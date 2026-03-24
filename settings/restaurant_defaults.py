"""
Project: Hospitality OS - System Defaults
Description: Centralized business rules, tax rates, and labor targets.
"""
from decimal import Decimal

# ==============================================================================
# FINANCIAL & TAX SETTINGS
# ==============================================================================

# 9.5% Sales Tax - Stored as Decimal for exact multiplication
TAX_RATE = Decimal("0.095")

# Currency formatting for Receipts
CURRENCY_SYMBOL = "$"

# ==============================================================================
# LABOR & COMPLIANCE SETTINGS
# ==============================================================================

# Minimum Wage: Set to $18.00 as per your latest requirements
MIN_WAGE = Decimal("18.00")

# Daily Overtime Limit: Hours worked before 1.5x pay rate applies
OVERTIME_LIMIT = Decimal("8.0")

# ==============================================================================
# BUSINESS INTELLIGENCE (KPIS)
# ==============================================================================

# Labor Cost Targets (Used by the AnalyticsEngine to trigger warnings)
# If BOH labor exceeds 15% of sales, a 'Red Flag' appears in the POS.
BOH_TARGET_PERCENT = Decimal("15.0") 

# If FOH labor exceeds 5% of sales, a 'Efficiency Alert' is logged.
FOH_TARGET_PERCENT = Decimal("5.0")

# ==============================================================================
# OPERATIONAL CONSTRAINTS
# ==============================================================================

# Limit modifiers to keep the kitchen from getting overwhelmed
MAX_MODS = 3

# Default file paths
MENU_FILE = "menu.csv"
STAFF_FILE = "staff.csv"

# settings/restaurant_defaults.py
GRATUITY_THRESHOLD = 6
GRATUITY_RATE = Decimal("0.18")