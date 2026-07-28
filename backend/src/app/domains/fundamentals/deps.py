"""Dependency-injection providers for the fundamentals domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``FundamentalsService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .repository import FundamentalsRepository
from .service import FundamentalsService


@lru_cache
def get_fundamentals_service() -> FundamentalsService:
    return FundamentalsService(FundamentalsRepository())
