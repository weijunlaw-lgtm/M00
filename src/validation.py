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
from scipy.ndimage import gaussian_filter, generic_filter

from src.indicators import compute_indicators
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


def fast_evaluate_ibs(
    closes: np.ndarray,
    sizing_adrs: np.ndarray,
    ibss: np.ndarray,
    ibs_entry: float = 0.10,
    ibs_exit: float = 0.50,
    max_hold: int = 5,
    risk_per_adr: float = 0.0125,
    cost_bps: float = 2.0,
    initial_capital: float = 50000.0,
) -> tuple[np.ndarray, int]:
    """Fast NumPy evaluation loop for IBS Strategy without pandas overhead.

    Matches run_ibs_strategy exactly when use_floating_yield=False and cash_yield_annual=0.0.
    """
    cost_factor = cost_bps * 1e-4
    n = len(closes)
    equity = float(initial_capital)
    in_pos = False
    bars_held = 0
    units = 0.0
    n_trades = 0
    eq_arr = np.empty(n, dtype=np.float64)

    for t in range(n):
        c_t = closes[t]
        a_t = sizing_adrs[t]
        i_t = ibss[t]

        if t == 0:
            if not np.isnan(i_t) and not np.isnan(a_t) and i_t < ibs_entry and a_t > 0:
                units = (equity * risk_per_adr) / a_t
                equity -= units * c_t * cost_factor
                in_pos = True
                bars_held = 0
            eq_arr[0] = equity
            continue

        if in_pos:
            bars_held += 1
            equity += units * (c_t - closes[t - 1])
            if i_t > ibs_exit or bars_held >= max_hold:
                equity -= units * c_t * cost_factor
                n_trades += 1
                in_pos = False
                bars_held = 0
                units = 0.0
        else:
            if not np.isnan(i_t) and not np.isnan(a_t) and i_t < ibs_entry and a_t > 0:
                units = (equity * risk_per_adr) / a_t
                equity -= units * c_t * cost_factor
                in_pos = True
                bars_held = 0

        eq_arr[t] = equity

    if in_pos and n > 0:
        equity -= units * closes[n - 1] * cost_factor
        eq_arr[n - 1] = equity
        n_trades += 1

    return eq_arr, n_trades


