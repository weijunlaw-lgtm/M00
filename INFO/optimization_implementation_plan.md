# Agent Implementation Plan: IBS Plateau Optimization & Shock-Damped ADR A/B Ablation

## 1. Architectural Objective
Build a decoupled, two-stage optimization pipeline and standalone CLI runner (`optimize_cli.py`) to find the most robust, non-overfit parameter set for **Strategy A (IBS Solo)** without altering core strategy logic, then plug the winning parameters into the **Combined 100/100 Overlay (Strategy A + Strategy B 12M Momentum)**.

To verify whether **Shock-Damped Effective ADR** adds genuine structural value or unnecessary complexity, the pipeline will run a strict **Side-by-Side Ablation Study**:
* **Track 1 (`DAMPED_ON`):** Strategy A optimized and evaluated with **Shock-Damped Effective ADR = `True`**.
* **Track 2 (`DAMPED_OFF`):** Strategy A optimized and evaluated with **Shock-Damped Effective ADR = `False`** (Standard Raw 20-day ADR sizing).
* **Cash Yield Rule:** **Floating T-Bill Yield (`^IRX`) is completely disabled (`use_cash_yield=False` / `rf_series=0.0`)** across all optimization and evaluation runs to isolate pure strategy alpha.

---

## 2. Core Mathematical Logic & Anti-Overfitting Protocol

### A. Coarse Cartesian Parameter Grid
Restrict the search space to macro-level steps so the optimizer cannot curve-fit micro-noise:
* **IBS Entry Threshold ($\tau_{\text{in}}$):** $\{0.10, 0.15, 0.20, 0.25, 0.30\}$
* **IBS Exit Threshold ($\tau_{\text{out}}$):** $\{0.50, 0.60, 0.70, 0.80, 0.85\}$
* **IBS Max Hold Sessions ($H$):** $\{3, 4, 5, 6, 7, 8\}$
* **Structural Constraint:** Enforce $\tau_{\text{out}} - \tau_{\text{in}} \ge 0.35$. Combinations violating this constraint are masked (`np.nan`).

### B. Sample-Size Adjusted Sharpe Ratio
For every valid coordinate $\theta = (\tau_{\text{in}}, \tau_{\text{out}}, H)$ on the 3D grid, compute the annualized Sharpe ratio with zero risk-free rate (`rf = 0.0`) and apply a soft trade-frequency penalty to prevent low-trade variance inflation:

$$S_{\text{adj}}(\theta) = S_{\text{raw}}(\theta) \times \min\left(1.0, \; \sqrt{\frac{N_{\text{trades}}(\theta)}{20 \times N_{\text{years}}}}\right)$$

### C. 3D Gaussian Plateau Centroid Selection
Instead of picking the highest raw Sharpe spike, smooth the 3D Sharpe tensor using a Gaussian kernel ($\sigma = 1.0$) and penalize local neighborhood standard deviation ($\lambda = 0.5$):

$$J(\theta) = \text{GaussianSmooth}_{3\text{D}}\big(S_{\text{adj}}(\theta), \sigma=1.0\big) - 0.5 \times \text{LocalStd}_{3\times 3\times 3}\big(S_{\text{adj}}(\theta)\big)$$

* **Ideal Centroid Parameter:** $\theta^* = \arg\max_{\theta} J(\theta)$.
* **Top-3 Plateau Ensemble:** Select the top 3 parameter tuples ranked by $J(\theta)$ subject to a minimum Manhattan grid distance $\|\text{coord}_a - \text{coord}_b\|_1 \ge 2$ so ensemble members represent distinct structural nodes on the plateau.

### D. Rolling Walk-Forward Optimization (WFO)
* **Window Configuration:** Rolling **5-Year In-Sample (IS = 1,260 bars)** training window followed by a **1-Year Out-of-Sample (OOS = 252 bars)** test window, stepping forward by 1 year (252 bars) per fold.
* **Walk-Forward Efficiency (WFE):**
  $$\text{WFE} = \frac{\text{Mean Annualized OOS Sharpe}}{\text{Mean Annualized IS Sharpe}}$$

