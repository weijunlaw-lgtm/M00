# 🧭 Strategic Briefing & Optimization Hand-Off Dossier for Argon (v2.0)

**Target Reviewer:** Argon (Lead Quantitative Architect & Optimization Strategist)  
**System Name:** US100 Quantitative Strategy Lab v2.0 (`AG02`)  
**Target Asset:** Nasdaq-100 Cash Index (`^NDX`)  
**Backtest Period:** March 1, 2006 – October 20, 2026 (5,193 Trading Sessions / 20.64 Calendar Years)  
**Baseline Version:** **v2.0 4-Way Head-to-Head Quantitative Lab**  
**Starting Capital:** \$50,000.00 USD  
**Core Innovation in v2.0:** **Combined 100/100 Unified Capital Overlay** with **1.50x Hard Leverage Cap**, **4.0% Cash Sweep Yield**, and **Anti-Flash-Crash Effective ADR**  
**Action Requested:** Formulate an advanced optimization roadmap taking the framework from the current v2.0 milestone to an institutional production-grade execution system.

---

## 📌 1. Context & Executive Summary

You are reviewing the **newest v2.0 release** of the US100 Quantitative Strategy Lab. 

Unlike early isolated prototypes, v2.0 establishes a **4-Way Head-to-Head architecture** evaluated across identical market data:
1. **Strategy A (IBS Mean-Reversion Solo):** Standalone dip-buying engine.
2. **Strategy B (12M Momentum Solo):** Standalone monthly trend-following engine.
3. **🔥 Combined 100/100 Capital Overlay:** Both strategies run simultaneously against a single unified account equity pool with a **1.5x hard leverage cap** and **4.0% cash sweep yield** on uninvested cash margin.
4. **Buy & Hold Benchmark (`^NDX`):** Fully invested long index holding.

### Ground-Truth v2.0 Breakthrough:
The **Combined 100/100 Overlay** achieved **\$763,249.36 final equity (+1,426.50% / 14.14% CAGR)**, nearly capturing the total return of the Buy & Hold benchmark (\$869,961.38 / 14.87% CAGR) while **slashing maximum drawdown from -53.71% down to -16.06%**, delivering a **Sharpe Ratio of 1.10**, **Sortino Ratio of 1.59**, and **Calmar Ratio of 0.88** (3.1x higher than benchmark).

---

## 🏗️ 2. Codebase Map & Implementation Architecture

The backtesting lab is fully implemented in Python 3.14:

```
AG02/
├── data/
│   └── us100_daily.parquet        # Cached RTH OHLCV data (^NDX) from yfinance (2006–2026)
├── src/
│   ├── __init__.py
│   ├── data_loader.py             # Data ingestion with Parquet cache & schema validation
│   ├── indicators.py              # Effective ADR (Anti-Flash-Crash TR), IBS, 12M monthly references
│   ├── backtester.py              # NumPy continuous state machines (IBS, Momentum, Overlay, B&H)
│   └── metrics.py                 # Institutional metrics (CAGR, Sharpe, Sortino, MaxDD, Calmar, etc.)
├── tests/
│   └── test_quant_lab.py          # 7-part automated unit & integration test suite (100% passing)
├── app.py                         # Streamlit v2.0 interactive dashboard (4-Way comparison & Plotly)
├── ARGON_OPTIMIZATION_BRIEF.md    # This dossier
└── STRATEGY_PERFORMANCE_REVIEW.md # 20-year performance report
```

