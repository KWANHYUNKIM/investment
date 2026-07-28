"""Performance / risk metrics computed from a daily return series."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def equity_curve(returns: pd.Series, start_value: float = 1.0) -> pd.Series:
    """Cumulative growth of 1 unit from a series of period returns."""
    return start_value * (1.0 + returns.fillna(0)).cumprod()


def cagr(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    curve = (1.0 + returns.fillna(0)).cumprod()
    if curve.empty:
        return 0.0
    total_growth = curve.iloc[-1]
    years = len(returns) / periods_per_year
    if years <= 0 or total_growth <= 0:
        return 0.0
    return total_growth ** (1.0 / years) - 1.0


def annual_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    return float(returns.std(ddof=0) * np.sqrt(periods_per_year))


def sharpe(returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS) -> float:
    excess = returns - risk_free / periods_per_year
    sd = excess.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(excess.mean() / sd * np.sqrt(periods_per_year))


def sortino(returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS) -> float:
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    dd = downside.std(ddof=0)
    if dd == 0 or np.isnan(dd):
        return 0.0
    return float(excess.mean() / dd * np.sqrt(periods_per_year))


def drawdown_series(returns: pd.Series) -> pd.Series:
    curve = (1.0 + returns.fillna(0)).cumprod()
    peak = curve.cummax()
    return curve / peak - 1.0


def max_drawdown(returns: pd.Series) -> float:
    dd = drawdown_series(returns)
    return float(dd.min()) if not dd.empty else 0.0


def calmar(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    mdd = abs(max_drawdown(returns))
    if mdd == 0:
        return 0.0
    return cagr(returns, periods_per_year) / mdd


def win_rate(returns: pd.Series) -> float:
    r = returns.dropna()
    if r.empty:
        return 0.0
    return float((r > 0).mean())


def summary(returns: pd.Series, risk_free: float = 0.0, periods_per_year: int = TRADING_DAYS) -> dict:
    """All headline metrics in one dict (rounded, JSON-friendly)."""
    r = returns.dropna()
    if r.empty:
        return {k: 0.0 for k in
                ("cagr", "volatility", "sharpe", "sortino", "max_drawdown",
                 "calmar", "win_rate", "total_return")}
    total = float((1.0 + r).prod() - 1.0)
    return {
        "cagr": round(cagr(r, periods_per_year), 4),
        "volatility": round(annual_volatility(r, periods_per_year), 4),
        "sharpe": round(sharpe(r, risk_free, periods_per_year), 4),
        "sortino": round(sortino(r, risk_free, periods_per_year), 4),
        "max_drawdown": round(max_drawdown(r), 4),
        "calmar": round(calmar(r, periods_per_year), 4),
        "win_rate": round(win_rate(r), 4),
        "total_return": round(total, 4),
    }
