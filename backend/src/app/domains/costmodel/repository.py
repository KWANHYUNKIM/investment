"""Data-access layer for the costmodel domain — intentionally empty.

Unlike ``prices``, the costmodel endpoints never touch ``app.data.infra.store``
directly: every read goes through the ``app.data.fundamentals`` / ``app.data
.news`` / ``app.data.schedulers`` engines, which own their own persistence and
caching. The service delegates to those engines, so there is nothing for a
repository to wrap today. This module exists only to keep the domain layout
parallel; if the engines' store access is ever inverted, it becomes the seam.
"""
from __future__ import annotations
