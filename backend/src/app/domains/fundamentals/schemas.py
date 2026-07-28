"""Response contracts for the fundamentals domain.

Intentionally empty of models: every endpoint here builds nested, partly
dynamic dicts (investor-flow rows, fundamentals Δ maps, DART statement trees
whose account columns come straight from DuckDB). They are passed through as
``dict`` on purpose — a strict model would risk silently stripping or coercing
fields the frontend reads, breaking the byte-identical strangler-fig contract.
"""
from __future__ import annotations
