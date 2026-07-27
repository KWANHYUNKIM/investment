"""Response contracts for the costmodel domain — passthrough on purpose.

Every costmodel payload is a rich, deeply nested dict produced by the
``app.data.fundamentals`` engines (cost teardowns, DART 사업보고서 파싱,
integrity X1~X35 evidence, peer boards …) whose column sets evolve with the
parsers. Applying strict pydantic models here would silently strip fields the
frontend reads, so no ``response_model=`` is used — dicts pass through
unchanged, exactly as in the legacy router.
"""
from __future__ import annotations
