"""Response contracts for the wealth domain.

Intentionally empty of models: every wealth payload (plan, holdings, sims,
picks, IPO schedule) is a dynamic dict assembled by ``app.data.market.wealthplan``
/ ``app.data.market.picks`` with an evolving key set the frontend reads
directly. A strict pydantic model here would silently strip fields, so the
endpoints pass the dicts through unchanged — identical to the legacy router.
"""
from __future__ import annotations
