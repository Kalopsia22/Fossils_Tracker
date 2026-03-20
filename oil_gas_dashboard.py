"""
Global Crude Oil & Natural Gas Tracker Dashboard
Run with: streamlit run oil_gas_dashboard.py
Requires: pip install streamlit plotly pandas numpy requests
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import requests

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Global Oil & Gas Tracker",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# THEME & STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif;
}

/* ---- Dark industrial background ---- */
.stApp {
    background: #0a0d14;
    color: #e8e4d9;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #0f1420 !important;
    border-right: 1px solid #1e2840;
}

/* ---- Metric cards ---- */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #111827 0%, #1a2035 100%);
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 16px 20px !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

div[data-testid="metric-container"] label {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #6b8cba !important;
}

div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.8rem !important;
    font-weight: 800;
    color: #f0e6c8 !important;
}

div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.78rem !important;
}

/* ---- Tab styling ---- */
div[data-testid="stTabs"] button {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #5a7a9e !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 20px !important;
}

div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f5a623 !important;
    border-bottom: 2px solid #f5a623 !important;
    background: transparent !important;
}

/* ---- Section headers ---- */
.section-header {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.05rem;
    letter-spacing: 0.04em;
    color: #c8a96e;
    text-transform: uppercase;
    margin: 0.5rem 0 1rem 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e3a5f;
}

/* ---- Hero banner ---- */
.hero-banner {
    background: linear-gradient(135deg, #0d1b2e 0%, #112240 50%, #0d1b2e 100%);
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    padding: 22px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
}

.hero-title {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 2rem;
    color: #f0e6c8;
    margin: 0;
    line-height: 1.1;
}

.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: #5a7a9e;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
}

/* ---- Badge chips ---- */
.badge {
    display: inline-block;
    background: #1a2e4a;
    border: 1px solid #2a4a6e;
    border-radius: 20px;
    padding: 3px 12px;
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    color: #7ab3d4;
    letter-spacing: 0.1em;
    margin-right: 6px;
}

.badge-live {
    background: #1a3020;
    border-color: #2a5530;
    color: #5ecb80;
}

/* ---- Info boxes ---- */
.info-box {
    background: #111827;
    border-left: 3px solid #f5a623;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    font-size: 0.85rem;
    color: #b0c4de;
    margin: 8px 0;
}

/* ---- Plotly chart override ---- */
.js-plotly-plot .plotly .modebar {
    background: transparent !important;
}

/* ---- Scrollbar ---- */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0a0d14; }
::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }

/* ---- Select/Slider labels ---- */
label[data-testid="stWidgetLabel"] p {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b8cba !important;
}

/* ---- Divider ---- */
hr { border-color: #1e2840; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS / DATA GENERATORS
# ─────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10,15,25,0.6)",
    font=dict(family="Space Mono, monospace", color="#8aa8c8", size=11),
    xaxis=dict(gridcolor="#1a2840", zerolinecolor="#1a2840", showgrid=True),
    yaxis=dict(gridcolor="#1a2840", zerolinecolor="#1a2840", showgrid=True),
    margin=dict(l=50, r=20, t=40, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
)

def hex_to_rgba(hex_color: str, alpha: float = 0.08) -> str:
    """Convert #RRGGBB to rgba(r,g,b,alpha)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def make_date_range(days: int) -> pd.DatetimeIndex:
    end = datetime.today()
    return pd.date_range(end=end, periods=days, freq="D")


@st.cache_data(ttl=3600)
def gen_crude_prices(days: int = 365) -> pd.DataFrame:
    """Simulate WTI & Brent crude prices with realistic dynamics."""
    np.random.seed(42)
    dates = make_date_range(days)
    wti_base, brent_base = 75.0, 79.0
    shocks = np.random.normal(0, 0.6, days).cumsum()
    seasonal = 3 * np.sin(np.linspace(0, 4 * np.pi, days))
    wti = wti_base + shocks + seasonal + np.random.normal(0, 0.4, days)
    brent = brent_base + shocks + seasonal + np.random.normal(0, 0.4, days) + np.random.normal(2.5, 0.3, days)
    dubai = brent - np.random.uniform(0.8, 1.5, days)
    volume_wti = np.random.randint(800_000, 1_400_000, days)
    volume_brent = np.random.randint(600_000, 1_100_000, days)
    return pd.DataFrame({"date": dates, "WTI": wti, "Brent": brent, "Dubai": dubai,
                         "vol_wti": volume_wti, "vol_brent": volume_brent})


@st.cache_data(ttl=3600)
def gen_natgas_prices(days: int = 365) -> pd.DataFrame:
    """Simulate Henry Hub, TTF, NBP natural gas prices."""
    np.random.seed(7)
    dates = make_date_range(days)
    base_hh = 2.8
    seasonal = 1.2 * np.sin(np.linspace(0, 4 * np.pi, days) + np.pi)
    shocks = np.random.normal(0, 0.12, days).cumsum()
    hh = np.clip(base_hh + shocks + seasonal + np.random.normal(0, 0.08, days), 1.5, 6.5)
    ttf = hh * np.random.uniform(3.2, 4.0, days) + np.random.normal(0, 0.3, days)
    nbp = ttf * np.random.uniform(0.95, 1.05, days) + np.random.normal(0, 0.2, days)
    lng_asia = ttf * np.random.uniform(1.05, 1.25, days) + np.random.normal(0, 0.5, days)
    return pd.DataFrame({"date": dates, "Henry Hub": hh, "TTF (Europe)": ttf,
                         "NBP (UK)": nbp, "JKM (LNG Asia)": lng_asia})


