"""Streamlit Interactive Quantitative Strategy Lab: US100 Pure v1.0 on Unified 100/100 Overlay Stack.

Features:
- Live/Cached Nasdaq-100 (^NDX) & 13-Week Treasury Bill (^IRX) integration
- 4-Way Head-to-Head comparison:
  1. Strategy A Solo: Pure v1.0 IBS Mean-Reversion (Entry < 0.10, Exit > 0.50 OR 5 days, no ATR stop)
  2. Strategy B Solo: Pure v1.0 12-Month Binary Momentum (Monthly hold, no mid-month stops)
  3. Combined 100/100 Overlay: Clean flat risk sizing, 2.0x static leverage cap,
     and fair floating T-Bill cash sweep yield
  4. Benchmark: Nasdaq-100 (^NDX) Buy & Hold
- Standardized institutional performance metrics (continuous Sortino across all N sessions)
- 5 Dedicated Tab Views:
  - Tab 1: 4-Way Head-to-Head Performance (Metrics, Dual-Axis Subplots, Leverage Timeline)
  - Tab 2: 4-Way Annual Returns Ledger (2006–Present)
  - Tab 3: Institutional Validation (In-Sample, Out-of-Sample, Holdout Testing)
  - Tab 4: Parameter Sensitivity Heatmaps (Sharpe & Calmar Stability Surfaces)
  - Tab 5: Trade Log Forensics (Categorized by Exit Reason with CSV Download)
"""

from datetime import date
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from src.backtester import (
    run_buy_and_hold,
    run_ibs_strategy,
    run_momentum_strategy,
    run_unified_overlay_strategy,
)
from src.data_loader import load_us100_data
from src.indicators import compute_indicators
from src.metrics import calculate_metrics
from src.validation import run_parameter_sensitivity_grid, run_regime_split_backtest

