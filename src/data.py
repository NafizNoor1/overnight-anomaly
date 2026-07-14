"""Download and cache daily OHLC data from Yahoo Finance.

Everything uses auto_adjust=True so that dividends and splits are folded
into the open, high, low and close consistently. This matters: dividends
land in the overnight gap, so mixing an adjusted close with an unadjusted
open would corrupt the overnight/intraday decomposition.
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def fetch_ohlc(ticker: str, start: str = "1993-01-01") -> pd.DataFrame:
    """Return daily adjusted OHLC for one ticker, cached locally as CSV."""
    DATA_DIR.mkdir(exist_ok=True)
    cache = DATA_DIR / f"{ticker}.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)

    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {ticker}")

    # yfinance returns MultiIndex columns even for a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Open", "Close"])
    df.index.name = "Date"
    df.to_csv(cache)
    return df
