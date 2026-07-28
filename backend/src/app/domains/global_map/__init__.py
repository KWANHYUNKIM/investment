"""Global map domain — global competition map (clusters) endpoints.

Layered: router (transport) → service (logic) → repository (DuckDB).
Strangler-fig migration of ``app/api/data/global_map.py``.
"""
from .router import router

__all__ = ["router"]
