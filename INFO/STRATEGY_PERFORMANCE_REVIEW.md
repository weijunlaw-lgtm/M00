# 📑 Quantitative Strategy Review Dossier: US100 Quantitative Strategy Lab v2.0

**Prepared for:** Argon / Quantitative Review & Risk Committee  
**Target Asset:** Nasdaq-100 Cash Index (`^NDX`)  
**Evaluation Window:** March 1, 2006 – October 20, 2026 (5,193 Trading Sessions / 20.64 Years)  
**Execution Environment:** Python 3.14 / NumPy / Pandas / Parquet RTH Engine  
**Friction Model:** Realistic 2.0 bps ($0.0002$) per-side commission & slippage on traded notional  
**Starting Capital:** \$50,000.00 USD  
**Lab Architecture:** **v2.0 4-Way Head-to-Head Comparison**  

---

## Executive Summary

This dossier reflects the official findings of the **v2.0 release** of the US100 Quantitative Strategy Lab, comparing:
1. **Strategy A (IBS Solo):** Intraday mean-reversion with Effective ADR volatility sizing.
2. **Strategy B (12M Momentum Solo):** Monthly trend following with zero-lookahead reference closes.
3. **🔥 Combined 100/100 Overlay:** Both strategies run simultaneously on a unified capital base with a **1.50x hard notional leverage cap** and **4.0% cash sweep yield** on idle cash margin.
4. **Buy & Hold Benchmark (`^NDX`):** 100% long index holding.

### Key Breakthrough:
The **Combined 100/100 Overlay** generated **\$763,249.36 (+1,426.50% / 14.14% CAGR)**, nearly matching Buy & Hold's total return (\$869,961.38 / 14.87% CAGR) while **crushing maximum drawdown from -53.71% down to -16.06%**, achieving a **Sharpe Ratio of 1.10**, **Sortino Ratio of 1.59**, and a **Calmar Ratio of 0.88** (3.1x benchmark).

---

## 📊 Official v2.0 4-Way Head-to-Head Performance Matrix

| Metric | Strategy A (IBS Solo) | Strategy B (12M Momentum Solo) | 🔥 Combined 100/100 Overlay | Buy & Hold Benchmark (`^NDX`) |
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
| **Total Trades / Cycles** | **499** | **214** | **713** | **1** |
| **Win Rate (%)** | **70.94%** | **63.08%** | **68.58%** | — |
| **Profit Factor** | **1.90** | **1.84** | **1.96** | — |
| **Time in Market (%)** | **15.93%** | **86.29%** | **88.72%** | **100.00%** |
| **Average Leverage** | 0.08x | 0.55x | **0.63x** | 1.00x |
| **Cash Interest Earned** | \$0.00 | \$0.00 | **+\$75,965.81** | \$0.00 |

---

## 🛡️ Crisis & Regime Stress-Testing (v2.0)

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

## 📅 Annual Returns Ledger (2006 – 2026)

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
*Report generated autonomously by Antigravity Quantitative Research Engine on 2026-10-22.*
