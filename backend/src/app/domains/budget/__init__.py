"""Budget domain — 가계부 (급여·카드내역·저축계획).

Layered: router (transport) → service (delegation to ``app.data.market.budget``).
Strangler-fig migration of the legacy ``app/api/data/budget.py`` router.
"""
from .router import router

__all__ = ["router"]