---

## 3. Codebase Integration Specification

### File 1: `src/validation.py` (Add 3D Plateau & Dual-Mode WFO Functions)
Inspect `src/backtester.py` and `src/indicators.py` to match exact function signatures (`precompute_indicators`, `run_backtest`, `compute_metrics`), then add the following functions to `src/validation.py`:

1. `compute_ibs_3d_tensor(df, entry_grid, exit_grid, hold_grid, target_risk_pct=0.0125, max_leverage=2.0, use_shock_damped_adr=True)`:
   * Precomputes indicators with `use_shock_damped_adr` toggled (`True` or `False`).
   * Loops over the valid 3D grid for **Strategy A (IBS Solo)** with `use_cash_yield=False` (`rf_series=0.0`).
   * Returns `sr_tensor` (3D `np.ndarray` of frequency-adjusted Sharpe ratios) and `trades_tensor` (3D `np.ndarray` of trade counts).
2. `select_plateau_ensemble(sr_tensor, trades_tensor, entry_grid, exit_grid, hold_grid, sigma=1.0, lambda_pen=0.5, top_k=3)`:
   * Uses `scipy.ndimage.gaussian_filter` and `scipy.ndimage.generic_filter` to compute the regularized plateau objective $J(\theta)$.
   * Returns a list of dictionaries containing the #1 Ideal Centroid (`rank=1`) and top-3 spatially separated ensemble parameter sets.
3. `run_rolling_wfo_ablation(df, entry_grid, exit_grid, hold_grid, is_years=5, oos_years=1, target_risk_pct=0.0125, max_leverage=2.0, use_shock_damped_adr=True)`:
   * Executes the rolling 5Y IS / 1Y OOS walk-forward loop for a given `use_shock_damped_adr` mode.
   * Returns the fold-by-fold DataFrame and aggregate WFE summary metrics.

---

### File 2: `optimize_cli.py` (Standalone CLI Runner in Project Root)
Create `optimize_cli.py` in the root directory. It must execute the full 2-stage workflow for both `DAMPED_ON` and `DAMPED_OFF`, plug the winning parameters into the **Combined 100/100 Overlay (Strategy A + Strategy B)**, and export both JSON and Markdown artifacts.

