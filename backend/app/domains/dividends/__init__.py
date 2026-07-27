"""Dividends domain — 배당 보드·종목 배당 계산기·배당왕/귀족·위기 생존주·ETF·적립식.

Layered: router (transport) → service (logic). All heavy lifting stays in the
``app.data.market`` business modules (dividends / dividend_detail /
dividend_royalty / dividend_etf / crisis_survivors); the domain only delegates.
"""
from .router import router

__all__ = ["router"]
