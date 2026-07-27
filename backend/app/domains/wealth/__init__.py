"""Wealth domain — 재테크 로드맵(목표금액 → 달성계획 + 자격조건별 상품추천).

Layered: router (transport) → service (delegation to ``app.data.market``).
Strangler-fig migration of ``app/api/data/wealth.py`` — behavior unchanged.
"""
from .router import router

__all__ = ["router"]