```python
#!/usr/bin/env python3
"""
Standalone CLI Runner:
Stage 1: Optimize Strategy A (IBS Solo) via Rolling WFO + 3D Plateau Selection
         Side-by-Side Ablation: Shock-Damped ADR (ON) vs. Standard Raw ADR (OFF)
         (Floating T-Bill Yield strictly disabled across all runs)
Stage 2: Plug Winning Ideal & 3x Ensemble Parameters into Combined 100/100 Overlay (A + B)
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter, generic_filter

from src.data_loader import fetch_or_load_data
from src.indicators import precompute_indicators
from src.backtester import run_backtest
from src.metrics import compute_metrics


def evaluate_single_ibs_run(
    df_ind: pd.DataFrame,
    ibs_entry: float,
    ibs_exit: float,
    max_hold: int,
    target_risk_pct: float,
    max_leverage: float,
    use_shock_damped_adr: bool,
) -> dict:
    """
    Adapter wrapper around src.backtester.run_backtest with T-Bill Yield disabled.
    Agent note: Align exact keyword arguments with src/backtester.py.
    """
    bt_res = run_backtest(
        df_ind,
        ibs_entry=ibs_entry,
        ibs_exit=ibs_exit,
        ibs_max_hold=max_hold,
        target_risk_pct=target_risk_pct,
        max_leverage=max_leverage,
        use_shock_damped_adr=use_shock_damped_adr,
        use_cash_yield=False,  # Strictly ignore Floating T-Bill Yield
    )
    return bt_res


def build_3d_plateau_tensor(
    df_slice: pd.DataFrame,
    entry_grid: np.ndarray,
    exit_grid: np.ndarray,
    hold_grid: np.ndarray,
    target_risk_pct: float,
    max_leverage: float,
    use_shock_damped_adr: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Builds 3D Sharpe and Trade Count tensors for Strategy A (IBS Solo)."""
    df_ind = precompute_indicators(df_slice.copy())
    years = max((df_slice.index[-1] - df_slice.index[0]).days / 365.25, 1.0)
    min_trades_req = 20.0 * years

    shape = (len(entry_grid), len(exit_grid), len(hold_grid))
    sr_tensor = np.full(shape, np.nan, dtype=np.float64)
    tr_tensor = np.zeros(shape, dtype=np.int32)

    for i, e_in in enumerate(entry_grid):
        for j, e_out in enumerate(exit_grid):
            if (e_out - e_in) < 0.35:
                continue
            for k, max_h in enumerate(hold_grid):
                bt = evaluate_single_ibs_run(
                    df_ind=df_ind,
                    ibs_entry=float(e_in),
                    ibs_exit=float(e_out),
                    max_hold=int(max_h),
                    target_risk_pct=target_risk_pct,
                    max_leverage=max_leverage,
                    use_shock_damped_adr=use_shock_damped_adr,
                )
                rets = bt["strat_a_ret"]
                n_trades = int(bt["strat_a_trades"])
                tr_tensor[i, j, k] = n_trades

                std = rets.std(ddof=1)
                if std > 1e-8 and n_trades >= 5:
                    raw_sr = (rets.mean() / std) * np.sqrt(252.0)
                    freq_scale = min(1.0, np.sqrt(n_trades / min_trades_req))
                    sr_tensor[i, j, k] = raw_sr * freq_scale
                else:
                    sr_tensor[i, j, k] = 0.0

    return sr_tensor, tr_tensor


def extract_top_plateau_params(
    sr_tensor: np.ndarray,
    tr_tensor: np.ndarray,
    entry_grid: np.ndarray,
    exit_grid: np.ndarray,
    hold_grid: np.ndarray,
    sigma: float = 1.0,
    lambda_pen: float = 0.5,
    top_k: int = 3,
) -> list[dict]:
    """Selects the #1 Plateau Centroid and Top-K spatially distinct ensemble parameters."""
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
                "ibs_entry": float(entry_grid[i]),
                "ibs_exit": float(exit_grid[j]),
                "max_hold": int(hold_grid[k]),
                "plateau_score": round(float(objective[coord]), 4),
                "adjusted_sharpe": round(float(sr_tensor[coord]), 4),
                "neighborhood_std": round(float(local_std[coord]), 4),
                "total_trades": int(tr_tensor[coord]),
            })
            if len(selected) >= top_k:
                break

    return selected


def run_rolling_wfo_track(
    df: pd.DataFrame,
    entry_grid: np.ndarray,
    exit_grid: np.ndarray,
    hold_grid: np.ndarray,
    is_years: int,
    oos_years: int,
    target_risk_pct: float,
    max_leverage: float,
    use_shock_damped_adr: bool,
) -> tuple[pd.DataFrame, dict]:
    """Runs Rolling WFO on Strategy A for either Shock-Damped ON or OFF."""
    is_bars = is_years * 252
    oos_bars = oos_years * 252
    folds = []

    for start in range(0, len(df) - is_bars - oos_bars + 1, oos_bars):
        is_df = df.iloc[start : start + is_bars]
        oos_df = df.iloc[start + is_bars : start + is_bars + oos_bars]

        sr_t, tr_t = build_3d_plateau_tensor(
            is_df, entry_grid, exit_grid, hold_grid,
            target_risk_pct, max_leverage, use_shock_damped_adr
        )
        winner = extract_top_plateau_params(
            sr_t, tr_t, entry_grid, exit_grid, hold_grid, top_k=1
        )[0]

        oos_ind = precompute_indicators(oos_df.copy())
        oos_bt = evaluate_single_ibs_run(
            df_ind=oos_ind,
            ibs_entry=winner["ibs_entry"],
            ibs_exit=winner["ibs_exit"],
            max_hold=winner["max_hold"],
            target_risk_pct=target_risk_pct,
            max_leverage=max_leverage,
            use_shock_damped_adr=use_shock_damped_adr,
        )
        oos_rets = oos_bt["strat_a_ret"]
        oos_std = oos_rets.std(ddof=1)
        oos_sr = (oos_rets.mean() / oos_std) * np.sqrt(252.0) if oos_std > 1e-8 else 0.0

        folds.append({
            "oos_period": f"{oos_df.index[0]:%Y-%m-%d} to {oos_df.index[-1]:%Y-%m-%d}",
            "entry": winner["ibs_entry"],
            "exit": winner["ibs_exit"],
            "hold": winner["max_hold"],
            "is_sharpe": winner["adjusted_sharpe"],
            "oos_sharpe": round(float(oos_sr), 4),
            "oos_trades": int(oos_bt["strat_a_trades"]),
        })

    wfo_df = pd.DataFrame(folds)
    mean_is = float(wfo_df["is_sharpe"].mean())
    mean_oos = float(wfo_df["oos_sharpe"].mean())
    summary = {
        "mean_is_sharpe": round(mean_is, 4),
        "mean_oos_sharpe": round(mean_oos, 4),
        "wfe_ratio": round(mean_oos / max(mean_is, 1e-6), 4),
        "positive_oos_folds_pct": round(float((wfo_df["oos_sharpe"] > 0).mean() * 100.0), 2),
    }
    return wfo_df, summary


def evaluate_stage2_overlay(
    df: pd.DataFrame,
    ideal_param: dict,
    ensemble_params: list[dict],
    target_risk_pct: float,
    max_leverage: float,
    use_shock_damped_adr: bool,
) -> dict:
    """
    Plugs the winning Strategy A parameters into Strategy A Solo and Combined 100/100 Overlay (A+B).
    Also evaluates the 3-Parameter Equal-Weight Ensemble.
    """
    df_ind = precompute_indicators(df.copy())
    zero_rf = pd.Series(0.0, index=df_ind.index)

    # 1. Ideal Centroid Evaluation (A Solo & Combined A+B)
    bt_ideal = evaluate_single_ibs_run(
        df_ind=df_ind,
        ibs_entry=ideal_param["ibs_entry"],
        ibs_exit=ideal_param["ibs_exit"],
        max_hold=ideal_param["max_hold"],
        target_risk_pct=target_risk_pct,
        max_leverage=max_leverage,
        use_shock_damped_adr=use_shock_damped_adr,
    )
    metrics_a_ideal = compute_metrics(
        bt_ideal["strat_a_ret"], zero_rf, bt_ideal["strat_a_trades"], bt_ideal["strat_a_wins"]
    )
    metrics_ab_ideal = compute_metrics(
        bt_ideal["combined_ret"], zero_rf, bt_ideal["combined_trades"], bt_ideal["combined_wins"]
    )

    # 2. 3-Set Equal-Weight Ensemble Evaluation (1/3 weight to each plateau node)
    ens_a_rets = []
    ens_ab_rets = []
    ens_a_trades = 0
    ens_ab_trades = 0

    for p in ensemble_params:
        bt_sub = evaluate_single_ibs_run(
            df_ind=df_ind,
            ibs_entry=p["ibs_entry"],
            ibs_exit=p["ibs_exit"],
            max_hold=p["max_hold"],
            target_risk_pct=target_risk_pct,
            max_leverage=max_leverage,
            use_shock_damped_adr=use_shock_damped_adr,
        )
        ens_a_rets.append(bt_sub["strat_a_ret"])
        ens_ab_rets.append(bt_sub["combined_ret"])
        ens_a_trades += int(bt_sub["strat_a_trades"])
        ens_ab_trades += int(bt_sub["combined_trades"])

    blended_a_ret = pd.concat(ens_a_rets, axis=1).mean(axis=1)
    blended_ab_ret = pd.concat(ens_ab_rets, axis=1).mean(axis=1)

    metrics_a_ensemble = compute_metrics(blended_a_ret, zero_rf, int(ens_a_trades / len(ensemble_params)), 0)
    metrics_ab_ensemble = compute_metrics(blended_ab_ret, zero_rf, int(ens_ab_trades / len(ensemble_params)), 0)

    return {
        "strategy_a_solo_ideal": metrics_a_ideal,
        "strategy_a_solo_3x_ensemble": metrics_a_ensemble,
        "combined_ab_overlay_ideal": metrics_ab_ideal,
        "combined_ab_overlay_3x_ensemble": metrics_ab_ensemble,
    }


def main():
    parser = argparse.ArgumentParser(description="IBS Plateau Optimizer & Shock-Damped ADR Side-by-Side CLI")
    parser.add_argument("--is-years", type=int, default=5)
    parser.add_argument("--oos-years", type=int, default=1)
    parser.add_argument("--risk-adr", type=float, default=0.0125)
    parser.add_argument("--max-lev", type=float, default=2.0)
    parser.add_argument("--export-dir", type=str, default="INFO")
    args = parser.parse_args()

    df = fetch_or_load_data()
    entry_grid = np.array([0.10, 0.15, 0.20, 0.25, 0.30])
    exit_grid  = np.array([0.50, 0.60, 0.70, 0.80, 0.85])
    hold_grid  = np.array([3, 4, 5, 6, 7, 8])

    ablation_results = {}

    for mode_label, damped_flag in [("SHOCK_DAMPED_ADR_ON", True), ("STANDARD_ADR_OFF", False)]:
        print(f"\n>>> Running Stage 1 & 2 Pipeline for [{mode_label}] (T-Bill Yield = OFF)...")
        wfo_df, wfo_summary = run_rolling_wfo_track(
            df, entry_grid, exit_grid, hold_grid,
            args.is_years, args.oos_years, args.risk_adr, args.max_lev,
            use_shock_damped_adr=damped_flag,
        )

        full_sr, full_tr = build_3d_plateau_tensor(
            df, entry_grid, exit_grid, hold_grid,
            args.risk_adr, args.max_lev, use_shock_damped_adr=damped_flag
        )
        top_ensemble = extract_top_plateau_params(
            full_sr, full_tr, entry_grid, exit_grid, hold_grid, top_k=3
        )
        ideal_centroid = top_ensemble[0]

        stage2_eval = evaluate_stage2_overlay(
            df, ideal_centroid, top_ensemble,
            args.risk_adr, args.max_lev, use_shock_damped_adr=damped_flag
        )

        ablation_results[mode_label] = {
            "use_shock_damped_adr": damped_flag,
            "use_tbill_cash_yield": False,
            "wfo_summary": wfo_summary,
            "wfo_folds": wfo_df.to_dict(orient="records"),
            "ideal_centroid_params": ideal_centroid,
            "top_3_ensemble_params": top_ensemble,
            "stage2_performance": stage2_eval,
        }

    out_dir = Path(args.export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_file = out_dir / "optimal_ibs_ablation.json"
    json_file.write_text(json.dumps(ablation_results, indent=2))
    print(f"\n[OK] Exported JSON payload to {json_file}")


if __name__ == "__main__":
    main()
```

