"""All figures for the project. Saved to figures/ as PNG."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .returns import wealth_curve

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"

COLOURS = {"overnight": "tab:blue", "intraday": "tab:orange", "daily": "tab:grey"}
LABELS = {"overnight": "Overnight only", "intraday": "Intraday only", "daily": "Buy and hold"}


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150)
    plt.close(fig)


def plot_wealth_curves(returns: pd.DataFrame, title: str, name: str) -> None:
    """The centrepiece chart: three cumulative wealth curves on a log scale."""
    fig, ax = plt.subplots(figsize=(10, 6))
    for col in ["daily", "overnight", "intraday"]:
        ax.plot(wealth_curve(returns[col]), label=LABELS[col], color=COLOURS[col], lw=1.2)
    ax.set_yscale("log")
    ax.set_ylabel("Growth of £1 (log scale)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    _save(fig, name)


def plot_asset_bars(table: pd.DataFrame, name: str) -> None:
    """Annualised overnight vs intraday return, one pair of bars per asset."""
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(table))
    width = 0.38
    ax.bar([i - width / 2 for i in x], table["overnight_ann_%"], width,
           label="Overnight", color=COLOURS["overnight"])
    ax.bar([i + width / 2 for i in x], table["intraday_ann_%"], width,
           label="Intraday", color=COLOURS["intraday"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(table.index)
    ax.set_ylabel("Annualised return (%)")
    ax.set_title("Overnight vs intraday annualised return by asset (full history)")
    ax.axhline(0, color="black", lw=0.8)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, name)


def plot_cost_sweep(sweep: pd.DataFrame, breakeven_bps: float, name: str) -> None:
    """Net Sharpe of the overnight strategy as round-trip costs rise."""
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(sweep["cost_bps"], sweep["net_sharpe"], marker="o", color=COLOURS["overnight"])
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(breakeven_bps, color="tab:red", ls="--", lw=1,
               label=f"Breakeven ≈ {breakeven_bps:.1f} bps round trip")
    ax.set_xlabel("Round-trip cost (bps)")
    ax.set_ylabel("Net annualised Sharpe")
    ax.set_title("SPY overnight strategy: net Sharpe vs round-trip trading cost")
    ax.legend()
    ax.grid(True, alpha=0.3)
    _save(fig, name)
