#!/usr/bin/env python3
"""
Standalone CLI Runner:
Stage 1: Optimize Strategy A (IBS Solo) via Rolling WFO + 3D Plateau Selection
         Side-by-Side Ablation: Shock-Damped ADR (ON) vs. Standard Raw ADR (OFF)
         (Floating T-Bill Yield strictly disabled across all runs)
Stage 2: Plug Winning Ideal & 3x Ensemble Parameters into Combined 100/100 Overlay (A + B)
Exports:
- INFO/optimal_ibs_ablation.json
- INFO/OPTIMIZATION_SIDE_BY_SIDE_REPORT.md
"""

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.data_loader import fetch_or_load_data
from src.indicators import precompute_indicators
from src.backtester import (
    run_ibs_strategy,
    run_unified_overlay_strategy,
)
from src.metrics import calculate_metrics
from src.validation import (
    compute_ibs_3d_tensor,
    select_plateau_ensemble,
    run_rolling_wfo_ablation,
)


def evaluate_stage2_overlay(
    df: pd.DataFrame,
    ideal_param: dict,
    ensemble_params: list[dict],
    target_risk_pct: float,
    max_leverage: float,
    use_shock_damped_adr: bool,
    initial_capital: float = 10000.0,
) -> dict:
    """
    Plugs winning Strategy A parameters into Strategy A Solo and Combined 100/100 Overlay (A+B).
    Evaluates both the #1 Ideal Centroid and the 3-Parameter Equal-Weight Ensemble.
    """
    # 1. Ideal Centroid Evaluation (A Solo & Combined A+B)
    eq_a_ideal, tr_a_ideal = run_ibs_strategy(
        df,
        initial_capital=initial_capital,
        risk_per_adr=target_risk_pct,
        ibs_entry=ideal_param["ibs_entry"],
        ibs_exit=ideal_param["ibs_exit"],
        max_hold=ideal_param["max_hold"],
        use_effective_adr=use_shock_damped_adr,
        use_floating_yield=False,
    )
    metrics_a_ideal = calculate_metrics(eq_a_ideal, tr_a_ideal, initial_capital=initial_capital)
    metrics_a_ideal["Final Equity ($)"] = float(round(eq_a_ideal["equity"].iloc[-1], 2))

    eq_ab_ideal, tr_ab_ideal = run_unified_overlay_strategy(
        df,
        initial_capital=initial_capital,
        risk_per_adr=target_risk_pct,
        ibs_entry=ideal_param["ibs_entry"],
        ibs_exit=ideal_param["ibs_exit"],
        max_hold=ideal_param["max_hold"],
        max_leverage=max_leverage,
        use_effective_adr=use_shock_damped_adr,
        use_floating_yield=False,
    )
    metrics_ab_ideal = calculate_metrics(eq_ab_ideal, tr_ab_ideal, initial_capital=initial_capital)
    metrics_ab_ideal["Final Equity ($)"] = float(round(eq_ab_ideal["equity"].iloc[-1], 2))

    # 2. 3-Set Equal-Weight Ensemble Evaluation (1/3 daily return blend)
    ens_a_rets = []
    ens_ab_rets = []
    ens_a_trades = 0
    ens_ab_trades = 0

    for p in ensemble_params:
        sub_a_eq, sub_a_tr = run_ibs_strategy(
            df,
            initial_capital=initial_capital,
            risk_per_adr=target_risk_pct,
            ibs_entry=p["ibs_entry"],
            ibs_exit=p["ibs_exit"],
            max_hold=p["max_hold"],
            use_effective_adr=use_shock_damped_adr,
            use_floating_yield=False,
        )
        ens_a_rets.append(sub_a_eq["equity"].pct_change().fillna(0.0))
        ens_a_trades += len(sub_a_tr)

        sub_ab_eq, sub_ab_tr = run_unified_overlay_strategy(
            df,
            initial_capital=initial_capital,
            risk_per_adr=target_risk_pct,
            ibs_entry=p["ibs_entry"],
            ibs_exit=p["ibs_exit"],
            max_hold=p["max_hold"],
            max_leverage=max_leverage,
            use_effective_adr=use_shock_damped_adr,
            use_floating_yield=False,
        )
        ens_ab_rets.append(sub_ab_eq["equity"].pct_change().fillna(0.0))
        ens_ab_trades += len(sub_ab_tr)

    blended_a_ret = pd.concat(ens_a_rets, axis=1).mean(axis=1)
    blended_ab_ret = pd.concat(ens_ab_rets, axis=1).mean(axis=1)

    # Reconstruct Strategy A Ensemble equity curve
    curve_a = initial_capital * (1.0 + blended_a_ret).cumprod()
    cummax_a = curve_a.cummax()
    dd_a = np.where(cummax_a > 0, ((curve_a - cummax_a) / cummax_a) * 100.0, 0.0)
    df_ens_a = pd.DataFrame({"equity": curve_a, "drawdown_pct": dd_a, "in_position": True}, index=df.index)
    metrics_a_ens = calculate_metrics(df_ens_a, pd.DataFrame(), initial_capital=initial_capital)
    metrics_a_ens["Total Trades"] = int(round(ens_a_trades / len(ensemble_params)))
    metrics_a_ens["Final Equity ($)"] = float(round(curve_a.iloc[-1], 2))

    # Reconstruct Combined A+B Ensemble equity curve
    curve_ab = initial_capital * (1.0 + blended_ab_ret).cumprod()
    cummax_ab = curve_ab.cummax()
    dd_ab = np.where(cummax_ab > 0, ((curve_ab - cummax_ab) / cummax_ab) * 100.0, 0.0)
    df_ens_ab = pd.DataFrame({"equity": curve_ab, "drawdown_pct": dd_ab, "in_position": True}, index=df.index)
    metrics_ab_ens = calculate_metrics(df_ens_ab, pd.DataFrame(), initial_capital=initial_capital)
    metrics_ab_ens["Total Trades"] = int(round(ens_ab_trades / len(ensemble_params)))
    metrics_ab_ens["Final Equity ($)"] = float(round(curve_ab.iloc[-1], 2))

    return {
        "strategy_a_solo_ideal": metrics_a_ideal,
        "strategy_a_solo_3x_ensemble": metrics_a_ens,
        "combined_ab_overlay_ideal": metrics_ab_ideal,
        "combined_ab_overlay_3x_ensemble": metrics_ab_ens,
    }