---

## 4. Required Output Artifacts & Side-by-Side Comparison Matrix

The coding agent must also generate a formatted Markdown report at `INFO/OPTIMIZATION_SIDE_BY_SIDE_REPORT.md` containing the following comparison tables:

### Table 1: Stage 1 — Strategy A (IBS Solo) Optimization & WFO Comparison (`^IRX` Disabled)
| Metric | Track 1: Strategy A (`Shock-Damped ADR = ON`) | Track 2: Strategy A (`Standard Raw ADR = OFF`) | Delta / Verdict |
| :--- | :--- | :--- | :--- |
| **Winning Centroid (`Entry`, `Exit`, `Hold`)** | `(e_in, e_out, h)` | `(e_in, e_out, h)` | Parameter shift check |
| **Top-3 Ensemble Tuples** | `[Tuple 1, Tuple 2, Tuple 3]` | `[Tuple 1, Tuple 2, Tuple 3]` | Plateau stability |
| **3D Plateau Score $J(\theta^*)$** | `X.XX` | `X.XX` | Higher = flatter/more stable |
| **Local Neighborhood Std $\sigma_{\mathcal{N}}$** | `X.XX` | `X.XX` | Lower = less cliff risk |
| **Rolling WFO Mean IS Sharpe** | `X.XX` | `X.XX` | In-sample baseline |
| **Rolling WFO Mean OOS Sharpe** | `X.XX` | `X.XX` | Out-of-sample realization |
| **Walk-Forward Efficiency (WFE)** | `XX.X%` | `XX.X%` | `> 60%` = Robust |
| **Strategy A Solo CAGR (%)** | `XX.XX%` | `XX.XX%` | Pure IBS compounding |
| **Strategy A Solo Sharpe Ratio** | `X.XX` | `X.XX` | Risk-adjusted edge |
| **Strategy A Solo Sortino Ratio** | `X.XX` | `X.XX` | Downside tail control |
| **Strategy A Solo Max Drawdown (%)** | `-XX.XX%` | `-XX.XX%` | Crash resilience |
| **Strategy A Total Trades** | `XXX` | `XXX` | Sample size check |

