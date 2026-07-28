"""Response contracts for the income domain.

All payloads (overview/salary/raise-sim/side) come straight from
``app.data.market.income`` as plain dicts with an evolving key set the frontend
reads directly, so they are passed through untyped on purpose — a strict model
here would silently strip fields and break the identical-behavior contract of
the strangler-fig migration. Typed models can be introduced per-endpoint once
the payload shapes are frozen.
"""
from __future__ import annotations
