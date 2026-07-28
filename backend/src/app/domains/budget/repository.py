"""Data-access layer for the budget domain — intentionally empty.

The legacy budget endpoints never touch ``app.data.infra.store`` directly; all
persistence lives behind ``app.data.market.budget``, which the service delegates
to wholesale. If budget-specific store access is ever pulled up into this
domain, a ``BudgetRepository`` goes here (the only place allowed to import
``app.data.infra.store``) — until then there is nothing to wrap.
"""
from __future__ import annotations
