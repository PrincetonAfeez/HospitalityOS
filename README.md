100 Days of Code = Day 1:

File 1: models.py
The "Blueprint" (Items, Carts, Transactions) and math logic. Classes defined.

File 2: database.py
The "Shared Brain" (CSV loading & JSON state). Storage handled.

File 3: validator.py
The "Security Guard" (Regex & Type checking). Defensive Input secured.


File 4: main.py
The "Orchestrator" (The User Interface), user flow  and Loop operational.



HospitalityOS - Phase 1: The Blueprint
A modular, Object-Oriented Point of Sale (POS) and Inventory Management System.

🏗️ Architecture
The system is divided into four main modules to ensure separation of concerns:

main.py: The entry point and User Interface loop.

models.py: Contains the MenuItem, Menu, Cart, and Transaction classes.

database.py: Handles CSV menu loading and JSON state persistence (The "Shared Brain").

validator.py: Manages robust input validation using RegEx and type-checking.


classDiagram
    class MenuItem {
        +String name
        +Decimal price
        +int line_inv
        +int walk_in_inv
        +int freezer_inv
        +int par_level
    }
    class Menu {
        +List items
        +find_item(name)
    }
    class Cart {
        +List items
        +subtotal
        +add_to_cart(MenuItem)
        +remove_from_cart(name)
    }
    class Transaction {
        +Cart cart
        +int table_num
        +Decimal tip
        +generate_receipt()
    }
    Menu "1" *-- "many" MenuItem
    Cart "1" o-- "many" MenuItem
    Transaction "1" -- "1" Cart

### 🔑 Staff & Auditor Integration (Day 6)
- **Mandatory Login:** System requires a valid `staff_id` (RegEx: `EMP-\d+`) verified against `staff.csv`.
- **Shared Brain Sync:** Every login and transaction updates `restaurant_state.json` with the active server's ID and real-time net sales.
- **Security Audit:** All item removals (voids) are timestamped and logged to `security.log` with the responsible staff member's name.
- **Labor Alerts:** POS provides real-time warnings if sales-to-labor ratios exceed 20%.

# Hospitality OS v3.0

## 🚀 Overview
A professional-grade Point of Sale (POS) and Labor Auditor designed for California compliance.

## 🏗️ Architecture
- **Object-Oriented Design:** Implemented a robust inheritance tree: `Person` -> `Staff` & `Guest`.
- **Domain Separation:** Logic is split between `models.py` (Operations) and `digitalfrontdesk.py` (Guest Intake).
- **CA Labor Law Engine:** Automated overtime (1.5x after 8h) and Meal Break Penalty calculations.
- **Financial Precision:** Powered by the `Decimal` library to ensure zero rounding errors in guest billing.

## 🛠️ Key Features
- Dynamic Inventory Management with "86-list" protection.
- Guest Loyalty & Tax-Exempt status tracking.
- Automated Payroll CSV exporting.