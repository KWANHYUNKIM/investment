"""Backtest engine.

Given a wide price matrix (index=date, columns=ticker) and a weighting scheme,
simulate a portfolio that rebalances on a fixed schedule. Between rebalances
weights *drift* with returns (no look-ahead, no daily rebalancing illusion).
Transaction costs are charged on turnover at each rebalance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.quant import metrics, portfolio

# pandas offset alias per rebalance frequency.
_FREQ = {"D": "D", "W": "W-FRI", "M": "ME", "Q": "QE", "Y": "YE"}


@dataclass
class BacktestConfig:
    scheme: str = "equal"          # equal | inverse_vol | min_variance | max_sharpe
    rebalance: str = "M"           # D | W | M | Q | Y
    cost_bps: float = 10.0         # round-trip cost per unit turnover, in bps
    lookback: int = 252            # trading days of history used to size weights
    risk_free: float = 0.0


def _rebalance_dates(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    if freq == "D":
        return index
    marks = pd.Series(1, index=index).resample(_FREQ[freq]).last().index
    # Snap each period end to the last available trading day on/before it.
    pos = index.searchsorted(marks, side="right") - 1
    pos = pos[(pos >= 0) & (pos < len(index))]
    return index[np.unique(pos)]


def run(prices: pd.DataFrame, config: BacktestConfig) -> dict:
    """Run the backtest. Returns equity curve, daily returns, weights, metrics."""
    prices = prices.sort_index().dropna(how="all")
    if prices.shape[0] < 2 or prices.shape[1] == 0:
        raise ValueError("not enough price history to backtest")

    asset_rets = prices.pct_change().fillna(0.0)
    index = prices.index
    rebal = set(_rebalance_dates(index, config.rebalance))

    tickers = list(prices.columns)
    weights = pd.Series(0.0, index=tickers)
    port_rets = pd.Series(0.0, index=index)
    weight_log: dict[pd.Timestamp, pd.Series] = {}
    first_alloc_done = False

    for i, day in enumerate(index):
        r = asset_rets.iloc[i]

        # Apply yesterday's weights to today's returns, then let them drift.
        if first_alloc_done:
            day_ret = float((weights * r).sum())
            drifted = weights * (1.0 + r)
            s = drifted.sum()
            weights = drifted / s if s > 0 else weights
        else:
            day_ret = 0.0

        # Rebalance at period boundaries (and to make the first allocation).
        if day in rebal or not first_alloc_done:
            hist = prices.iloc[max(0, i - config.lookback + 1): i + 1]
            valid = hist.columns[hist.iloc[-1].notna()]
            target = portfolio.build_weights(
                hist[valid], scheme=config.scheme, risk_free=config.risk_free
            ).reindex(tickers).fillna(0.0)

            turnover = float((target - weights).abs().sum()) if first_alloc_done else 1.0
            day_ret -= turnover * (config.cost_bps / 10_000.0)

            weights = target
            weight_log[day] = weights.copy()
            first_alloc_done = True

        port_rets.iloc[i] = day_ret

    curve = metrics.equity_curve(port_rets)
    weights_df = pd.DataFrame(weight_log).T

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in index],
        "equity_curve": [round(v, 6) for v in curve.tolist()],
        "drawdown": [round(v, 6) for v in metrics.drawdown_series(port_rets).tolist()],
        "daily_returns": [round(v, 8) for v in port_rets.tolist()],
        "metrics": metrics.summary(port_rets, config.risk_free),
        "weights": {
            d.strftime("%Y-%m-%d"): {k: round(v, 4) for k, v in row.items() if v > 1e-6}
            for d, row in weights_df.iterrows()
        },
        "rebalance_count": len(weight_log),
    }


def with_benchmark(prices: pd.DataFrame, benchmark: pd.Series, config: BacktestConfig) -> dict:
    """Run a backtest and append a buy-and-hold benchmark equity curve."""
    result = run(prices, config)
    bench_rets = benchmark.reindex(pd.to_datetime(result["dates"])).pct_change().fillna(0.0)
    result["benchmark"] = {
        "equity_curve": [round(v, 6) for v in metrics.equity_curve(bench_rets).tolist()],
        "metrics": metrics.summary(bench_rets, config.risk_free),
    }
    return result