@st.cache_data(ttl=3600)
def gen_production_data() -> pd.DataFrame:
    """Top crude producers (kb/d)."""
    return pd.DataFrame({
        "Country": ["United States", "Saudi Arabia", "Russia", "Canada", "Iraq",
                    "UAE", "Brazil", "Iran", "Kuwait", "China"],
        "Production_kbd": [13_300, 9_800, 9_200, 5_700, 4_500,
                           3_800, 3_600, 3_400, 2_700, 4_200],
        "YoY_pct": [3.2, -1.5, -4.8, 2.1, 1.8, 2.5, 5.6, 1.2, -0.4, 2.8],
        "Type": ["Non-OPEC", "OPEC", "Non-OPEC", "Non-OPEC", "OPEC",
                 "OPEC", "Non-OPEC", "OPEC", "OPEC", "Non-OPEC"],
    })


@st.cache_data(ttl=3600)
def gen_inventory_data(days: int = 180) -> pd.DataFrame:
    """US EIA-style crude & gasoline inventory data (MMbbl)."""
    np.random.seed(99)
    dates = make_date_range(days)
    crude_inv = 420 + np.random.normal(0, 1.5, days).cumsum() + 15 * np.sin(np.linspace(0, 2 * np.pi, days))
    gasoline = 220 + np.random.normal(0, 0.8, days).cumsum() + 8 * np.sin(np.linspace(0, 2 * np.pi, days) + 1)
    distillate = 115 + np.random.normal(0, 0.5, days).cumsum()
    return pd.DataFrame({"date": dates, "Crude Oil": crude_inv,
                         "Gasoline": gasoline, "Distillate": distillate})


@st.cache_data(ttl=3600)
def gen_natgas_storage(days: int = 180) -> pd.DataFrame:
    """US Natural Gas storage (Bcf)."""
    np.random.seed(55)
    dates = make_date_range(days)
    storage = 2100 + np.random.normal(0, 15, days).cumsum() + 500 * np.sin(np.linspace(0, 2 * np.pi, days))
    five_yr_avg = 2000 + 450 * np.sin(np.linspace(0, 2 * np.pi, days))
    return pd.DataFrame({"date": dates, "Storage (Bcf)": storage, "5-Year Avg": five_yr_avg})


@st.cache_data(ttl=3600)
def gen_field_locations() -> pd.DataFrame:
    """Major global oil/gas field locations."""
    return pd.DataFrame({
        "Field": ["Ghawar", "Burgan", "Ahvaz", "Permian Basin", "Rumaila",
                  "Safaniya", "Cantarell", "Samotlor", "Pembina", "Daqing",
                  "Marcellus Shale", "Haynesville", "Barnett", "Groningen",
                  "North Field", "Siberian Gas", "Appalachian"],
        "Lat": [24.8, 29.0, 31.3, 32.0, 30.4, 27.9, 19.7, 61.5, 52.8, 46.6,
                41.5, 32.0, 32.8, 53.3, 25.9, 61.0, 38.5],
        "Lon": [49.5, 47.8, 49.5, -102.0, 47.1, 49.5, -91.9, 68.4, -114.5, 124.7,
                -77.5, -93.5, -97.4, 6.8, 51.4, 73.0, -81.5],
        "Type": ["Crude", "Crude", "Crude", "Crude", "Crude",
                 "Crude", "Crude", "Crude", "Crude", "Crude",
                 "Natural Gas", "Natural Gas", "Natural Gas", "Natural Gas",
                 "Natural Gas", "Natural Gas", "Natural Gas"],
        "Reserves_Gboe": [75, 66, 65, 55, 43, 37, 18, 14, 8, 7,
                          141, 75, 44, 2.7, 900, 1688, 32],
        "Country": ["Saudi Arabia", "Kuwait", "Iran", "USA", "Iraq",
                    "Saudi Arabia", "Mexico", "Russia", "Canada", "China",
                    "USA", "USA", "USA", "Netherlands", "Qatar", "Russia", "USA"],
    })


