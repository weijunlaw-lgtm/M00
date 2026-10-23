"""Performance metrics calculation module for US100 Quantitative Strategy Lab v3.0.

Calculates standard institutional quantitative metrics:
- Total Return (%)
- CAGR (%)
- Annualized Volatility (%)
- Sharpe Ratio
- Sortino Ratio (Continuous Downside Deviation across all N sessions)
- Max Drawdown (%)
- Calmar Ratio
- Total Trades
- Win Rate (%)
- Profit Factor
- Time in Market (%)
- Cumulative Interest Earned ($)
- Average Notional Leverage (x)
- Max Notional Leverage (x)
"""

import numpy as np
import pandas as pd


def calculate_metrics(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    initial_capital: float = 50000.0,
) -> dict:
    """Calculate institutional performance metrics for an equity curve and trade log.

    Parameters
    ----------
    equity_df : pd.DataFrame
        DataFrame indexed by Date containing 'equity', 'in_position',
        and optional 'leverage', 'cash_interest'.
    trades_df : pd.DataFrame
        DataFrame of trades containing 'net_pnl'.
    initial_capital : float, default 50000.0
        Starting portfolio capital in USD.

    Returns
    -------
    dict
        Dictionary of formatted metrics.
    """
    if equity_df is None or equity_df.empty or len(equity_df) < 2:
        return {
            "Total Return (%)": 0.0,
            "CAGR (%)": 0.0,
            "Annualized Volatility (%)": 0.0,
            "Sharpe Ratio": 0.0,
            "Sortino Ratio": 0.0,
            "Max Drawdown (%)": 0.0,
            "Calmar Ratio": 0.0,
            "Total Trades": 0,
            "Win Rate (%)": 0.0,
            "Profit Factor": 0.0,
            "Time in Market (%)": 0.0,
            "Cumulative Interest Earned ($)": 0.0,
            "Average Notional Leverage (x)": 0.0,
            "Max Notional Leverage (x)": 0.0,
        }

    e_0 = float(initial_capital) if initial_capital > 0 else float(equity_df["equity"].iloc[0])
    e_final = float(equity_df["equity"].iloc[-1])
    n_days = len(equity_df)

    # 1. Total Return (%)
    total_return = ((e_final / e_0) - 1.0) * 100.0

    # 2. CAGR (%)
    if e_final > 0 and e_0 > 0 and n_days > 0:
        cagr = (((e_final / e_0) ** (252.0 / n_days)) - 1.0) * 100.0
    else:
        cagr = -100.0

    # Daily Returns
    r_daily = equity_df["equity"].pct_change().dropna()
    mean_r = float(r_daily.mean()) if len(r_daily) > 0 else 0.0
    std_r = float(r_daily.std(ddof=1)) if len(r_daily) > 1 else 0.0

    # 3. Annualized Volatility (%)
    ann_vol = std_r * np.sqrt(252.0) * 100.0

    # 4. Sharpe Ratio
    if std_r > 1e-12:
        sharpe = (mean_r / std_r) * np.sqrt(252.0)
    else:
        sharpe = 0.0

    # 5. Sortino Ratio (Continuous Downside Deviation across all N sessions)
    neg_r = np.minimum(0.0, r_daily.to_numpy())
    downside_var = float(np.mean(neg_r ** 2))
    downside_dev = np.sqrt(downside_var * 252.0)

    if downside_dev > 1e-12:
        sortino = cagr / (downside_dev * 100.0)
    else:
        sortino = 0.0 if cagr <= 0 else 99.99

    # 6. Max Drawdown (%)
    if "drawdown_pct" in equity_df.columns:
        max_dd = float(equity_df["drawdown_pct"].min())
    else:
        cummax = equity_df["equity"].cummax()
        dd = np.where(cummax > 0, ((equity_df["equity"] - cummax) / cummax) * 100.0, 0.0)
        max_dd = float(np.min(dd))
    if max_dd > 0:
        max_dd = 0.0

    # 7. Calmar Ratio
    abs_dd = abs(max_dd)
    if abs_dd > 1e-6:
        calmar = cagr / abs_dd
    else:
        calmar = 0.0

    # Trade statistics
    if trades_df is not None and not trades_df.empty and "net_pnl" in trades_df.columns:
        total_trades = int(len(trades_df))
        winning_trades = trades_df[trades_df["net_pnl"] > 0]
        losing_trades = trades_df[trades_df["net_pnl"] < 0]

        # 8. Total Trades
        # 9. Win Rate (%)
        win_rate = (len(winning_trades) / total_trades) * 100.0

        # 10. Profit Factor
        gross_profit = float(winning_trades["net_pnl"].sum())
        gross_loss = float(abs(losing_trades["net_pnl"].sum()))
        if gross_loss > 1e-8:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 99.99
        else:
            profit_factor = 0.0
    else:
        total_trades = 0
        win_rate = 0.0
        profit_factor = 0.0

    # 11. Time in Market (%)
    if "in_position" in equity_df.columns:
        time_in_market = float(equity_df["in_position"].astype(float).mean() * 100.0)
    else:
        time_in_market = 0.0

    # 12. Cash interest & leverage exposure
    cumulative_interest = float(equity_df["cash_interest"].sum()) if "cash_interest" in equity_df.columns else 0.0
    avg_leverage = float(equity_df["leverage"].mean()) if "leverage" in equity_df.columns else (time_in_market / 100.0)
    max_leverage = float(equity_df["leverage"].max()) if "leverage" in equity_df.columns else (1.0 if time_in_market > 0 else 0.0)

    return {
        "Total Return (%)": float(np.round(total_return, 2)),
        "CAGR (%)": float(np.round(cagr, 2)),
        "Annualized Volatility (%)": float(np.round(ann_vol, 2)),
        "Sharpe Ratio": float(np.round(sharpe, 2)),
        "Sortino Ratio": float(np.round(sortino, 2)),
        "Max Drawdown (%)": float(np.round(max_dd, 2)),
        "Calmar Ratio": float(np.round(calmar, 2)),
        "Total Trades": total_trades,
        "Win Rate (%)": float(np.round(win_rate, 2)),
        "Profit Factor": float(np.round(profit_factor, 2)),
        "Time in Market (%)": float(np.round(time_in_market, 2)),
        "Cumulative Interest Earned ($)": float(np.round(cumulative_interest, 2)),
        "Average Notional Leverage (x)": float(np.round(avg_leverage, 2)),
        "Max Notional Leverage (x)": float(np.round(max_leverage, 2)),
    }


if __name__ == "__main__":
    from src.data_loader import load_us100_data
    from src.indicators import compute_indicators
    from src.backtester import run_ibs_strategy, run_momentum_strategy, run_buy_and_hold

    raw = load_us100_data()
    ind = compute_indicators(raw)
    valid = ind.dropna().copy()

    ibs_eq, ibs_tr = run_ibs_strategy(valid)
    mom_eq, mom_tr = run_momentum_strategy(valid)
    bnh_eq = run_buy_and_hold(valid)
    bnh_tr = pd.DataFrame()

    print("--- IBS Metrics ---")
    print(calculate_metrics(ibs_eq, ibs_tr))

    print("\n--- Momentum Metrics ---")
    print(calculate_metrics(mom_eq, mom_tr))

    print("\n--- Buy & Hold Metrics ---")
    print(calculate_metrics(bnh_eq, bnh_tr))
