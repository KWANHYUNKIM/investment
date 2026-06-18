"""DuckDB-backed market data store.

All time series live in a single DuckDB file (configurable via DATA_DIR).
DuckDB gives us columnar, analytics-friendly storage that is great for the
kind of wide time-series scans backtesting needs, while staying a single
file with zero server to run.

Three tables:
  securities    — one row per instrument (ticker, name, market, sector)
  prices        — daily OHLCV, long format
  fundamentals  — periodic fundamental snapshots (PER/PBR/ROE/market cap/...)
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator, Sequence

import duckdb
import numpy as np
import pandas as pd

from app.core.config import get_settings

# DuckDB connections are not thread-safe to share across threads; we serialize
# access with a lock and use a single process-wide connection. For heavier
# concurrency you would move to a connection pool or Postgres.
_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS securities (
    market   VARCHAR NOT NULL,        -- 'KR' | 'US'
    ticker   VARCHAR NOT NULL,
    name     VARCHAR,
    sector   VARCHAR,
    PRIMARY KEY (market, ticker)
);

CREATE TABLE IF NOT EXISTS prices (
    market   VARCHAR NOT NULL,
    ticker   VARCHAR NOT NULL,
    date     DATE    NOT NULL,
    open     DOUBLE,
    high     DOUBLE,
    low      DOUBLE,
    close    DOUBLE,
    volume   DOUBLE,
    PRIMARY KEY (market, ticker, date)
);

CREATE TABLE IF NOT EXISTS fundamentals (
    market      VARCHAR NOT NULL,
    ticker      VARCHAR NOT NULL,
    date        DATE    NOT NULL,
    per         DOUBLE,
    pbr         DOUBLE,
    pcr         DOUBLE,
    psr         DOUBLE,
    eps         DOUBLE,
    bps         DOUBLE,
    roe         DOUBLE,
    div_yield   DOUBLE,
    market_cap  DOUBLE,
    foreign_ratio DOUBLE,
    PRIMARY KEY (market, ticker, date)
);

CREATE TABLE IF NOT EXISTS investor_flow (
    market      VARCHAR NOT NULL,
    ticker      VARCHAR NOT NULL,
    date        DATE    NOT NULL,
    individual  DOUBLE,        -- net-buy quantity (shares)
    foreigner   DOUBLE,        -- 'foreign' is a SQL reserved word
    organ       DOUBLE,
    foreign_ratio DOUBLE,
    PRIMARY KEY (market, ticker, date)
);

CREATE TABLE IF NOT EXISTS company_profile (
    market         VARCHAR NOT NULL,
    ticker         VARCHAR NOT NULL,
    name           VARCHAR,
    industry       VARCHAR,        -- KSIC industry (사업자등록 표준산업분류)
    wics_sector    VARCHAR,        -- WICS 업종 (네이버 금융 = 증권사 표준, 그룹핑 기준)
    products       VARCHAR,        -- 주요 제품/사업
    region         VARCHAR,
    representative VARCHAR,
    homepage       VARCHAR,
    listing_date   VARCHAR,
    market_cap     DOUBLE,
    PRIMARY KEY (market, ticker)
);

CREATE TABLE IF NOT EXISTS financials (
    market      VARCHAR NOT NULL,
    ticker      VARCHAR NOT NULL,
    period      VARCHAR NOT NULL,   -- 사업연도 'YYYY/MM'
    sales       DOUBLE,             -- 매출액 (억원)
    op_profit   DOUBLE,             -- 영업이익 (억원)
    net_income  DOUBLE,             -- 당기순이익 (억원)
    op_margin   DOUBLE,             -- 영업이익률 (%)
    PRIMARY KEY (market, ticker, period)
);

-- 해외 종목 펀더멘털(Finnhub) — 글로벌 경쟁지도용. 시총은 USD 환산, 마진은 %.
CREATE TABLE IF NOT EXISTS foreign_fin (
    symbol         VARCHAR NOT NULL,
    name           VARCHAR,
    country        VARCHAR,
    exchange       VARCHAR,
    currency       VARCHAR,
    industry       VARCHAR,
    market_cap_usd DOUBLE,            -- 시가총액 (USD)
    revenue_usd    DOUBLE,            -- 매출액 (USD, TTM)
    op_profit_usd  DOUBLE,            -- 영업이익 (USD, 추정=매출×영업이익률)
    net_income_usd DOUBLE,            -- 순이익 (USD, 추정=매출×순이익률)
    op_margin      DOUBLE,            -- 영업이익률 (%)
    net_margin     DOUBLE,            -- 순이익률 (%)
    gross_margin   DOUBLE,            -- 매출총이익률 (%)
    roe            DOUBLE,            -- 자기자본이익률 (%)
    debt_equity    DOUBLE,            -- 부채비율(총부채/자기자본, 배)
    pe             DOUBLE,            -- PER
    pb             DOUBLE,            -- PBR
    div_yield      DOUBLE,            -- 배당수익률 (%)
    price          DOUBLE,            -- 현재가 (현지통화)
    change_pct     DOUBLE,            -- 당일 등락률 (%)
    updated        VARCHAR,
    PRIMARY KEY (symbol)
);

-- DART 전자공시 전체 재무제표(전 계정·연도별). 회계 원장 그대로 — 재무상태표(BS)/
-- 손익계산서(IS·CIS)/현금흐름표(CF)의 모든 계정을 long-format으로 적재. 금액은 원(KRW).
CREATE TABLE IF NOT EXISTS dart_financials (
    ticker      VARCHAR NOT NULL,
    sj_div      VARCHAR NOT NULL,   -- BS/IS/CIS/CF/SCE
    year        INTEGER NOT NULL,   -- 사업연도(YYYY)
    account_nm  VARCHAR NOT NULL,   -- 계정명 (자산총계·부채총계·매출액·영업이익 …)
    account_id  VARCHAR,            -- DART 표준계정ID (없으면 '-')
    ord         INTEGER,            -- 보고서 내 표시 순서
    fs_div      VARCHAR,            -- CFS(연결)/OFS(별도)
    amount      DOUBLE,             -- 금액 (원)
    PRIMARY KEY (ticker, sj_div, year, account_nm)
);
"""


