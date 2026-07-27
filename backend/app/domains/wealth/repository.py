"""Data-access layer for the wealth domain — intentionally empty.

The legacy wealth endpoints never touch ``app.data.infra.store`` directly;
all persistence (profile/holdings) lives behind ``app.data.market.wealthplan``
and the picks snapshots behind ``app.data.market.picks``. Until those modules
are themselves decomposed, there is nothing for a repository to wrap, so this
file exists only to keep the domain layout symmetric with ``domains/prices``.
If wealth ever needs direct store access, it goes here and nowhere else.
"""
from __future__ import annotations
