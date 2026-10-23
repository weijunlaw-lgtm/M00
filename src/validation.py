"""Anti-overfitting validation and parameter sensitivity module for US100 v1.0-Restored.

Implements:
1. Regime Split Walk-Forward Validation:
   - In-Sample (IS): 2006-03-01 to 2018-12-31
   - Out-of-Sample (OOS): 2019-01-01 to 2022-12-31
   - Holdout Testing: 2023-01-01 to present
2. Parameter Sensitivity Grid Search:
   - Evaluates a 5x5 grid over IBS Entry and Risk per ADR
   - Returns 2D matrices of Sharpe and Calmar ratios
"""

import numpy as np
import pandas as pd
from src.backtester import (
    run_buy_and_hold,
    run_ibs_strategy,
    run_momentum_strategy,
    run_unified_overlay_strategy,
)
from src.metrics import calculate_metrics


def run_regime_split_backtest(df: pd.DataFrame, initial_capital: float = 50000.0) -> pd.DataFrame:
    """Execute backtests across 3 distinct macroeconomic sub-periods.

    Parameters
    ----------
    df : pd.DataFrame
        Clean, indicator-enriched DataFrame with DatetimeIndex.
    initial_capital : float, default 50000.0

    Returns
    -------
    pd.DataFrame
        Comparative table with metrics across IS, OOS, and Holdout periods.
    """
    splits = {
        "In-Sample (2006-2018)": ("2006-03-01", "2018-12-31"),
        "Out-of-Sample (2019-2022)": ("2019-01-01", "2022-12-31"),
        "Holdout (2023-Present)": ("2023-01-01", str(df.index.max().date())),
        "Full Lifecycle (2006-Present)": (str(df.index.min().date()), str(df.index.max().date())),
    }

    results = []

    for label, (s_date, e_date) in splits.items():
        sub_df = df.loc[s_date:e_date].copy()
        if len(sub_df) < 20:
            continue

        ovl_eq, ovl_tr = run_unified_overlay_strategy(sub_df, initial_capital=initial_capital)
        bnh_eq = run_buy_and_hold(sub_df, initial_capital=initial_capital)
        ibs_eq, ibs_tr = run_ibs_strategy(sub_df, initial_capital=initial_capital)
        mom_eq, mom_tr = run_momentum_strategy(sub_df, initial_capital=initial_capital)

        m_ovl = calculate_metrics(ovl_eq, ovl_tr, initial_capital=initial_capital)
        m_bnh = calculate_metrics(bnh_eq, pd.DataFrame(), initial_capital=initial_capital)
        m_ibs = calculate_metrics(ibs_eq, ibs_tr, initial_capital=initial_capital)
        m_mom = calculate_metrics(mom_eq, mom_tr, initial_capital=initial_capital)

        results.append({
            "Period": label,
            "Trading Days": len(sub_df),
            "Overlay CAGR (%)": m_ovl["CAGR (%)"],
            "Overlay Sharpe": m_ovl["Sharpe Ratio"],
            "Overlay MaxDD (%)": m_ovl["Max Drawdown (%)"],
            "Overlay Calmar": m_ovl["Calmar Ratio"],
            "Overlay WinRate (%)": m_ovl["Win Rate (%)"],
            "B&H CAGR (%)": m_bnh["CAGR (%)"],
            "B&H MaxDD (%)": m_bnh["Max Drawdown (%)"],
            "B&H Sharpe": m_bnh["Sharpe Ratio"],
            "IBS CAGR (%)": m_ibs["CAGR (%)"],
            "MOM CAGR (%)": m_mom["CAGR (%)"],
        })

    return pd.DataFrame(results)


def run_parameter_sensitivity_grid(
    df: pd.DataFrame,
    ibs_entries: list[float] | None = None,
    risk_bases: list[float] | None = None,
    initial_capital: float = 50000.0,
) -> dict:
    """Compute a 5x5 sensitivity matrix over IBS Entry Threshold and Risk per ADR.

    Parameters
    ----------
    df : pd.DataFrame
    ibs_entries : list of float, optional
        Default [0.06, 0.08, 0.10, 0.12, 0.14]
    risk_bases : list of float, optional
        Default [0.008, 0.010, 0.012, 0.014, 0.016]

    Returns
    -------
    dict
        {'sharpe_matrix': pd.DataFrame, 'calmar_matrix': pd.DataFrame, 'cagr_matrix': pd.DataFrame}
    """
    if ibs_entries is None:
        ibs_entries = [0.06, 0.08, 0.10, 0.12, 0.14]
    if risk_bases is None:
        risk_bases = [0.008, 0.010, 0.012, 0.014, 0.016]

    sharpe_grid = np.zeros((len(ibs_entries), len(risk_bases)), dtype=np.float64)
    calmar_grid = np.zeros((len(ibs_entries), len(risk_bases)), dtype=np.float64)
    cagr_grid = np.zeros((len(ibs_entries), len(risk_bases)), dtype=np.float64)

    for i, ibs_e in enumerate(ibs_entries):
        for j, r_base in enumerate(risk_bases):
            # v1.0-Restored: single flat risk_per_adr for both strategies
            eq, tr = run_unified_overlay_strategy(
                df,
                initial_capital=initial_capital,
                risk_per_adr=r_base,
                ibs_entry=ibs_e,
            )
            m = calculate_metrics(eq, tr, initial_capital=initial_capital)
            sharpe_grid[i, j] = m["Sharpe Ratio"]
            calmar_grid[i, j] = m["Calmar Ratio"]
            cagr_grid[i, j] = m["CAGR (%)"]

    y_labels = [f"IBS {v:.2f}" for v in ibs_entries]
    x_labels = [f"Risk {v:.3f}" for v in risk_bases]

    return {
        "sharpe_matrix": pd.DataFrame(sharpe_grid, index=y_labels, columns=x_labels),
        "calmar_matrix": pd.DataFrame(calmar_grid, index=y_labels, columns=x_labels),
        "cagr_matrix": pd.DataFrame(cagr_grid, index=y_labels, columns=x_labels),
        "ibs_entries": ibs_entries,
        "risk_bases": risk_bases,
    }


if __name__ == "__main__":
    from src.data_loader import load_us100_data
    from src.indicators import compute_indicators

    raw = load_us100_data()
    ind = compute_indicators(raw).dropna().copy()

    print("Running sub-period split validation...")
    split_df = run_regime_split_backtest(ind)
    print(split_df.to_string(index=False))

    print("\nRunning sample parameter grid...")
    grid_res = run_parameter_sensitivity_grid(
        ind,
        ibs_entries=[0.08, 0.10, 0.12],
        risk_bases=[0.010, 0.012, 0.014],
    )
    print("\nSharpe Matrix:\n", grid_res["sharpe_matrix"])
