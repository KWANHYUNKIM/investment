"""Costmodel domain — unit economics, company cost models, statement audit,
DART full parsing, integrity score, future value, peer comparison.

Layered: router (transport) → service (delegation to ``app.data.*`` engines).
Part of the strangler-fig migration of ``app/api/data``.
"""
from .router import router

__all__ = ["router"]
