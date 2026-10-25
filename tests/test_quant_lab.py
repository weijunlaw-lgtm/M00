"""Comprehensive test suite for US100 Quantitative Strategy Lab v1.0-Restored."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_us100_data
from src.indicators import compute_indicators
from src.backtester import (
    run_ibs_strategy,
    run_momentum_strategy,
    run_buy_and_hold,
    run_unified_overlay_strategy,
    run_backtest,
)
from src.metrics import calculate_metrics, compute_metrics
from src.validation import (
    run_regime_split_backtest,
    run_parameter_sensitivity_grid,
    compute_ibs_3d_tensor,
    select_plateau_ensemble,
    run_rolling_wfo_ablation,
)


def test_data_loader_cache():
    """Verify data loader loads properly and has the expected schema including rf_annual."""
    df = load_us100_data()
    assert not df.empty, "Dataframe should not be empty"
    expected_cols = ["Open", "High", "Low", "Close", "Volume", "rf_annual"]
    for col in expected_cols:
        assert col in df.columns, f"Column {col} missing"
    assert isinstance(df.index, pd.DatetimeIndex), "Index must be DatetimeIndex"
    assert df.index.tz is None, "Index should be timezone-naive"
    assert df.index.is_monotonic_increasing, "Index must be sorted ascending"
    assert df["rf_annual"].isna().sum() == 0, "rf_annual should have no NaNs"
    assert (df["rf_annual"] >= 0.0).all(), "rf_annual must be non-negative"


def test_indicators_math():
    """Verify indicators compute correctly and match formula definitions."""
    dates = pd.date_range("2020-01-01", periods=250, freq="B")
    mock_df = pd.DataFrame({
        "Open": [100.0] * 250,
        "High": [105.0] * 250,
        "Low": [95.0] * 250,
        "Close": [100.0] * 250,
        "Volume": [1000.0] * 250,
        "rf_annual": [0.04] * 250,
    }, index=dates)

    ind = compute_indicators(mock_df, adr_window=14)

    # Daily Range: 105 - 95 = 10
    assert np.allclose(ind["daily_range"].to_numpy(), 10.0)

    # ADR_14 after 14 bars should be 10.0
    assert np.allclose(ind["adr"].iloc[13:].to_numpy(), 10.0)

    # True range: 10.0
    assert np.allclose(ind["tr"].iloc[13:].to_numpy(), 10.0)

    # Effective ADR: max(10, 10/1.75) = 10.0
    assert np.allclose(ind["effective_adr"].iloc[13:].to_numpy(), 10.0)

    # IBS: (100 - 95) / (105 - 95) = 5 / 10 = 0.50
    assert np.allclose(ind["ibs"].to_numpy(), 0.50)

    # Zero range protection test
    mock_df_zero = pd.DataFrame({
        "Open": [100.0],
        "High": [100.0],
        "Low": [100.0],
        "Close": [100.0],
        "Volume": [1000.0],
        "rf_annual": [0.0],
    }, index=pd.date_range("2020-01-01", periods=1))
    ind_zero = compute_indicators(mock_df_zero)
    assert np.isfinite(ind_zero["ibs"].iloc[0]), "IBS with zero range must not produce inf/nan"
    assert np.isfinite(ind_zero["effective_adr"].iloc[0]), "Effective ADR with zero range must not produce inf/nan"


def test_momentum_reference_dates():
    """Verify momentum reference closes have zero lookahead bias."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    feb_2006 = valid.loc["2006-02"]
    jan_2005_last_close = df.loc["2005-01", "Close"].iloc[-1]
    jan_2006_last_close = df.loc["2006-01", "Close"].iloc[-1]

    assert np.allclose(feb_2006["close_12m_ago"].iloc[0], jan_2005_last_close)
    assert np.allclose(feb_2006["last_month_close"].iloc[0], jan_2006_last_close)


def test_ibs_state_machine():
    """Verify pure v1.0 IBS entry, exit, holding, and cash yield logic."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    initial_capital = 50000.0
    eq_df, tr_df = run_ibs_strategy(
        valid,
        initial_capital=initial_capital,
        risk_per_adr=0.01,
        ibs_entry=0.10,
        ibs_exit=0.50,
        max_hold=5,
    )

    assert len(eq_df) == len(valid)
    assert not tr_df.empty

    valid_reasons = {"IBS Exit", "Max Hold", "End of Period"}
    for _, trade in tr_df.iterrows():
        assert trade["bars_held"] >= 1
        assert trade["exit_reason"] in valid_reasons
        assert trade["units"] > 0

    assert "cash_interest" in eq_df.columns
    assert eq_df["cash_interest"].sum() > 0


def test_momentum_state_machine():
    """Verify pure v1.0 12-Month Momentum with monthly hold and cash yield."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    initial_capital = 50000.0
    eq_df, tr_df = run_momentum_strategy(
        valid,
        initial_capital=initial_capital,
        risk_per_adr=0.01,
    )

    assert len(eq_df) == len(valid)
    assert not tr_df.empty

    valid_reasons = {"Monthly Rebalance", "End of Period"}
    for _, trade in tr_df.iterrows():
        assert trade["exit_reason"] in valid_reasons
        assert trade["units"] > 0


