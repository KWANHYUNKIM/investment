"""Data-access layer for the watchlist domain — intentionally empty.

This is the only file in the domain allowed to import ``app.data.infra.store``,
but the watchlist domain never touches the store directly: persistence is owned
by the delegated business module ``app.data.market.watchlist``. If store access
is ever pulled in-domain, add a ``WatchlistRepository`` here and inject it into
``WatchlistService`` (see ``app/domains/prices/repository.py`` for the pattern).
"""
from __future__ import annotations
