"""Response contracts for the earnings domain — none, on purpose.

All four endpoints return the dynamic board payloads built by
``app.data.market.earnings`` / ``delisting`` / ``earnings_quality`` and the
delisting scheduler's status dict. Their column sets are wide and evolving, so
they are passed through untyped — a strict model here would silently strip
fields the frontend reads (same rationale as the dynamic endpoints in
``domains/prices``).
"""
from __future__ import annotations