### Table 2: Stage 2 — Combined 100/100 Overlay (Strategy A + Strategy B 12M Momentum) Plug-In Results
| Metric | A+B Ideal Centroid (`Damped ON`) | A+B Ideal Centroid (`Damped OFF`) | A+B 3x Ensemble (`Damped ON`) | A+B 3x Ensemble (`Damped OFF`) |
| :--- | :--- | :--- | :--- | :--- |
| **Final Equity ($10k Start)** | `$X,XXX,XXX` | `$X,XXX,XXX` | `$X,XXX,XXX` | `$X,XXX,XXX` |
| **CAGR (%)** | `XX.XX%` | `XX.XX%` | `XX.XX%` | `XX.XX%` |
| **Annualized Volatility (%)** | `XX.XX%` | `XX.XX%` | `XX.XX%` | `XX.XX%` |
| **Sharpe Ratio (0% RF)** | `X.XX` | `X.XX` | `X.XX` | `X.XX` |
| **Sortino Ratio** | `X.XX` | `X.XX` | `X.XX` | `X.XX` |
| **Max Drawdown (%)** | `-XX.XX%` | `-XX.XX%` | `-XX.XX%` | `-XX.XX%` |
| **Calmar Ratio** | `X.XX` | `X.XX` | `X.XX` | `X.XX` |

