"""Dependency-injection providers for the report domain.

Providers live *inside* the domain (not in ``app/core``) so ``core`` stays a
dependency-free leaf and there is no core→domain import cycle. ``lru_cache``
gives the domain one shared service per process; tests can still build their
own ``ReportService`` directly.
"""
from __future__ import annotations

from functools import lru_cache

from .repository import ReportRepository
from .service import ReportService


@lru_cache
def get_report_service() -> ReportService:
    return ReportService(ReportRepository())