def _connect() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    conn = duckdb.connect(str(settings.duckdb_path))
    conn.execute(_SCHEMA)
    # Backfill wics_sector on DBs created before the WICS grouping landed.
    try:
        conn.execute("ALTER TABLE company_profile ADD COLUMN IF NOT EXISTS wics_sector VARCHAR")
    except Exception:
        pass
    # Backfill the deep foreign-fundamentals columns (report-grade comparison).
    for col in ("revenue_usd", "op_profit_usd", "net_income_usd", "gross_margin",
                "roe", "debt_equity", "pe", "pb", "div_yield"):
        try:
            conn.execute(f"ALTER TABLE foreign_fin ADD COLUMN IF NOT EXISTS {col} DOUBLE")
        except Exception:
            pass
    return conn


@contextmanager
def connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Yield the shared connection under a lock."""
    global _conn
    with _lock:
        if _conn is None:
            _conn = _connect()
        yield _conn


def init_db() -> None:
    with connection() as conn:
        conn.execute(_SCHEMA)
        # Backfill column on pre-existing DBs created before foreign_ratio existed.
        try:
            conn.execute("ALTER TABLE fundamentals ADD COLUMN IF NOT EXISTS foreign_ratio DOUBLE")
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Writes (upsert semantics)
# --------------------------------------------------------------------------- #
def _upsert(table: str, df: pd.DataFrame, keys: Sequence[str]) -> int:
    if df.empty:
        return 0
    with connection() as conn:
        conn.register("_incoming", df)
        cols = list(df.columns)
        col_list = ", ".join(cols)
        # DuckDB upsert: delete colliding keys, then insert.
        key_match = " AND ".join(f"t.{k} = s.{k}" for k in keys)
        conn.execute(
            f"DELETE FROM {table} t USING _incoming s WHERE {key_match}"
        )
        conn.execute(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM _incoming")
        conn.unregister("_incoming")
        return len(df)


def upsert_securities(df: pd.DataFrame) -> int:
    return _upsert("securities", df, ["market", "ticker"])


def upsert_prices(df: pd.DataFrame) -> int:
    return _upsert("prices", df, ["market", "ticker", "date"])


def upsert_fundamentals(df: pd.DataFrame) -> int:
    return _upsert("fundamentals", df, ["market", "ticker", "date"])


# Fields whose change makes a snapshot "new" worth storing.
_FUND_FIELDS = ["per", "pbr", "pcr", "psr", "eps", "bps", "roe", "div_yield", "market_cap", "foreign_ratio"]


def _changed(a, b) -> bool:
    """True if two numeric snapshot values differ (NaN-aware, small tolerance)."""
    an = a is None or (isinstance(a, float) and a != a)
    bn = b is None or (isinstance(b, float) and b != b)
    if an and bn:
        return False
    if an or bn:
        return True
    try:
        return abs(float(a) - float(b)) > 1e-9
    except (TypeError, ValueError):
        return a != b


def upsert_fundamentals_if_changed(df: pd.DataFrame) -> int:
    """Insert a snapshot row only when it differs from the ticker's latest stored
    one — so duplicates are skipped and only real changes accumulate over time."""
    if df.empty:
        return 0
    keep = []
    with connection() as conn:
        for _, row in df.iterrows():
            latest = conn.execute(
                "SELECT * FROM fundamentals WHERE market = ? AND ticker = ? ORDER BY date DESC LIMIT 1",
                [row["market"], row["ticker"]],
            ).df()
            if latest.empty:
                keep.append(row)
                continue
            prev = latest.iloc[0]
            if any(_changed(row.get(f), prev.get(f)) for f in _FUND_FIELDS if f in df.columns):
                keep.append(row)
    if not keep:
        return 0
    return upsert_fundamentals(pd.DataFrame(keep))


def fundamentals_history(ticker: str, market: str = "KR") -> pd.DataFrame:
    """All stored fundamental snapshots for a ticker (oldest→newest)."""
    with connection() as conn:
        return conn.execute(
            "SELECT * FROM fundamentals WHERE market = ? AND ticker = ? ORDER BY date",
            [market, ticker],
        ).df()


def fundamentals_latest_map() -> dict[str, dict]:
    """ticker -> latest {per, pbr, roe, div_yield, eps, bps} (글로벌 비교 KR 보강용)."""
    with connection() as conn:
        df = conn.execute(
            """
            WITH ranked AS (
                SELECT ticker, per, pbr, roe, div_yield, eps, bps,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
                FROM fundamentals
            )
            SELECT ticker, per, pbr, roe, div_yield, eps, bps FROM ranked WHERE rn = 1
            """
        ).df()
    return {r["ticker"]: r for r in df.to_dict("records")}


def upsert_investor_flow(df: pd.DataFrame) -> int:
    """Accumulate daily investor net-buy (dedup by date → new days pile up,
    existing days refresh). Builds long-term history beyond Naver's ~10-day window."""
    return _upsert("investor_flow", df, ["market", "ticker", "date"])


