# HospitalityOS — Architecture (v4)

## Entry points

- **`launcher.py`** — Splash, folder preflight, UTF-8 stdout hint, then `main.system_bootstrap()` + `main_loop`.
- **`main.py`** — Login, global menu. **Service floor (option 2)** uses **`digitalpos.run_pos`** with a synthetic walk-in `Guest` so ordering logic is not duplicated.
- **`setup_os.py`** — Creates `data/`, `settings/`, seed CSVs, `manager_auth.json`. **Does not overwrite** `restaurant_defaults.py` if present. **`restaurant_defaults.example.py`** is the template for new environments.

## Data flow

1. **`database.load_system_state`** — Reads `menu.csv`, `staff.csv`, hydrates `restaurant_state.json` into `DailyLedger` (total_revenue, **total_tips**, transaction_count, inventory snapshot).
2. **`database.save_system_state(menu, ledger, staff_id=?)`** — Writes the full ledger + inventory snapshot + `last_updated`.
3. **Paths** — Always **`utils.PathManager.get_path(basename)`** (or named constants in `utils.py`). Avoid string paths like `"data/foo.json"` in new code.
4. **Security audit** — **`models.SecurityLog`** → `data/logs/security.log` via PathManager.

## Money & tips

- **`DailyLedger.record_sale(amount, tip=None)`** — Increments `total_revenue` and optionally **`total_tips`** (tips are tracked separately from net sales for reporting).
- **Z-reports** (`manager_tools.ManagerTools.generate_z_report`) archive both totals, then reset ledger.

## Manager override

- **`manager_auth.verify_manager_override`** — Manager `staff_id` must exist in `staff.csv` with **dept MANAGER**; PIN must match **`settings/manager_auth.json`** (`override_pin`), default `5555` for training.
- **`require_manager_auth`** — If the first argument is **`ManagerTools`**, prompts for override (PIN path). If first argument is **`Staff`** and role is MANAGER, allows; otherwise requires override.

## Training / demo scope

- **`Staff.calculate_shift_pay`**, **`laborcostauditor`**, and labor-related UI strings are **not** legal payroll or CA compliance systems — labels and disclaimers say “training / demo”.

## Tests

- **`test_suite.py`** — Unit tests (no disk required for core cases).
- **`test_setup.py`** — Integration test; **skips** if `menu.csv` or `Classic Burger` row missing.

## Dependencies

- **`requirements.txt`** — Flexible `pydantic>=2,<3`.
- **`requirements-lock.txt`** — Optional pinned install for reproducibility.
