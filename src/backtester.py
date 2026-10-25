"""Stateful mark-to-market backtesting engines for US100 Quantitative Strategies v1.0-Restored.

Implements pure v1.0 strategy rules on the unified infrastructure stack:
- Shock-Damped Effective ADR sizing (max(ADR_14, TR / 1.75))
- IBS Mean-Reversion: Entry IBS < 0.10, Exit IBS > 0.50 OR bars_held >= 5 (no ATR stop)
- 12-Month Binary Momentum: Full monthly hold, no mid-month stops, no 3-tranche
- Single flat risk_per_adr parameter for both strategies
- Static max_leverage cap (default 2.0x), no dynamic vol-targeting
- Floating 13-Week Treasury Bill yield credited fairly across all cash balances
- Baseline Buy & Hold benchmark
"""

import numpy as np
import pandas as pd

TRADE_COLS = [
    "entry_date",
    "exit_date",
    "entry_price",
    "exit_price",
    "units",
    "net_pnl",
    "bars_held",
    "exit_reason",
]


def run_ibs_strategy(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    risk_per_adr: float = 0.01,
    ibs_entry: float = 0.10,
    ibs_exit: float = 0.50,
    max_hold: int = 5,
    use_effective_adr: bool = True,
    use_floating_yield: bool = True,
    cash_yield_annual: float = 0.0,
    cost_bps: float = 2.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute mark-to-market backtest of the IBS strategy with pure v1.0 exit rules.

    v1.0 Rules Restored:
    - Entry: Close-on-close when IBS < ibs_entry
    - Exit: IBS > ibs_exit OR bars_held >= max_hold (no ATR stop)
    - Sizing: equity * risk_per_adr / effective_adr (or raw adr)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with ['Open', 'High', 'Low', 'Close', 'adr', 'effective_adr', 'ibs']
        and optional 'rf_annual'.
    initial_capital : float, default 50000.0
    risk_per_adr : float, default 0.01 (1.0%)
    ibs_entry : float, default 0.10
    ibs_exit : float, default 0.50
    max_hold : int, default 5
    use_effective_adr : bool, default True
        If True, uses shock-damped effective_adr; if False, uses raw adr_14.
    use_floating_yield : bool, default True
    cash_yield_annual : float, default 0.0
    cost_bps : float, default 2.0
    """
    cost_factor = cost_bps * 1e-4
    n = len(df)
    if n == 0:
        empty_eq = pd.DataFrame(columns=[
            "equity", "drawdown_pct", "units", "in_position", "cash_interest", "leverage"
        ])
        empty_tr = pd.DataFrame(columns=TRADE_COLS)
        return empty_eq, empty_tr

    dates = df.index
    closes = df["Close"].to_numpy(dtype=np.float64)
    raw_adrs = df["adr"].to_numpy(dtype=np.float64)
    if use_effective_adr and "effective_adr" in df.columns:
        sizing_adrs = df["effective_adr"].to_numpy(dtype=np.float64)
    else:
        sizing_adrs = raw_adrs
    ibss = df["ibs"].to_numpy(dtype=np.float64)

    if use_floating_yield and "rf_annual" in df.columns:
        rf_daily = (df["rf_annual"].to_numpy(dtype=np.float64) / 252.0)
    else:
        rf_daily = np.full(n, cash_yield_annual / 252.0, dtype=np.float64)

    in_position = False
    bars_held = 0
    units = 0.0
    equity = float(initial_capital)
    entry_price = 0.0
    entry_date = None

    equity_arr = np.empty(n, dtype=np.float64)
    units_arr = np.zeros(n, dtype=np.float64)
    in_pos_arr = np.zeros(n, dtype=bool)
    interest_arr = np.zeros(n, dtype=np.float64)
    leverage_arr = np.zeros(n, dtype=np.float64)
    trades = []

    for t in range(n):
        close_t = closes[t]
        adr_t = sizing_adrs[t]
        ibs_t = ibss[t]
        date_t = dates[t]
        rf_t = rf_daily[t]

        interest_t = 0.0

        if t == 0:
            if not np.isnan(ibs_t) and not np.isnan(adr_t) and ibs_t < ibs_entry and adr_t > 0:
                units = (equity * risk_per_adr) / adr_t
                entry_cost = units * close_t * cost_factor
                equity -= entry_cost
                in_position = True
                bars_held = 0
                entry_price = close_t
                entry_date = date_t
            equity_arr[0] = equity
            units_arr[0] = units
            in_pos_arr[0] = in_position
            interest_arr[0] = 0.0
            leverage_arr[0] = (units * close_t / equity) if equity > 0 else 0.0
            continue

        # 1. Mark to market & Idle Cash Yield
        if in_position:
            bars_held += 1
            equity += units * (close_t - closes[t - 1])

            # v1.0 exit rules: IBS > exit threshold OR max hold reached
            is_ibs_exit = ibs_t > ibs_exit
            is_max_hold = bars_held >= max_hold

            if is_ibs_exit or is_max_hold:
                exit_cost = units * close_t * cost_factor
                equity -= exit_cost

                entry_cost = units * entry_price * cost_factor
                gross_pnl = units * (close_t - entry_price)
                net_pnl = gross_pnl - (entry_cost + exit_cost)

                reason = "IBS Exit" if is_ibs_exit else "Max Hold"
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date_t,
                    "entry_price": entry_price,
                    "exit_price": close_t,
                    "units": units,
                    "net_pnl": net_pnl,
                    "bars_held": bars_held,
                    "exit_reason": reason,
                })
                in_position = False
                bars_held = 0
                units = 0.0
        else:
            # Idle cash interest from t-1 to t
            if rf_t > 0:
                uninvested_cash = equity_arr[t - 1]
                interest_t = max(0.0, uninvested_cash) * rf_t
                equity += interest_t

            # Entry check at close of t
            if not np.isnan(ibs_t) and not np.isnan(adr_t) and ibs_t < ibs_entry and adr_t > 0:
                units = (equity * risk_per_adr) / adr_t
                entry_cost = units * close_t * cost_factor
                equity -= entry_cost
                in_position = True
                bars_held = 0
                entry_price = close_t
                entry_date = date_t

        equity_arr[t] = equity
        units_arr[t] = units
        in_pos_arr[t] = in_position
        interest_arr[t] = interest_t
        leverage_arr[t] = (units * close_t / equity) if equity > 0 else 0.0

    if in_position and n > 0:
        final_close = closes[n - 1]
        exit_cost = units * final_close * cost_factor
        equity_arr[n - 1] -= exit_cost
        entry_cost = units * entry_price * cost_factor
        gross_pnl = units * (final_close - entry_price)
        net_pnl = gross_pnl - (entry_cost + exit_cost)
        trades.append({
            "entry_date": entry_date,
            "exit_date": dates[n - 1],
            "entry_price": entry_price,
            "exit_price": final_close,
            "units": units,
            "net_pnl": net_pnl,
            "bars_held": bars_held,
            "exit_reason": "End of Period",
        })

    equity_series = pd.Series(equity_arr, index=dates)
    cummax = equity_series.cummax()
    drawdown_pct = np.where(cummax > 0, ((equity_series - cummax) / cummax) * 100.0, 0.0)

    equity_df = pd.DataFrame({
        "equity": equity_arr,
        "drawdown_pct": drawdown_pct,
        "units": units_arr,
        "in_position": in_pos_arr,
        "cash_interest": interest_arr,
        "leverage": leverage_arr,
    }, index=dates)
    equity_df.index.name = "Date"

    trades_df = pd.DataFrame(trades, columns=TRADE_COLS)
    return equity_df, trades_df


def run_momentum_strategy(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    risk_per_adr: float = 0.01,
    use_effective_adr: bool = True,
    use_floating_yield: bool = True,
    cash_yield_annual: float = 0.0,
    cost_bps: float = 2.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute mark-to-market backtest of pure v1.0 12-Month Binary Momentum.

    v1.0 Rules Restored:
    - Signal: Binary 12M momentum (last_month_close > close_12m_ago) evaluated ONLY
      on is_first_day_of_month == True.
    - Entry: Full position size (no 3-tranche conviction scaling).
    - Exit: Monthly rebalance only. No mid-month Chandelier trailing stop.
      "Next month's check decides."
    - Sizing: equity * risk_per_adr / effective_adr (or raw adr).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with ['Close', 'adr', 'effective_adr', 'last_month_close',
        'close_12m_ago', 'is_first_day_of_month'] and optional 'rf_annual'.
    """
    cost_factor = cost_bps * 1e-4
    n = len(df)
    if n == 0:
        empty_eq = pd.DataFrame(columns=[
            "equity", "drawdown_pct", "units", "in_position", "cash_interest", "leverage"
        ])
        empty_tr = pd.DataFrame(columns=TRADE_COLS)
        return empty_eq, empty_tr

    dates = df.index
    closes = df["Close"].to_numpy(dtype=np.float64)
    raw_adrs = df["adr"].to_numpy(dtype=np.float64)
    if use_effective_adr and "effective_adr" in df.columns:
        sizing_adrs = df["effective_adr"].to_numpy(dtype=np.float64)
    else:
        sizing_adrs = raw_adrs

    # Pure v1.0 binary 12M momentum signal
    last_month_closes = df["last_month_close"].to_numpy(dtype=np.float64)
    close_12m_agos = df["close_12m_ago"].to_numpy(dtype=np.float64)
    is_first_days = df["is_first_day_of_month"].to_numpy(dtype=bool)

    if use_floating_yield and "rf_annual" in df.columns:
        rf_daily = (df["rf_annual"].to_numpy(dtype=np.float64) / 252.0)
    else:
        rf_daily = np.full(n, cash_yield_annual / 252.0, dtype=np.float64)

    in_position = False
    units = 0.0
    equity = float(initial_capital)
    entry_price = 0.0
    entry_date = None
    bars_held = 0

    equity_arr = np.empty(n, dtype=np.float64)
    units_arr = np.zeros(n, dtype=np.float64)
    in_pos_arr = np.zeros(n, dtype=bool)
    interest_arr = np.zeros(n, dtype=np.float64)
    leverage_arr = np.zeros(n, dtype=np.float64)
    trades = []

    for t in range(n):
        close_t = closes[t]
        adr_t = sizing_adrs[t]
        date_t = dates[t]
        is_first_day = is_first_days[t]
        rf_t = rf_daily[t]

        interest_t = 0.0

        # Mark to market and interest
        if t > 0:
            if in_position:
                equity += units * (close_t - closes[t - 1])
                bars_held += 1
            else:
                if rf_t > 0:
                    interest_t = max(0.0, equity_arr[t - 1]) * rf_t
                    equity += interest_t

        # Monthly Rebalance Check — ONLY on first day of month
        if is_first_day:
            # Close existing position
            if in_position:
                exit_cost = units * close_t * cost_factor
                equity -= exit_cost
                entry_cost = units * entry_price * cost_factor
                gross_pnl = units * (close_t - entry_price)
                net_pnl = gross_pnl - (entry_cost + exit_cost)
                trades.append({
                    "entry_date": entry_date,
                    "exit_date": date_t,
                    "entry_price": entry_price,
                    "exit_price": close_t,
                    "units": units,
                    "net_pnl": net_pnl,
                    "bars_held": bars_held,
                    "exit_reason": "Monthly Rebalance",
                })
                in_position = False
                units = 0.0
                bars_held = 0

            # v1.0 binary 12M momentum signal: last_month_close > close_12m_ago
            lmc = last_month_closes[t]
            c12m = close_12m_agos[t]
            mom_signal = (
                not np.isnan(lmc)
                and not np.isnan(c12m)
                and lmc > c12m
            )

            if mom_signal and adr_t > 0 and not np.isnan(adr_t):
                # Full position — no conviction scaling
                desired_units = (equity * risk_per_adr) / adr_t
                entry_cost = desired_units * close_t * cost_factor
                equity -= entry_cost

                in_position = True
                units = desired_units
                entry_price = close_t
                entry_date = date_t
                bars_held = 0

        # v1.0: No mid-month stops. "Next month's check decides."

        equity_arr[t] = equity
        units_arr[t] = units
        in_pos_arr[t] = in_position
        interest_arr[t] = interest_t
        leverage_arr[t] = (units * close_t / equity) if equity > 0 else 0.0

    if in_position and n > 0:
        final_close = closes[n - 1]
        exit_cost = units * final_close * cost_factor
        equity_arr[n - 1] -= exit_cost
        entry_cost = units * entry_price * cost_factor
        gross_pnl = units * (final_close - entry_price)
        net_pnl = gross_pnl - (entry_cost + exit_cost)
        trades.append({
            "entry_date": entry_date,
            "exit_date": dates[n - 1],
            "entry_price": entry_price,
            "exit_price": final_close,
            "units": units,
            "net_pnl": net_pnl,
            "bars_held": bars_held,
            "exit_reason": "End of Period",
        })

    equity_series = pd.Series(equity_arr, index=dates)
    cummax = equity_series.cummax()
    drawdown_pct = np.where(cummax > 0, ((equity_series - cummax) / cummax) * 100.0, 0.0)

    equity_df = pd.DataFrame({
        "equity": equity_arr,
        "drawdown_pct": drawdown_pct,
        "units": units_arr,
        "in_position": in_pos_arr,
        "cash_interest": interest_arr,
        "leverage": leverage_arr,
    }, index=dates)
    equity_df.index.name = "Date"

    trades_df = pd.DataFrame(trades, columns=TRADE_COLS)
    return equity_df, trades_df


def run_buy_and_hold(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    cost_bps: float = 2.0,
) -> pd.DataFrame:
    """Execute baseline Buy and Hold benchmark over the identical valid date range."""
    n = len(df)
    if n == 0:
        return pd.DataFrame(columns=["equity", "drawdown_pct", "units", "in_position", "leverage", "cash_interest"])

    cost_factor = cost_bps * 1e-4
    close_0 = float(df["Close"].iloc[0])

    units = initial_capital / (close_0 * (1.0 + cost_factor))
    equity = units * df["Close"].to_numpy(dtype=np.float64)
    equity_series = pd.Series(equity, index=df.index)
    cummax = equity_series.cummax()
    drawdown_pct = np.where(cummax > 0, ((equity_series - cummax) / cummax) * 100.0, 0.0)

    out = pd.DataFrame({
        "equity": equity,
        "drawdown_pct": drawdown_pct,
        "units": np.full(n, units, dtype=np.float64),
        "in_position": np.ones(n, dtype=bool),
        "leverage": np.ones(n, dtype=np.float64),
        "cash_interest": np.zeros(n, dtype=np.float64),
    }, index=df.index)
    out.index.name = "Date"
    return out


def run_unified_overlay_strategy(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    risk_per_adr: float = 0.0125,
    ibs_entry: float = 0.10,
    ibs_exit: float = 0.50,
    max_hold: int = 5,
    max_leverage: float = 2.0,
    use_effective_adr: bool = True,
    use_floating_yield: bool = True,
    cash_yield_annual: float = 0.0,
    cost_bps: float = 2.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute Unified 100/100 Overlay with pure v1.0 rules and flat risk sizing.

    v1.0 Rules Restored:
    - IBS: Entry IBS < 0.10, Exit IBS > 0.50 OR bars_held >= 5 (no ATR stop)
    - Momentum: Binary 12M signal, full monthly hold (no Chandelier stop)
    - Single flat risk_per_adr for both strategies (no regime-adaptive asymmetric budgets)
    - Static max_leverage cap (default 2.0x, no dynamic vol-targeting)
    - Floating T-Bill yield on idle cash

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with indicators: ['Open', 'High', 'Low', 'Close', 'adr', 'effective_adr',
        'ibs', 'last_month_close', 'close_12m_ago', 'is_first_day_of_month',
        'rf_annual'].
    risk_per_adr : float, default 0.0125
        Single flat risk budget applied equally to both IBS and Momentum.
    max_leverage : float, default 2.0
        Static leverage cap for the overlay.
    use_effective_adr : bool, default True
        If True, uses shock-damped effective_adr; if False, uses raw adr_14.
    """
    cost_factor = cost_bps * 1e-4
    n = len(df)
    if n == 0:
        empty_eq = pd.DataFrame(columns=[
            "equity", "drawdown_pct", "units", "in_position",
            "units_ibs", "units_mom", "leverage", "max_lev_cap", "cash_interest"
        ])
        empty_tr = pd.DataFrame(columns=TRADE_COLS + ["strategy"])
        return empty_eq, empty_tr

    dates = df.index
    closes = df["Close"].to_numpy(dtype=np.float64)
    raw_adrs = df["adr"].to_numpy(dtype=np.float64)
    if use_effective_adr and "effective_adr" in df.columns:
        sizing_adrs = df["effective_adr"].to_numpy(dtype=np.float64)
    else:
        sizing_adrs = raw_adrs
    ibss = df["ibs"].to_numpy(dtype=np.float64)

    # Pure v1.0 binary 12M momentum references
    last_month_closes = df["last_month_close"].to_numpy(dtype=np.float64)
    close_12m_agos = df["close_12m_ago"].to_numpy(dtype=np.float64)
    is_first_days = df["is_first_day_of_month"].to_numpy(dtype=bool)

    if use_floating_yield and "rf_annual" in df.columns:
        rf_daily = (df["rf_annual"].to_numpy(dtype=np.float64) / 252.0)
    else:
        rf_daily = np.full(n, cash_yield_annual / 252.0, dtype=np.float64)

    equity = float(initial_capital)

    # Strategy A (IBS)
    in_pos_ibs = False
    units_ibs = 0.0
    bars_held_ibs = 0
    entry_price_ibs = 0.0
    entry_date_ibs = None

    # Strategy B (Momentum)
    in_pos_mom = False
    units_mom = 0.0
    entry_price_mom = 0.0
    entry_date_mom = None
    bars_held_mom = 0

    equity_arr = np.empty(n, dtype=np.float64)
    units_arr = np.zeros(n, dtype=np.float64)
    units_ibs_arr = np.zeros(n, dtype=np.float64)
    units_mom_arr = np.zeros(n, dtype=np.float64)
    in_pos_arr = np.zeros(n, dtype=bool)
    leverage_arr = np.zeros(n, dtype=np.float64)
    max_lev_arr = np.full(n, max_leverage, dtype=np.float64)
    interest_arr = np.zeros(n, dtype=np.float64)
    trades = []

    for t in range(n):
        close_t = closes[t]
        adr_t = sizing_adrs[t]
        ibs_t = ibss[t]
        date_t = dates[t]
        is_first_day = is_first_days[t]
        rf_t = rf_daily[t]

        # -----------------------------------------------------------------
        # 1. Daily Mark-to-Market + Idle Cash Interest
        # -----------------------------------------------------------------
        interest_t = 0.0
        if t > 0:
            total_active_units = units_ibs + units_mom
            if total_active_units > 0:
                equity += total_active_units * (close_t - closes[t - 1])
                if in_pos_ibs:
                    bars_held_ibs += 1
                if in_pos_mom:
                    bars_held_mom += 1

            # Idle cash interest
            if rf_t > 0:
                prev_notional = total_active_units * closes[t - 1]
                uninvested_cash = max(0.0, equity_arr[t - 1] - prev_notional)
                if uninvested_cash > 0:
                    interest_t = uninvested_cash * rf_t
                    equity += interest_t

        interest_arr[t] = interest_t

        # -----------------------------------------------------------------
        # 2. Momentum Monthly Rebalance (v1.0: no mid-month stops)
        # -----------------------------------------------------------------
        if is_first_day:
            if in_pos_mom:
                exit_cost = units_mom * close_t * cost_factor
                equity -= exit_cost

                entry_cost = units_mom * entry_price_mom * cost_factor
                gross_pnl = units_mom * (close_t - entry_price_mom)
                net_pnl = gross_pnl - (entry_cost + exit_cost)

                trades.append({
                    "entry_date": entry_date_mom,
                    "exit_date": date_t,
                    "entry_price": entry_price_mom,
                    "exit_price": close_t,
                    "units": units_mom,
                    "net_pnl": net_pnl,
                    "bars_held": bars_held_mom,
                    "exit_reason": "Monthly Rebalance",
                    "strategy": "Momentum",
                })
                in_pos_mom = False
                units_mom = 0.0
                bars_held_mom = 0

            # v1.0 binary 12M momentum signal
            lmc = last_month_closes[t]
            c12m = close_12m_agos[t]
            mom_signal = (
                not np.isnan(lmc)
                and not np.isnan(c12m)
                and lmc > c12m
            )

            if mom_signal and adr_t > 0 and not np.isnan(adr_t):
                desired_units = (equity * risk_per_adr) / adr_t
                entry_cost = desired_units * close_t * cost_factor
                equity -= entry_cost

                in_pos_mom = True
                units_mom = desired_units
                entry_price_mom = close_t
                entry_date_mom = date_t
                bars_held_mom = 0

        # v1.0: No mid-month Chandelier stop. Hold for full month.

        # -----------------------------------------------------------------
        # 3. IBS Daily Evaluation (at Close) — v1.0 rules
        # -----------------------------------------------------------------
        if in_pos_ibs:
            is_ibs_exit = ibs_t > ibs_exit
            is_max_hold = bars_held_ibs >= max_hold

            if is_ibs_exit or is_max_hold:
                exit_cost = units_ibs * close_t * cost_factor
                equity -= exit_cost

                entry_cost = units_ibs * entry_price_ibs * cost_factor
                gross_pnl = units_ibs * (close_t - entry_price_ibs)
                net_pnl = gross_pnl - (entry_cost + exit_cost)

                reason = "IBS Exit" if is_ibs_exit else "Max Hold"
                trades.append({
                    "entry_date": entry_date_ibs,
                    "exit_date": date_t,
                    "entry_price": entry_price_ibs,
                    "exit_price": close_t,
                    "units": units_ibs,
                    "net_pnl": net_pnl,
                    "bars_held": bars_held_ibs,
                    "exit_reason": reason,
                    "strategy": "IBS",
                })
                in_pos_ibs = False
                bars_held_ibs = 0
                units_ibs = 0.0

        elif not in_pos_ibs:
            if not np.isnan(ibs_t) and not np.isnan(adr_t) and ibs_t < ibs_entry and adr_t > 0:
                desired_units = (equity * risk_per_adr) / adr_t
                entry_cost = desired_units * close_t * cost_factor
                equity -= entry_cost

                in_pos_ibs = True
                units_ibs = desired_units
                bars_held_ibs = 0
                entry_price_ibs = close_t
                entry_date_ibs = date_t

        # -----------------------------------------------------------------
        # 4. Static Leverage Cap (v1.0: no dynamic vol-targeting)
        # -----------------------------------------------------------------
        total_units = units_ibs + units_mom
        current_notional = total_units * close_t
        max_allowed_notional = max_leverage * max(equity, 0.0)

        if total_units > 0 and current_notional > max_allowed_notional:
            scale_factor = max_allowed_notional / current_notional
            units_ibs *= scale_factor
            units_mom *= scale_factor
            total_units = units_ibs + units_mom
            current_notional = total_units * close_t

        current_leverage = (current_notional / equity) if equity > 0 else 0.0

        equity_arr[t] = equity
        units_ibs_arr[t] = units_ibs
        units_mom_arr[t] = units_mom
        units_arr[t] = total_units
        in_pos_arr[t] = (total_units > 0)
        leverage_arr[t] = current_leverage

    # Handle remaining open positions at simulation end
    if n > 0:
        final_close = closes[n - 1]
        if in_pos_ibs:
            exit_cost = units_ibs * final_close * cost_factor
            equity_arr[n - 1] -= exit_cost
            entry_cost = units_ibs * entry_price_ibs * cost_factor
            gross_pnl = units_ibs * (final_close - entry_price_ibs)
            net_pnl = gross_pnl - (entry_cost + exit_cost)
            trades.append({
                "entry_date": entry_date_ibs,
                "exit_date": dates[n - 1],
                "entry_price": entry_price_ibs,
                "exit_price": final_close,
                "units": units_ibs,
                "net_pnl": net_pnl,
                "bars_held": bars_held_ibs,
                "exit_reason": "End of Period",
                "strategy": "IBS",
            })
        if in_pos_mom:
            exit_cost = units_mom * final_close * cost_factor
            equity_arr[n - 1] -= exit_cost
            entry_cost = units_mom * entry_price_mom * cost_factor
            gross_pnl = units_mom * (final_close - entry_price_mom)
            net_pnl = gross_pnl - (entry_cost + exit_cost)
            trades.append({
                "entry_date": entry_date_mom,
                "exit_date": dates[n - 1],
                "entry_price": entry_price_mom,
                "exit_price": final_close,
                "units": units_mom,
                "net_pnl": net_pnl,
                "bars_held": bars_held_mom,
                "exit_reason": "End of Period",
                "strategy": "Momentum",
            })

    equity_series = pd.Series(equity_arr, index=dates)
    cummax = equity_series.cummax()
    drawdown_pct = np.where(cummax > 0, ((equity_series - cummax) / cummax) * 100.0, 0.0)

    equity_df = pd.DataFrame({
        "equity": equity_arr,
        "drawdown_pct": drawdown_pct,
        "units": units_arr,
        "in_position": in_pos_arr,
        "units_ibs": units_ibs_arr,
        "units_mom": units_mom_arr,
        "leverage": leverage_arr,
        "max_lev_cap": max_lev_arr,
        "cash_interest": interest_arr,
    }, index=dates)
    equity_df.index.name = "Date"

    trade_cols_extended = TRADE_COLS + ["strategy"]
    trades_df = pd.DataFrame(trades, columns=trade_cols_extended)
    return equity_df, trades_df


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 50000.0,
    target_risk_pct: float = 0.0125,
    ibs_entry: float = 0.10,
    ibs_exit: float = 0.50,
    ibs_max_hold: int = 5,
    max_leverage: float = 2.0,
    use_shock_damped_adr: bool = True,
    use_cash_yield: bool = False,
    cost_bps: float = 2.0,
) -> dict:
    """Unified backtest execution wrapper for optimization pipelines.

    Executes both Strategy A (IBS Solo) and Combined 100/100 Overlay (A + B).
    """
    strat_a_eq, strat_a_tr = run_ibs_strategy(
        df,
        initial_capital=initial_capital,
        risk_per_adr=target_risk_pct,
        ibs_entry=ibs_entry,
        ibs_exit=ibs_exit,
        max_hold=ibs_max_hold,
        use_effective_adr=use_shock_damped_adr,
        use_floating_yield=use_cash_yield,
        cost_bps=cost_bps,
    )
    strat_a_ret = strat_a_eq["equity"].pct_change().fillna(0.0)
    strat_a_trades = len(strat_a_tr)
    strat_a_wins = int((strat_a_tr["net_pnl"] > 0).sum()) if not strat_a_tr.empty else 0

    combined_eq, combined_tr = run_unified_overlay_strategy(
        df,
        initial_capital=initial_capital,
        risk_per_adr=target_risk_pct,
        ibs_entry=ibs_entry,
        ibs_exit=ibs_exit,
        max_hold=ibs_max_hold,
        max_leverage=max_leverage,
        use_effective_adr=use_shock_damped_adr,
        use_floating_yield=use_cash_yield,
        cost_bps=cost_bps,
    )
    combined_ret = combined_eq["equity"].pct_change().fillna(0.0)
    combined_trades = len(combined_tr)
    combined_wins = int((combined_tr["net_pnl"] > 0).sum()) if not combined_tr.empty else 0

    return {
        "strat_a_eq": strat_a_eq,
        "strat_a_tr": strat_a_tr,
        "strat_a_ret": strat_a_ret,
        "strat_a_trades": strat_a_trades,
        "strat_a_wins": strat_a_wins,
        "combined_eq": combined_eq,
        "combined_tr": combined_tr,
        "combined_ret": combined_ret,
        "combined_trades": combined_trades,
        "combined_wins": combined_wins,
    }


if __name__ == "__main__":
    from src.data_loader import load_us100_data
    from src.indicators import compute_indicators
    from src.metrics import calculate_metrics

    raw = load_us100_data()
    ind = compute_indicators(raw)
    valid = ind.dropna().copy()

    print("=== US100 v1.0-Restored Backtests ===")
    print(f"Valid data: {len(valid)} rows, {valid.index[0].date()} to {valid.index[-1].date()}")

    # IBS Solo at risk_per_adr=0.01
    ibs_eq, ibs_tr = run_ibs_strategy(valid, risk_per_adr=0.01)
    print(f"\nIBS Solo (risk=1.0%):  ${ibs_eq['equity'].iloc[-1]:,.2f} | Trades: {len(ibs_tr)}")
    ibs_m = calculate_metrics(ibs_eq, ibs_tr)
    print(f"  Sharpe: {ibs_m['Sharpe Ratio']:.2f} | MaxDD: {ibs_m['Max Drawdown (%)']:.2f}%")

    # Momentum Solo at risk_per_adr=0.01
    mom_eq, mom_tr = run_momentum_strategy(valid, risk_per_adr=0.01)
    print(f"\n12M Momentum Solo (risk=1.0%): ${mom_eq['equity'].iloc[-1]:,.2f} | Trades: {len(mom_tr)}")
    mom_m = calculate_metrics(mom_eq, mom_tr)
    print(f"  Sharpe: {mom_m['Sharpe Ratio']:.2f} | MaxDD: {mom_m['Max Drawdown (%)']:.2f}%")

    # Combined Overlay at risk_per_adr=0.0125
    ovl_eq, ovl_tr = run_unified_overlay_strategy(valid, risk_per_adr=0.0125)
    print(f"\nCombined 100/100 Overlay (risk=1.25%): ${ovl_eq['equity'].iloc[-1]:,.2f} | Trades: {len(ovl_tr)}")
    ovl_m = calculate_metrics(ovl_eq, ovl_tr)
    print(f"  Sharpe: {ovl_m['Sharpe Ratio']:.2f} | MaxDD: {ovl_m['Max Drawdown (%)']:.2f}%")

    # Buy & Hold
    bnh_eq = run_buy_and_hold(valid)
    print(f"\nBuy & Hold Benchmark:  ${bnh_eq['equity'].iloc[-1]:,.2f}")
