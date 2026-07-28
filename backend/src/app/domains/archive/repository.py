"""Data-access layer for the archive domain — intentionally empty.

The archive domain never touches ``app.data.infra.store`` directly: persistence
of daily reports lives behind ``app.data.reports.daily_archive`` (its own
file/DB seam), which the service delegates to. If archive-specific store
queries appear later, they belong here and nowhere else in the domain.
"""
from __future__ import annotations
