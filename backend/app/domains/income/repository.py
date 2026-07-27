"""Data-access layer for the income domain — intentionally empty.

The income domain does not touch ``app.data.infra.store`` (DuckDB) at all: its
persistence is per-user JSON files managed *inside* ``app.data.market.income``,
which the service delegates to wholesale. Until that module is decomposed,
there is no storage seam to wrap here. This placeholder keeps the package shape
consistent with the other layered domains (e.g. ``app/domains/prices``) and
marks where store access must go if the domain ever needs it.
"""
from __future__ import annotations
