"""Data-access layer for the global_map domain.

The repository is the *seam* between the domain and the physical store: it is
the only place in the domain that knows ``app.data.infra.store`` (DuckDB)
exists. Today it wraps the legacy module-level ``store`` functions; when
``store`` later moves under ``app/infra/db``, only this file changes —
service/router don't.
"""
from __future__ import annotations

from app.data.infra import store


class GlobalMapRepository:
    def foreign_fin_count(self) -> int:
        return store.foreign_fin_count()
