"""Response contracts for the watchlist domain — passthrough on purpose.

Every endpoint returns the payload built by ``app.data.market.watchlist``
(watch rows with live price/signal/upside fields, portfolio diagnosis with an
evolving column set). A strict model here would silently strip fields the
frontend reads, so no ``response_model=`` is applied — shapes stay identical to
the legacy router.
"""
from __future__ import annotations