def compute_ibs_3d_tensor(
    df: pd.DataFrame,
    entry_grid: np.ndarray | list[float],
    exit_grid: np.ndarray | list[float],
    hold_grid: np.ndarray | list[int],
    target_risk_pct: float = 0.0125,
    max_leverage: float = 2.0,
    use_shock_damped_adr: bool = True,
    cost_bps: float = 2.0,
    initial_capital: float = 50000.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute 3D Sharpe and Trade Count tensors for Strategy A (IBS Solo).

    Enforces structural constraint (ibs_exit - ibs_entry >= 0.35) and applies
    soft trade-frequency penalty. Floating T-Bill yield is strictly disabled.
    """
    if "effective_adr" not in df.columns or "ibs" not in df.columns:
        df_ind = compute_indicators(df).dropna()
    else:
        df_ind = df

    closes = df_ind["Close"].to_numpy(dtype=np.float64)
    if use_shock_damped_adr and "effective_adr" in df_ind.columns:
        sizing_adrs = df_ind["effective_adr"].to_numpy(dtype=np.float64)
    else:
        sizing_adrs = df_ind["adr"].to_numpy(dtype=np.float64)
    ibss = df_ind["ibs"].to_numpy(dtype=np.float64)

    years = max(len(df_ind) / 252.0, 1.0)
    min_trades_req = 20.0 * years

    shape = (len(entry_grid), len(exit_grid), len(hold_grid))
    sr_tensor = np.full(shape, np.nan, dtype=np.float64)
    tr_tensor = np.zeros(shape, dtype=np.int32)

    for i, e_in in enumerate(entry_grid):
        for j, e_out in enumerate(exit_grid):
            if (e_out - e_in) < 0.35:
                continue
            for k, max_h in enumerate(hold_grid):
                eq_arr, n_trades = fast_evaluate_ibs(
                    closes=closes,
                    sizing_adrs=sizing_adrs,
                    ibss=ibss,
                    ibs_entry=float(e_in),
                    ibs_exit=float(e_out),
                    max_hold=int(max_h),
                    risk_per_adr=target_risk_pct,
                    cost_bps=cost_bps,
                    initial_capital=initial_capital,
                )
                tr_tensor[i, j, k] = n_trades

                if len(eq_arr) > 1 and n_trades >= 5:
                    rets = np.diff(eq_arr) / np.maximum(eq_arr[:-1], 1e-8)
                    std = np.std(rets, ddof=1)
                    if std > 1e-8:
                        raw_sr = (np.mean(rets) / std) * np.sqrt(252.0)
                        freq_scale = min(1.0, np.sqrt(n_trades / min_trades_req))
                        sr_tensor[i, j, k] = raw_sr * freq_scale
                    else:
                        sr_tensor[i, j, k] = 0.0
                else:
                    sr_tensor[i, j, k] = 0.0

    return sr_tensor, tr_tensor


def select_plateau_ensemble(
    sr_tensor: np.ndarray,
    trades_tensor: np.ndarray,
    entry_grid: np.ndarray | list[float],
    exit_grid: np.ndarray | list[float],
    hold_grid: np.ndarray | list[int],
    sigma: float = 1.0,
    lambda_pen: float = 0.5,
    top_k: int = 3,
) -> list[dict]:
    """Select #1 Plateau Centroid and Top-K spatially distinct ensemble parameters."""
    entry_arr = np.asarray(entry_grid, dtype=np.float64)
    exit_arr = np.asarray(exit_grid, dtype=np.float64)
    hold_arr = np.asarray(hold_grid, dtype=np.int32)

    valid_mask = ~np.isnan(sr_tensor)
    filled = np.where(valid_mask, sr_tensor, 0.0)

    smoothed = gaussian_filter(filled, sigma=sigma, mode="nearest")
    local_std = generic_filter(filled, np.std, size=3, mode="nearest")
    objective = np.where(valid_mask, smoothed - lambda_pen * local_std, -np.inf)

    flat_order = np.argsort(objective, axis=None)[::-1]
    selected = []
    coords_taken = []

    for flat_idx in flat_order:
        coord = np.unravel_index(flat_idx, objective.shape)
        if objective[coord] == -np.inf:
            break
        if all(np.sum(np.abs(np.array(coord) - np.array(c))) >= 2 for c in coords_taken):
            coords_taken.append(coord)
            i, j, k = coord
            selected.append({
                "rank": len(selected) + 1,
                "ibs_entry": float(entry_arr[i]),
                "ibs_exit": float(exit_arr[j]),
                "max_hold": int(hold_arr[k]),
                "plateau_score": round(float(objective[coord]), 4),
                "adjusted_sharpe": round(float(sr_tensor[coord]), 4),
                "neighborhood_std": round(float(local_std[coord]), 4),
                "total_trades": int(trades_tensor[coord]),
            })
            if len(selected) >= top_k:
                break

    return selected


def run_rolling_wfo_ablation(
    df: pd.DataFrame,
    entry_grid: np.ndarray | list[float],
    exit_grid: np.ndarray | list[float],
    hold_grid: np.ndarray | list[int],
    is_years: int = 5,
    oos_years: int = 1,
    target_risk_pct: float = 0.0125,
    max_leverage: float = 2.0,
    use_shock_damped_adr: bool = True,
    cost_bps: float = 2.0,
) -> tuple[pd.DataFrame, dict]:
    """Execute rolling 5Y IS / 1Y OOS Walk-Forward Optimization for Strategy A."""
    if "effective_adr" not in df.columns or "ibs" not in df.columns:
        df_ind = compute_indicators(df).dropna()
    else:
        df_ind = df

    is_bars = is_years * 252
    oos_bars = oos_years * 252
    folds = []

    for start in range(0, len(df_ind) - is_bars - oos_bars + 1, oos_bars):
        is_df = df_ind.iloc[start : start + is_bars]
        oos_df = df_ind.iloc[start + is_bars : start + is_bars + oos_bars]

        sr_t, tr_t = compute_ibs_3d_tensor(
            is_df, entry_grid, exit_grid, hold_grid,
            target_risk_pct=target_risk_pct,
            max_leverage=max_leverage,
            use_shock_damped_adr=use_shock_damped_adr,
            cost_bps=cost_bps,
        )
        winner = select_plateau_ensemble(
            sr_t, tr_t, entry_grid, exit_grid, hold_grid, top_k=1
        )[0]

        oos_eq, oos_tr = run_ibs_strategy(
            oos_df,
            risk_per_adr=target_risk_pct,
            ibs_entry=winner["ibs_entry"],
            ibs_exit=winner["ibs_exit"],
            max_hold=winner["max_hold"],
            use_effective_adr=use_shock_damped_adr,
            use_floating_yield=False,
            cost_bps=cost_bps,
        )
        oos_rets = oos_eq["equity"].pct_change().dropna()
        oos_std = float(oos_rets.std(ddof=1)) if len(oos_rets) > 1 else 0.0
        oos_sr = (float(oos_rets.mean()) / oos_std) * np.sqrt(252.0) if oos_std > 1e-8 else 0.0

        folds.append({
            "oos_period": f"{oos_df.index[0]:%Y-%m-%d} to {oos_df.index[-1]:%Y-%m-%d}",
            "entry": winner["ibs_entry"],
            "exit": winner["ibs_exit"],
            "hold": winner["max_hold"],
            "is_sharpe": winner["adjusted_sharpe"],
            "oos_sharpe": round(float(oos_sr), 4),
            "oos_trades": len(oos_tr),
        })

    wfo_df = pd.DataFrame(folds)
    mean_is = float(wfo_df["is_sharpe"].mean()) if not wfo_df.empty else 0.0
    mean_oos = float(wfo_df["oos_sharpe"].mean()) if not wfo_df.empty else 0.0
    wfe_ratio = (mean_oos / max(mean_is, 1e-6)) if mean_is > 0 else 0.0
    pos_pct = float((wfo_df["oos_sharpe"] > 0).mean() * 100.0) if not wfo_df.empty else 0.0

    summary = {
        "mean_is_sharpe": round(mean_is, 4),
        "mean_oos_sharpe": round(mean_oos, 4),
        "wfe_ratio": round(wfe_ratio, 4),
        "positive_oos_folds_pct": round(pos_pct, 2),
    }
    return wfo_df, summary


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
