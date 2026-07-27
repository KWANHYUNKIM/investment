"""Dependency-injection providers for the prices domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service (and thus one shared quote cache) per
process; tests can still build their own ``PricesService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .repository import PricesRepository
from .service import PricesService


@lru_cache
def get_prices_service() -> PricesService:
    return PricesService(PricesRepository())
