"""Data-access layer for the earnings domain — intentionally empty.

This domain performs no direct ``app.data.infra.store`` (DuckDB) access: every
legacy endpoint delegates to the ``app.data.market`` board builders /
``app.data.schedulers.delisting_scheduler``, which own their storage reads.
The module exists only to keep the layered layout uniform across domains; if
the boards' store access is ever pulled into the domain, it belongs here.
"""
from __future__ import annotations
