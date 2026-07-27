"""Income domain — 소득·성장 (급여 상세·인상 시뮬·부업·투자수익).

Layered: router (transport) → service (delegation). Strangler-fig migration of
``app/api/data/income.py``; behavior is identical — the service delegates to the
same ``app.data.market.income`` functions the legacy endpoints called.
"""
from .router import router

__all__ = ["router"]
