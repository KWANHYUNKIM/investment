"""Portfolio construction — turn a set of tickers + price history into weights.

Schemes:
  equal          — 1/N
  inverse_vol    — proportional to 1 / volatility (risk parity-ish)
  min_variance   — minimise portfolio variance (long-only, fully invested)
  max_sharpe     — maximise Sharpe (mean-variance) (long-only, fully invested)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


def _returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.sort_index().pct_change().dropna(how="all")


def equal_weight(tickers: list[str]) -> pd.Series:
    n = len(tickers)
    if n == 0:
        return pd.Series(dtype=float)
    return pd.Series(1.0 / n, index=tickers)


def inverse_vol(prices: pd.DataFrame) -> pd.Series:
    rets = _returns(prices)
    vol = rets.std(ddof=0)
    vol = vol.replace(0, np.nan).dropna()
    if vol.empty:
        return equal_weight(list(prices.columns))
    inv = 1.0 / vol
    return inv / inv.sum()


def _portfolio_stats(weights: np.ndarray, mean: np.ndarray, cov: np.ndarray):
    ret = float(weights @ mean) * TRADING_DAYS
    vol = float(np.sqrt(weights @ cov @ weights)) * np.sqrt(TRADING_DAYS)
    return ret, vol


def _optimize(prices: pd.DataFrame, objective: str, risk_free: float = 0.0) -> pd.Series:
    rets = _returns(prices).dropna(axis=1, how="any")
    cols = list(rets.columns)
    n = len(cols)
    if n == 0:
        return pd.Series(dtype=float)
    if n == 1:
        return pd.Series([1.0], index=cols)

    mean = rets.mean().values
    cov = rets.cov().values
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    x0 = np.repeat(1.0 / n, n)

    if objective == "min_variance":
        def fun(w):
            return w @ cov @ w
    elif objective == "max_sharpe":
        def fun(w):
            ret, vol = _portfolio_stats(w, mean, cov)
            if vol == 0:
                return 1e6
            return -(ret - risk_free) / vol
    else:
        raise ValueError(f"unknown objective: {objective}")

    res = minimize(fun, x0, method="SLSQP", bounds=bounds, constraints=constraints,
                   options={"maxiter": 500, "ftol": 1e-9})
    w = res.x if res.success else x0
    w = np.clip(w, 0, None)
    w = w / w.sum() if w.sum() > 0 else x0
    return pd.Series(w, index=cols)


def build_weights(
    prices: pd.DataFrame,
    scheme: str = "equal",
    risk_free: float = 0.0,
) -> pd.Series:
    """Return target weights (summing to 1) for the given scheme."""
    tickers = list(prices.columns)
    if scheme == "equal":
        return equal_weight(tickers)
    if scheme == "inverse_vol":
        return inverse_vol(prices)
    if scheme in ("min_variance", "max_sharpe"):
        return _optimize(prices, scheme, risk_free)
    raise ValueError(f"unknown weighting scheme: {scheme}")
