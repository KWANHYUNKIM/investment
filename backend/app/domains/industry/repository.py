"""Data-access layer for the industry domain — intentionally empty.

The legacy industry endpoints never touch ``app.data.infra.store`` directly;
all persistence is hidden behind the ``app.data.intel.industry`` /
``industry_research`` business modules the service delegates to. This file is
kept as the designated seam: if the domain ever needs direct store access, it
goes here (and only here), mirroring ``app/domains/prices/repository.py``.
"""
from __future__ import annotations
