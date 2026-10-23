# 🎯 US100 Quantitative Strategy Lab v2.0 (Unified 100/100 Overlay & 4-Way Comparison)

An institutional quantitative research and mark-to-market backtesting platform for the **Nasdaq-100 Cash Index (`^NDX`)**. 

v2.0 eliminates capital-splitting drag and provides a **4-Way Head-to-Head Comparison**:
1. **Strategy A Solo:** Internal Bar Strength (IBS) Mean-Reversion (100% allocation)
2. **Strategy B Solo:** 12-Month Momentum Trend-Following (100% allocation)
3. **🔥 Combined 100/100 Overlay (Unified Stack):** Both strategies run simultaneously against a single unified equity base with a hard leverage cap (`max_leverage = 1.5x`) and idle cash yield (SOFR/T-Bill cash sweep).
4. **Benchmark:** Nasdaq-100 (`^NDX`) Buy & Hold (100% allocation)

---

## 🏗️ System Architecture

```
AG02/
├── data/
│   └── us100_daily.parquet         # Auto-cached RTH OHLCV data (^NDX)
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # yfinance fetcher + Parquet cache validation
│   ├── indicators.py               # Vectorized IBS, ADR_14, Effective ADR, and 12M Momentum
│   ├── backtester.py               # Solo and Unified 100/100 Overlay backtest engines
│   └── metrics.py                  # Institutional Sortino, Sharpe, CAGR, Max DD, etc.
├── tests/
│   └── test_quant_lab.py           # 8-part comprehensive unit & integration test suite
├── app.py                          # Streamlit interactive dashboard with 4-Way comparison
├── requirements.txt                # Pinned dependencies
└── README.md                       # Project documentation & execution guide
```

---

## 🧮 Mathematical Enhancements in v2.0

### 1. Anti-Flash-Crash Effective ADR (`src/indicators.py`)
Protects against sudden overnight gaps or cascades:
$$\text{TrueRange}_t = \max\left(\text{High}_t - \text{Low}_t,\; \vert{}\text{High}_t - \text{Close}_{t-1}\vert{},\; \vert{}\text{Low}_t - \text{Close}_{t-1}\vert{}\right)$$
$$\text{Effective\_ADR}_t = \max\left(ADR_{14, t},\; \text{TrueRange}_t,\; 10^{-8}\right)$$

### 2. Corrected Institutional Sortino Ratio (`src/metrics.py`)
Downside deviation is computed over all $N$ trading sessions (preserving zero-return cash days):
$$\sigma_{\text{downside}} = \sqrt{\frac{252}{N} \sum_{t=1}^{N} \min(0, R_t)^2}$$
$$\text{Sortino Ratio} = \frac{\text{CAGR}}{\sigma_{\text{downside}}}$$

### 3. Unified 100/100 Overlay Engine (`src/backtester.py`)
- Simultaneous execution of IBS & Momentum on 100% of the active account equity.
- Uninvested margin earns cash sweep yield ($\text{Cash}_{t-1} \times \frac{\text{Cash\_Yield}}{252}$).
- Hard notional leverage ceiling enforced dynamically:
  $$\text{Leverage} = \frac{(Units_{\text{ibs}} + Units_{\text{mom}}) \times \text{Close}_t}{E_t} \le \text{max\_leverage}$$

---

## 🚀 How to Run

### 1. Run Test Suite
```bash
python tests/test_quant_lab.py
```

### 2. Run Headless Verification
```bash
python -c "from src.data_loader import load_us100_data; from src.indicators import compute_indicators; from src.backtester import run_unified_overlay_strategy; from src.metrics import calculate_metrics; df = compute_indicators(load_us100_data()).dropna().copy(); eq, tr = run_unified_overlay_strategy(df, cash_yield_annual=0.04); print('Overlay Metrics:', calculate_metrics(eq, tr))"
```

### 3. Launch Streamlit Dashboard
```bash
cd "OneDrive\ドキュメント\AG02"
streamlit run app.py
```
