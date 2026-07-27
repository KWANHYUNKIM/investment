"""Data-access layer for the macro domain — intentionally empty.

The macro domain reads nothing from ``app.data.infra.store`` (DuckDB): every
endpoint delegates to an ``app.data.macro`` module (korea_flow, korea_diagnosis,
realestate, realestate_map, rent, ecos, money_supply, money_analysis,
realeconomy) that owns its own upstream I/O and caching. This stub exists only
to keep the domain layout symmetric; if macro data ever lands in the store,
this becomes the seam — service/router won't change.
"""
from __future__ import annotations
