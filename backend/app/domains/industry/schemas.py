"""Response contracts for the industry domain.

Intentionally empty of models: every payload (industry groups, research feed,
scheduler status, refresh summary) comes straight from ``app.data.intel`` /
``app.data.schedulers`` with a wide, evolving key set. A strict model here
would silently strip fields the frontend reads, so the endpoints pass dicts
through unchanged — exactly like the legacy router did.
"""
from __future__ import annotations
