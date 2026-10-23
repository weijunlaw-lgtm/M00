# 🎯 Technical Blueprint: US100 Quantitative Strategy Lab (IBS vs. 12-Month Momentum)

**Target Agent:** Autonomous Coding Agent (Gemini 3.8 Flash in Google Antigravity)

**Execution Mode:** Local Machine (Autonomous File Generation & Terminal Execution)

## 🏗️ 1. Construction Site & Environment Snapshot

* **Language / Runtime:** Python 3.11+

* **Target Tech Stack:** `pandas`, `numpy`, `yfinance`, `pyarrow` (Parquet caching), `plotly`, `streamlit`

* **Data Source:** Automated fetch of Nasdaq-100 Cash Index (`^NDX`) Regular Trading Hours (RTH: 09:30–16:00 NY) daily OHLCV data via `yfinance`, cached locally to `data/us100_daily.parquet`.

* **Starting Capital:** `$50,000.00`

* **Standard Sizing Rule:** Volatility-adjusted sizing where 1 Average Daily Range ($ADR_{14}$) risks `1.0%` (`0.01`) of current account equity.

* **Standard Friction:** `2.0 bps` (`0.0002`) per side (commission + slippage combined) on notional value traded.

* **Evaluation Mode:** Test both strategies separately side-by-side against a Buy & Hold (`^NDX`) benchmark.

## 📂 2. System Architecture & File Tree

Do not create unnecessary microservices, databases, or abstract classes. Build this exact flat modular structure:

```
us100_quant_backtest/
├── data/
│   └── us100_daily.parquet     # Auto-cached RTH OHLCV data (^NDX)
├── src/
│   ├── __init__.py
│   ├── data_loader.py          # yfinance fetcher + Parquet cache validation
│   ├── indicators.py           # Vectorized IBS, ADR_14, and 12M Momentum math
│   ├── backtester.py           # Stateful NumPy mark-to-market simulation engines
│   └── metrics.py              # CAGR, Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor
├── app.py                      # Streamlit interactive UI & equity curve comparison
└── requirements.txt            # Minimal pinned dependencies

```

## 🧮 3. Concrete Mathematical Formulas & State Logic

### A. Indicator & Sizing Formulas (`src/indicators.py`)

1. **Daily Range (**$DR_t$**):**
   

   $$
   DR_t = \text{High}_t - \text{Low}_t
   $$

2. **14-Day Average Daily Range (**$ADR_{14, t}$**):**
   

   $$
   ADR_{14, t} = \frac{1}{14} \sum_{i=0}^{13} DR_{t-i}
   $$

3. **Internal Bar Strength (**$IBS_t$**):**
   

   $$
   IBS_t = \frac{\text{Close}_t - \text{Low}_t}{\max(\text{High}_t - \text{Low}_t, 10^{-8})}
   $$

4. **Volatility-Adjusted Position Sizing (**$Units_t$**):**

   * Given current Account Equity $E_t$ and risk fraction $\text{Risk\%} = 0.01$:
     

     $$
     Units_t = \frac{E_t \times \text{Risk\%}}{ADR_{14, t}}
     $$

5. **Transaction Cost Deduction (**$Cost_t$**):**

   * Whenever units change by $\vert{}\Delta Units_t\vert{}$ at execution price $\text{Close}_t$ with $\text{Cost}_{\text{bps}} = 2.0$:
     

     $$
     Cost_t = \vert{}\Delta Units_t\vert{} \times \text{Close}_t \times (\text{Cost}_{\text{bps}} \times 10^{-4})
     $$

6. **12-Month Momentum Reference Prices (Zero Lookahead Bias):**

   * Resample `df['Close']` to month-end (`'ME'`) taking `.last()`.

   * For any trading day $t$ falling in calendar month $m$:

     * $C_{\text{last\_month}}$ is the closing price on the final trading day of month $m-1$.

     * $C_{12\text{m\_ago}}$ is the closing price on the final trading day of month $m-13$ (exact 12-month lookback from $C_{\text{last\_month}}$).

   * Define boolean flag `is_first_day_of_month`:
     

     $$
     \text{is\_first\_day\_of\_month}_t = (\text{Month}_t \neq \text{Month}_{t-1})
     $$

### B. Strategy 1 State Machine: Internal Bar Strength (IBS) (`src/backtester.py`)

* **Approximation Rule:** RTH Daily Close ($\text{Close}_t$) represents the 15:55 NY execution check.

* **State Variables:**

  * `in_position: bool = False`

  * `bars_held: int = 0`

  * `units: float = 0.0`

  * `equity: float = 50000.0`

