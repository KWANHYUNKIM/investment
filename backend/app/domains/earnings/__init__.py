"""Earnings domain — earnings board, delisting risk, earnings quality.

Layered: router (transport) → service (delegates to ``app.data`` boards).
Part of the strangler-fig migration of ``app/api/data`` (see ``domains/prices``
for the reference implementation).
"""
from .router import router

__all__ = ["router"]
