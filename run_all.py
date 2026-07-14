"""Run the whole overnight-anomaly analysis end to end.

Usage:
    python run_all.py

Downloads daily OHLC via yfinance (cached in data/), then writes every
figure to figures/ and every table to results/.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data import fetch_ohlc
from src.plots import plot_asset_bars, plot_cost_sweep, plot_wealth_curves
from src.returns import TRADING_DAYS, ann_return, decompose, sharpe, summary_table

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
REFERENCE = ROOT / "reference"

ASSETS = ["SPY", "QQQ", "AAPL", "MSFT", "JPM", "GLD"]

SUB_PERIODS = {
    "1993-2009": (None, "2009-12-31"),
    "2010-2026": ("2010-01-01", None),
    "2020 crash (19 Feb - 30 Apr)": ("2020-02-19", "2020-04-30"),
    "2022": ("2022-01-01", "2022-12-31"),
}


def save_table(df: pd.DataFrame, name: str) -> None:
    RESULTS.mkdir(exist_ok=True)
    df.to_csv(RESULTS / name)
    print(f"\n--- {name} ---")
    print(df.to_string())


def leg_stats(returns: pd.DataFrame) -> dict:
    """Annualised return and Sharpe for both legs of one returns frame."""
    return {
        "overnight_ann_%": round(100 * ann_return(returns["overnight"]), 2),
        "overnight_sharpe": round(sharpe(returns["overnight"]), 2),
        "intraday_ann_%": round(100 * ann_return(returns["intraday"]), 2),
        "intraday_sharpe": round(sharpe(returns["intraday"]), 2),
        "n_days": len(returns),
    }


def stage1_replicate(spy_returns: pd.DataFrame) -> pd.DataFrame:
    """Decompose SPY and draw the three-curve wealth chart."""
    start = spy_returns.index[0].year
    end = spy_returns.index[-1].year
    plot_wealth_curves(
        spy_returns,
        f"SPY {start}-{end}: overnight vs intraday vs buy-and-hold",
        "spy_wealth_curves.png",
    )
    table = summary_table(spy_returns)
    save_table(table, "stage1_summary.csv")

    # Data-quality check: a stale open (open printed equal to the previous
    # close) shows up as an overnight return of exactly zero.
    zero_overnight = spy_returns["overnight"].abs() < 1e-6
    by_decade = zero_overnight.groupby(spy_returns.index.year // 10 * 10).mean()
    quality = pd.DataFrame({"share_zero_overnight_%": (100 * by_decade).round(2)})
    quality.index = [f"{d}s" for d in quality.index]
    save_table(quality, "stage1_data_quality.csv")
    return table


def stage2_stress_test(spy_returns: pd.DataFrame) -> pd.DataFrame:
    """Sub-periods for SPY, then the same decomposition on other assets."""
    sub = {}
    for label, (start, end) in SUB_PERIODS.items():
        sub[label] = leg_stats(spy_returns.loc[start:end])
    save_table(pd.DataFrame(sub).T, "stage2_subperiods.csv")

    assets = {}
    for ticker in ASSETS:
        returns = decompose(fetch_ohlc(ticker))
        stats = leg_stats(returns)
        stats = {"from": str(returns.index[0].date()), **stats}
        assets[ticker] = stats
    asset_table = pd.DataFrame(assets).T
    save_table(asset_table, "stage2_assets.csv")
    plot_asset_bars(asset_table, "asset_decomposition.png")
    return asset_table


def stage3_costs(spy_returns: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Trade the overnight leg (buy close, sell open) net of round-trip costs.

    One round trip per day, so a cost of c bps knocks c/10000 off every
    day's overnight return -- roughly 2.52% a year per bp of cost.
    """
    overnight = spy_returns["overnight"]
    breakeven_bps = overnight.mean() * 1e4  # cost that sets the mean net return to zero

    rows = []
    for cost_bps in np.arange(0, 5.5, 0.5):
        net = overnight - cost_bps / 1e4
        rows.append({
            "cost_bps": cost_bps,
            "net_ann_return_%": round(100 * ann_return(net), 2),
            "net_sharpe": round(sharpe(net), 2),
        })
    sweep = pd.DataFrame(rows)
    save_table(sweep.set_index("cost_bps"), "stage3_cost_sweep.csv")
    plot_cost_sweep(sweep, breakeven_bps, "net_sharpe_vs_cost.png")
    print(f"\nBreakeven round-trip cost: {breakeven_bps:.2f} bps")
    return sweep, breakeven_bps


