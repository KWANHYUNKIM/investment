"""Response contracts for the market domain.

Every endpoint here aggregates a legacy ``app.data`` module whose payload is a
wide, evolving dict (snapshots, forecasts, AI narratives, archives). Typing
those with strict pydantic models would silently strip fields the frontend
reads, so all responses are passed through as plain ``dict`` on purpose — the
underlying modules remain the single source of truth for their shapes.
"""
from __future__ import annotations