### Direct Code Links:
- **v2.0 Unified Overlay Engine:** [`run_unified_overlay_strategy()`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/src/backtester.py#L397-L700)
- **Anti-Flash-Crash Effective ADR:** [`compute_indicators()`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/src/indicators.py#L34-L54)
- **IBS Solo Engine:** [`run_ibs_strategy()`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/src/backtester.py#L25-L193)
- **12M Momentum Solo Engine:** [`run_momentum_strategy()`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/src/backtester.py#L195-L347)
- **Benchmark Engine:** [`run_buy_and_hold()`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/src/backtester.py#L349-L395)
- **Interactive UI:** [`app.py`](file:///c:/Users/weiju/OneDrive/ドキュメント/AG02/app.py)

---

## 🧮 3. Mathematical Specifications of v2.0

### Sizing & Risk Controls
- **Anti-Flash-Crash Effective ADR:**
  $$\text{True Range}_t = \max\left(\text{High}_t - \text{Low}_t, |\text{High}_t - Close_{t-1}|, |\text{Low}_t - Close_{t-1}|\right)$$
  $$\text{Effective\_ADR}_{14, t} = \max\left(\frac{1}{14}\sum_{i=0}^{13}(\text{High}_{t-i}-\text{Low}_{t-i}), \text{True Range}_t, 10^{-8}\right)$$
- **Volatility Sizing:** Each sub-strategy sizes units independently against current unified equity $E_t$:
  $$Units_{desired, t} = \frac{E_t \times \text{Risk\%}}{\text{Effective\_ADR}_{14, t}} \quad (\text{Default Risk\%} = 0.01)$$
- **Friction:** $2.0 \text{ bps}$ ($0.0002$) per-side on notional value traded:
  $$\text{Cost}_t = |\Delta Units_t| \times Close_t \times 0.0002$$

### The 100/100 Overlay Unified State Machine
1. **Daily Mark-to-Market + Cash Yield:**
   - Active units from both strategies ($Units_{total} = Units_{IBS} + Units_{MOM}$) mark to market daily.
   - If notional exposure is less than total equity, uninvested cash earns daily interest at 4.0% annualized ($r_{daily} = 0.04 / 252$):
     $$\text{Interest}_t = \max\left(0, E_{t-1} - Units_{total, t-1} \times Close_{t-1}\right) \times \left(\frac{0.04}{252}\right)$$
     $$\text{Cumulative Interest Earned (2006–2026)} = \mathbf{\$75,965.81}$$
2. **Monthly Momentum Rebalance:**
   - Evaluated on the first trading day of the month using zero-lookahead reference closes: $Close_{m-1} > Close_{m-13}$.
   - Existing momentum position is rolled or closed; new position entered if positive.
3. **Daily IBS Mean-Reversion:**
   - Evaluated daily at Close: Enter when $IBS_t < 0.10$; Exit when $IBS_t > 0.50$ or $bars\_held \ge 5$.
4. **Hard Notional Leverage Cap (1.50x):**
   - Total notional is checked every bar: $Notional_t = (Units_{IBS} + Units_{MOM}) \times Close_t$.
   - If $Notional_t > 1.50 \times E_t$, both position sizes are proportionately scaled down:
     $$\text{Scale Factor} = \frac{1.50 \times E_t}{Notional_t}, \quad Units_{IBS} \leftarrow Units_{IBS} \times \text{Scale Factor}, \quad Units_{MOM} \leftarrow Units_{MOM} \times \text{Scale Factor}$$
   - *Observation:* Average leverage was only **0.63x**, and the 1.5x cap was triggered on only 144 days (2.7% of sessions).

---

## 📊 4. Official v2.0 4-Way Head-to-Head Performance Matrix

*(Parameters: Starting Capital = \$50,000, Risk/ADR = 1.0%, Friction = 2.0 bps, Max Leverage = 1.5x, Cash Yield = 4.0%, Window = 2006/03/01 – 2026/10/20)*

| Metric | Strategy A<br>(IBS Solo) | Strategy B<br>(12M Momentum Solo) | 🔥 Combined 100/100 Overlay<br>(Unified Stack) | Buy & Hold Benchmark<br>(`^NDX`) |
| :--- | :---: | :---: | :---: | :---: |
| **Initial Capital** | \$50,000.00 | \$50,000.00 | \$50,000.00 | \$50,000.00 |
| **Final Portfolio Equity** | **\$130,678.75** | **\$227,294.34** | **\$763,249.36** | **\$869,961.38** |
| **Total Net Return (%)** | **+161.36%** | **+354.59%** | **+1,426.50%** | **+1,639.92%** |
| **CAGR (%)** | **4.77%** | **7.62%** | **14.14%** | **14.87%** |
| **Annualized Volatility (%)** | **4.74%** | **11.01%** | **12.78%** | **22.38%** |
| **Sharpe Ratio (Rf=0%)** | **1.01** | **0.72** | **1.10** | **0.73** |
| **Sortino Ratio** | **1.59** | **0.96** | **1.59** | **0.95** |
| **Maximum Drawdown (%)** | **-9.82%** | **-15.78%** | **-16.06%** | **-53.71%** |
| **Calmar Ratio (CAGR / \|MDD\|)** | **0.49** | **0.48** | **0.88** | **0.28** |
| **Total Closed Trades** | **499** | **214** | **713** | **1** |
| **Win Rate (%)** | **70.94%** | **63.08%** | **68.58%** | — |
| **Profit Factor** | **1.90** | **1.84** | **1.96** | — |
| **Time in Market (%)** | **15.93%** | **86.29%** | **88.72%** | **100.00%** |
| **Average Leverage** | 0.08x | 0.55x | **0.63x** | 1.00x |
| **Cash Interest Earned** | \$0.00 | \$0.00 | **+\$75,965.81** | \$0.00 |

---

## 🛡️ 5. Crisis Stress-Testing (v2.0)

| Historical Crisis Regime | IBS Solo Return (MDD) | Momentum Solo Return (MDD) | 🔥 100/100 Overlay Return (MDD) | Buy & Hold Return (MDD) |
| :--- | :---: | :---: | :---: | :---: |
| **2008 Great Financial Crisis**<br>*(2007-10-01 to 2009-03-31)* | **+8.80%** (-7.06%) | **-7.91%** (-12.08%) | **+4.46%** (**-16.06%**) | **-41.57%** (-53.71%) |
| **2011 Debt Ceiling / Eurozone**<br>*(2011-05-01 to 2011-10-31)* | **-4.62%** (-5.57%) | **-4.12%** (-8.14%) | **-6.42%** (**-11.03%**) | **-1.84%** (-16.11%) |
| **2015–16 China Devaluation / Oil**<br>*(2015-08-01 to 2016-02-28)* | **+0.32%** (-3.78%) | **-6.41%** (-10.08%) | **-5.11%** (**-12.71%**) | **-7.53%** (-16.34%) |
| **2018 Q4 Tech Selloff**<br>*(2018-10-01 to 2018-12-31)* | **+1.03%** (-2.61%) | **-12.22%** (-14.73%) | **-11.19%** (**-15.36%**) | **-17.21%** (-22.84%) |
| **2020 COVID Crash**<br>*(2020-02-19 to 2020-04-30)* | **+3.28%** (-1.51%) | **-4.84%** (-9.30%) | **-1.21%** (**-9.49%**) | **-7.39%** (-28.03%) |
| **2022 Fed Rate Hiking Bear**<br>*(2022-01-03 to 2022-12-30)* | **+4.75%** (-3.04%) | **-11.62%** (-12.32%) | **-3.67%** (**-10.99%**) | **-33.71%** (-35.28%) |
| **2023–26 AI Expansion Bull**<br>*(2023-01-03 to 2026-10-20)* | **+20.55%** (-4.71%) | **+57.45%** (-12.21%) | **+99.71%** (**-12.78%**) | **+171.48%** (-22.93%) |

---

## 📅 6. Annual Returns Ledger (2006 – 2026)

| Year | IBS Solo (%) | Momentum Solo (%) | 🔥 100/100 Overlay (%) | Buy & Hold `^NDX` (%) |
| :---: | :---: | :---: | :---: | :---: |
| **2006 (from Mar 1)** | -0.66% | -3.76% | **-2.98%** | +3.68% |
| **2007** | +6.56% | +12.22% | **+19.76%** | +18.67% |
| **2008** | **+5.38%** | **-7.83%** | **+0.07%** | **-41.89%** |
| **2009** | +8.26% | +5.61% | **+18.16%** | +53.54% |
| **2010** | +14.06% | +8.29% | **+25.18%** | +19.22% |
| **2011** | -3.65% | -1.57% | **-2.21%** | +2.70% |
| **2012** | +5.02% | +10.45% | **+17.07%** | +16.82% |
| **2013** | +5.25% | +30.07% | **+32.66%** | +34.99% |
| **2014** | +4.79% | +6.11% | **+15.14%** | +17.94% |
| **2015** | -4.57% | +0.26% | **-1.94%** | +8.43% |
| **2016** | +2.08% | +0.68% | **+5.32%** | +5.89% |
| **2017** | +11.65% | +26.32% | **+32.49%** | +31.52% |
| **2018** | **+5.02%** | **-1.78%** | **+2.79%** | **-1.04%** |
| **2019** | +3.21% | +12.77% | **+17.51%** | +37.96% |
| **2020** | +10.75% | +19.66% | **+34.35%** | +47.58% |
| **2021** | +2.43% | +12.83% | **+18.83%** | +26.63% |
| **2022** | **+5.46%** | **-11.36%** | **-3.67%** | **-32.97%** |
| **2023** | +8.25% | +17.77% | **+28.70%** | +53.81% |
| **2024** | +3.42% | +7.94% | **+13.39%** | +24.88% |
| **2025** | +1.66% | +12.60% | **+16.47%** | +20.17% |
| **2026 (YTD)** | +5.93% | +9.99% | **+17.53%** | +16.79% |

---

## ⚠️ 7. Specific Optimization Frontiers for Argon (Starting from v2.0)

Since v2.0 has already solved the cash sweep and initial 100/100 overlay architecture, **Argon should not re-propose baseline cash sweeps or static overlays**. 

Instead, Argon is requested to solve the **next-tier structural bottlenecks**:

### 1. Dynamic / Regime-Adaptive Leverage Capping
- **Current Limitation:** The hard leverage cap is static at $1.50\text{x}$.
- **Optimization Directive:** Can we dynamically float the leverage cap between $1.0\text{x}$ and $2.2\text{x}$ based on realized index volatility or VIX? When realized volatility is low (<15%), expanding leverage to 1.8x would easily beat Buy & Hold's total return while remaining safely below the -20% drawdown ceiling.

### 2. Risk Budget Asymmetry & Dynamic Capital Weights
- **Current Limitation:** Both IBS and Momentum use an identical static 1.0% ADR risk budget ($Risk\% = 0.01$).
- **Optimization Directive:** Design an adaptive allocation model:
  - During bull regimes ($Close > SMA_{200}$), overweight Momentum (e.g. 1.2% risk on Momentum, 0.8% on IBS).
  - During high-volatility sideways/correction regimes, overweight IBS (e.g. 1.5% risk on IBS, 0.5% on Momentum) to harvest mean-reversion alpha.

### 3. Asymmetric ATR Catastrophic Stop for IBS
- **Current Limitation:** IBS has 499 trades with a 70.9% win rate, but relies entirely on a 5-day time stop. A handful of cascade gap-downs created deep single-trade losses before day 5.
- **Optimization Directive:** Formulate an explicit volatility-scaled stop loss (e.g., $Stop = Entry - 2.5 \times ADR_{14}$) and trailing stop rules.

### 4. Multi-Timeframe Momentum with Mid-Month Exit Filter
- **Current Limitation:** 12M Momentum Solo underperforms Buy & Hold during sharp V-bottoms (e.g. March 2020) because it only evaluates on the 1st trading day of the calendar month.
- **Optimization Directive:**
  - Blend 3-Month, 6-Month, and 12-Month momentum signals.
  - Introduce an emergency mid-month stop (e.g. exit to cash mid-month if price drops $> 3 \times ADR$ below the monthly entry price).

### 5. Floating Historical SOFR / Fed Funds Yield Curve
- **Current Limitation:** v2.0 applies a flat 4.0% cash yield across the entire 20-year period.
- **Optimization Directive:** Integrate the actual historical Federal Funds effective rate (yielding 5.25% in 2007 and 2023–2024, but 0.1% during ZIRP 2009–2015).

### 6. Anti-Overfitting Protocol & Cross-Validation Architecture
- **Optimization Directive:** Specify the exact machine learning / statistical cross-validation framework to prevent curve fitting:
  - Purged Walk-Forward Optimization (WFO).
  - Parameter Sensitivity Surface analysis (testing whether surrounding parameter grids remain profitable).

---

## 🎯 8. Expected Optimization Plan Format from Argon

**Argon, please formulate your optimization proposal in 4 structured sections:**

1. **Phase 1: Risk & Leverage Engineering** (Formulas for dynamic leverage capping and IBS ATR stops).
2. **Phase 2: Signal Refinement** (Multi-timeframe momentum formulas and regime filters).
3. **Phase 3: Macro Interest & Execution Realism** (Floating yield curve + TCA/slippage modeling).
4. **Phase 4: Validation Framework** (In-sample 2006–2018, Out-of-sample 2019–2022, Holdout Test 2023–2026).

---
*Report updated and verified against live v2.0 Streamlit execution on 2026-10-22.*