* **Daily Loop at Bar** $t$ **(for** $t \ge 1$ **where** $ADR_{14, t}$ **is valid):**

  1. **If `in_position == True`:**

     * Increment `bars_held += 1`

     * Mark-to-market daily PnL:
       

       $$
       E_t = E_{t-1} + \text{units} \times (\text{Close}_t - \text{Close}_{t-1})
       $$

     * **Check Exit Condition:** If $IBS_t > 0.50$ (closes above midpoint of today's range) **OR** `bars_held >= 5`:

       * Deduct exit friction:
         

         $$
         E_t \leftarrow E_t - (\text{units} \times \text{Close}_t \times 0.0002)
         $$

       * Record completed trade in `trade_log` (`entry_date`, `exit_date`, `entry_price`, `exit_price`, `units`, `net_pnl`, `bars_held`, `exit_reason`).

       * Reset `in_position = False`, `bars_held = 0`, `units = 0.0`.

  2. **Else (`in_position == False`):**

     * Carry equity forward: $E_t = E_{t-1}$

     * **Check Entry Condition:** If $IBS_t < 0.10$ and $ADR_{14, t} > 0$:

       * Calculate position size:
         

         $$
         \text{units} = \frac{E_t \times 0.01}{ADR_{14, t}}
         $$

       * Deduct entry friction:
         

         $$
         E_t \leftarrow E_t - (\text{units} \times \text{Close}_t \times 0.0002)
         $$

       * Set `in_position = True`, `bars_held = 0`, `entry_price = Close_t`, `entry_date = Date_t`.

### C. Strategy 2 State Machine: 12-Month Momentum (`src/backtester.py`)

* **State Variables:**

  * `in_position: bool = False`

  * `units: float = 0.0`

  * `equity: float = 50000.0`

* **Daily Loop at Bar** $t$ **(where** $C_{\text{last\_month}}$**,** $C_{12\text{m\_ago}}$**, and** $ADR_{14, t}$ **are valid):**

  1. **Mark-to-Market Open Position First:**

     * If `in_position == True`:
       

       $$
       E_t = E_{t-1} + \text{units} \times (\text{Close}_t - \text{Close}_{t-1})
       $$

     * Else:
       

       $$
       E_t = E_{t-1}
       $$

  2. **Monthly Rebalance Check (`if is_first_day_of_month[t] == True`):**

     * **Rule 1 (Close any open position on the first day of the month):**

       * If `in_position == True`:

         * Deduct exit friction:
           

           $$
           E_t \leftarrow E_t - (\text{units} \times \text{Close}_t \times 0.0002)
           $$

         * Record completed monthly trade in `trade_log`.

         * Set `in_position = False`, `units = 0.0`.

     * **Rule 2 & 3 (Compare last month's close with close 12 months before):**

       * If $\text{Close}_{t-1} > C_{12\text{m\_ago}, t}$ and $ADR_{14, t} > 0$:

         * Calculate fresh monthly volatility-adjusted size:
           

           $$
           \text{units} = \frac{E_t \times 0.01}{ADR_{14, t}}
           $$

         * Deduct entry friction:
           

           $$
           E_t \leftarrow E_t - (\text{units} \times \text{Close}_t \times 0.0002)
           $$

         * Set `in_position = True`, `entry_price = Close_t`, `entry_date = Date_t`.

## 🤖 4. Numbered Agent Execution Checklist

Execute the following tasks sequentially. Validate each step before proceeding to the next.

### Task 1: Project Initialization & Dependencies

1. Create folders `data/` and `src/`, plus `src/__init__.py`.

2. Write `requirements.txt`:

   ```
   pandas>=2.2.0
   numpy>=1.26.0
   yfinance>=0.2.40
   pyarrow>=16.0.0
   plotly>=5.22.0
   streamlit>=1.36.0
   
   ```

3. Run terminal command: `pip install -r requirements.txt`

### Task 2: Build Data Loader (`src/data_loader.py`)

1. Implement `load_us100_data(ticker: str = "^NDX", start_date: str = "2005-01-01", force_refresh: bool = False) -> pd.DataFrame`.

2. If `data/us100_daily.parquet` exists and `force_refresh` is `False`, load and return it.

3. Otherwise, download via `yf.download(ticker, start=start_date, auto_adjust=False, progress=False)`.

4. If columns are a `pd.MultiIndex`, flatten them via `df.columns = df.columns.get_level_values(0)`.

5. Keep strictly `['Open', 'High', 'Low', 'Close', 'Volume']`, drop any rows with `NaN`, sort index ascending, and strip timezone metadata if present.

6. Save to `data/us100_daily.parquet` and return the DataFrame.

### Task 3: Build Vectorized Indicators (`src/indicators.py`)

1. Implement `compute_indicators(df: pd.DataFrame, adr_window: int = 14) -> pd.DataFrame`.

2. Compute `daily_range`, `adr`, and `ibs` using the exact formulas in Section 3A.

3. Compute monthly reference closes without lookahead bias:

   * Create a `year_month` period column `df.index.to_period('M')`.

   * Group by `year_month` and take `.last()` on `'Close'` to create a monthly series `m_close`.

   * Compute `last_month_close = m_close.shift(1)` and `close_12m_ago = m_close.shift(13)`.

   * Map `last_month_close` and `close_12m_ago` back onto `df` via `df['year_month'].map(...)`.

4. Compute boolean column `is_first_day_of_month = df['year_month'] != df['year_month'].shift(1)`.

5. Return the enriched DataFrame.

### Task 4: Build Stateful Backtest Engines (`src/backtester.py`)

1. Implement `run_ibs_strategy(df: pd.DataFrame, initial_capital: float = 50000.0, risk_per_adr: float = 0.01, ibs_entry: float = 0.10, ibs_exit: float = 0.50, max_hold: int = 5, cost_bps: float = 2.0) -> tuple[pd.DataFrame, pd.DataFrame]`.

   * Follow Section 3B state machine strictly.

   * Return `(equity_df, trades_df)` where `equity_df` is indexed by `Date` with columns `['equity', 'drawdown_pct', 'units', 'in_position']`.

2. Implement `run_momentum_strategy(df: pd.DataFrame, initial_capital: float = 50000.0, risk_per_adr: float = 0.01, cost_bps: float = 2.0) -> tuple[pd.DataFrame, pd.DataFrame]`.

   * Follow Section 3C state machine strictly.

   * Return `(equity_df, trades_df)`.

3. Implement `run_buy_and_hold(df: pd.DataFrame, initial_capital: float = 50000.0) -> pd.DataFrame` as a baseline comparison benchmark over the identical valid date range.

### Task 5: Build Performance Metrics Module (`src/metrics.py`)

1. Implement `calculate_metrics(equity_df: pd.DataFrame, trades_df: pd.DataFrame, initial_capital: float = 50000.0) -> dict`.

2. Compute:

   * `Total Return (%)`: $\left(\frac{E_{\text{final}}}{E_0} - 1\right) \times 100$

   * `CAGR (%)`: $\left(\left(\frac{E_{\text{final}}}{E_0}\right)^{\frac{252}{N_{\text{days}}}} - 1\right) \times 100$

   * `Annualized Volatility (%)`: $\text{std}(r_{\text{daily}}) \times \sqrt{252} \times 100$

   * `Sharpe Ratio`: $\frac{\text{mean}(r_{\text{daily}})}{\text{std}(r_{\text{daily}})} \times \sqrt{252}$ (guard against zero division)

   * `Sortino Ratio`: $\frac{\text{mean}(r_{\text{daily}})}{\text{std}(r_{\text{daily}} < 0)} \times \sqrt{252}$

   * `Max Drawdown (%)`: $\min\left(\frac{E_t - \max_{s \le t} E_s}{\max_{s \le t} E_s}\right) \times 100$

   * `Calmar Ratio`: $\frac{\text{CAGR}}{\vert{}\text{Max Drawdown}\vert{}}$

   * `Total Trades`: `len(trades_df)`

   * `Win Rate (%)`: Percentage of trades with `net_pnl > 0`

   * `Profit Factor`: $\frac{\sum (\text{net\_pnl} > 0)}{\vert{}\sum (\text{net\_pnl} < 0)\vert{}}$

   * `Time in Market (%)`: Mean of `equity_df['in_position'] * 100`

### Task 6: Build Streamlit Interactive Dashboard (`app.py`)

1. Configure page: `st.set_page_config(page_title="US100 Quant Strategy Lab", layout="wide")`.

2. **Sidebar Parameters:**

   * Date Range Picker (default: `2006-03-01` to latest available date, ensuring 13 months of warmup for 12M Momentum).

   * Initial Capital (`$50,000`), Risk per 1 ADR (`1.0%`), ADR Lookback (`14` days), Friction (`2.0` bps).

   * IBS Controls: Entry Threshold (`0.10`), Exit Threshold (`0.50`), Max Hold Sessions (`5`).

   * Button to Force Refresh Yahoo Finance Cache.

3. **Main Layout:**

   * **Row 1:** Side-by-side Performance Comparison Table (`st.dataframe` or metric cards) comparing **IBS Strategy**, **12-Month Momentum**, and **US100 Buy & Hold**.

   * **Row 2:** Interactive Plotly 2-row subplot:

     * Top Chart: Equity Curves (`Log` / `Linear` toggle) for IBS, 12M Momentum, and Buy & Hold.

     * Bottom Chart: Underwater Drawdown (%) Curves.

   * **Row 3:** Two tabs (`Tab 1: IBS Trade Log & Distribution`, `Tab 2: 12M Momentum Trade Log & Distribution`) with full trade tables and CSV download buttons.

### Task 7: Automated Terminal Verification

1. Run headless smoke test in terminal to verify data fetching, indicator alignment, and both backtest engines:

   ```
   python -c "from src.data_loader import load_us100_data; from src.indicators import compute_indicators; from src.backtester import run_ibs_strategy, run_momentum_strategy; from src.metrics import calculate_metrics; df = compute_indicators(load_us100_data()); df_valid = df.dropna().copy(); ibs_eq, ibs_tr = run_ibs_strategy(df_valid); mom_eq, mom_tr = run_momentum_strategy(df_valid); print('IBS Metrics:', calculate_metrics(ibs_eq, ibs_tr)); print('Momentum Metrics:', calculate_metrics(mom_eq, mom_tr))"
   
   ```

2. Verify zero exceptions and confirm all metrics are finite numbers.

3. Launch the Streamlit application:

   ```
   streamlit run app.py
   
   ```