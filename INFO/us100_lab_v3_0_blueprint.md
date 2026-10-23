# 🏛️ Technical Blueprint: US100 Quantitative Strategy Lab v3.0 (Institutional Multi-Engine Overlay)

**Target System:** US100 Quantitative Strategy Lab (`AG02`)  
**Target Asset:** Nasdaq-100 Cash Index (`^NDX`)  
**Target Agent:** Autonomous Coding Agent (Gemini 3.8 Flash in Google Antigravity)  
**Execution Environment:** Python 3.11+ / NumPy / Pandas / Parquet / Streamlit  
**Starting Capital:** \$50,000.00 USD  
**Core Objective:** Refactor v2.0 in-place to patch the 4 performance bottlenecks and implement the 4 institutional alpha optimizations, driving Combined Overlay CAGR past the Buy & Hold benchmark while maintaining a Maximum Drawdown below -18%.

---

## 🏗️ 1. Architecture & Core Milestone Changes (v2.0 ➔ v3.0)

| Module / Component | v2.0 Limitation (The Leaks) | v3.0 Institutional Upgrade (The Alpha Solution) |
| :--- | :--- | :--- |
| **Position Sizing** | $\max(ADR_{14}, \text{TR})$ shrinks size by 25–40% on normal dip entries. | **Shock-Damped Effective ADR:** Only damps position size if $\text{TR}_t > 1.75 \times ADR_{14, t}$. |
| **Momentum Signal** | 12M lookback evaluated once a month; misses post-crash V-recoveries. | **3-Tranche Momentum:** Weighted blend of 3M (25%), 6M (35%), and 12M (40%) signals. |
| **Risk Allocation** | Static 1.0% risk per ADR on both strategies across all regimes. | **Regime-Adaptive Asymmetry:** $SMA_{200}$ switch: Bull (1.35% Mom / 1.0% IBS) vs. Bear (0.60% Mom / 1.5% IBS). |
| **Leverage Cap** | Static 1.50x hard cap; average exposure starved at 0.63x. | **Volatility-Targeted Dynamic Cap:** Cap scales between 1.00x and 2.00x inversely with 20-day realized volatility. |
| **Risk Management** | IBS has no stop-loss (relies on 5-day hold); Mom has no mid-month exit. | **Dual Catastrophic Circuit Breakers:** IBS ATR stop at $-2.50 \times ADR_{14}$; Mom Chandelier stop at $-3.50 \times ADR_{14}$. |
| **Cash Sweep Yield** | Static 4.0% interest rate; credited only to Overlay (\$0.00 to Solo engines). | **Floating T-Bill Yield (`^IRX`):** Historical 13-Week T-Bill yield credited fairly across all 3 active strategies. |
| **Downside Risk** | Sortino calculation ignored zero-return cash days, distorting ratio. | **Continuous Downside Deviation:** Standardized Sortino evaluated over all $N$ trading sessions. |
| **Validation** | No formal walk-forward or parameter surface analysis. | **3-Period Split & Parameter Heatmap:** In-Sample (2006–2018), Out-of-Sample (2019–2022), Holdout (2023–2026). |

---

## 🧮 2. Mathematical Formulations & Indicator Logic (`src/indicators.py`)

### A. Shock-Damped Effective ADR
Compute standard 14-day Average Daily Range:
$$DR_t = \text{High}_t - \text{Low}_t$$
$$ADR_{14, t} = \frac{1}{14}\sum_{i=0}^{13} DR_{t-i}$$
Compute True Range ($TR_t$):
$$TR_t = \max\left(\text{High}_t - \text{Low}_t,\; |\text{High}_t - \text{Close}_{t-1}|,\; |\text{Low}_t - \text{Close}_{t-1}|\right)$$
Compute Shock-Damped Effective ADR with a 1.75 tail-shock scaling factor:
$$\text{Effective\_ADR}_{14, t} = \max\left(ADR_{14, t},\; \frac{TR_t}{1.75},\; 10^{-8}\right)$$

### B. Regime Filter & Realized Volatility
* **Regime Filter:** 200-day Simple Moving Average:
  $$SMA_{200, t} = \frac{1}{200}\sum_{i=0}^{199} \text{Close}_{t-i}$$
  $$\text{Is\_Bull}_t = \mathbb{I}(\text{Close}_t > SMA_{200, t})$$
* **20-Day Annualized Realized Volatility:**
  $$\sigma_{20, t} = \text{Std}\left(\frac{\text{Close}_\tau - \text{Close}_{\tau-1}}{\text{Close}_{\tau-1}}\right)_{\tau=t-19}^{t} \times \sqrt{252}$$

