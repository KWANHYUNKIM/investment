"""Business logic for the global_map domain.

Delegates to the same ``app.data`` functions the legacy endpoints called —
cluster index/detail from ``app.data.intel.global_map``, foreign fundamentals
refresh via ``app.data.fundamentals.finnhub`` over the
``app.data.infra.global_universe`` symbol list. Depends on the repository
(store counts) — never on FastAPI.
"""
from __future__ import annotations

from app.data.fundamentals import finnhub
from app.data.intel import global_map
from app.data.infra import global_universe

from .repository import GlobalMapRepository
from .schemas import ClusterDetail, ClustersResponse, RefreshResponse


class GlobalMapService:
    def __init__(self, repo: GlobalMapRepository) -> None:
        self._repo = repo

    def clusters(self) -> ClustersResponse:
        return {
            "clusters": global_map.index(),
            "finnhub": finnhub.enabled(),
            "foreign_loaded": self._repo.foreign_fin_count(),
        }

    def cluster(self, key: str) -> ClusterDetail | None:
        """One cluster's peer table, or ``None``/falsy when the key is unknown
        (the router turns that into the legacy 404)."""
        return global_map.get(key)

    def finnhub_enabled(self) -> bool:
        return finnhub.enabled()

    def refresh(self) -> RefreshResponse:
        n = finnhub.refresh_many(global_universe.all_foreign_symbols())
        global_map.invalidate()
        return {"fetched": n, "foreign_loaded": self._repo.foreign_fin_count()}
