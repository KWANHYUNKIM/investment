"""Response contracts for the archive domain.

Intentionally empty of typed models: every payload here (archived daily
reports, snapshotter status) is a dynamic dict built by
``app.data.reports.daily_archive`` with a wide, evolving key set. A strict
model would silently strip fields the frontend reads, so the endpoints pass
the dicts through unchanged — exactly like the legacy router did.
"""
from __future__ import annotations
