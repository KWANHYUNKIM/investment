"""Business logic seam for the watchlist domain.

The watchlist/portfolio logic (current prices, signals, diagnosis) already
lives in ``app.data.market.watchlist``; this service delegates to those exact
functions unchanged — same behavior, same payload shapes. The absolute import
``app.data.market.watchlist`` does not clash with this package
(``app.domains.watchlist``). When that logic later moves in-domain, only this
file grows — router stays a thin transport layer.

No repository: the business module owns its own persistence, so this domain
never touches ``app.data.infra.store`` directly (see ``repository.py`` note).
"""
from __future__ import annotations

from app.data.market import watchlist as watchlist_data


class WatchlistService:
    def get_watch(self, user: str):
        return watchlist_data.get_watch(user)

    def add_watch(self, user: str, ticker: str):
        return watchlist_data.add_watch(user, ticker)

    def remove_watch(self, user: str, ticker: str):
        return watchlist_data.remove_watch(user, ticker)

    def diagnose(self, user: str):
        return watchlist_data.diagnose(user)

    def set_holdings(self, user: str, holdings: list[dict]):
        return watchlist_data.set_holdings(user, holdings)
