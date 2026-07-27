"""Response contracts for the dividends domain.

Intentionally empty: every endpoint passes through the dict built by the
``app.data.market`` business modules themselves (dynamic, evolving key sets —
rankings, checklists, crisis tables, ETF references). A strict model here would
silently strip fields the frontend reads.
"""
from __future__ import annotations
