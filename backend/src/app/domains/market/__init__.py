"""Market domain — cross-asset, pulse, premarket, signals, movers, briefing.

Layered: router (transport) → service (delegation to ``app.data`` market
modules). This domain is an aggregator: business logic stays in the underlying
``app.data.market`` / ``app.data.macro`` / ``app.data.news`` /
``app.data.reports`` modules; the service only delegates. No repository layer —
the domain never touches ``app.data.infra.store`` directly.
"""
from .router import router

__all__ = ["router"]
