"""Archive domain — daily-report archive dates, load, and snapshot.

Layered: router (transport) → service (logic) → app.data.reports/schedulers.
Strangler-fig migration of the legacy ``app/api/data/archive.py`` module.
"""
from .router import router

__all__ = ["router"]
