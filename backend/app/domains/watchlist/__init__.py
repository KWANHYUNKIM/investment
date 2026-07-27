"""Watchlist domain — watchlist CRUD + portfolio diagnosis.

Layered: router (transport) → service (delegation to ``app.data.market.watchlist``).
Strangler-fig migration of the legacy ``app/api/data/watchlist.py`` router.
"""
from .router import router

__all__ = ["router"]
