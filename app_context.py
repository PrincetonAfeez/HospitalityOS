"""
Application session context — composition root for one HospitalityOS process.
Keeps domain objects together with a stable run_id for audit correlation (see docs/observability.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from hospitality_models import FloorMap
from models import DailyLedger, Menu, Staff


@dataclass
class SessionContext:
    """One logged-in operator session over shared menu, ledger, and floor state."""

    run_id: str
    menu: Menu
    ledger: DailyLedger
    floor: FloorMap
    user: Optional[Staff] = None
