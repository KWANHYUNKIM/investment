"""Prices domain — coverage, securities, prices, quotes, live, screen, OHLC.

Layered: router (transport) → service (logic + cache) → repository (DuckDB).
Reference implementation for the strangler-fig migration of ``app/api/data``.
"""
from .router import router

__all__ = ["router"]