### C. 3-Tranche Multi-Timeframe Momentum Signal
Resample monthly closes without lookahead bias. For day $t$ in month $m$, compare the previous month-end close ($Close_{m-1}$) against prior month-end closes:
$$S_{3\text{M}, t} = \mathbb{I}(Close_{m-1} > Close_{m-4})$$
$$S_{6\text{M}, t} = \mathbb{I}(Close_{m-1} > Close_{m-7})$$
$$S_{12\text{M}, t} = \mathbb{I}(Close_{m-1} > Close_{m-13})$$
Compute the weighted momentum conviction score:
$$W_{\text{MOM}, t} = 0.25 \cdot S_{3\text{M}, t} + 0.35 \cdot S_{6\text{M}, t} + 0.40 \cdot S_{12\text{M}, t} \quad \in [0.0, 1.0]$$

---

## ⚙️ 3. Execution Engines & State Machines (`src/backtester.py`)

### A. Dynamic Leverage Ceiling & Asymmetric Risk Budgets
At each daily session $t$:
* **Dynamic Leverage Cap:**
  $$\text{Max\_Lev}_t = \text{clip}\left(\frac{0.18}{\max(\sigma_{20, t}, 0.08)},\; 1.00,\; 2.00\right)$$
* **Regime-Adaptive Risk Budgets:**
  $$\text{Risk}_{\text{MOM}, t} = \begin{cases} 0.0135 & \text{if } \text{Is\_Bull}_t = 1 \\ 0.0060 & \text{if } \text{Is\_Bull}_t = 0 \end{cases}$$
  $$\text{Risk}_{\text{IBS}, t} = \begin{cases} 0.0100 & \text{if } \text{Is\_Bull}_t = 1 \\ 0.0150 & \text{if } \text{Is\_Bull}_t = 0 \end{cases}$$

### B. Strategy A: IBS Mean-Reversion Engine (with Hard ATR Stop)
* **Entry Trigger (Daily at Close):** If `in_position == False` and $IBS_t < 0.10$:
  $$Units = \frac{E_t \times \text{Risk}_{\text{IBS}, t}}{\text{Effective\_ADR}_{14, t}}$$
  $$P_{\text{stop}} = \text{Close}_t - 2.50 \times ADR_{14, t}$$
  Record `entry_price = Close_t`, `bars_held = 0`, `in_position = True`. Deduct 2.0 bps entry friction.
* **Exit Logic (Evaluated on subsequent bars $t$ while `in_position == True`):**
  1. **Catastrophic Stop Check:** If $\text{Low}_t \le P_{\text{stop}}$:
     $$\text{Exit\_Price} = \min(\text{Open}_t,\; P_{\text{stop}})$$
     Liquidate position, deduct 2.0 bps exit friction, record trade with reason `"ATR_STOP"`, reset state.
  2. **Standard Mean-Reversion Exit:** If $IBS_t > 0.50$ OR `bars_held >= 5`:
     $$\text{Exit\_Price} = \text{Close}_t$$
     Liquidate position, deduct 2.0 bps exit friction, record trade with reason `"IBS_TARGET"` or `"TIME_STOP"`, reset state.

### C. Strategy B: 3-Tranche Momentum Engine (with Chandelier Trailing Stop)
* **Monthly Rebalance (on `is_first_day_of_month == True`):**
  1. Liquidate existing momentum position at $\text{Close}_t$ and deduct exit friction.
  2. If $W_{\text{MOM}, t} > 0$:
     $$Units = W_{\text{MOM}, t} \times \frac{E_t \times \text{Risk}_{\text{MOM}, t}}{\text{Effective\_ADR}_{14, t}}$$
     Set $\text{Peak\_Close} = \text{Close}_t$. Deduct entry friction.
* **Daily Mid-Month Chandelier Stop Check:**
  While in position:
  $$\text{Peak\_Close} = \max(\text{Peak\_Close},\; \text{Close}_t)$$
  $$\text{Chandelier\_Stop}_t = \text{Peak\_Close} - 3.50 \times ADR_{14, t}$$
  If $\text{Close}_t < \text{Chandelier\_Stop}_t$:
  Liquidate full momentum position immediately at $\text{Close}_t$, deduct exit friction, set $Units = 0$, and stay in cash for the remainder of the calendar month.