def investor_flow_history(ticker: str, market: str = "KR", days: int = 60) -> pd.DataFrame:
    """Most recent accumulated investor-flow rows for a ticker (newest→oldest)."""
    with connection() as conn:
        return conn.execute(
            "SELECT date, individual, foreigner, organ, foreign_ratio "
            "FROM investor_flow WHERE market = ? AND ticker = ? ORDER BY date DESC LIMIT ?",
            [market, ticker, days],
        ).df()


def latest_investor_flow_map(market: str = "KR") -> dict[str, dict]:
    """One entry per ticker with its two most recent investor-flow rows.

    Feeds the daily archive's *bulk* layer: every ticker that has accumulated
    flow gets a signal-based "왜 샀나/팔았나" without a per-ticker live fetch.
    Returns ``{ticker: {individual, foreigner, organ, foreign_ratio,
    foreign_ratio_prev}}``.
    """
    with connection() as conn:
        df = conn.execute(
            """
            WITH r AS (
                SELECT ticker, date, individual, foreigner, organ, foreign_ratio,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) rn
                FROM investor_flow WHERE market = ?
            )
            SELECT l.ticker, l.individual, l.foreigner, l.organ, l.foreign_ratio,
                   p.foreign_ratio AS foreign_ratio_prev
            FROM (SELECT * FROM r WHERE rn = 1) l
            LEFT JOIN (SELECT ticker, foreign_ratio FROM r WHERE rn = 2) p
              ON p.ticker = l.ticker
            """,
            [market],
        ).df()
    out: dict[str, dict] = {}
    for rec in df.to_dict("records"):
        out[rec["ticker"]] = rec
    return out


def upsert_company_profile(df: pd.DataFrame) -> int:
    """Replace the company industry/products profile (from KRX-DESC + marcap)."""
    return _upsert("company_profile", df, ["market", "ticker"])


def company_profiles() -> pd.DataFrame:
    """All stored company profiles (industry / products / marcap)."""
    with connection() as conn:
        return conn.execute("SELECT * FROM company_profile").df()


def company_profile_count() -> int:
    with connection() as conn:
        v = conn.execute("SELECT COUNT(*) FROM company_profile").fetchone()
    return int(v[0]) if v else 0


