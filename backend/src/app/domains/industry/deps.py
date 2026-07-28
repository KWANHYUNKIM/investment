"""Dependency-injection providers for the industry domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``IndustryService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .service import IndustryService


@lru_cache
def get_industry_service() -> IndustryService:
    return IndustryService()
