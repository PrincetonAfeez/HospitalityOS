HospitalityOS v4.0 🍽️
Architect: Princeton Afeez

Status: Production-Ready / California Labor Law Compliant

HospitalityOS is a full-stack restaurant management ecosystem designed to bridge the gap between front-of-house operations, back-of-house inventory management, and executive-level labor auditing.

🚀 Core Modules
🛋️ Digital Front Desk: Smart table allocation and party-size optimization with a real-time Waitlist Manager.

🍔 Service Floor (POS): A high-precision ordering engine that deducts inventory atomically and handles complex modifiers.

📊 Labor & Compliance Auditor: Automated payroll calculation featuring California-mandated meal break penalties and overtime math.

🧠 The "Shared Brain": A centralized JSON state manager that ensures data persistence across all departmental modules.

✨ Key Features
CA Labor Compliance: Automatically applies a +1 hour base-pay penalty for shifts exceeding 6 hours without a recorded 30-minute break.

Guest 360 CRM: Integrated loyalty tracking that monitors guest spend and automatically applies VIP tags and Tax-Exempt status.

Prime Cost Analytics: Real-time calculation of Labor % vs. COGS (Cost of Goods Sold) to provide GMs with an immediate snapshot of profitability.

Inventory Guard: Prevents the sale of "86'd" items using a specialized InsufficientStockError exception.

🛠️ Technical Stack
Language: Python 3.10+

Data Strategy: CSV for static databases (Menu/Staff); JSON for dynamic state persistence.

Math Engine: decimal.Decimal implementation to prevent floating-point drift in financial transactions.

Pattern: Singleton Pattern for the DailyLedger to maintain a single source of truth for revenue.

Roadmap & Future Phases
[ ] Phase 5: Integration of a KDS (Kitchen Display System) using WebSockets.

[ ] Phase 6: Migration from JSON/CSV to a PostgreSQL relational database.

[ ] Phase 7: Predictive labor scheduling using historical sales data.