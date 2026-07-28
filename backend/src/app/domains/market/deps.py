"""Dependency-injection providers for the market domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``MarketService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .service import MarketService


@lru_cache
def get_market_service() -> MarketService:
    return MarketService()