def upsert_financials(df: pd.DataFrame) -> int:
    """Upsert 기업실적분석 rows (one per ticker × 사업연도)."""
    return _upsert("financials", df, ["market", "ticker", "period"])


def financials_count() -> int:
    with connection() as conn:
        v = conn.execute("SELECT COUNT(DISTINCT ticker) FROM financials").fetchone()
    return int(v[0]) if v else 0


def financials_series(ticker: str) -> pd.DataFrame:
    """All stored 사업연도 rows for one ticker, oldest→newest."""
    with connection() as conn:
        return conn.execute(
            "SELECT period, sales, op_profit, net_income, op_margin "
            "FROM financials WHERE ticker = ? ORDER BY period",
            [ticker],
        ).df()


def upsert_foreign_fin(df: pd.DataFrame) -> int:
    """Upsert 해외 종목 펀더멘털(Finnhub)."""
    return _upsert("foreign_fin", df, ["symbol"])


def foreign_fin_map() -> dict[str, dict]:
    """symbol -> {name, country, market_cap_usd, op_margin, ...} (글로벌 클러스터용)."""
    with connection() as conn:
        df = conn.execute("SELECT * FROM foreign_fin").df()
    return {r["symbol"]: r for r in df.to_dict("records")}


def foreign_fin_count() -> int:
    with connection() as conn:
        v = conn.execute("SELECT COUNT(*) FROM foreign_fin").fetchone()
    return int(v[0]) if v else 0


def upsert_dart_financials(df: pd.DataFrame) -> int:
    """Upsert DART 전 계정 재무제표 rows (long-format)."""
    return _upsert("dart_financials", df, ["ticker", "sj_div", "year", "account_nm"])


def dart_financials_count() -> int:
    with connection() as conn:
        v = conn.execute("SELECT COUNT(DISTINCT ticker) FROM dart_financials").fetchone()
    return int(v[0]) if v else 0


def dart_financials_tickers() -> set[str]:
    """Tickers that already have DART statements stored (scheduler skip-set)."""
    with connection() as conn:
        rows = conn.execute("SELECT DISTINCT ticker FROM dart_financials").fetchall()
    return {r[0] for r in rows}


def dart_financials(ticker: str) -> pd.DataFrame:
    """All stored DART accounts for one ticker (statement, year, account, amount)."""
    with connection() as conn:
        return conn.execute(
            "SELECT sj_div, year, account_nm, account_id, ord, fs_div, amount "
            "FROM dart_financials WHERE ticker = ? ORDER BY sj_div, ord, account_nm, year",
            [ticker],
        ).df()


def dart_latest_bs_map() -> dict[str, dict]:
    """ticker -> 최신연도 {자산총계, 부채총계, 자본총계} (KR 부채비율 계산용, 원)."""
    with connection() as conn:
        df = conn.execute(
            """
            WITH bs AS (
                SELECT ticker, account_nm, amount,
                       ROW_NUMBER() OVER (PARTITION BY ticker, account_nm ORDER BY year DESC) AS rn
                FROM dart_financials
                WHERE sj_div = 'BS' AND account_nm IN ('자산총계', '부채총계', '자본총계')
            )
            SELECT ticker, account_nm, amount FROM bs WHERE rn = 1
            """
        ).df()
    out: dict[str, dict] = {}
    for r in df.to_dict("records"):
        out.setdefault(r["ticker"], {})[r["account_nm"]] = r["amount"]
    return out


def financials_latest() -> pd.DataFrame:
    """Per ticker: most recent 사업연도 figures + YoY 영업이익 증감률 (prior year)."""
    with connection() as conn:
        return conn.execute(
            """
            WITH ranked AS (
                SELECT ticker, period, sales, op_profit, net_income, op_margin,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY period DESC) AS rn
                FROM financials
            ),
            cur AS (SELECT * FROM ranked WHERE rn = 1),
            prev AS (SELECT ticker, op_profit AS prev_op FROM ranked WHERE rn = 2)
            SELECT cur.ticker, cur.period, cur.sales, cur.op_profit,
                   cur.net_income, cur.op_margin,
                   CASE WHEN prev.prev_op IS NOT NULL AND prev.prev_op <> 0
                        THEN round((cur.op_profit - prev.prev_op) / abs(prev.prev_op) * 100, 1)
                        END AS op_yoy
            FROM cur LEFT JOIN prev USING (ticker)
            """
        ).df()