@st.cache_data(ttl=3600)
def gen_refinery_margins(days: int = 365) -> pd.DataFrame:
    """Crack spread / refinery margin data."""
    np.random.seed(11)
    dates = make_date_range(days)
    wti_321 = 18 + np.random.normal(0, 0.8, days).cumsum() + 5 * np.sin(np.linspace(0, 4 * np.pi, days))
    brent_321 = wti_321 + np.random.normal(1.5, 0.3, days)
    return pd.DataFrame({"date": dates, "WTI 3-2-1 Crack": wti_321, "Brent 3-2-1 Crack": brent_321})


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 10px 0 20px;'>
        <div style='font-size:2.5rem'>🛢️</div>
        <div style='font-family:Syne,sans-serif; font-weight:800; font-size:1.1rem; color:#f0e6c8;'>OIL & GAS</div>
        <div style='font-family:Space Mono,monospace; font-size:0.6rem; color:#5a7a9e; letter-spacing:0.15em;'>GLOBAL TRACKER</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("<div class='section-header'>⚙ Parameters</div>", unsafe_allow_html=True)

    lookback = st.selectbox("Price History Window",
                            options=[30, 90, 180, 365, 730],
                            index=2,
                            format_func=lambda x: f"{x} Days" if x < 365 else f"{x//365} Year{'s' if x > 365 else ''}")

    commodity = st.multiselect("Crude Benchmarks",
                               options=["WTI", "Brent", "Dubai"],
                               default=["WTI", "Brent"])

    natgas_hubs = st.multiselect("Natural Gas Hubs",
                                 options=["Henry Hub", "TTF (Europe)", "NBP (UK)", "JKM (LNG Asia)"],
                                 default=["Henry Hub", "TTF (Europe)"])

    st.markdown("---")
    st.markdown("<div class='section-header'>🗺 Map Filters</div>", unsafe_allow_html=True)
    map_commodity = st.radio("Show Fields", ["Both", "Crude Only", "Natural Gas Only"])
    map_style = st.selectbox("Map Projection", ["natural earth", "orthographic", "equirectangular", "mercator"])

    st.markdown("---")
    st.markdown("<div class='section-header'>📊 Chart Style</div>", unsafe_allow_html=True)
    chart_type = st.radio("Price Chart Type", ["Line", "Candlestick (OHLC)"])
    show_volume = st.toggle("Show Trading Volume", value=True)
    show_ma = st.toggle("Show Moving Averages", value=True)
    ma_period = st.slider("MA Period (days)", 5, 50, 20) if show_ma else 20

    st.markdown("---")
    st.markdown("""
    <div style='font-family:Space Mono,monospace; font-size:0.6rem; color:#2a4a6e; text-align:center; padding-top:8px;'>
        DATA: SIMULATED · EIA STRUCTURE<br>
        REFRESH: HOURLY
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
crude_df = gen_crude_prices(lookback)
ng_df = gen_natgas_prices(lookback)
prod_df = gen_production_data()
inv_df = gen_inventory_data(min(lookback, 180))
storage_df = gen_natgas_storage(min(lookback, 180))
fields_df = gen_field_locations()
margin_df = gen_refinery_margins(lookback)

# Latest values
wti_now = crude_df["WTI"].iloc[-1]
wti_prev = crude_df["WTI"].iloc[-2]
brent_now = crude_df["Brent"].iloc[-1]
brent_prev = crude_df["Brent"].iloc[-2]
hh_now = ng_df["Henry Hub"].iloc[-1]
hh_prev = ng_df["Henry Hub"].iloc[-2]
ttf_now = ng_df["TTF (Europe)"].iloc[-1]
ttf_prev = ng_df["TTF (Europe)"].iloc[-2]
spread = brent_now - wti_now

# ─────────────────────────────────────────────
# HERO BANNER
# ─────────────────────────────────────────────
st.markdown(f"""
<div class='hero-banner'>
    <div style='font-size:3rem; line-height:1;'>🛢️</div>
    <div>
        <div class='hero-title'>Global Oil & Gas Tracker</div>
        <div class='hero-sub'>Real-time commodities intelligence · {datetime.today().strftime('%d %b %Y')}</div>
        <div style='margin-top:10px;'>
            <span class='badge badge-live'>● LIVE</span>
            <span class='badge'>WTI ${wti_now:.2f}</span>
            <span class='badge'>BRENT ${brent_now:.2f}</span>
            <span class='badge'>HENRY HUB ${hh_now:.2f}/MMBtu</span>
            <span class='badge'>TTF €{ttf_now:.2f}/MWh</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# GLOBAL KPI ROW
# ─────────────────────────────────────────────
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("WTI Crude", f"${wti_now:.2f}", f"{wti_now-wti_prev:+.2f} ({(wti_now/wti_prev-1)*100:+.1f}%)")
k2.metric("Brent Crude", f"${brent_now:.2f}", f"{brent_now-brent_prev:+.2f} ({(brent_now/brent_prev-1)*100:+.1f}%)")
k3.metric("Brent–WTI Spread", f"${spread:.2f}", f"{spread - (crude_df['Brent'].iloc[-2] - crude_df['WTI'].iloc[-2]):+.2f}")
k4.metric("Henry Hub Gas", f"${hh_now:.3f}", f"{hh_now-hh_prev:+.3f} MMBtu")
k5.metric("TTF (Europe)", f"€{ttf_now:.2f}", f"{ttf_now-ttf_prev:+.2f} MWh")
k6.metric("Dubai Crude", f"${crude_df['Dubai'].iloc[-1]:.2f}", f"{crude_df['Dubai'].iloc[-1]-crude_df['Dubai'].iloc[-2]:+.2f}")

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab_prices, tab_natgas, tab_map, tab_supply, tab_inventory, tab_margins, tab_analytics = st.tabs([
    "📈 Crude Prices",
    "🔥 Natural Gas",
    "🗺️ Field Map",
    "⛽ Supply & Production",
    "🏪 Inventories",
    "🏭 Refinery Margins",
    "📊 Analytics",
])

# ╔══════════════════════════════════════════════╗
# ║  TAB 1 · CRUDE PRICES                       ║
# ╚══════════════════════════════════════════════╝
with tab_prices:
    st.markdown("<div class='section-header'>Crude Oil Benchmark Prices</div>", unsafe_allow_html=True)

    if not commodity:
        st.warning("Select at least one benchmark in the sidebar.")
    else:
        COLORS = {"WTI": "#f5a623", "Brent": "#4ecdc4", "Dubai": "#c77dff"}

        if chart_type == "Line":
            fig = go.Figure()
            for col in commodity:
                series = crude_df[col]
                ma = series.rolling(ma_period).mean() if show_ma else None
                fig.add_trace(go.Scatter(
                    x=crude_df["date"], y=series, name=col,
                    line=dict(color=COLORS[col], width=2),
                    fill="tozeroy", fillcolor=hex_to_rgba(COLORS[col], 0.07),
                ))
                if show_ma and ma is not None:
                    fig.add_trace(go.Scatter(
                        x=crude_df["date"], y=ma, name=f"{col} {ma_period}MA",
                        line=dict(color=COLORS[col], width=1.5, dash="dot"), showlegend=True,
                    ))
        else:
            # Simulate OHLC for WTI only (primary)
            primary = commodity[0]
            close = crude_df[primary].values
            high = close + np.abs(np.random.normal(0, 0.4, len(close)))
            low = close - np.abs(np.random.normal(0, 0.4, len(close)))
            open_ = np.roll(close, 1)
            fig = go.Figure(go.Candlestick(
                x=crude_df["date"], open=open_, high=high, low=low, close=close,
                name=primary, increasing_line_color="#5ecb80", decreasing_line_color="#e05c5c",
            ))

        fig.update_layout(**PLOTLY_LAYOUT, title=f"Crude Oil Prices — USD/bbl ({lookback}d)", height=380)
        st.plotly_chart(fig, use_container_width=True)

        # Volume chart
        if show_volume and chart_type == "Line":
            vol_fig = go.Figure()
            if "WTI" in commodity:
                vol_fig.add_trace(go.Bar(x=crude_df["date"], y=crude_df["vol_wti"],
                                         name="WTI Volume", marker_color="rgba(245,166,35,0.25)"))
            if "Brent" in commodity:
                vol_fig.add_trace(go.Bar(x=crude_df["date"], y=crude_df["vol_brent"],
                                         name="Brent Volume", marker_color="rgba(78,205,196,0.25)"))
            vol_fig.update_layout(**PLOTLY_LAYOUT, title="Trading Volume (contracts)", height=180,
                                  margin=dict(l=50, r=20, t=30, b=30))
            st.plotly_chart(vol_fig, use_container_width=True)

        # Spread analysis
        st.markdown("<div class='section-header'>Spread Analysis</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            spread_series = crude_df["Brent"] - crude_df["WTI"]
            sp_fig = go.Figure(go.Scatter(
                x=crude_df["date"], y=spread_series, fill="tozeroy",
                line=dict(color="#4ecdc4", width=1.8),
                fillcolor="rgba(78,205,196,0.08)", name="Brent–WTI Spread",
            ))
            sp_fig.add_hline(y=spread_series.mean(), line_dash="dash", line_color="rgba(245,166,35,0.5)",
                             annotation_text=f"Avg ${spread_series.mean():.2f}")
            sp_fig.update_layout(**PLOTLY_LAYOUT, title="Brent–WTI Spread ($/bbl)", height=250)
            st.plotly_chart(sp_fig, use_container_width=True)

        with c2:
            pct_fig = go.Figure()
            for col in commodity:
                pct = (crude_df[col] / crude_df[col].iloc[0] - 1) * 100
                pct_fig.add_trace(go.Scatter(x=crude_df["date"], y=pct, name=col,
                                             line=dict(color=COLORS[col], width=1.8)))
            pct_fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.13)")
            pct_fig.update_layout(**PLOTLY_LAYOUT, title=f"% Return from Period Start", height=250)
            st.plotly_chart(pct_fig, use_container_width=True)

# ╔══════════════════════════════════════════════╗
# ║  TAB 2 · NATURAL GAS                        ║
# ╚══════════════════════════════════════════════╝
with tab_natgas:
    st.markdown("<div class='section-header'>Natural Gas Hub Prices</div>", unsafe_allow_html=True)

    NG_COLORS = {"Henry Hub": "#ff6b6b", "TTF (Europe)": "#feca57",
                 "NBP (UK)": "#48dbfb", "JKM (LNG Asia)": "#ff9ff3"}

    if not natgas_hubs:
        st.warning("Select at least one hub in the sidebar.")
    else:
        ng_fig = go.Figure()
        for hub in natgas_hubs:
            if hub in ng_df.columns:
                series = ng_df[hub]
                ng_fig.add_trace(go.Scatter(
                    x=ng_df["date"], y=series, name=hub,
                    line=dict(color=NG_COLORS[hub], width=2),
                ))
                if show_ma:
                    ng_fig.add_trace(go.Scatter(
                        x=ng_df["date"], y=series.rolling(ma_period).mean(),
                        name=f"{hub} {ma_period}MA",
                        line=dict(color=NG_COLORS[hub], width=1.2, dash="dot"),
                    ))
        ng_fig.update_layout(**PLOTLY_LAYOUT, title="Natural Gas Prices", height=380,
                             yaxis_title="USD/MMBtu or EUR/MWh")
        st.plotly_chart(ng_fig, use_container_width=True)

        # Hub comparison bar
        st.markdown("<div class='section-header'>Current Hub Comparison</div>", unsafe_allow_html=True)
        bar_hubs = [h for h in natgas_hubs if h in ng_df.columns]
        bar_vals = [ng_df[h].iloc[-1] for h in bar_hubs]
        bar_colors = [NG_COLORS[h] for h in bar_hubs]
        bar_fig = go.Figure(go.Bar(
            x=bar_hubs, y=bar_vals, marker_color=bar_colors,
            text=[f"{v:.2f}" for v in bar_vals], textposition="outside",
        ))
        bar_fig.update_layout(**PLOTLY_LAYOUT, title="Latest Price by Hub", height=280,
                              yaxis_title="Price", showlegend=False)
        st.plotly_chart(bar_fig, use_container_width=True)

        # Seasonal heatmap (Henry Hub)
        st.markdown("<div class='section-header'>Henry Hub — Monthly Seasonality</div>", unsafe_allow_html=True)
        full_ng = gen_natgas_prices(730)
        full_ng["month"] = full_ng["date"].dt.strftime("%b")
        full_ng["year"] = full_ng["date"].dt.year
        pivot = full_ng.pivot_table(index="year", columns="month", values="Henry Hub", aggfunc="mean")
        month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        pivot = pivot.reindex(columns=[m for m in month_order if m in pivot.columns])
        heat_fig = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns.tolist(), y=[str(y) for y in pivot.index],
            colorscale=[[0, "#0d2137"], [0.5, "#f5a623"], [1, "#ff4444"]],
            text=[[f"${v:.2f}" for v in row] for row in pivot.values],
            texttemplate="%{text}", showscale=True,
        ))
        heat_fig.update_layout(**PLOTLY_LAYOUT, title="Henry Hub Monthly Avg ($/MMBtu)", height=220)
        st.plotly_chart(heat_fig, use_container_width=True)

        # US Natural Gas storage
        st.markdown("<div class='section-header'>US Natural Gas Storage</div>", unsafe_allow_html=True)
        stor_fig = go.Figure()
        stor_fig.add_trace(go.Scatter(x=storage_df["date"], y=storage_df["Storage (Bcf)"],
                                      name="Working Gas", fill="tozeroy",
                                      line=dict(color="#ff6b6b", width=2),
                                      fillcolor="rgba(255,107,107,0.1)"))
        stor_fig.add_trace(go.Scatter(x=storage_df["date"], y=storage_df["5-Year Avg"],
                                      name="5-Year Avg", line=dict(color="#feca57", width=1.5, dash="dash")))
        stor_fig.update_layout(**PLOTLY_LAYOUT, title="US Natural Gas Storage (Bcf)", height=280)
        st.plotly_chart(stor_fig, use_container_width=True)