st.set_page_config(
    page_title="US100 Quant Strategy Lab v1.0-Unified",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def get_processed_data(force_refresh: bool = False, adr_window: int = 14) -> pd.DataFrame:
    """Fetch raw data and compute indicators with Streamlit caching."""
    raw = load_us100_data(force_refresh=force_refresh)
    enriched = compute_indicators(raw, adr_window=adr_window)
    return enriched


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.title("🏛️ Strategy Controls")

if st.sidebar.button("🔄 Force Refresh Data (^NDX & ^IRX)", use_container_width=True):
    st.cache_data.clear()
    with st.spinner("Downloading fresh ^NDX and ^IRX data..."):
        get_processed_data(force_refresh=True)
    st.sidebar.success("Cache refreshed successfully!")

base_data = get_processed_data(force_refresh=False)
min_date = base_data.index.min().date()
max_date = base_data.index.max().date()
default_start = date(2006, 3, 1) if date(2006, 3, 1) >= min_date else min_date

st.sidebar.subheader("📅 Backtest Period")
date_range = st.sidebar.date_input(
    "Select Range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_sel, end_sel = date_range
else:
    start_sel, end_sel = default_start, max_date

st.sidebar.subheader("💰 Account & Execution")
initial_capital = st.sidebar.number_input(
    "Starting Capital ($)",
    min_value=1000.0,
    max_value=10_000_000.0,
    value=50000.0,
    step=5000.0,
)

cost_bps = st.sidebar.slider(
    "Friction per side (bps)",
    min_value=0.0,
    max_value=10.0,
    value=2.0,
    step=0.5,
    help="Commission + slippage combined (2.0 bps = 0.0002)",
)

st.sidebar.subheader("⚖️ Unified Risk & Sizing")
risk_per_adr = st.sidebar.slider(
    "Risk per ADR (Flat Budget)",
    min_value=0.0050,
    max_value=0.0250,
    value=0.0125,
    step=0.0005,
    format="%.4f",
    help="Unified risk fraction applied equally to both IBS and 12M Momentum (default 1.25%).",
)

use_effective_adr = st.sidebar.checkbox(
    "Use Shock-Damped Effective ADR",
    value=True,
    help="Uses max(ADR_14, TR / 1.75) to prevent over-sizing during gap shocks. Toggle off for pure v1.0 ADR_14.",
)

max_leverage = st.sidebar.slider(
    "Max Leverage Cap (x)",
    min_value=1.0,
    max_value=3.0,
    value=2.0,
    step=0.1,
    help="Static maximum notional leverage cap across the combined overlay (default 2.0x).",
)

st.sidebar.subheader("💵 Idle Cash Yield")
use_floating_yield = st.sidebar.checkbox(
    "Use Floating T-Bill Yield (^IRX)",
    value=True,
    help="Credits actual historical 13-Week T-Bill interest across all cash balances.",
)

static_cash_yield = 0.0
if not use_floating_yield:
    static_cash_yield = st.sidebar.slider("Static Cash Yield (%)", 0.0, 8.0, 4.0, 0.25) / 100.0

st.sidebar.subheader("🎯 IBS Strategy Parameters")
ibs_entry = st.sidebar.slider("IBS Entry Threshold", 0.02, 0.25, 0.10, 0.01)
ibs_exit = st.sidebar.slider("IBS Exit Threshold", 0.30, 0.80, 0.50, 0.05)
max_hold = st.sidebar.slider("IBS Max Hold Sessions", 1, 15, 5, 1)

scale_mode = st.sidebar.radio("Equity Chart Scale", ["Logarithmic", "Linear"], index=0, horizontal=True)

# ---------------------------------------------------------
# Data Filtering & Backtest Execution
# ---------------------------------------------------------
full_df = get_processed_data(force_refresh=False)
mask = (full_df.index >= pd.Timestamp(start_sel)) & (full_df.index <= pd.Timestamp(end_sel))
df_sub = full_df.loc[mask].dropna().copy()

if len(df_sub) < 30:
    st.error("Selected date range has too few valid data points. Please expand the date range.")
    st.stop()

# 1. IBS Solo
ibs_eq, ibs_tr = run_ibs_strategy(
    df_sub,
    initial_capital=initial_capital,
    risk_per_adr=risk_per_adr,
    ibs_entry=ibs_entry,
    ibs_exit=ibs_exit,
    max_hold=max_hold,
    use_effective_adr=use_effective_adr,
    use_floating_yield=use_floating_yield,
    cash_yield_annual=static_cash_yield,
    cost_bps=cost_bps,
)

# 2. Momentum Solo
mom_eq, mom_tr = run_momentum_strategy(
    df_sub,
    initial_capital=initial_capital,
    risk_per_adr=risk_per_adr,
    use_effective_adr=use_effective_adr,
    use_floating_yield=use_floating_yield,
    cash_yield_annual=static_cash_yield,
    cost_bps=cost_bps,
)

# 3. Combined 100/100 Overlay
overlay_eq, overlay_tr = run_unified_overlay_strategy(
    df_sub,
    initial_capital=initial_capital,
    risk_per_adr=risk_per_adr,
    ibs_entry=ibs_entry,
    ibs_exit=ibs_exit,
    max_hold=max_hold,
    max_leverage=max_leverage,
    use_effective_adr=use_effective_adr,
    use_floating_yield=use_floating_yield,
    cash_yield_annual=static_cash_yield,
    cost_bps=cost_bps,
)

# 4. Buy & Hold Benchmark
bnh_eq = run_buy_and_hold(df_sub, initial_capital=initial_capital, cost_bps=cost_bps)

# Metrics
ibs_m = calculate_metrics(ibs_eq, ibs_tr, initial_capital=initial_capital)
mom_m = calculate_metrics(mom_eq, mom_tr, initial_capital=initial_capital)
ovl_m = calculate_metrics(overlay_eq, overlay_tr, initial_capital=initial_capital)
bnh_m = calculate_metrics(bnh_eq, pd.DataFrame(), initial_capital=initial_capital)

# ---------------------------------------------------------
# Header & KPI Cards
# ---------------------------------------------------------
st.title("🏛️ US100 Quantitative Strategy Lab")
st.markdown(
    "**Unified Multi-Engine Quantitative Architecture on Nasdaq-100 (`^NDX`)**. "
    "Featuring **Pure v1.0 Strategy Rules**: IBS Mean-Reversion dip-buying, "
    "**12-Month Binary Momentum** with monthly hold, **Clean Flat Risk Sizing**, "
    "**Shock-Damped Effective ADR Denominator**, and **Historical Floating T-Bill Yield (`^IRX`)**."
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric(
        "IBS Solo Final Equity",
        f"${ibs_eq['equity'].iloc[-1]:,.2f}",
        f"{ibs_m['CAGR (%)']}% CAGR | Sharpe {ibs_m['Sharpe Ratio']:.2f}",
    )
with k2:
    st.metric(
        "12M Momentum Solo",
        f"${mom_eq['equity'].iloc[-1]:,.2f}",
        f"{mom_m['CAGR (%)']}% CAGR | Sharpe {mom_m['Sharpe Ratio']:.2f}",
    )
with k3:
    st.metric(
        "🔥 Combined 100/100 Overlay",
        f"${overlay_eq['equity'].iloc[-1]:,.2f}",
        f"{ovl_m['CAGR (%)']}% CAGR | Sharpe {ovl_m['Sharpe Ratio']:.2f}",
    )
with k4:
    st.metric(
        "Buy & Hold Benchmark",
        f"${bnh_eq['equity'].iloc[-1]:,.2f}",
        f"{bnh_m['CAGR (%)']}% CAGR | MaxDD {bnh_m['Max Drawdown (%)']:.1f}%",
    )

st.markdown("---")

# ---------------------------------------------------------
# Main Tabs Layout
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 4-Way Head-to-Head Performance",
    "📅 Annual Returns Ledger",
    "🔬 Institutional Walk-Forward Validation",
    "🗺️ Parameter Sensitivity Surfaces",
    "🕵️ Trade Log Forensics",
])

# =========================================================
# TAB 1: 4-Way Head-to-Head Performance
# =========================================================
with tab1:
    st.subheader("📊 4-Way Performance Matrix Comparison")

    comparison_dict = {
        "Total Return (%)": [
            f"{ibs_m['Total Return (%)']:,.2f}%",
            f"{mom_m['Total Return (%)']:,.2f}%",
            f"{ovl_m['Total Return (%)']:,.2f}%",
            f"{bnh_m['Total Return (%)']:,.2f}%",
        ],
        "CAGR (%)": [
            f"{ibs_m['CAGR (%)']:,.2f}%",
            f"{mom_m['CAGR (%)']:,.2f}%",
            f"{ovl_m['CAGR (%)']:,.2f}%",
            f"{bnh_m['CAGR (%)']:,.2f}%",
        ],
        "Annualized Volatility (%)": [
            f"{ibs_m['Annualized Volatility (%)']:,.2f}%",
            f"{mom_m['Annualized Volatility (%)']:,.2f}%",
            f"{ovl_m['Annualized Volatility (%)']:,.2f}%",
            f"{bnh_m['Annualized Volatility (%)']:,.2f}%",
        ],
        "Sharpe Ratio": [
            f"{ibs_m['Sharpe Ratio']:.2f}",
            f"{mom_m['Sharpe Ratio']:.2f}",
            f"{ovl_m['Sharpe Ratio']:.2f}",
            f"{bnh_m['Sharpe Ratio']:.2f}",
        ],
        "Sortino Ratio (Continuous)": [
            f"{ibs_m['Sortino Ratio']:.2f}",
            f"{mom_m['Sortino Ratio']:.2f}",
            f"{ovl_m['Sortino Ratio']:.2f}",
            f"{bnh_m['Sortino Ratio']:.2f}",
        ],
        "Max Drawdown (%)": [
            f"{ibs_m['Max Drawdown (%)']:,.2f}%",
            f"{mom_m['Max Drawdown (%)']:,.2f}%",
            f"{ovl_m['Max Drawdown (%)']:,.2f}%",
            f"{bnh_m['Max Drawdown (%)']:,.2f}%",
        ],
        "Calmar Ratio": [
            f"{ibs_m['Calmar Ratio']:.2f}",
            f"{mom_m['Calmar Ratio']:.2f}",
            f"{ovl_m['Calmar Ratio']:.2f}",
            f"{bnh_m['Calmar Ratio']:.2f}",
        ],
        "Total Trades": [
            f"{ibs_m['Total Trades']:,}",
            f"{mom_m['Total Trades']:,}",
            f"{ovl_m['Total Trades']:,}",
            "1 (Buy & Hold)",
        ],
        "Win Rate (%)": [
            f"{ibs_m['Win Rate (%)']:.2f}%",
            f"{mom_m['Win Rate (%)']:.2f}%",
            f"{ovl_m['Win Rate (%)']:.2f}%",
            "N/A",
        ],
        "Profit Factor": [
            f"{ibs_m['Profit Factor']:.2f}",
            f"{mom_m['Profit Factor']:.2f}",
            f"{ovl_m['Profit Factor']:.2f}",
            "N/A",
        ],
        "Time in Market (%)": [
            f"{ibs_m['Time in Market (%)']:.2f}%",
            f"{mom_m['Time in Market (%)']:.2f}%",
            f"{ovl_m['Time in Market (%)']:.2f}%",
            "100.00%",
        ],
        "Cumulative Interest Earned ($)": [
            f"${ibs_m['Cumulative Interest Earned ($)']:,.2f}",
            f"${mom_m['Cumulative Interest Earned ($)']:,.2f}",
            f"${ovl_m['Cumulative Interest Earned ($)']:,.2f}",
            "$0.00",
        ],
        "Average Notional Leverage": [
            f"{ibs_m['Average Notional Leverage (x)']:.2f}x",
            f"{mom_m['Average Notional Leverage (x)']:.2f}x",
            f"{ovl_m['Average Notional Leverage (x)']:.2f}x",
            "1.00x",
        ],
        "Peak Leverage Reached": [
            f"{ibs_m['Max Notional Leverage (x)']:.2f}x",
            f"{mom_m['Max Notional Leverage (x)']:.2f}x",
            f"{ovl_m['Max Notional Leverage (x)']:.2f}x",
            "1.00x",
        ],
    }

    comp_df = pd.DataFrame(
        comparison_dict,
        index=[
            "Strategy A (IBS Solo)",
            "Strategy B (12M Momentum Solo)",
            "🔥 Combined 100/100 Overlay",
            "Buy & Hold Benchmark (^NDX)",
        ],
    ).T

    st.dataframe(comp_df, use_container_width=True)

    # 3-row Plotly charts: Equity, Drawdown, and Leverage Exposure
    st.subheader("📈 Interactive Equity Progression, Underwater Drawdowns & Leverage Timeline")

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=(
            f"Mark-to-Market Equity Progression (${scale_mode} Scale)",
            "Underwater Drawdown (%)",
            "Active Notional Leverage & Max Cap",
        ),
    )

    c_ibs = "#10B981"
    c_mom = "#3B82F6"
    c_ovl = "#8B5CF6"
    c_bnh = "#F59E0B"

    # Row 1: Equity
    fig.add_trace(go.Scatter(x=ibs_eq.index, y=ibs_eq["equity"], name="IBS Solo", line=dict(color=c_ibs, width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=mom_eq.index, y=mom_eq["equity"], name="12M Momentum Solo", line=dict(color=c_mom, width=1.6)), row=1, col=1)
    fig.add_trace(go.Scatter(x=overlay_eq.index, y=overlay_eq["equity"], name="🔥 Combined 100/100 Overlay", line=dict(color=c_ovl, width=2.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=bnh_eq.index, y=bnh_eq["equity"], name="Buy & Hold Benchmark", line=dict(color=c_bnh, width=1.5, dash="dot")), row=1, col=1)

    # Row 2: Drawdowns
    fig.add_trace(go.Scatter(x=ibs_eq.index, y=ibs_eq["drawdown_pct"], name="IBS Drawdown", line=dict(color=c_ibs, width=1.2), fill="tozeroy", fillcolor="rgba(16, 185, 129, 0.08)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=mom_eq.index, y=mom_eq["drawdown_pct"], name="Mom Drawdown", line=dict(color=c_mom, width=1.2), fill="tozeroy", fillcolor="rgba(59, 130, 246, 0.08)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=overlay_eq.index, y=overlay_eq["drawdown_pct"], name="Overlay Drawdown", line=dict(color=c_ovl, width=1.8), fill="tozeroy", fillcolor="rgba(139, 92, 246, 0.20)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=bnh_eq.index, y=bnh_eq["drawdown_pct"], name="B&H Drawdown", line=dict(color=c_bnh, width=1.2, dash="dash")), row=2, col=1)

    # Row 3: Leverage
    fig.add_trace(go.Scatter(x=overlay_eq.index, y=overlay_eq["leverage"], name="Overlay Active Leverage", line=dict(color=c_ovl, width=1.5)), row=3, col=1)
    if "max_lev_cap" in overlay_eq.columns:
        fig.add_trace(go.Scatter(x=overlay_eq.index, y=overlay_eq["max_lev_cap"], name="Max Leverage Cap", line=dict(color="red", width=1.2, dash="dash")), row=3, col=1)

    y_type = "log" if scale_mode == "Logarithmic" else "linear"
    fig.update_yaxes(type=y_type, title_text="Portfolio Value ($)", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
    fig.update_yaxes(title_text="Leverage (x)", row=3, col=1)
    fig.update_xaxes(title_text="Date", row=3, col=1)

    fig.update_layout(
        height=850,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


# =========================================================
# TAB 2: Annual Returns Ledger
# =========================================================
with tab2:
    st.subheader("📅 Year-by-Year Calendar Returns Ledger (4-Way)")

    annual_ibs = ibs_eq["equity"].resample("YE").last().pct_change() * 100.0
    annual_mom = mom_eq["equity"].resample("YE").last().pct_change() * 100.0
    annual_ovl = overlay_eq["equity"].resample("YE").last().pct_change() * 100.0
    annual_bnh = bnh_eq["equity"].resample("YE").last().pct_change() * 100.0

    first_yr = ibs_eq.index[0].year
    annual_ibs.iloc[0] = ((ibs_eq["equity"].loc[ibs_eq.index.year == first_yr].iloc[-1] / initial_capital) - 1.0) * 100.0
    annual_mom.iloc[0] = ((mom_eq["equity"].loc[mom_eq.index.year == first_yr].iloc[-1] / initial_capital) - 1.0) * 100.0
    annual_ovl.iloc[0] = ((overlay_eq["equity"].loc[overlay_eq.index.year == first_yr].iloc[-1] / initial_capital) - 1.0) * 100.0
    annual_bnh.iloc[0] = ((bnh_eq["equity"].loc[bnh_eq.index.year == first_yr].iloc[-1] / initial_capital) - 1.0) * 100.0

    annual_df = pd.DataFrame({
        "Year": annual_ibs.index.year,
        "IBS Solo (%)": annual_ibs.values,
        "Momentum Solo (%)": annual_mom.values,
        "🔥 Combined 100/100 Overlay (%)": annual_ovl.values,
        "Buy & Hold Benchmark (%)": annual_bnh.values,
    }).sort_values("Year", ascending=False)

    annual_display = annual_df.copy()
    for c in ["IBS Solo (%)", "Momentum Solo (%)", "🔥 Combined 100/100 Overlay (%)", "Buy & Hold Benchmark (%)"]:
        annual_display[c] = annual_display[c].map("{:+,.2f}%".format)

    st.dataframe(annual_display, use_container_width=True, hide_index=True)


# =========================================================
# TAB 3: Institutional Validation (IS / OOS / Holdout)
# =========================================================
with tab3:
    st.subheader("🔬 3-Period Walk-Forward & Macroeconomic Regime Breakdown")
    st.markdown(
        """
        To confirm statistical robustness and ensure zero over-fitting, performance is partitioned across:
        1. **In-Sample Period (2006–2018):** GFC 2008 Crash, post-crisis zero-rate regime.
        2. **Out-of-Sample Period (2019–2022):** COVID-19 waterfall collapse & recovery, 2022 Fed rate hike bear market.
        3. **Holdout Testing (2023–Present):** Generative AI bull market & modern high-rate regime.
        """
    )
    with st.spinner("Calculating walk-forward validation across regimes..."):
        validation_df = run_regime_split_backtest(df_sub, initial_capital=initial_capital)

    val_display = validation_df.copy()
    val_display["Overlay CAGR (%)"] = val_display["Overlay CAGR (%)"].map("{:+,.2f}%".format)
    val_display["Overlay MaxDD (%)"] = val_display["Overlay MaxDD (%)"].map("{:,.2f}%".format)
    val_display["Overlay Sharpe"] = val_display["Overlay Sharpe"].map("{:.2f}".format)
    val_display["Overlay Calmar"] = val_display["Overlay Calmar"].map("{:.2f}".format)
    val_display["Overlay WinRate (%)"] = val_display["Overlay WinRate (%)"].map("{:.2f}%".format)
    val_display["B&H CAGR (%)"] = val_display["B&H CAGR (%)"].map("{:+,.2f}%".format)
    val_display["B&H MaxDD (%)"] = val_display["B&H MaxDD (%)"].map("{:,.2f}%".format)
    val_display["B&H Sharpe"] = val_display["B&H Sharpe"].map("{:.2f}".format)
    val_display["IBS CAGR (%)"] = val_display["IBS CAGR (%)"].map("{:+,.2f}%".format)
    val_display["MOM CAGR (%)"] = val_display["MOM CAGR (%)"].map("{:+,.2f}%".format)

    st.dataframe(val_display, use_container_width=True, hide_index=True)


# =========================================================
# TAB 4: Parameter Sensitivity Surfaces
# =========================================================
with tab4:
    st.subheader("🗺️ Parameter Sensitivity Heatmaps (Sharpe & Calmar Stability)")
    st.markdown("Evaluates parameter stability around `ibs_entry` and `risk_per_adr` to verify wide plateau stability.")

    if st.button("Generate 5x5 Parameter Sensitivity Grid"):
        with st.spinner("Evaluating 25 simulation matrices across parameter space..."):
            grid_out = run_parameter_sensitivity_grid(df_sub, initial_capital=initial_capital)

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            fig_sh = px.imshow(
                grid_out["sharpe_matrix"],
                labels=dict(x="Risk per ADR", y="IBS Entry Threshold", color="Sharpe Ratio"),
                title="Overlay Sharpe Ratio Stability Surface",
                color_continuous_scale="Viridis",
                text_auto=".2f",
            )
            fig_sh.update_layout(template="plotly_white")
            st.plotly_chart(fig_sh, use_container_width=True)

        with col_h2:
            fig_cal = px.imshow(
                grid_out["calmar_matrix"],
                labels=dict(x="Risk per ADR", y="IBS Entry Threshold", color="Calmar Ratio"),
                title="Overlay Calmar Ratio Stability Surface",
                color_continuous_scale="Plasma",
                text_auto=".2f",
            )
            fig_cal.update_layout(template="plotly_white")
            st.plotly_chart(fig_cal, use_container_width=True)
    else:
        st.info("Click the button above to run the 5x5 parameter grid analysis.")


# =========================================================
# TAB 5: Trade Log Forensics
# =========================================================
with tab5:
    st.subheader("🕵️ Institutional Trade Log Forensics")

    def format_trades(df_tr: pd.DataFrame) -> pd.DataFrame:
        if df_tr.empty:
            return df_tr
        disp = df_tr.copy()
        disp["entry_date"] = pd.to_datetime(disp["entry_date"]).dt.strftime("%Y-%m-%d")
        disp["exit_date"] = pd.to_datetime(disp["exit_date"]).dt.strftime("%Y-%m-%d")
        disp["entry_price"] = disp["entry_price"].map("${:,.2f}".format)
        disp["exit_price"] = disp["exit_price"].map("${:,.2f}".format)
        disp["units"] = disp["units"].map("{:,.4f}".format)
        disp["net_pnl"] = disp["net_pnl"].map("${:,.2f}".format)
        return disp

    sub_t1, sub_t2, sub_t3 = st.tabs(["🔥 Overlay Trades", "IBS Solo Trades", "Momentum Solo Trades"])

    with sub_t1:
        if not overlay_tr.empty:
            reason_filter = st.multiselect(
                "Filter Exit Reasons",
                options=list(overlay_tr["exit_reason"].unique()),
                default=list(overlay_tr["exit_reason"].unique()),
            )
            filtered_ovl = overlay_tr[overlay_tr["exit_reason"].isin(reason_filter)]

            c_f1, c_f2, c_f3 = st.columns(3)
            with c_f1:
                st.metric("Displayed Trades", f"{len(filtered_ovl):,}")
            with c_f2:
                win_pct = (filtered_ovl["net_pnl"] > 0).mean() * 100 if len(filtered_ovl) > 0 else 0
                st.metric("Win Rate", f"{win_pct:.2f}%")
            with c_f3:
                avg_pnl = filtered_ovl["net_pnl"].mean() if len(filtered_ovl) > 0 else 0
                st.metric("Avg Trade PnL", f"${avg_pnl:,.2f}")

            st.dataframe(format_trades(filtered_ovl), use_container_width=True, height=400)
            csv_data = filtered_ovl.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Overlay Trades CSV", data=csv_data, file_name="us100_overlay_trades.csv", mime="text/csv")
        else:
            st.info("No trades executed.")

    with sub_t2:
        if not ibs_tr.empty:
            st.dataframe(format_trades(ibs_tr), use_container_width=True, height=400)
            csv_data = ibs_tr.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download IBS Trades CSV", data=csv_data, file_name="us100_ibs_trades.csv", mime="text/csv")

    with sub_t3:
        if not mom_tr.empty:
            st.dataframe(format_trades(mom_tr), use_container_width=True, height=400)
            csv_data = mom_tr.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Momentum Trades CSV", data=csv_data, file_name="us100_mom_trades.csv", mime="text/csv")
