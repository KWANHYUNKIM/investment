"""Response contracts for the report domain.

Intentionally empty: both payloads (daily report, news list) are built by the
legacy ``app.data`` modules with wide, evolving key sets, so they are passed
through as ``dict`` on purpose — a strict model here would silently strip
fields the frontend reads.
"""
from __future__ import annotations
