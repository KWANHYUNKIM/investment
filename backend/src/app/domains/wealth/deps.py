"""Dependency-injection providers for the wealth domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``WealthService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .service import WealthService


@lru_cache
def get_wealth_service() -> WealthService:
    return WealthService()