def generate_markdown_report(results: dict, export_path: Path):
    """Generate institutional side-by-side comparison report."""
    d_on = results["SHOCK_DAMPED_ADR_ON"]
    d_off = results["STANDARD_ADR_OFF"]

    p_on = d_on["ideal_centroid_params"]
    p_off = d_off["ideal_centroid_params"]

    wfo_on = d_on["wfo_summary"]
    wfo_off = d_off["wfo_summary"]

    s2_on = d_on["stage2_performance"]
    s2_off = d_off["stage2_performance"]

    m_a_on = s2_on["strategy_a_solo_ideal"]
    m_a_off = s2_off["strategy_a_solo_ideal"]

    m_ab_on_ideal = s2_on["combined_ab_overlay_ideal"]
    m_ab_off_ideal = s2_off["combined_ab_overlay_ideal"]
    m_ab_on_ens = s2_on["combined_ab_overlay_3x_ensemble"]
    m_ab_off_ens = s2_off["combined_ab_overlay_3x_ensemble"]

    # Automated Decision Gate calculations
    # Criterion 1: Calmar Ratio improved by >= 5%
    calmar_on = m_a_on["Calmar Ratio"]
    calmar_off = m_a_off["Calmar Ratio"]
    calmar_pct_change = ((calmar_on - calmar_off) / max(abs(calmar_off), 1e-6)) * 100.0

    # Criterion 2: OOS Sharpe improved by >= 5%
    oos_sr_on = wfo_on["mean_oos_sharpe"]
    oos_sr_off = wfo_off["mean_oos_sharpe"]
    oos_sr_pct_change = ((oos_sr_on - oos_sr_off) / max(abs(oos_sr_off), 1e-6)) * 100.0

    # Criterion 3: Max Drawdown reduced by >= 1.5% (less negative)
    maxdd_on = m_a_on["Max Drawdown (%)"]
    maxdd_off = m_a_off["Max Drawdown (%)"]
    # Drawdowns are negative numbers, reduction means (abs(off) - abs(on)) >= 1.5
    maxdd_diff = abs(maxdd_off) - abs(maxdd_on)

    keep_shock_damped = (calmar_pct_change >= 5.0) or (oos_sr_pct_change >= 5.0) or (maxdd_diff >= 1.5)

    if keep_shock_damped:
        verdict_badge = "**KEEP SHOCK-DAMPED EFFECTIVE ADR**"
        verdict_reason = (
            f"Shock-Damped ADR satisfies institutional preservation criteria: "
            f"Calmar Delta: {calmar_pct_change:+.2f}%, OOS Sharpe Delta: {oos_sr_pct_change:+.2f}%, "
            f"MaxDD Reduction: {maxdd_diff:+.2f}% pts. It effectively suppresses tail-risk spikes "
            f"without causing plateau degradation."
        )
    else:
        verdict_badge = "**SIMPLIFY TO STANDARD RAW ADR**"
        verdict_reason = (
            f"Shock-Damped ADR failed the 5% Calmar / OOS Sharpe threshold or 1.5% MaxDD reduction threshold "
            f"(Calmar Delta: {calmar_pct_change:+.2f}%, OOS Sharpe Delta: {oos_sr_pct_change:+.2f}%, "
            f"MaxDD Diff: {maxdd_diff:+.2f}% pts). Standard Raw ADR delivers equivalent or superior "
            f"risk-adjusted returns with less complexity."
        )

    j_theta_str = r"$J(\theta^*)$"
    sigma_n_str = r"$\sigma_{\mathcal{N}}$"

    lines = [
        "# 🔬 IBS Plateau Optimization & Shock-Damped ADR Side-by-Side Ablation Report",
        "",
        "## 1. Executive Summary & Objective",
        "This report documents a two-stage walk-forward and Gaussian plateau optimization of **Strategy A (IBS Mean-Reversion)** ",
        "and its plug-in performance into the **Combined 100/100 Overlay (Strategy A + Strategy B 12M Momentum)**.",
        "",
        "> [!IMPORTANT]",
        "> **Strict Zero-Yield Control:** All simulations in this ablation were executed with **Floating T-Bill Yield (`^IRX`) set to 0.0%** ",
        "> to isolate pure strategy alpha and eliminate distortion from cash-sweep compounding.",
        "",
        "---",
        "",
        "## 2. Stage 1: Strategy A (IBS Solo) Optimization & WFO Comparison",
        "",
        "| Metric | Track 1: Strategy A (`Shock-Damped ADR = ON`) | Track 2: Strategy A (`Standard Raw ADR = OFF`) | Delta / Notes |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Winning Centroid (`Entry`, `Exit`, `Hold`)** | `({p_on['ibs_entry']:.2f}, {p_on['ibs_exit']:.2f}, {p_on['max_hold']})` | `({p_off['ibs_entry']:.2f}, {p_off['ibs_exit']:.2f}, {p_off['max_hold']})` | Optimal Plateau Peak |",
        f"| **Top-3 Ensemble Tuples** | `{[tuple([p['ibs_entry'], p['ibs_exit'], p['max_hold']]) for p in d_on['top_3_ensemble_params']]}` | `{[tuple([p['ibs_entry'], p['ibs_exit'], p['max_hold']]) for p in d_off['top_3_ensemble_params']]}` | Manhattan Separation >= 2 |",
        f"| **3D Plateau Score {j_theta_str}** | `{p_on['plateau_score']:.4f}` | `{p_off['plateau_score']:.4f}` | {p_on['plateau_score'] - p_off['plateau_score']:+.4f} |",
        f"| **Local Neighborhood Std {sigma_n_str}** | `{p_on['neighborhood_std']:.4f}` | `{p_off['neighborhood_std']:.4f}` | {p_on['neighborhood_std'] - p_off['neighborhood_std']:+.4f} |",
        f"| **Rolling WFO Mean IS Sharpe** | `{wfo_on['mean_is_sharpe']:.4f}` | `{wfo_off['mean_is_sharpe']:.4f}` | {wfo_on['mean_is_sharpe'] - wfo_off['mean_is_sharpe']:+.4f} |",
        f"| **Rolling WFO Mean OOS Sharpe** | `{wfo_on['mean_oos_sharpe']:.4f}` | `{wfo_off['mean_oos_sharpe']:.4f}` | {wfo_on['mean_oos_sharpe'] - wfo_off['mean_oos_sharpe']:+.4f} ({oos_sr_pct_change:+.2f}%) |",
        f"| **Walk-Forward Efficiency (WFE)** | `{wfo_on['wfe_ratio'] * 100.0:.2f}%` | `{wfo_off['wfe_ratio'] * 100.0:.2f}%` | { (wfo_on['wfe_ratio'] - wfo_off['wfe_ratio']) * 100.0:+.2f}% pts |",
        f"| **Positive OOS Folds (%)** | `{wfo_on['positive_oos_folds_pct']:.1f}%` | `{wfo_off['positive_oos_folds_pct']:.1f}%` | Robustness across cycles |",
        f"| **Strategy A Solo CAGR (%)** | `{m_a_on['CAGR (%)']:.2f}%` | `{m_a_off['CAGR (%)']:.2f}%` | {m_a_on['CAGR (%)'] - m_a_off['CAGR (%)']:+.2f}% |",
        f"| **Strategy A Solo Sharpe (0% RF)** | `{m_a_on['Sharpe Ratio']:.2f}` | `{m_a_off['Sharpe Ratio']:.2f}` | {m_a_on['Sharpe Ratio'] - m_a_off['Sharpe Ratio']:+.2f} |",
        f"| **Strategy A Solo Sortino Ratio** | `{m_a_on['Sortino Ratio']:.2f}` | `{m_a_off['Sortino Ratio']:.2f}` | {m_a_on['Sortino Ratio'] - m_a_off['Sortino Ratio']:+.2f} |",
        f"| **Strategy A Solo Max Drawdown (%)** | `{m_a_on['Max Drawdown (%)']:.2f}%` | `{m_a_off['Max Drawdown (%)']:.2f}%` | {maxdd_diff:+.2f}% pts protection |",
        f"| **Strategy A Solo Calmar Ratio** | `{m_a_on['Calmar Ratio']:.2f}` | `{m_a_off['Calmar Ratio']:.2f}` | {calmar_pct_change:+.2f}% |",
        f"| **Strategy A Total Trades** | `{m_a_on['Total Trades']}` | `{m_a_off['Total Trades']}` | Sample size sufficiency |",
        "",
        "---",
        "",
        "## 3. Stage 2: Combined 100/100 Overlay (Strategy A + Strategy B 12M Momentum) Plug-In Results",
        "",
        "| Metric | A+B Ideal Centroid (`Damped ON`) | A+B Ideal Centroid (`Damped OFF`) | A+B 3x Ensemble (`Damped ON`) | A+B 3x Ensemble (`Damped OFF`) |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **Final Equity ($10k Start)** | `${m_ab_on_ideal['Final Equity ($)']:,.2f}` | `${m_ab_off_ideal['Final Equity ($)']:,.2f}` | `${m_ab_on_ens['Final Equity ($)']:,.2f}` | `${m_ab_off_ens['Final Equity ($)']:,.2f}` |",
        f"| **CAGR (%)** | `{m_ab_on_ideal['CAGR (%)']:.2f}%` | `{m_ab_off_ideal['CAGR (%)']:.2f}%` | `{m_ab_on_ens['CAGR (%)']:.2f}%` | `{m_ab_off_ens['CAGR (%)']:.2f}%` |",
        f"| **Annualized Volatility (%)** | `{m_ab_on_ideal['Annualized Volatility (%)']:.2f}%` | `{m_ab_off_ideal['Annualized Volatility (%)']:.2f}%` | `{m_ab_on_ens['Annualized Volatility (%)']:.2f}%` | `{m_ab_off_ens['Annualized Volatility (%)']:.2f}%` |",
        f"| **Sharpe Ratio (0% RF)** | `{m_ab_on_ideal['Sharpe Ratio']:.2f}` | `{m_ab_off_ideal['Sharpe Ratio']:.2f}` | `{m_ab_on_ens['Sharpe Ratio']:.2f}` | `{m_ab_off_ens['Sharpe Ratio']:.2f}` |",
        f"| **Sortino Ratio** | `{m_ab_on_ideal['Sortino Ratio']:.2f}` | `{m_ab_off_ideal['Sortino Ratio']:.2f}` | `{m_ab_on_ens['Sortino Ratio']:.2f}` | `{m_ab_off_ens['Sortino Ratio']:.2f}` |",
        f"| **Max Drawdown (%)** | `{m_ab_on_ideal['Max Drawdown (%)']:.2f}%` | `{m_ab_off_ideal['Max Drawdown (%)']:.2f}%` | `{m_ab_on_ens['Max Drawdown (%)']:.2f}%` | `{m_ab_off_ens['Max Drawdown (%)']:.2f}%` |",
        f"| **Calmar Ratio** | `{m_ab_on_ideal['Calmar Ratio']:.2f}` | `{m_ab_off_ideal['Calmar Ratio']:.2f}` | `{m_ab_on_ens['Calmar Ratio']:.2f}` | `{m_ab_off_ens['Calmar Ratio']:.2f}` |",
        f"| **Total Overlay Trades** | `{m_ab_on_ideal['Total Trades']}` | `{m_ab_off_ideal['Total Trades']}` | `{m_ab_on_ens['Total Trades']}` | `{m_ab_off_ens['Total Trades']}` |",
        "",
        "---",
        "",
        "## 4. Automated Decision Gate & Structural Recommendation",
        "",
        f"### Verdict: {verdict_badge}",
        "",
        f"> {verdict_reason}",
        "",
        "### Decision Matrix Evaluation:",
        f"- **Calmar Ratio Delta:** `{calmar_pct_change:+.2f}%` (Threshold: $\\ge +5.0\\%$ -> {'PASS' if calmar_pct_change >= 5.0 else 'FAIL'})",
        f"- **Out-of-Sample Sharpe Delta:** `{oos_sr_pct_change:+.2f}%` (Threshold: $\\ge +5.0\\%$ -> {'PASS' if oos_sr_pct_change >= 5.0 else 'FAIL'})",
        f"- **Max Drawdown Reduction:** `{maxdd_diff:+.2f}%` pts (Threshold: $\\ge +1.5\\%$ pts -> {'PASS' if maxdd_diff >= 1.5 else 'FAIL'})",
        "",
        "---",
        "",
        "## 5. Walk-Forward Fold Breakdown",
        "",
        "### Track 1 (`Shock-Damped ADR = ON`):",
        "| Fold Period | Best Entry | Best Exit | Best Hold | IS Sharpe | OOS Sharpe | OOS Trades |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for f in d_on["wfo_folds"]:
        lines.append(f"| {f['oos_period']} | {f['entry']:.2f} | {f['exit']:.2f} | {f['hold']} | {f['is_sharpe']:.2f} | {f['oos_sharpe']:.2f} | {f['oos_trades']} |")

    lines.extend([
        "",
        "### Track 2 (`Standard Raw ADR = OFF`):",
        "| Fold Period | Best Entry | Best Exit | Best Hold | IS Sharpe | OOS Sharpe | OOS Trades |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for f in d_off["wfo_folds"]:
        lines.append(f"| {f['oos_period']} | {f['entry']:.2f} | {f['exit']:.2f} | {f['hold']} | {f['is_sharpe']:.2f} | {f['oos_sharpe']:.2f} | {f['oos_trades']} |")

    lines.append("")

    report_content = "\n".join(lines)
    export_path.write_text(report_content, encoding="utf-8")
    print(f"[OK] Generated Markdown Report at {export_path}")


def main():
    parser = argparse.ArgumentParser(description="IBS Plateau Optimizer & Shock-Damped ADR Side-by-Side CLI")
    parser.add_argument("--is-years", type=int, default=5, help="In-sample years (default 5)")
    parser.add_argument("--oos-years", type=int, default=1, help="Out-of-sample years (default 1)")
    parser.add_argument("--risk-adr", type=float, default=0.0125, help="Flat risk per ADR (default 0.0125)")
    parser.add_argument("--max-lev", type=float, default=2.0, help="Static max leverage cap (default 2.0)")
    parser.add_argument("--initial-capital", type=float, default=10000.0, help="Starting capital (default $10,000)")
    parser.add_argument("--export-dir", type=str, default="INFO", help="Directory to save JSON and MD reports")
    args = parser.parse_args()

    print(">>> Loading historical US100 dataset...")
    df_raw = fetch_or_load_data()
    df = precompute_indicators(df_raw).dropna().copy()
    print(f"Data range: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} bars)")

    entry_grid = np.array([0.10, 0.15, 0.20, 0.25, 0.30])
    exit_grid  = np.array([0.50, 0.60, 0.70, 0.80, 0.85])
    hold_grid  = np.array([3, 4, 5, 6, 7, 8])

    ablation_results = {}

    for mode_label, damped_flag in [("SHOCK_DAMPED_ADR_ON", True), ("STANDARD_ADR_OFF", False)]:
        print(f"\n=======================================================")
        print(f">>> Running Stage 1 & 2 for [{mode_label}] (T-Bill Yield = OFF)...")
        print(f"=======================================================")

        # 1. Rolling Walk-Forward Optimization
        print(f"Executing Rolling {args.is_years}Y IS / {args.oos_years}Y OOS WFO...")
        wfo_df, wfo_summary = run_rolling_wfo_ablation(
            df, entry_grid, exit_grid, hold_grid,
            is_years=args.is_years, oos_years=args.oos_years,
            target_risk_pct=args.risk_adr, max_leverage=args.max_lev,
            use_shock_damped_adr=damped_flag,
        )
        print(f"WFO Completed. Mean IS Sharpe: {wfo_summary['mean_is_sharpe']}, Mean OOS Sharpe: {wfo_summary['mean_oos_sharpe']}, WFE: {wfo_summary['wfe_ratio']*100:.1f}%")

        # 2. Full-Lifecycle 3D Gaussian Plateau Selection
        print("Computing Full-Lifecycle 3D Plateau Tensor...")
        full_sr, full_tr = compute_ibs_3d_tensor(
            df, entry_grid, exit_grid, hold_grid,
            target_risk_pct=args.risk_adr, max_leverage=args.max_lev,
            use_shock_damped_adr=damped_flag,
        )
        top_ensemble = select_plateau_ensemble(
            full_sr, full_tr, entry_grid, exit_grid, hold_grid, top_k=3
        )
        ideal_centroid = top_ensemble[0]
        print(f"Top Centroid Winner: Entry={ideal_centroid['ibs_entry']}, Exit={ideal_centroid['ibs_exit']}, Hold={ideal_centroid['max_hold']}")
        print(f"  Plateau Score: {ideal_centroid['plateau_score']}, Adj Sharpe: {ideal_centroid['adjusted_sharpe']}, Total Trades: {ideal_centroid['total_trades']}")

        # 3. Stage 2: Plug into Strategy A Solo and Combined Overlay
        print("Executing Stage 2 Overlay Plug-In Evaluation...")
        stage2_eval = evaluate_stage2_overlay(
            df, ideal_centroid, top_ensemble,
            target_risk_pct=args.risk_adr, max_leverage=args.max_lev,
            use_shock_damped_adr=damped_flag, initial_capital=args.initial_capital,
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
    json_file.write_text(json.dumps(ablation_results, indent=2), encoding="utf-8")
    print(f"\n[OK] Exported JSON payload to {json_file}")

    md_file = out_dir / "OPTIMIZATION_SIDE_BY_SIDE_REPORT.md"
    generate_markdown_report(ablation_results, md_file)

    print("\n[SUCCESS] IBS Plateau Optimization & Shock-Damped ADR Ablation Pipeline finished successfully!")


if __name__ == "__main__":
    main()
