---
name: ibs-optimization
description: >-
  Use this skill whenever the user wants to optimize Strategy A (IBS Mean-Reversion),
  run the Shock-Damped Effective ADR vs. Standard Raw ADR A/B ablation study,
  execute rolling walk-forward optimization (WFO), or re-evaluate the 3D Gaussian
  plateau parameters and Combined 100/100 Overlay plug-in.
---

# 🏔️ IBS Plateau Optimization & ADR Ablation Skill

This skill teaches the agent how to execute the two-stage **IBS Gaussian Plateau Optimization** and the **Shock-Damped Effective ADR vs. Standard Raw ADR Ablation Study** for the Nasdaq-100 Cash Index (`^NDX`).

---

## 🚀 Quick Execution

Run the standalone CLI runner from the project root:

```bash
python optimize_cli.py
```

### Custom Parameter Overrides:
```bash
python optimize_cli.py --risk-adr 0.0125 --max-lev 2.0 --is-years 5 --oos-years 1 --initial-capital 10000 --export-dir INFO
```

CLI Argument | Default | Description
:--- | :--- | :---
`--risk-adr` | `0.0125` (1.25%) | Flat risk budget per ADR applied equally to IBS and Momentum.
`--max-lev` | `2.0` (2.0x) | Static maximum leverage cap for the master 100/100 Overlay.
`--is-years` | `5` (1,260 bars) | Rolling In-Sample training window length.
`--oos-years` | `1` (252 bars) | Rolling Out-of-Sample evaluation window length.
`--initial-capital` | `10000.0` | Portfolio starting capital for compounding evaluations.
`--export-dir` | `INFO` | Output folder for JSON data and Markdown reports.

---

## 📐 Optimization Architecture

1. **A/B Ablation Gauntlet:**
   - **Track 1 (`SHOCK_DAMPED_ADR_ON`):** Position sizing denominator uses $\max(\text{ADR}_{14}, \text{TR} / 1.75)$.
   - **Track 2 (`STANDARD_ADR_OFF`):** Position sizing denominator uses standard raw $\text{ADR}_{14}$.
   - **Zero Cash Yield Control:** Floating T-Bill yield (`^IRX`) is strictly $0.0\%$ to measure pure alpha.

2. **Stage 1 — Strategy A (IBS Solo):**
   - **Coarse Grid:** Entry $\in \{0.10, 0.15, 0.20, 0.25, 0.30\}$, Exit $\in \{0.50, 0.60, 0.70, 0.80, 0.85\}$, Hold $\in \{3, 4, 5, 6, 7, 8\}$.
   - **Structural Constraint:** Masks out pairs where $(\text{Exit} - \text{Entry}) < 0.35$.
   - **Frequency Adjustment:** $S_{\text{adj}} = S_{\text{raw}} \times \min(1.0, \sqrt{N_{\text{trades}} / (20 \times N_{\text{years}})})$.
   - **3D Gaussian Plateau Filter:** $J(\theta) = \text{GaussianSmooth}_{3\text{D}}(S_{\text{adj}}, \sigma=1.0) - 0.5 \times \text{LocalStd}_{3\times 3\times 3}(S_{\text{adj}})$.
   - **Top-3 Spatial Ensemble:** Selects top 3 plateau members with Manhattan distance $\|\Delta \text{coord}\|_1 \ge 2$.
   - **Rolling Walk-Forward:** 15 cycles (5Y IS / 1Y OOS) computing Walk-Forward Efficiency ($\text{WFE} = \text{Mean OOS} / \text{Mean IS}$).

3. **Stage 2 — Master Overlay Plug-In:**
   - Plugs the winning Centroid and 3-Parameter Ensemble into Strategy A Solo and Combined 100/100 Overlay (IBS + 12M Momentum).

---

## 📂 Generated Artifacts & Reports

After running the workflow, verify that all artifacts are updated:

1. **JSON Payload:** `INFO/optimal_ibs_ablation.json` (Full numerical parameters, WFO folds, and stage 2 metrics).
2. **Side-by-Side Markdown Report:** `INFO/OPTIMIZATION_SIDE_BY_SIDE_REPORT.md` (Table 1, Table 2, and Decision Gate Verdict).
3. **Interactive HTML Dashboard:** `optimization_results.html` (Double-clickable in browser for visual exploration).

---

## 🧪 Verification & Regression Testing

Always run the 13-suite test harness before and after any modifications:

```bash
python tests/test_quant_lab.py
```
Ensure all 13 tests return `[OK]` and exit with status code 0.
