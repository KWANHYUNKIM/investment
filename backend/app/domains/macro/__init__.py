"""Macro domain — Korea macro / real-estate / money-supply endpoints.

Layered: router (transport) → service (delegation to ``app.data.macro``).
Strangler-fig migration of the legacy ``app/api/data/macro.py`` router.
"""
from .router import router

__all__ = ["router"]
