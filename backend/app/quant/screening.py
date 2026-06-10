"""Factor screening & ranking.

Two layers:
  1. Hard filters  — keep only rows whose factor is within [min, max].
  2. Factor ranking — z-score each chosen factor (respecting whether high or
     low is "good"), combine with weights, and rank.

A "good" direction of -1 means a *lower* raw value is better (e.g. PER, PBR);
+1 means higher is better (e.g. ROE, dividend yield).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Sensible default "good" direction per known factor.
LOWER_IS_BETTER = {"per", "pbr", "pcr", "psr"}
HIGHER_IS_BETTER = {"roe", "div_yield", "eps", "bps", "market_cap"}


@dataclass
class Filter:
    factor: str
    min: float | None = None
    max: float | None = None


@dataclass
class FactorWeight:
    factor: str
    weight: float = 1.0
    # If None, inferred from LOWER/HIGHER_IS_BETTER tables.
    direction: int | None = None


@dataclass
class ScreenConfig:
    filters: list[Filter] = field(default_factory=list)
    factors: list[FactorWeight] = field(default_factory=list)
    top_n: int = 30


def _direction(factor: str, override: int | None) -> int:
    if override in (-1, 1):
        return override
    if factor in LOWER_IS_BETTER:
        return -1
    if factor in HIGHER_IS_BETTER:
        return 1
    return 1  # default: higher is better


def _zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sd


def apply_filters(df: pd.DataFrame, filters: list[Filter]) -> pd.DataFrame:
    out = df.copy()
    for f in filters:
        if f.factor not in out.columns:
            continue
        col = pd.to_numeric(out[f.factor], errors="coerce")
        if f.min is not None:
            out = out[col >= f.min]
            col = col.loc[out.index]
        if f.max is not None:
            out = out[col <= f.max]
            col = col.loc[out.index]
    return out


def rank(df: pd.DataFrame, config: ScreenConfig) -> pd.DataFrame:
    """Return the screened, scored, ranked table (best first)."""
    filtered = apply_filters(df, config.filters)
    if filtered.empty:
        return filtered.assign(score=[])

    scored = filtered.copy()
    score = pd.Series(0.0, index=scored.index)
    total_w = 0.0
    for fw in config.factors:
        if fw.factor not in scored.columns:
            continue
        raw = pd.to_numeric(scored[fw.factor], errors="coerce")
        # Drop rows missing a scoring factor from contributing (treat as neutral 0).
        z = _zscore(raw.fillna(raw.median())) * _direction(fw.factor, fw.direction)
        score = score + z * fw.weight
        total_w += abs(fw.weight)

    scored["score"] = (score / total_w) if total_w else score
    scored = scored.sort_values("score", ascending=False)
    if config.top_n:
        scored = scored.head(config.top_n)
    return scored.reset_index(drop=True)