# ╔══════════════════════════════════════════════╗
# ║  TAB 3 · FIELD MAP                          ║
# ╚══════════════════════════════════════════════╝
with tab_map:
    st.markdown("<div class='section-header'>Global Oil & Gas Field Locations</div>", unsafe_allow_html=True)

    filt = fields_df.copy()
    if map_commodity == "Crude Only":
        filt = filt[filt["Type"] == "Crude"]
    elif map_commodity == "Natural Gas Only":
        filt = filt[filt["Type"] == "Natural Gas"]

    color_map = {"Crude": "#f5a623", "Natural Gas": "#ff6b6b"}
    symbol_map = {"Crude": "circle", "Natural Gas": "diamond"}

    map_fig = go.Figure()
    for ftype, grp in filt.groupby("Type"):
        map_fig.add_trace(go.Scattergeo(
            lat=grp["Lat"], lon=grp["Lon"],
            mode="markers+text",
            text=grp["Field"],
            textposition="top center",
            textfont=dict(size=9, color="rgba(255,255,255,0.5)"),
            marker=dict(
                size=grp["Reserves_Gboe"].clip(upper=500) / 12 + 8,
                color=color_map[ftype],
                symbol=symbol_map[ftype],
                opacity=0.85,
                line=dict(width=1, color="rgba(255,255,255,0.19)"),
            ),
            name=ftype,
            hovertemplate="<b>%{text}</b><br>Reserves: %{customdata[0]:,.0f} Gboe<br>Country: %{customdata[1]}<extra></extra>",
            customdata=grp[["Reserves_Gboe", "Country"]].values,
        ))

    map_fig.update_layout(
        geo=dict(
            projection_type=map_style,
            showland=True, landcolor="#1a2535",
            showocean=True, oceancolor="#0d1520",
            showcountries=True, countrycolor="#2a3a55",
            showlakes=False,
            bgcolor="#0a0d14",
        ),
        paper_bgcolor="#0a0d14",
        font=dict(color="#8aa8c8", family="Space Mono, monospace"),
        legend=dict(bgcolor="rgba(10,15,25,0.8)", bordercolor="#1e3a5f", borderwidth=1),
        margin=dict(l=0, r=0, t=30, b=0),
        height=520,
        title=dict(text="Major Global Oil & Gas Fields (bubble = reserves)", font=dict(color="#c8a96e")),
    )
    st.plotly_chart(map_fig, use_container_width=True)

    # Field table
    st.markdown("<div class='section-header'>Field Details</div>", unsafe_allow_html=True)
    display_df = filt[["Field", "Country", "Type", "Reserves_Gboe", "Lat", "Lon"]].copy()
    display_df["Reserves_Gboe"] = display_df["Reserves_Gboe"].apply(lambda x: f"{x:,.1f}")
    st.dataframe(
        display_df.rename(columns={"Reserves_Gboe": "Reserves (Gboe)", "Lat": "Latitude", "Lon": "Longitude"}),
        use_container_width=True, hide_index=True,
    )

