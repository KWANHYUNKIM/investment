"""Business logic for the themes domain.

There is deliberately almost none: each method is a straight delegation to
``app.data.intel.futuretheme`` (crawl/snapshot/mapping owner) or the
``growth_scheduler`` singleton's ``status()``. No store access, so no
repository dependency. ``get`` returns the raw lookup result (possibly empty);
translating "not found" into a 404 is the router's transport concern.
"""
from __future__ import annotations

from app.data.intel import futuretheme
from app.data.schedulers import growth_scheduler


class ThemesService:
    def index(self) -> dict:
        return {"themes": futuretheme.index()}

    def get(self, key: str):
        return futuretheme.get(key)

    def scheduler_status(self) -> dict:
        return growth_scheduler.status()

    def list_dates(self) -> dict:
        return {"dates": futuretheme.list_dates()}

    def refresh(self) -> dict:
        futuretheme.themes(force=True)
        return futuretheme.snapshot(force=True)
