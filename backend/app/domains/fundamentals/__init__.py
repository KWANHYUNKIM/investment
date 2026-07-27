"""Fundamentals domain — investor flow, fundamentals, financials, DART statements, holders.

Layered: router (transport) → service (logic) → repository (DuckDB).
Strangler-fig migration of ``app/api/data/fundamentals.py``.
"""
from .router import router

__all__ = ["router"]