def test_buy_and_hold():
    """Verify Buy & Hold benchmark math."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    initial_capital = 50000.0
    bnh_df = run_buy_and_hold(valid, initial_capital=initial_capital)

    assert len(bnh_df) == len(valid)
    assert np.all(bnh_df["in_position"].to_numpy())
    assert np.allclose(bnh_df["units"].iloc[0], bnh_df["units"].iloc[-1])


def test_unified_overlay_v1_restored():
    """Verify Unified 100/100 Overlay flat risk sizing, leverage cap, and interest."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    initial_capital = 50000.0
    max_lev = 2.0
    eq_df, tr_df = run_unified_overlay_strategy(
        valid,
        initial_capital=initial_capital,
        risk_per_adr=0.0125,
        max_leverage=max_lev,
    )

    assert len(eq_df) == len(valid)
    assert not tr_df.empty

    # Leverage cap check: leverage must not exceed max_lev (with small float tolerance)
    leverage_diff = eq_df["leverage"] - max_lev
    assert (leverage_diff <= 1e-4).all(), f"Active leverage exceeded max cap: {leverage_diff.max()}"

    # Verify interest earned
    assert eq_df["cash_interest"].sum() > 0

    # Verify strategies present in trades
    strategies = set(tr_df["strategy"].unique())
    assert "IBS" in strategies
    assert "Momentum" in strategies


def test_metrics_continuous_sortino():
    """Verify standardized continuous Sortino and metrics calculations."""
    dates = pd.date_range("2020-01-01", periods=253, freq="B")
    equity = np.linspace(50000.0, 100000.0, 253)
    eq_df = pd.DataFrame({
        "equity": equity,
        "drawdown_pct": np.zeros(253),
        "in_position": np.ones(253, dtype=bool),
        "leverage": np.ones(253),
        "cash_interest": np.zeros(253),
    }, index=dates)

    trades_df = pd.DataFrame([
        {"net_pnl": 100.0},
        {"net_pnl": -50.0},
        {"net_pnl": 200.0},
    ])

    m = calculate_metrics(eq_df, trades_df, initial_capital=50000.0)

    assert np.isclose(m["Total Return (%)"], 100.0)
    assert m["Total Trades"] == 3
    assert np.isclose(m["Win Rate (%)"], 66.67, atol=0.1)
    assert np.isclose(m["Profit Factor"], 6.0)
    assert np.isfinite(m["CAGR (%)"])
    assert np.isfinite(m["Sharpe Ratio"])
    assert np.isfinite(m["Sortino Ratio"])


def test_validation_split_and_grid():
    """Verify validation regime split and parameter grid functions."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().copy()

    # Sub-period split
    split_res = run_regime_split_backtest(valid)
    assert len(split_res) >= 3
    assert "Overlay Sharpe" in split_res.columns

    # Parameter grid
    grid_res = run_parameter_sensitivity_grid(
        valid,
        ibs_entries=[0.08, 0.10],
        risk_bases=[0.010, 0.012],
    )
    assert grid_res["sharpe_matrix"].shape == (2, 2)
    assert np.isfinite(grid_res["sharpe_matrix"].values).all()


def test_run_backtest_wrapper():
    """Verify unified run_backtest wrapper returns complete dual-stream dictionary."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().iloc[-300:].copy()

    res = run_backtest(valid, ibs_entry=0.10, ibs_exit=0.50, ibs_max_hold=5)
    expected_keys = [
        "strat_a_eq", "strat_a_tr", "strat_a_ret", "strat_a_trades", "strat_a_wins",
        "combined_eq", "combined_tr", "combined_ret", "combined_trades", "combined_wins",
    ]
    for k in expected_keys:
        assert k in res, f"Key {k} missing from run_backtest result"
    assert len(res["strat_a_ret"]) == len(valid)
    assert len(res["combined_ret"]) == len(valid)


