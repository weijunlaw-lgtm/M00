"""Data loader module for US100 Quantitative Strategy Lab.

Handles fetching historical daily OHLCV data from Yahoo Finance (^NDX)
and 13-Week Treasury Bill yield (^IRX) for floating cash sweep yield,
and caching to a local Parquet file.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

# Default cache file path relative to project root
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "us100_daily.parquet"


def load_us100_data(
    ticker: str = "^NDX",
    rf_ticker: str = "^IRX",
    start_date: str = "2005-01-01",
    force_refresh: bool = False,
    cache_path: Path | str | None = None,
) -> pd.DataFrame:
    """Load US100 daily OHLCV data and risk-free yield, from cache or Yahoo Finance.

    Parameters
    ----------
    ticker : str, default "^NDX"
        Ticker symbol to fetch for Nasdaq-100.
    rf_ticker : str, default "^IRX"
        Ticker symbol for 13-Week Treasury Bill yield index.
    start_date : str, default "2005-01-01"
        Start date for data fetch (YYYY-MM-DD).
    force_refresh : bool, default False
        If True, ignores cached file and fetches fresh data from Yahoo Finance.
    cache_path : Path | str | None, optional
        Custom cache file path. Defaults to data/us100_daily.parquet.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by Date (ascending, tz-naive) with columns:
        ['Open', 'High', 'Low', 'Close', 'Volume', 'rf_annual'].
    """
    target_cache = Path(cache_path) if cache_path else DEFAULT_CACHE_FILE

    if not force_refresh and target_cache.exists():
        df = pd.read_parquet(target_cache)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "Date"
        df = df.sort_index()

        # If cache already has rf_annual, return it
        if "rf_annual" in df.columns and (df["rf_annual"].isna().sum() == 0):
            return df

    # Fetch ^NDX data via yfinance
    df = yf.download(ticker, start=start_date, auto_adjust=False, progress=False)
    if df.empty:
        raise ValueError(f"No data returned from Yahoo Finance for ticker '{ticker}' starting from {start_date}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Downloaded data missing required columns: {missing_cols}")

    df = df[required_cols].copy().dropna()

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "Date"
    df = df.sort_index()

    for col in required_cols:
        df[col] = df[col].astype("float64")

    # Fetch ^IRX data (13-Week Treasury Bill yield)
    try:
        irx_raw = yf.download(rf_ticker, start=start_date, auto_adjust=False, progress=False)
        if isinstance(irx_raw.columns, pd.MultiIndex):
            irx_raw.columns = irx_raw.columns.get_level_values(0)

        if not isinstance(irx_raw.index, pd.DatetimeIndex):
            irx_raw.index = pd.to_datetime(irx_raw.index)
        if irx_raw.index.tz is not None:
            irx_raw.index = irx_raw.index.tz_localize(None)

        irx_close = irx_raw["Close"].astype("float64")
        # Align to ^NDX trading calendar, convert % to decimal (e.g. 4.25 -> 0.0425)
        rf_aligned = irx_close.reindex(df.index).ffill().bfill() / 100.0
        rf_aligned = rf_aligned.clip(lower=0.0).fillna(0.0)
    except Exception as e:
        print(f"Warning: Failed to fetch {rf_ticker} ({e}), fallback to static 0.04")
        rf_aligned = pd.Series(0.04, index=df.index, dtype="float64")

    df["rf_annual"] = rf_aligned.astype("float64")

    # Assert integrity
    assert df["rf_annual"].isna().sum() == 0, "rf_annual must not contain NaNs"
    assert (df["rf_annual"] >= 0.0).all(), "rf_annual must be non-negative"

    target_cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(target_cache)

    return df


# Alias for compatibility with external runner scripts
fetch_or_load_data = load_us100_data


if __name__ == "__main__":
    print("Testing data loader...")
    data = load_us100_data(force_refresh=True)
    print(f"Data shape: {data.shape}")
    print(f"Date range: {data.index.min()} to {data.index.max()}")
    print("rf_annual stats:\n", data["rf_annual"].describe())
    print(data.tail(3))
