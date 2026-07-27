"""Response contracts for the themes domain.

Intentionally empty: every endpoint passes through the dict/list payloads built
by ``futuretheme`` / ``growth_scheduler`` themselves (dynamic, evolving key
sets — theme summaries, news trends, mapped tickers, snapshot metadata). A
strict model here would silently strip fields the frontend reads.
"""
from __future__ import annotations
