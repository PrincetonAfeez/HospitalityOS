# HospitalityOS v4.0

**Text-only** (console) restaurant operations simulator — front desk, POS, waitlist, manager tools, and file-backed ledger state. Intended as a **system architect portfolio** piece: clear boundaries, documented tradeoffs, and a deliberate **non-production** scope.

## What this is

- Single-process Python CLI with **CSV catalogs** (`menu.csv`, `staff.csv`) and **`restaurant_state.json`** for daily totals and inventory snapshot.
- **Composition root:** `SessionContext` in `app_context.py` (menu, ledger, floor, user + **run_id** for audit correlation).
- **Documentation:** start at **[docs/README.md](docs/README.md)** (C4, ADRs, NFR table, threat sketch, demo script).

## What this is not

No web UI, no card processing, no legal payroll — see **[docs/non-goals.md](docs/non-goals.md)**.

## Quick start

```bash
python setup_os.py          # first-time: folders + seed data + settings template
python diagnose_paths.py    # optional: paths + CSV/JSON smoke checks
python launcher.py          # splash + preflight + main
# or: python main.py
```

**Staff IDs** live in `data/staff.csv` (`EMP-…`). Login is **ID-only (demo)** — not real authentication. Manager overrides use `settings/manager_auth.json`.

## Portfolio map

| Artifact | Location |
|----------|----------|
| C4 diagrams | [docs/c4/overview.md](docs/c4/overview.md) |
| ADRs | [docs/adr/](docs/adr/) |
| NFRs | [docs/nfr.md](docs/nfr.md) |
| Threat sketch | [docs/threat-model.md](docs/threat-model.md) |
| Module boundaries | [docs/modules.md](docs/modules.md) |
| Run ID & audit | [docs/observability.md](docs/observability.md) |
| Demo walkthrough | [docs/DEMO.md](docs/DEMO.md) |
| Runtime overview | [docs/architecture.md](docs/architecture.md) |

## Tests & CI

```bash
python -m unittest discover -s . -p "test_*.py" -v
```

CI runs the same via GitHub Actions (`.github/workflows/ci.yml`).

## Dependencies

- `requirements.txt` — `pydantic>=2,<3`
- `requirements-lock.txt` — optional pinned install

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

*Architect portfolio — Princeton Afeez / HospitalityOS.*
