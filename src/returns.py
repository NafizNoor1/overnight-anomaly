"""Return decomposition and summary statistics.

Definitions:
    overnight return = today's open / yesterday's close - 1
    intraday return  = today's close / today's open - 1

The two legs compound to the full close-to-close daily return:
    (1 + overnight) * (1 + intraday) = 1 + daily
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def decompose(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Split each day's total return into overnight and intraday legs."""
    prev_close = ohlc["Close"].shift(1)
    out = pd.DataFrame(index=ohlc.index)
    out["overnight"] = ohlc["Open"] / prev_close - 1
    out["intraday"] = ohlc["Close"] / ohlc["Open"] - 1
    out["daily"] = ohlc["Close"] / prev_close - 1
    return out.dropna()


def ann_return(r: pd.Series) -> float:
    """Geometric annualised return (CAGR) of a daily return series."""
    years = len(r) / TRADING_DAYS
    return (1 + r).prod() ** (1 / years) - 1


def ann_vol(r: pd.Series) -> float:
    return r.std() * np.sqrt(TRADING_DAYS)


def sharpe(r: pd.Series) -> float:
    """Annualised Sharpe ratio with the risk-free rate taken as zero."""
    return r.mean() / r.std() * np.sqrt(TRADING_DAYS)


def summary_table(returns: pd.DataFrame) -> pd.DataFrame:
    """One row of annualised stats per column of daily returns."""
    rows = {}
    for col in returns.columns:
        r = returns[col]
        rows[col] = {
            "ann_return_%": 100 * ann_return(r),
            "ann_vol_%": 100 * ann_vol(r),
            "sharpe": sharpe(r),
        }
    return pd.DataFrame(rows).T.round(2)


def wealth_curve(r: pd.Series) -> pd.Series:
    """Growth of £1 invested in this leg only."""
    return (1 + r).cumprod()
