"""Response contracts for the macro domain — passthrough on purpose.

Every macro payload (ECOS series, RTMS trade aggregates, geocoded apartment
maps, money-supply comparisons) is a wide, evolving dict assembled by its
``app.data.macro`` module. A strict pydantic model here would silently strip
fields the frontend reads, so all endpoints return the delegates' dicts
untyped — identical to the legacy router.
"""
from __future__ import annotations
