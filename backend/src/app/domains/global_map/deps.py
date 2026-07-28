"""Dependency-injection providers for the global_map domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``GlobalMapService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .repository import GlobalMapRepository
from .service import GlobalMapService


@lru_cache
def get_global_map_service() -> GlobalMapService:
    return GlobalMapService(GlobalMapRepository())
