"""Report domain — per-stock daily report and news lookup.

Layered: router (transport) → service (delegation to ``app.data`` modules).
No repository: this domain never touches ``app.data.infra.store`` — the report
and news builders own their own I/O and caching.
"""
from .router import router

__all__ = ["router"]