def max_price_date(market: str | None = None) -> str | None:
    """Latest date present in the price series (cheap scheduler check)."""
    where, params = "", []
    if market:
        where, params = "WHERE market = ?", [market]
    with connection() as conn:
        v = conn.execute(f"SELECT MAX(date) FROM prices {where}", params).fetchone()
    return str(v[0])[:10] if v and v[0] is not None else None


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def list_securities(market: str | None = None) -> pd.DataFrame:
    with connection() as conn:
        if market:
            return conn.execute(
                "SELECT * FROM securities WHERE market = ? ORDER BY ticker", [market]
            ).df()
        return conn.execute("SELECT * FROM securities ORDER BY market, ticker").df()


def load_prices(
    tickers: Sequence[str] | None = None,
    market: str | None = None,
    start: str | None = None,
    end: str | None = None,
    field: str = "close",
) -> pd.DataFrame:
    """Return a *wide* price matrix: index=date, columns=ticker, values=field.

    This is the shape the backtester and metrics expect.
    """
    where = []
    params: list = []
    if market:
        where.append("market = ?")
        params.append(market)
    if tickers:
        placeholders = ", ".join(["?"] * len(tickers))
        where.append(f"ticker IN ({placeholders})")
        params.extend(tickers)
    if start:
        where.append("date >= CAST(? AS DATE)")
        params.append(start)
    if end:
        where.append("date <= CAST(? AS DATE)")
        params.append(end)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn:
        long_df = conn.execute(
            f"SELECT date, ticker, {field} AS value FROM prices {clause} ORDER BY date",
            params,
        ).df()

    if long_df.empty:
        return pd.DataFrame()
    wide = long_df.pivot(index="date", columns="ticker", values="value")
    wide.index = pd.to_datetime(wide.index)
    return wide.sort_index()


def latest_fundamentals(market: str | None = None, on: str | None = None) -> pd.DataFrame:
    """Most recent fundamental row per ticker (optionally as-of a date)."""
    where = []
    params: list = []
    if market:
        where.append("market = ?")
        params.append(market)
    if on:
        where.append("date <= CAST(? AS DATE)")
        params.append(on)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn:
        return conn.execute(
            f"""
            SELECT f.*
            FROM fundamentals f
            JOIN (
                SELECT market, ticker, MAX(date) AS mx
                FROM fundamentals {clause}
                GROUP BY market, ticker
            ) m ON f.market = m.market AND f.ticker = m.ticker AND f.date = m.mx
            """,
            params,
        ).df()


def screening_table(market: str | None = None, on: str | None = None) -> pd.DataFrame:
    """Fundamentals joined with security names — the screener's input."""
    fund = latest_fundamentals(market=market, on=on)
    if fund.empty:
        return fund
    secs = list_securities(market=market)[["market", "ticker", "name", "sector"]]
    return fund.merge(secs, on=["market", "ticker"], how="left")


def coverage() -> pd.DataFrame:
    """Quick summary of what data we hold — handy for the dashboard."""
    with connection() as conn:
        return conn.execute(
            """
            SELECT market,
                   COUNT(DISTINCT ticker)            AS tickers,
                   MIN(date)                         AS first_date,
                   MAX(date)                         AS last_date,
                   COUNT(*)                          AS rows
            FROM prices
            GROUP BY market
            ORDER BY market
            """
        ).df()


def latest_quotes(market: str | None = None) -> pd.DataFrame:
    """One row per ticker with its most recent close plus reference closes.

    Powers the brokerage-style market list: last price, day-over-day change,
    and an ~1-month change (≈21 trading days back).
    """
    params: list = []
    mkt_clause = ""
    if market:
        mkt_clause = "AND market = ?"
        params.append(market)
    with connection() as conn:
        return conn.execute(
            f"""
            WITH r AS (
                SELECT ticker, date, close, volume,
                       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) rn
                FROM prices
                WHERE 1=1 {mkt_clause}
            )
            SELECT s.ticker            AS ticker,
                   s.name              AS name,
                   s.sector            AS sector,
                   l.date              AS date,
                   l.close             AS close,
                   l.volume            AS volume,
                   p.close             AS prev_close,
                   m.close             AS close_1m
            FROM (SELECT * FROM r WHERE rn = 1) l
            JOIN securities s ON s.ticker = l.ticker
            LEFT JOIN (SELECT ticker, close FROM r WHERE rn = 2)  p ON p.ticker = l.ticker
            LEFT JOIN (SELECT ticker, close FROM r WHERE rn = 22) m ON m.ticker = l.ticker
            ORDER BY l.volume DESC NULLS LAST
            """,
            params,
        ).df()