# ╔══════════════════════════════════════════════╗
# ║  TAB 4 · SUPPLY & PRODUCTION                ║
# ╚══════════════════════════════════════════════╝
with tab_supply:
    st.markdown("<div class='section-header'>Global Crude Oil Production</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])
    with c1:
        prod_sorted = prod_df.sort_values("Production_kbd", ascending=True)
        colors = ["#f5a623" if t == "Non-OPEC" else "#4ecdc4" for t in prod_sorted["Type"]]
        bar_h = go.Figure(go.Bar(
            x=prod_sorted["Production_kbd"], y=prod_sorted["Country"],
            orientation="h", marker_color=colors,
            text=[f"{v:,} kb/d" for v in prod_sorted["Production_kbd"]],
            textposition="outside",
        ))
        bar_h.update_layout(**PLOTLY_LAYOUT, title="Production by Country (kb/d)", height=420,
                            xaxis_title="Thousand Barrels/Day", showlegend=False)
        st.plotly_chart(bar_h, use_container_width=True)

    with c2:
        opec_total = prod_df[prod_df["Type"] == "OPEC"]["Production_kbd"].sum()
        non_opec_total = prod_df[prod_df["Type"] == "Non-OPEC"]["Production_kbd"].sum()
        pie_fig = go.Figure(go.Pie(
            labels=["OPEC", "Non-OPEC"],
            values=[opec_total, non_opec_total],
            marker=dict(colors=["#4ecdc4", "#f5a623"]),
            hole=0.55,
            textfont=dict(family="Space Mono, monospace", size=11),
        ))
        pie_fig.update_layout(**PLOTLY_LAYOUT, title="OPEC vs Non-OPEC Share", height=280,
                              margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(pie_fig, use_container_width=True)

        # YoY changes
        yoy_fig = go.Figure(go.Bar(
            x=prod_df["Country"],
            y=prod_df["YoY_pct"],
            marker_color=["#5ecb80" if v > 0 else "#e05c5c" for v in prod_df["YoY_pct"]],
            text=[f"{v:+.1f}%" for v in prod_df["YoY_pct"]],
            textposition="outside",
        ))
        yoy_fig.update_layout(**PLOTLY_LAYOUT, title="YoY Production Change (%)", height=260,
                              margin=dict(l=20, r=20, t=40, b=60))
        yoy_fig.update_xaxes(tickangle=-30, tickfont=dict(size=9))
        st.plotly_chart(yoy_fig, use_container_width=True)

    # OPEC quota table
    st.markdown("<div class='section-header'>OPEC+ Quick Reference</div>", unsafe_allow_html=True)
    opec_data = prod_df[prod_df["Type"] == "OPEC"][["Country", "Production_kbd", "YoY_pct"]].copy()
    opec_data["Production_kbd"] = opec_data["Production_kbd"].apply(lambda x: f"{x:,}")
    opec_data["YoY_pct"] = opec_data["YoY_pct"].apply(lambda x: f"{x:+.1f}%")
    st.dataframe(opec_data.rename(columns={"Production_kbd": "Production (kb/d)", "YoY_pct": "YoY Δ"}),
                 use_container_width=True, hide_index=True)

# ╔══════════════════════════════════════════════╗
# ║  TAB 5 · INVENTORIES                        ║
# ╚══════════════════════════════════════════════╝
with tab_inventory:
    st.markdown("<div class='section-header'>US Petroleum Inventories (EIA Structure)</div>", unsafe_allow_html=True)

    INV_COLORS = {"Crude Oil": "#f5a623", "Gasoline": "#4ecdc4", "Distillate": "#c77dff"}
    inv_metric = st.selectbox("Select Product", ["Crude Oil", "Gasoline", "Distillate"])

    inv_fig = go.Figure()
    inv_fig.add_trace(go.Scatter(
        x=inv_df["date"], y=inv_df[inv_metric], name=inv_metric,
        fill="tozeroy", line=dict(color=INV_COLORS[inv_metric], width=2),
        fillcolor=hex_to_rgba(INV_COLORS[inv_metric], 0.09),
    ))
    # 4-week MA
    inv_fig.add_trace(go.Scatter(
        x=inv_df["date"], y=inv_df[inv_metric].rolling(28).mean(),
        name="28d MA", line=dict(color="rgba(255,255,255,0.31)", width=1.2, dash="dot"),
    ))
    inv_fig.update_layout(**PLOTLY_LAYOUT, title=f"US {inv_metric} Inventory (MMbbl)", height=320,
                          yaxis_title="Million Barrels")
    st.plotly_chart(inv_fig, use_container_width=True)

    # Weekly change
    inv_df["weekly_chg"] = inv_df[inv_metric].diff(7)
    chg_fig = go.Figure(go.Bar(
        x=inv_df["date"], y=inv_df["weekly_chg"],
        marker_color=["#5ecb80" if v > 0 else "#e05c5c" for v in inv_df["weekly_chg"]],
        name="Weekly Change",
    ))
    chg_fig.update_layout(**PLOTLY_LAYOUT, title=f"{inv_metric} Weekly Build/Draw (MMbbl)", height=220,
                          margin=dict(l=50, r=20, t=40, b=30))
    st.plotly_chart(chg_fig, use_container_width=True)

    # All three on one panel
    st.markdown("<div class='section-header'>All Products Comparison</div>", unsafe_allow_html=True)
    multi_fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                              subplot_titles=["Crude Oil (MMbbl)", "Gasoline (MMbbl)", "Distillate (MMbbl)"])
    for i, (product, color) in enumerate(INV_COLORS.items(), 1):
        multi_fig.add_trace(go.Scatter(x=inv_df["date"], y=inv_df[product],
                                       line=dict(color=color, width=1.8), name=product,
                                       fill="tozeroy", fillcolor=hex_to_rgba(color, 0.07)), row=i, col=1)
    multi_fig.update_layout(**PLOTLY_LAYOUT, height=500, showlegend=False)
    multi_fig.update_annotations(font=dict(size=10, color="#6b8cba"))
    st.plotly_chart(multi_fig, use_container_width=True)

# ╔══════════════════════════════════════════════╗
# ║  TAB 6 · REFINERY MARGINS                   ║
# ╚══════════════════════════════════════════════╝
with tab_margins:
    st.markdown("<div class='section-header'>Refinery Crack Spreads & Margins</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class='info-box'>
    <b>3-2-1 Crack Spread</b> = (2 × Gasoline + 1 × Distillate − 3 × Crude) / 3 — a proxy for refinery profitability.
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("WTI 3-2-1 Crack", f"${margin_df['WTI 3-2-1 Crack'].iloc[-1]:.2f}/bbl",
              f"{margin_df['WTI 3-2-1 Crack'].iloc[-1] - margin_df['WTI 3-2-1 Crack'].iloc[-2]:+.2f}")
    m2.metric("Brent 3-2-1 Crack", f"${margin_df['Brent 3-2-1 Crack'].iloc[-1]:.2f}/bbl",
              f"{margin_df['Brent 3-2-1 Crack'].iloc[-1] - margin_df['Brent 3-2-1 Crack'].iloc[-2]:+.2f}")
    m3.metric("Avg Margin (30d)", f"${margin_df['WTI 3-2-1 Crack'].tail(30).mean():.2f}/bbl", "")

    crack_fig = go.Figure()
    crack_fig.add_trace(go.Scatter(x=margin_df["date"], y=margin_df["WTI 3-2-1 Crack"],
                                   name="WTI 3-2-1", line=dict(color="#f5a623", width=2), fill="tozeroy",
                                   fillcolor="rgba(245,166,35,0.07)"))
    crack_fig.add_trace(go.Scatter(x=margin_df["date"], y=margin_df["Brent 3-2-1 Crack"],
                                   name="Brent 3-2-1", line=dict(color="#4ecdc4", width=2)))
    if show_ma:
        for col, color in [("WTI 3-2-1 Crack", "rgba(245,166,35,0.5)"), ("Brent 3-2-1 Crack", "rgba(78,205,196,0.5)")]:
            crack_fig.add_trace(go.Scatter(x=margin_df["date"],
                                           y=margin_df[col].rolling(ma_period).mean(),
                                           name=f"{col[:3]} {ma_period}MA",
                                           line=dict(color=color, width=1.2, dash="dot")))
    crack_fig.update_layout(**PLOTLY_LAYOUT, title="3-2-1 Crack Spread ($/bbl)", height=350)
    st.plotly_chart(crack_fig, use_container_width=True)

    # Spread distribution
    dist_fig = go.Figure()
    dist_fig.add_trace(go.Histogram(x=margin_df["WTI 3-2-1 Crack"], name="WTI",
                                    marker_color="rgba(245,166,35,0.5)", nbinsx=30))
    dist_fig.add_trace(go.Histogram(x=margin_df["Brent 3-2-1 Crack"], name="Brent",
                                    marker_color="rgba(78,205,196,0.5)", nbinsx=30))
    dist_fig.update_layout(**PLOTLY_LAYOUT, barmode="overlay",
                           title="Crack Spread Distribution (period)", height=260)
    st.plotly_chart(dist_fig, use_container_width=True)

# ╔══════════════════════════════════════════════╗
# ║  TAB 7 · ANALYTICS                          ║
# ╚══════════════════════════════════════════════╝
with tab_analytics:
    st.markdown("<div class='section-header'>Statistical Analytics</div>", unsafe_allow_html=True)

    a1, a2 = st.columns(2)
    with a1:
        # Volatility rolling
        st.markdown("**Rolling 30-Day Volatility — Crude Benchmarks**")
        vol_fig = go.Figure()
        COLORS = {"WTI": "#f5a623", "Brent": "#4ecdc4", "Dubai": "#c77dff"}
        for col in ["WTI", "Brent", "Dubai"]:
            roll_vol = crude_df[col].pct_change().rolling(30).std() * np.sqrt(252) * 100
            vol_fig.add_trace(go.Scatter(x=crude_df["date"], y=roll_vol, name=col,
                                         line=dict(color=COLORS[col], width=1.8)))
        vol_fig.update_layout(**PLOTLY_LAYOUT, height=280, yaxis_title="Annualized Vol (%)")
        st.plotly_chart(vol_fig, use_container_width=True)

    with a2:
        # Correlation matrix
        st.markdown("**Cross-Commodity Correlation**")
        combined = crude_df[["WTI", "Brent", "Dubai"]].join(
            ng_df[["Henry Hub", "TTF (Europe)"]].reset_index(drop=True))
        corr = combined.corr()
        corr_fig = go.Figure(go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.columns.tolist(),
            colorscale=[[0, "#0d2137"], [0.5, "#1e3a5f"], [1, "#f5a623"]],
            text=corr.round(2).astype(str).values,
            texttemplate="%{text}",
            showscale=True, zmin=-1, zmax=1,
        ))
        corr_fig.update_layout(**PLOTLY_LAYOUT, height=280, margin=dict(l=90, r=20, t=30, b=80))
        corr_fig.update_xaxes(tickangle=-30)
        st.plotly_chart(corr_fig, use_container_width=True)

    # Summary statistics table
    st.markdown("<div class='section-header'>Descriptive Statistics</div>", unsafe_allow_html=True)
    stats = crude_df[["WTI", "Brent", "Dubai"]].describe().T
    stats.columns = ["Count", "Mean", "Std Dev", "Min", "25%", "Median", "75%", "Max"]
    stats = stats.applymap(lambda x: f"{x:.2f}")
    st.dataframe(stats, use_container_width=True)

    # Correlation of crude vs natgas
    st.markdown("<div class='section-header'>WTI vs Henry Hub — Rolling Correlation</div>", unsafe_allow_html=True)
    rc = crude_df["WTI"].pct_change().rolling(30).corr(ng_df["Henry Hub"].pct_change())
    rc_fig = go.Figure(go.Scatter(x=crude_df["date"], y=rc, fill="tozeroy",
                                  line=dict(color="#c77dff", width=1.8),
                                  fillcolor="rgba(199,125,255,0.07)"))
    rc_fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.13)")
    rc_fig.update_layout(**PLOTLY_LAYOUT, title="30-Day Rolling Correlation: WTI vs Henry Hub",
                         height=220, yaxis=dict(range=[-1, 1], **PLOTLY_LAYOUT["yaxis"]))
    st.plotly_chart(rc_fig, use_container_width=True)

    # Monte Carlo forward price simulation
    st.markdown("<div class='section-header'>Monte Carlo Price Simulation (90-Day Forward)</div>", unsafe_allow_html=True)
    np.random.seed(0)
    fwd_days = 90
    n_paths = 200
    last_wti = crude_df["WTI"].iloc[-1]
    mu = crude_df["WTI"].pct_change().mean()
    sigma = crude_df["WTI"].pct_change().std()
    paths = np.zeros((fwd_days, n_paths))
    paths[0] = last_wti
    for t in range(1, fwd_days):
        paths[t] = paths[t - 1] * np.exp((mu - 0.5 * sigma**2) + sigma * np.random.randn(n_paths))
    fwd_dates = pd.date_range(crude_df["date"].iloc[-1], periods=fwd_days, freq="D")
    mc_fig = go.Figure()
    for i in range(min(80, n_paths)):
        mc_fig.add_trace(go.Scatter(x=fwd_dates, y=paths[:, i], mode="lines",
                                    line=dict(width=0.5, color="rgba(245,166,35,0.12)"),
                                    showlegend=False))
    mc_fig.add_trace(go.Scatter(x=fwd_dates, y=np.percentile(paths, 90, axis=1),
                                name="90th Pctile", line=dict(color="#5ecb80", width=2, dash="dot")))
    mc_fig.add_trace(go.Scatter(x=fwd_dates, y=np.percentile(paths, 50, axis=1),
                                name="Median", line=dict(color="#f5a623", width=2)))
    mc_fig.add_trace(go.Scatter(x=fwd_dates, y=np.percentile(paths, 10, axis=1),
                                name="10th Pctile", line=dict(color="#e05c5c", width=2, dash="dot")))
    mc_fig.update_layout(**PLOTLY_LAYOUT, title=f"WTI Monte Carlo ({n_paths} paths, GBM)",
                         height=300, yaxis_title="USD/bbl")
    st.plotly_chart(mc_fig, use_container_width=True)

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; font-family:Space Mono,monospace; font-size:0.62rem; color:#2a4a6e; padding:10px 0;'>
    ⚠ DATA IS SIMULATED FOR DEMONSTRATION · Structure mirrors EIA, CME & ICE reporting formats<br>
    For live data: register at <b>eia.gov/opendata</b> and replace generator functions with API calls<br>
    Built with Streamlit · Plotly · NumPy · Pandas
</div>
""", unsafe_allow_html=True)
