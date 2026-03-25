# Contributing

## Environment

- Python 3.10+ recommended (uses `list[str]` typing style in places; 3.9 may need minor typing tweaks).
- Install: `pip install -r requirements.txt` or `pip install -r requirements-lock.txt`.

## Run from repo root

Imports assume the project root is on `PYTHONPATH` (e.g. `python main.py` from the repo root).

## Tests

```bash
python -m unittest discover -s . -p "test_*.py" -v
```

## Code style

- Prefer **`PathManager.get_path(basename)`** for files under `data/`, `data/logs/`, `settings/`.
- Domain money rules live in **`models`**; persistence in **`database`** / **`storage`**.
- New features should update **docs** (especially `docs/modules.md` or a new ADR if the decision is significant).

## Destructive scripts

- **`menu.py`** / **`staff.py`** overwrite CSVs — use only when regenerating demo data.