_screen_cache: tuple[float, list[dict]] | None = None
_SCREEN_TTL = 300.0  # refresh so the background fundamentals crawler surfaces


def _r2(v) -> float | None:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 2)


def screen_table_prices() -> list[dict]:
    """Spreadsheet-style table of price-derived factors for every ticker.

    Fundamentals are unavailable (pykrx broken), so this computes everything we
    honestly can from the price series: multi-horizon returns, annualised
    volatility, YTD, and distance from the 52-week high. Cached (data is static).
    """
    global _screen_cache
    if _screen_cache is not None and (time.time() - _screen_cache[0] < _SCREEN_TTL):
        return _screen_cache[1]

    with connection() as conn:
        df = conn.execute(
            "SELECT ticker, date, close, volume FROM prices ORDER BY ticker, date"
        ).df()
        secs = conn.execute("SELECT ticker, name, sector FROM securities").df()

    names = dict(zip(secs["ticker"], secs["name"]))
    sectors = dict(zip(secs["ticker"], secs["sector"]))

    fund = latest_fundamentals(market="KR")
    fmap = {row["ticker"]: row for _, row in fund.iterrows()} if not fund.empty else {}

    last_date = pd.Timestamp(df["date"].max())
    ytd_cut = pd.Timestamp(year=last_date.year, month=1, day=1)

    out: list[dict] = []
    for tk, sub in df.groupby("ticker", sort=False):
        c = sub["close"].to_numpy(dtype="float64")
        v = sub["volume"].to_numpy(dtype="float64")
        d = pd.to_datetime(sub["date"].to_numpy())
        n = len(c)
        if n < 2 or c[-1] <= 0:
            continue
        last = c[-1]

        def ret(k: int):
            return ((last / c[-1 - k] - 1.0) * 100.0) if (n > k and c[-1 - k] > 0) else None

        win = c[-252:]
        dr = np.diff(win) / win[:-1]
        vol = float(np.std(dr) * np.sqrt(252) * 100.0) if len(dr) > 5 else None

        ytd = None
        mask = d >= ytd_cut
        if mask.any():
            base = c[int(np.argmax(mask))]
            if base > 0:
                ytd = (last / base - 1.0) * 100.0

        hi = float(np.max(win))
        fd = fmap.get(tk)
        out.append(
            {
                "ticker": tk,
                "name": names.get(tk),
                "sector": sectors.get(tk),
                "date": pd.Timestamp(d[-1]).strftime("%Y-%m-%d"),
                "close": _r2(last),
                "change": _r2(last - c[-2]),
                "change_pct": _r2(ret(1)),
                "ret_1w": _r2(ret(5)),
                "ret_1m": _r2(ret(21)),
                "ret_3m": _r2(ret(63)),
                "ret_6m": _r2(ret(126)),
                "ret_12m": _r2(ret(252)),
                "ret_ytd": _r2(ytd),
                "vol": _r2(vol),
                "pct_from_high": _r2((last / hi - 1.0) * 100.0) if hi > 0 else None,
                "volume": _r2(v[-1]) if len(v) else None,
                "per": _r2(fd["per"]) if fd is not None else None,
                "pbr": _r2(fd["pbr"]) if fd is not None else None,
                "eps": _r2(fd["eps"]) if fd is not None else None,
                "bps": _r2(fd["bps"]) if fd is not None else None,
                "roe": _r2(fd["roe"]) if fd is not None else None,
                "div_yield": _r2(fd["div_yield"]) if fd is not None else None,
                "foreign_ratio": _r2(fd["foreign_ratio"]) if fd is not None else None,
                "market_cap": _r2(fd["market_cap"]) if fd is not None else None,
            }
        )

    _screen_cache = (time.time(), out)
    return out


def ohlc(ticker: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Full OHLCV history for one ticker — feeds the candlestick chart."""
    where = ["ticker = ?"]
    params: list = [ticker]
    if start:
        where.append("date >= CAST(? AS DATE)")
        params.append(start)
    if end:
        where.append("date <= CAST(? AS DATE)")
        params.append(end)
    clause = "WHERE " + " AND ".join(where)
    with connection() as conn:
        return conn.execute(
            f"SELECT date, open, high, low, close, volume FROM prices {clause} ORDER BY date",
            params,
        ).df()
