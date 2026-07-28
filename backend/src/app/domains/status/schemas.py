"""Response contracts for the status domain.

Intentionally empty: every endpoint passes through the progress dict built by
the crawler/scheduler modules themselves (dynamic, evolving key sets). A strict
model here would silently strip fields the ops dashboard reads.
"""
from __future__ import annotations