### D. Unified 100/100 Overlay State Machine & Fair Cash Yield
1. **Daily Mark-to-Market & Fair Cash Interest:**
   $$\text{Notional}_{t-1} = (Units_{\text{IBS}, t-1} + Units_{\text{MOM}, t-1}) \times \text{Close}_{t-1}$$
   $$\text{Cash}_{t-1} = \max\left(0.0,\; E_{t-1} - \text{Notional}_{t-1}\right)$$
   $$\text{Interest}_t = \text{Cash}_{t-1} \times \left(\frac{r_{\text{T-Bill}, t}}{252}\right)$$
   $$E_t = E_{t-1} + (Units_{\text{IBS}, t-1} + Units_{\text{MOM}, t-1}) \times (\text{Close}_t - \text{Close}_{t-1}) + \text{Interest}_t$$
   *(Apply the exact same daily cash interest formula to IBS Solo and Momentum Solo using their respective uninvested cash).*
2. **Dynamic Leverage Scaling Check:**
   Every bar after executing trades, compute total notional:
   $$\text{Total\_Notional}_t = (Units_{\text{IBS}, t} + Units_{\text{MOM}, t}) \times \text{Close}_t$$
   If $\text{Total\_Notional}_t > \text{Max\_Lev}_t \times E_t$:
   $$\text{Scale} = \frac{\text{Max\_Lev}_t \times E_t}{\text{Total\_Notional}_t}$$
   $$Units_{\text{IBS}, t} \leftarrow Units_{\text{IBS}, t} \times \text{Scale}, \quad Units_{\text{MOM}, t} \leftarrow Units_{\text{MOM}, t} \times \text{Scale}$$

---

## 📊 4. Standardized Metrics Module (`src/metrics.py`)

Compute institutional performance metrics without survivor or lookahead bias:
* **Continuous Downside Deviation (All $N$ Sessions):**
  $$\sigma_{\text{downside}} = \sqrt{\frac{252}{N}\sum_{t=1}^N \min(0, R_t)^2}$$
  $$\text{Sortino Ratio} = \frac{\text{CAGR}}{\sigma_{\text{downside}}}$$
* **Maximum Drawdown & Calmar Ratio:**
  $$DD_t = \frac{E_t - \max_{s \le t} E_s}{\max_{s \le t} E_s}$$
  $$\text{Calmar Ratio} = \frac{\text{CAGR}}{|\min_t DD_t|}$$
* **Turnover & Exposure Analytics:**
  Average Notional Exposure (%), Peak Leverage ($x$), Time in Market (%), and Cumulative Cash Yield Earned (\$).

---

## 🤖 5. Sequential Agent Implementation Checklist

Execute these tasks in order. Ensure unit test suite passes after each step.

### Task 1: Ingest Floating 13-Week T-Bill Yields (`src/data_loader.py`)
1. Update `load_us100_data()` to also fetch `^IRX` (13-Week Treasury Bill yield index) from Yahoo Finance starting from the same date (`2005-01-01`).
2. Align `^IRX` Close to the `^NDX` date index:
   * Divide `^IRX` Close by 100.0 to convert percentage to decimal ($4.25\% \rightarrow 0.0425$).
   * Forward-fill missing dates (holidays where bond markets closed but equity opened) and clip at $\ge 0.0$.
   * Save aligned column `rf_annual` into `data/us100_daily.parquet`.
3. Assert that `df['rf_annual'].isna().sum() == 0` and `(df['rf_annual'] >= 0.0).all()`.

### Task 2: Vectorized Indicator Expansion (`src/indicators.py`)
1. Implement `compute_indicators(df: pd.DataFrame, adr_window: int = 14) -> pd.DataFrame`.
2. Compute `tr = np.maximum(df['High'] - df['Low'], np.maximum((df['High'] - df['Close'].shift(1)).abs(), (df['Low'] - df['Close'].shift(1)).abs()))`.
3. Compute `adr = (df['High'] - df['Low']).rolling(adr_window).mean()`.
4. Compute `effective_adr = np.maximum(adr, np.maximum(tr / 1.75, 1e-8))`.
5. Compute `sma_200 = df['Close'].rolling(200).mean()` and boolean `is_bull = df['Close'] > sma_200`.
6. Compute 20-day annualized realized volatility: `realized_vol_20 = df['Close'].pct_change().rolling(20).std() * np.sqrt(252)`.
7. Compute monthly closes `m_close = df['Close'].resample('ME').last()`.
8. Map 3M, 6M, and 12M lookbacks to daily rows without lookahead:
   * $S_{3M} = m\_close.shift(1) > m\_close.shift(4)$
   * $S_{6M} = m\_close.shift(1) > m\_close.shift(7)$
   * $S_{12M} = m\_close.shift(1) > m\_close.shift(13)$
   * Compute composite score `mom_conviction = 0.25 * S_3M + 0.35 * S_6M + 0.40 * S_12M`.
9. Flag `is_first_day_of_month = df.index.to_series().dt.month != df.index.to_series().dt.month.shift(1)`.