def stage4_conditionals(spy_returns: pd.DataFrame) -> None:
    """Two cheap conditionals: after big moves, and around FOMC days."""
    # (a) Tonight's overnight return, bucketed by today's full-day return
    prev_day = spy_returns["daily"].shift(1)
    bins = [-np.inf, -0.02, -0.01, 0, 0.01, 0.02, np.inf]
    labels = ["< -2%", "-2% to -1%", "-1% to 0%", "0% to 1%", "1% to 2%", "> 2%"]
    bucket = pd.cut(prev_day, bins=bins, labels=labels)

    grouped = spy_returns["overnight"].groupby(bucket, observed=True)
    prevday = pd.DataFrame({
        "mean_overnight_bps": (1e4 * grouped.mean()).round(2),
        "t_stat": (grouped.mean() / (grouped.std() / np.sqrt(grouped.count()))).round(2),
        "n_days": grouped.count(),
    })
    save_table(prevday, "stage4_prevday.csv")

    # (b) FOMC announcement days (scheduled meetings only; see reference/)
    fomc_file = REFERENCE / "fomc_dates.csv"
    if not fomc_file.exists():
        print("\nreference/fomc_dates.csv not found -- skipping the FOMC split.")
        return
    fomc = pd.to_datetime(pd.read_csv(fomc_file)["date"])
    on_fomc = spy_returns.index.isin(fomc)
    day_after = spy_returns.index.isin(fomc + pd.offsets.BDay(1))

    groups = {
        "FOMC announcement day": spy_returns[on_fomc],
        "day after FOMC": spy_returns[day_after & ~on_fomc],
        "all other days": spy_returns[~on_fomc & ~day_after],
    }
    fomc_table = pd.DataFrame({
        label: {
            "mean_overnight_bps": round(1e4 * r["overnight"].mean(), 2),
            "mean_intraday_bps": round(1e4 * r["intraday"].mean(), 2),
            "n_days": len(r),
        }
        for label, r in groups.items()
    }).T
    save_table(fomc_table, "stage4_fomc.csv")


def main() -> None:
    spy_returns = decompose(fetch_ohlc("SPY"))

    table = stage1_replicate(spy_returns)
    stage2_stress_test(spy_returns)
    sweep, breakeven_bps = stage3_costs(spy_returns)
    stage4_conditionals(spy_returns)

    # Headline numbers in one place, mostly for the write-up
    key = {
        "sample": f"{spy_returns.index[0].date()} to {spy_returns.index[-1].date()}",
        "n_days": len(spy_returns),
        "overnight_ann_return_%": table.loc["overnight", "ann_return_%"],
        "overnight_sharpe": table.loc["overnight", "sharpe"],
        "intraday_ann_return_%": table.loc["intraday", "ann_return_%"],
        "intraday_sharpe": table.loc["intraday", "sharpe"],
        "daily_ann_return_%": table.loc["daily", "ann_return_%"],
        "daily_sharpe": table.loc["daily", "sharpe"],
        "breakeven_round_trip_bps": round(breakeven_bps, 2),
    }
    with open(RESULTS / "key_numbers.json", "w") as f:
        json.dump(key, f, indent=2)
    print("\n--- key numbers ---")
    print(json.dumps(key, indent=2))


if __name__ == "__main__":
    main()
