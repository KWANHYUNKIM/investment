"""Screening endpoint."""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException

from app.data.infra import store
from app.models.schemas import ScreenRequest
from app.quant import screening

router = APIRouter(prefix="/api/screen", tags=["screening"])


@router.post("")
def screen(req: ScreenRequest):
    table = store.screening_table(market=req.market, on=req.as_of)
    if table.empty:
        raise HTTPException(404, "no fundamentals in store — run the ingest script first")

    config = screening.ScreenConfig(
        filters=[screening.Filter(f.factor, f.min, f.max) for f in req.filters],
        factors=[screening.FactorWeight(f.factor, f.weight, f.direction) for f in req.factors],
        top_n=req.top_n,
    )
    ranked = screening.rank(table, config)
    ranked = ranked.replace({np.nan: None})
    return {
        "count": len(ranked),
        "results": ranked.to_dict(orient="records"),
    }
