"""Response contracts for the budget domain — passthrough on purpose.

Every payload comes straight from ``app.data.market.budget`` as a plain dict
with an evolving key set (summary buckets, parsed payslip fields, import
reports, plan breakdowns). The legacy endpoints returned those dicts verbatim
and the frontend reads them as-is, so no ``response_model`` is applied — a
strict model here would silently strip keys and change behavior.
"""
from __future__ import annotations