def test_plateau_tensor_and_ensemble():
    """Verify 3D plateau tensor calculation and spatial ensemble selection."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().iloc[-600:].copy()

    entry_grid = [0.10, 0.20]
    exit_grid = [0.50, 0.70]
    hold_grid = [3, 5]

    sr_t, tr_t = compute_ibs_3d_tensor(
        valid, entry_grid, exit_grid, hold_grid,
        target_risk_pct=0.0125, max_leverage=2.0, use_shock_damped_adr=True,
    )
    assert sr_t.shape == (2, 2, 2)
    assert tr_t.shape == (2, 2, 2)

    # Constraint check: 0.50 - 0.20 = 0.30 < 0.35 -> must be NaN
    assert np.isnan(sr_t[1, 0, 0]), "Combinations violating exit - entry >= 0.35 must be NaN"
    assert np.isnan(sr_t[1, 0, 1]), "Combinations violating exit - entry >= 0.35 must be NaN"

    ensemble = select_plateau_ensemble(
        sr_t, tr_t, entry_grid, exit_grid, hold_grid, top_k=2
    )
    assert len(ensemble) >= 1
    assert "plateau_score" in ensemble[0]
    assert "adjusted_sharpe" in ensemble[0]
    assert ensemble[0]["rank"] == 1


def test_rolling_wfo_ablation():
    """Verify rolling WFO ablation returns proper fold counts and summary metrics."""
    df = load_us100_data()
    ind = compute_indicators(df)
    valid = ind.dropna().iloc[-1600:].copy()

    # Small slice: 5Y IS (1260) + 1Y OOS (252) = 1512 bars -> 1 fold
    entry_grid = [0.10]
    exit_grid = [0.60]
    hold_grid = [5]

    wfo_df, summary = run_rolling_wfo_ablation(
        valid, entry_grid, exit_grid, hold_grid,
        is_years=5, oos_years=1, target_risk_pct=0.0125,
        use_shock_damped_adr=True,
    )
    assert len(wfo_df) >= 1
    assert "is_sharpe" in wfo_df.columns
    assert "oos_sharpe" in wfo_df.columns
    assert "wfe_ratio" in summary
    assert "mean_oos_sharpe" in summary


def test_optimize_cli_artifacts():
    """Verify that optimization JSON payload and Markdown report are valid."""
    json_path = ROOT_DIR / "INFO" / "optimal_ibs_ablation.json"
    md_path = ROOT_DIR / "INFO" / "OPTIMIZATION_SIDE_BY_SIDE_REPORT.md"

    assert json_path.exists(), "optimal_ibs_ablation.json must exist"
    assert md_path.exists(), "OPTIMIZATION_SIDE_BY_SIDE_REPORT.md must exist"

    import json
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "SHOCK_DAMPED_ADR_ON" in data
    assert "STANDARD_ADR_OFF" in data
    assert "ideal_centroid_params" in data["SHOCK_DAMPED_ADR_ON"]
    assert "stage2_performance" in data["SHOCK_DAMPED_ADR_ON"]

    md_content = md_path.read_text(encoding="utf-8")
    assert "## 2. Stage 1: Strategy A (IBS Solo) Optimization" in md_content
    assert "## 3. Stage 2: Combined 100/100 Overlay" in md_content
    assert "## 4. Automated Decision Gate" in md_content


if __name__ == "__main__":
    print("Running v1.0-Restored test suites...")
    test_data_loader_cache()
    print("[OK] test_data_loader_cache passed")
    test_indicators_math()
    print("[OK] test_indicators_math passed")
    test_momentum_reference_dates()
    print("[OK] test_momentum_reference_dates passed")
    test_ibs_state_machine()
    print("[OK] test_ibs_state_machine passed")
    test_momentum_state_machine()
    print("[OK] test_momentum_state_machine passed")
    test_buy_and_hold()
    print("[OK] test_buy_and_hold passed")
    test_unified_overlay_v1_restored()
    print("[OK] test_unified_overlay_v1_restored passed")
    test_metrics_continuous_sortino()
    print("[OK] test_metrics_continuous_sortino passed")
    test_validation_split_and_grid()
    print("[OK] test_validation_split_and_grid passed")
    test_run_backtest_wrapper()
    print("[OK] test_run_backtest_wrapper passed")
    test_plateau_tensor_and_ensemble()
    print("[OK] test_plateau_tensor_and_ensemble passed")
    test_rolling_wfo_ablation()
    print("[OK] test_rolling_wfo_ablation passed")
    test_optimize_cli_artifacts()
    print("[OK] test_optimize_cli_artifacts passed")
    print("\nAll 13 test suites PASSED successfully!")