### Task 3: State Machine Upgrades (`src/backtester.py`)
1. Refactor `run_ibs_strategy()`:
   * Add ATR catastrophic stop logic: track `stop_price = entry_close - 2.50 * adr`.
   * On intraday stop breach (`Low <= stop_price`), exit at `min(Open, stop_price)`.
   * Add fair daily cash interest tracking using `df['rf_annual']`.
2. Refactor `run_momentum_strategy()`:
   * Size position using `mom_conviction` and dynamic risk budget.
   * Track `peak_close` each month and trigger emergency exit if `Close < peak_close - 3.50 * adr`.
   * Add fair daily cash interest tracking using `df['rf_annual']`.
3. Refactor `run_unified_overlay_strategy()`:
   * Implement asymmetric risk budgets based on `is_bull`.
   * Calculate dynamic leverage cap: `max_lev = np.clip(0.18 / np.maximum(realized_vol_20, 0.08), 1.0, 2.0)`.
   * Scale both positions if total notional exceeds `max_lev * equity`.
   * Credit daily interest on uninvested cash margin using floating `df['rf_annual']`.
4. Maintain `run_buy_and_hold()` for benchmark comparison.

### Task 4: Fix Performance Metrics Module (`src/metrics.py`)
1. Update Sortino calculation to evaluate over all $N$ days using the continuous downside formula.
2. Add output fields: `Cumulative Interest Earned ($)`, `Average Notional Leverage (x)`, `Max Notional Leverage (x)`, and `Calmar Ratio`.

### Task 5: Anti-Overfitting Validation Suite (`src/validation.py`)
Create a new module `src/validation.py` containing:
1. `run_regime_split_backtest(df)`:
   * Automatically executes the strategies across 3 distinct sub-periods:
     * **In-Sample (IS):** `2006-03-01` to `2018-12-31`
     * **Out-of-Sample (OOS):** `2019-01-01` to `2022-12-31`
     * **Holdout Testing:** `2023-01-01` to `2026-10-20`
   * Returns a comparative KPI table across IS, OOS, and Holdout.
2. `run_parameter_sensitivity_grid(df)`:
   * Computes a $5 \times 5$ sensitivity grid over `ibs_entry` $\in [0.06, 0.08, 0.10, 0.12, 0.14]$ and `risk_base` $\in [0.008, 0.010, 0.012, 0.014, 0.016]$.
   * Returns a 2D matrix of Sharpe and Calmar ratios for heatmap rendering.

### Task 6: Refactor Streamlit UI (`app.py`)
1. **Sidebar Controls:**
   * Dynamic Leverage Cap Toggle (Default: Enabled, Min `1.0x`, Max `2.0x`).
   * ATR Stop Multiplier for IBS (Default: `2.5x`).
   * Chandelier Stop Multiplier for Momentum (Default: `3.5x`).
   * Floating T-Bill Yield Toggle (Default: Enabled via `^IRX`).
2. **Main Dashboard Tabs:**
   * **Tab 1: 4-Way Head-to-Head Performance:** Metric cards, Plotly Equity Curves (Log/Linear), Underwater Drawdown, and Leverage Exposure Subplots.
   * **Tab 2: Annual Returns Ledger:** Year-by-year returns table (2006–2026) comparing all 4 streams.
   * **Tab 3: Institutional Validation (IS / OOS / Holdout):** Sub-period performance breakdown and Walk-Forward stability analysis.
   * **Tab 4: Parameter Sensitivity Heatmap:** 2D Plotly heatmap displaying Sharpe and Calmar plateau stability.
   * **Tab 5: Trade Log Forensics:** Filterable trade log with exit reasons (`IBS_TARGET`, `ATR_STOP`, `TIME_STOP`, `CHANDELIER_STOP`, `MOM_REBALANCE`).

### Task 7: Comprehensive Verification & Test Suite
1. Run updated unit tests in `tests/test_quant_lab.py`:
   ```bash
   pytest tests/test_quant_lab.py -v
   ```
2. Run headless verification script:
   ```bash
   python -c "from src.data_loader import load_us100_data; from src.indicators import compute_indicators; from src.backtester import run_unified_overlay_strategy; from src.metrics import calculate_metrics; df = compute_indicators(load_us100_data()); eq, tr = run_unified_overlay_strategy(df.dropna()); print('v3.0 Final Equity:', eq['equity'].iloc[-1]); print('v3.0 Max Drawdown:', eq['drawdown_pct'].min()); print('v3.0 Sharpe:', calculate_metrics(eq, tr)['Sharpe Ratio'])"
   ```
3. Confirm that Final Equity exceeds benchmark (\$870k+) while Max Drawdown remains safely under -18%.
4. Launch dashboard: `streamlit run app.py`.