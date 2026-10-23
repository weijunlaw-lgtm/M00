# 🏛️ US100 Quantitative Strategy Lab v3.0 (Institutional Multi-Engine Overlay)

An institutional quantitative research and mark-to-market backtesting platform for the **Nasdaq-100 Cash Index (`^NDX`)**. 

v3.0 implements the complete institutional multi-engine architecture, eliminating leverage starvation and risk-regime mismatch through:
1. **Shock-Damped Effective ADR:** Prevents oversizing during waterfall cascades while preserving dip entry size.
2. **3-Tranche Momentum:** Multi-timeframe conviction (3M 25%, 6M 35%, 12M 40%) capturing post-crash V-recoveries.
3. **Regime-Adaptive Asymmetry:** $SMA_{200}$ regime switch (Bull: 1.35% Mom / 1.0% IBS; Bear: 0.60% Mom / 1.5% IBS).
4. **Volatility-Targeted Dynamic Leverage:** Scales between 1.0x and 2.0x inversely with 20-day realized volatility.
5. **Dual Catastrophic Circuit Breakers:** Intraday IBS ATR Stop ($-2.50 \times ADR_{14}$) and Momentum Chandelier Stop ($-3.50 \times ADR_{14}$).
6. **Floating 13-Week T-Bill Yield (`^IRX`):** Historical treasury yield credited fairly across all active strategies.
7. **Institutional Walk-Forward Validation:** Evaluates performance across In-Sample (2006–2018), Out-of-Sample (2019–2022), and Holdout (2023–Present).
8. **Parameter Sensitivity Surfaces:** 2D stability heatmaps over Sharpe and Calmar plateaus.

---

## 🏗️ System Architecture

```
AG02/
├── data/
│   └── us100_daily.parquet         # Auto-cached daily ^NDX OHLCV + ^IRX rf_annual data
├── src/
│   ├── __init__.py
│   ├── data_loader.py              # Yahoo Finance data loader with ^NDX and ^IRX ingestion
│   ├── indicators.py               # Vectorized Shock-Damped ADR, SMA200, Realized Vol, 3-Tranche Momentum
│   ├── backtester.py               # IBS (with ATR Stop), Momentum (with Chandelier), Unified Overlay, B&H
│   ├── metrics.py                  # Standardized continuous Sortino across all N sessions, Sharpe, Calmar
│   └── validation.py               # Regime split walk-forward & 5x5 parameter sensitivity grid
├── tests/
│   └── test_quant_lab.py           # 9-part comprehensive unit and integration test suite
├── app.py                          # Streamlit v3.0 dashboard with 5 dedicated tab views
├── requirements.txt                # Pinned dependencies
└── README.md                       # Documentation & run instructions
```

---

## 🚀 How to Run

### 1. Run Complete Test Suite
```bash
python tests/test_quant_lab.py
```

### 2. Headless Verification
```bash
python -c "from src.data_loader import load_us100_data; from src.indicators import compute_indicators; from src.backtester import run_unified_overlay_strategy; from src.metrics import calculate_metrics; df = compute_indicators(load_us100_data()); eq, tr = run_unified_overlay_strategy(df.dropna()); print('Overlay Sharpe:', calculate_metrics(eq, tr)['Sharpe Ratio'])"
```

### 3. Open Interactive Dashboard
The Streamlit server is already running! Open in your browser:
👉 **[http://localhost:8501](http://localhost:8501)**
