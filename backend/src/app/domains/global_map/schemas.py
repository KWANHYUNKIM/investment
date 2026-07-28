"""Response contracts for the global_map domain.

All payloads here are passed through as ``dict`` on purpose: cluster summaries
and per-cluster peer tables come straight from ``app.data.intel.global_map``
with a rich, evolving nested shape — a strict model would silently strip
fields the frontend reads. Aliases below document the endpoint shapes without
constraining them.
"""
from __future__ import annotations

# {"clusters": [...], "finnhub": bool, "foreign_loaded": int}
ClustersResponse = dict

# One cluster's full peer comparison (Korea + foreign) — dynamic nested dict.
ClusterDetail = dict

# {"fetched": int, "foreign_loaded": int}
RefreshResponse = dict
