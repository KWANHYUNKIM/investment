"""Themes domain — future growth-theme (미래 성장테마) endpoints.

Layered: router (transport) → service (logic). Pure delegation to the
``app.data.intel.futuretheme`` module and the ``growth_scheduler`` singleton —
no store access, so no repository. Part of the strangler-fig migration of
``app/api/data``.
"""
from .router import router

__all__ = ["router"]
