"""Vectorized technical indicators, regime filters, and momentum reference calculations.

Implements v3.0 institutional features:
- Daily Range (DR) & True Range (TR)
- 14-day Average Daily Range (ADR_14)
- Shock-Damped Effective ADR (with 1.75 scaling factor)
- 200-day Simple Moving Average regime filter (Is_Bull)
- 20-day annualized realized volatility (realized_vol_20)
- Internal Bar Strength (IBS)
- 3-Tranche Multi-Timeframe Momentum Conviction Score (3M 25%, 6M 35%, 12M 40%)
"""

import numpy as np
import pandas as pd


def compute_indicators(df: pd.DataFrame, adr_window: int = 14) -> pd.DataFrame:
    """Compute vectorized indicators for US100 v3.0 strategy simulation.

    Parameters
    ----------
    df : pd.DataFrame
        Historical OHLCV data with DatetimeIndex and columns:
        ['Open', 'High', 'Low', 'Close', 'Volume'] plus optional 'rf_annual'.
    adr_window : int, default 14
        Rolling window for Average Daily Range.

    Returns
    -------
    pd.DataFrame
        Enriched DataFrame with additional columns:
        ['daily_range', 'adr', 'tr', 'effective_adr', 'ibs',
         'sma_200', 'is_bull', 'realized_vol_20',
         'year_month', 'last_month_close', 'close_3m_ago', 'close_6m_ago',
         'close_12m_ago', 'mom_s3', 'mom_s6', 'mom_s12', 'mom_conviction',
         'is_first_day_of_month']
    """
    out = df.copy()

    # 1. Daily Range & True Range
    out["daily_range"] = out["High"] - out["Low"]
    out["adr"] = out["daily_range"].rolling(window=adr_window).mean()

    prev_close = out["Close"].shift(1)
    tr = np.maximum(
        out["High"] - out["Low"],
        np.maximum(
            (out["High"] - prev_close).abs(),
            (out["Low"] - prev_close).abs(),
        ),
    )
    out["tr"] = tr.fillna(out["High"] - out["Low"])

    # Shock-Damped Effective ADR: max(ADR_14, TR / 1.75, 1e-8)
    eff_tail = np.maximum(out["tr"] / 1.75, 1e-8)
    # If adr is NaN (during the first 13 bars), fallback to eff_tail
    out["effective_adr"] = np.where(out["adr"].isna(), eff_tail, np.maximum(out["adr"], eff_tail))

    # 2. Internal Bar Strength (IBS_t)
    denom = np.maximum(out["High"] - out["Low"], 1e-8)
    out["ibs"] = (out["Close"] - out["Low"]) / denom

    # 3. 200-day SMA Regime Filter & 20-day Realized Volatility
    out["sma_200"] = out["Close"].rolling(window=200).mean()
    out["is_bull"] = out["Close"] > out["sma_200"]

    daily_ret = out["Close"].pct_change()
    out["realized_vol_20"] = daily_ret.rolling(window=20).std() * np.sqrt(252.0)

    # 4. 3-Tranche Multi-Timeframe Momentum Reference Closes (Zero Lookahead Bias)
    out["year_month"] = out.index.to_period("M")

    # Monthly last close series
    m_close = out.groupby("year_month")["Close"].last()

    # Shifted reference series:
    # shift(1): Close on final trading day of month m-1
    # shift(4): Close on final trading day of month m-4 (3-month lookback)
    # shift(7): Close on final trading day of month m-7 (6-month lookback)
    # shift(13): Close on final trading day of month m-13 (12-month lookback)
    last_month_close = m_close.shift(1)
    close_3m_ago = m_close.shift(4)
    close_6m_ago = m_close.shift(7)
    close_12m_ago = m_close.shift(13)

    out["last_month_close"] = out["year_month"].map(last_month_close).astype("float64")
    out["close_3m_ago"] = out["year_month"].map(close_3m_ago).astype("float64")
    out["close_6m_ago"] = out["year_month"].map(close_6m_ago).astype("float64")
    out["close_12m_ago"] = out["year_month"].map(close_12m_ago).astype("float64")

    # Sub-signals based on previous month-end close
    s3 = (out["last_month_close"] > out["close_3m_ago"]).astype("float64")
    s6 = (out["last_month_close"] > out["close_6m_ago"]).astype("float64")
    s12 = (out["last_month_close"] > out["close_12m_ago"]).astype("float64")

    out["mom_s3"] = s3
    out["mom_s6"] = s6
    out["mom_s12"] = s12
    out["mom_signal"] = s12
    out["mom_conviction"] = (0.25 * s3 + 0.35 * s6 + 0.40 * s12).astype("float64")

    # Flag for first trading day of calendar month
    out["is_first_day_of_month"] = out["year_month"] != out["year_month"].shift(1)

    return out


# Alias for compatibility with external runner scripts
precompute_indicators = compute_indicators


if __name__ == "__main__":
    from src.data_loader import load_us100_data

    raw = load_us100_data()
    ind = compute_indicators(raw)
    print("v3.0 Indicators computed successfully.")
    print("Columns:", list(ind.columns))
    valid = ind.dropna().copy()
    print("\nSample row:")
    print(valid[["Close", "effective_adr", "ibs", "is_bull", "realized_vol_20", "mom_conviction"]].tail(5))