---

## 5. Agent Decision Gate & Verification Checklist

1. **Inspection Step First:** Before writing code, inspect `src/backtester.py` and `src/indicators.py` to see how `use_shock_damped_adr` is currently computed. If `run_backtest()` switches between `ADR_Eff` (Shock-Damped) and raw `ADR_20` (Standard), wire the boolean flag `use_shock_damped_adr: bool = True` directly into `run_backtest()`.
2. **Strict Zero Cash Yield:** Ensure `rf_series` / `^IRX` cash compounding is set to `0.0` during all Stage 1 and Stage 2 runs so T-Bill rates do not distort parameter selection or the ADR ablation comparison.
3. **Zero Lookahead Verification:** Ensure `scipy.ndimage.gaussian_filter` is only applied to the In-Sample tensor inside each WFO fold, never leaking future OOS returns.
4. **Automated Decision Verdict:** In the generated report `INFO/OPTIMIZATION_SIDE_BY_SIDE_REPORT.md`, automatically flag whether **Shock-Damped Effective ADR** should be kept or dropped based on this rule:
   * **Keep Shock-Damped ADR** only if it improves Strategy A's **Calmar Ratio** or **OOS Sharpe Ratio** by $\ge 5\%$ OR reduces **Max Drawdown** by $\ge 1.5\%$ without shifting the plateau centroid into a cliff. Otherwise, recommend simplifying to **Standard Raw ADR**.
5. **Test Suite Pass:** Run `pytest tests/test_quant_lab.py` and `python optimize_cli.py` to verify all artifacts generate cleanly with zero errors.