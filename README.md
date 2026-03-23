HospitalityOS v4.0 — Enterprise Edition
Lead Architect: Princeton Afeez

Release Date: March 2026

Status: Stable / Production-Ready

🚀 The Leap to v4.0
While v3.0 focused on basic Object-Oriented structures, v4.0 introduces professional "Mission-Critical" features: Atomic Data Integrity, Advanced Financial Guardrails, and Role-Based Access Control (RBAC).

🛠️ Technical Milestone Log (v4.0 Updates)
1. Atomic Persistence Engine (database.py)
To prevent data loss during the high-paced environment of a restaurant, we moved beyond standard file writing.

The Swap Pattern: The system now writes state data to a hidden temporary file and performs an atomic os.replace. This ensures that even a sudden power failure cannot corrupt the "Shared Brain" (JSON state).

2. High-Precision Financials (models.py)
Decimal Sovereignty: Replaced all float logic with Decimal to ensure 100% accuracy for tax, tips, and split-checks.

Dynamic Tip Parsing: Integrated a smart validator that detects % vs $ symbols, providing a seamless checkout experience.

3. California Labor Compliance 2026
v4.0 is "Audit-Ready." The Staff model now autonomously manages:

Wage Floor: Hard-coded setter logic prevents wages below the $18.00/hr mandate.

Overtime Automations: Calculations for 1.5x pay after 8 hours are baked into the core payroll export.

Penalty Logic: Automatic tracking of "Meal Break Penalties" for shifts exceeding 5 hours.

4. Hardened Security Perimeter (validator.py)
Sanitization Decorators: Implemented a Senior-level Python decorator pattern to scrub all user input for injection characters (;, \) before it reaches the database.

RBAC Gatekeeping: The POS now validates "Department" metadata to restrict sensitive Manager Panel actions to authorized personnel only.

5. Forensic Audit Logging
The SecurityLog: Every high-sensitivity action (Voids, Price Adjustments, Discounts) is now captured in security.log with a Staff ID "fingerprint" and a precise timestamp.

📂 Architecture Overview
main.py: High-performance UI and event coordination.

models.py: OOP blueprints for Transactions, Labor, and Inventory.

database.py: The Fail-Safe persistence layer.

validator.py: Input security and RegEx enforcement.

settings/: Centralized configuration (Tax: 9.5%, Min Wage: $18).

📊 Analytics & KPI Tracking
The system now provides a "Shift Snapshot" including:

Net Sales (Tax-exclusive).

SPLH (Sales Per Labor Hour) to measure server efficiency.

Labor-to-Sales Ratio based on BOH/FOH targets defined in settings.