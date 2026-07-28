"""Industry domain — KSIC industry map, per-industry research feed, scheduler.

Layered: router (transport) → service (delegation to ``app.data.intel`` /
``app.data.schedulers``). Part of the strangler-fig migration of
``app/api/data``; behavior is identical to the legacy endpoints.
"""
from .router import router

__all__ = ["router"]
