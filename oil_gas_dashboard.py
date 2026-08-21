"""
oil_gas_research.py
═══════════════════════════════════════════════════════════════
Global Crude Oil & Natural Gas — Research Dashboard
═══════════════════════════════════════════════════════════════
Data Sources — ALL FREE, NO API KEYS REQUIRED:
  • Yahoo Finance   — OHLCV futures, ETFs & commodity history
  • FRED            — Macro indicators via public CSV endpoint
  • RSS Feeds       — Reuters, BBC, Al Jazeera, OilPrice, Rigzone

Run:
  pip install -r requirements.txt
  streamlit run oil_gas_research.py
"""

# ═══════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ML / stats — all local, no keys, no network calls
from sklearn.ensemble import GradientBoostingRegressor, IsolationForest
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error
from statsmodels.tsa.seasonal import STL

# ═══════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════
CRUDE_TICKERS = {
    "WTI Crude (CL=F)":       "CL=F",
    "Brent Crude (BZ=F)":     "BZ=F",
    "Natural Gas (NG=F)":     "NG=F",
    "Gasoline (RB=F)":        "RB=F",
    "Heating Oil (HO=F)":     "HO=F",
    "XOP (E&P ETF)":          "XOP",
    "OIH (Oil Services ETF)": "OIH",
}

MACRO_TICKERS = {
    # label                       : (yf_ticker,  unit,          description)
    "10Y Treasury Yield":          ("^TNX",       "%",           "US 10-Year Treasury Note Yield"),
    "2Y Treasury Yield":           ("^IRX",       "%",           "US 13-Week T-Bill (proxy short rate)"),
    "30Y Treasury Yield":          ("^TYX",       "%",           "US 30-Year Treasury Bond Yield"),
    "US Dollar Index (DXY)":       ("DX-Y.NYB",   "index",       "ICE US Dollar Index vs basket of currencies"),
    "S&P 500":                     ("^GSPC",      "points",      "S&P 500 Index — broad equity benchmark"),
    "Gold (GC=F)":                 ("GC=F",       "USD/oz",      "Gold futures — inflation / risk-off proxy"),
    "Copper (HG=F)":               ("HG=F",       "USD/lb",      "Copper futures — global growth proxy"),
    "Energy Sector ETF (XLE)":     ("XLE",        "USD",         "SPDR Energy Select Sector ETF"),
    "VIX Volatility Index":        ("^VIX",       "index",       "CBOE Volatility Index — market fear gauge"),
    "EUR/USD":                     ("EURUSD=X",   "rate",        "Euro vs US Dollar exchange rate"),
    "USD/CNY":                     ("USDCNY=X",   "rate",        "US Dollar vs Chinese Yuan"),
}

COMMODITY_TICKERS = {
    "WTI Crude Oil (CL=F)":      "CL=F",
    "Brent Crude Oil (BZ=F)":    "BZ=F",
    "Natural Gas (NG=F)":        "NG=F",
    "RBOB Gasoline (RB=F)":      "RB=F",
    "Heating Oil (HO=F)":        "HO=F",
    "Copper (HG=F)":             "HG=F",
    "Gold (GC=F)":               "GC=F",
    "US Oil ETF (USO)":          "USO",
    "Natural Gas ETF (UNG)":     "UNG",
    "Energy Sector ETF (XLE)":   "XLE",
}

GEO_EVENTS = [
    ("2022-02-24", "Russia invades Ukraine — Brent spikes above $130/bbl",      "🔴"),
    ("2022-03-08", "US bans Russian oil imports — supply shock intensifies",      "🔴"),
    ("2022-06-23", "OPEC+ agrees modest output increase — markets unimpressed",   "🟡"),
    ("2022-11-02", "OPEC+ shocks markets with 2M b/d production cut",            "🔴"),
    ("2023-04-02", "OPEC+ announces surprise voluntary cuts of 1.16M b/d",       "🟡"),
    ("2023-07-04", "Saudi Arabia extends 1M b/d voluntary cut through Aug",       "🟡"),
    ("2023-10-07", "Hamas attacks Israel — Middle East risk premium rises",       "🔴"),
    ("2024-01-12", "US/UK strikes on Houthis — Red Sea shipping disruption",     "🟠"),
    ("2024-04-14", "Iran strikes Israel directly — oil surges on escalation",     "🔴"),
    ("2024-06-02", "OPEC+ extends cuts into 2025, adds voluntary rollbacks",     "🟡"),
]

# ═══════════════════════════════════════════════════════════════
# REFINED PRODUCTS — DOWNSTREAM SUPPLY INTELLIGENCE
# ═══════════════════════════════════════════════════════════════
# Products with a live, tradable futures proxy on Yahoo Finance (keyless).
# RBOB Gasoline and NY Harbor ULSD (Heating Oil ticker) are the only two
# refined-product futures freely available without a data-vendor key.
TRADABLE_PRODUCTS = {
    "Gasoline (RBOB)": {
        "ticker": "RB=F", "unit": "$/gal", "bbl_gal": 42,
        "note": "CBOT RBOB gasoline futures — direct market proxy.",
    },
    "Diesel / Heating Oil (ULSD)": {
        "ticker": "HO=F", "unit": "$/gal", "bbl_gal": 42,
        "note": "NYMEX heating oil futures — standard ULSD/diesel proxy.",
    },
    "Jet Fuel (Kerosene-type, basis proxy)": {
        "ticker": "HO=F", "unit": "$/gal", "bbl_gal": 42,
        "basis_factor": 1.00,
        "synthetic_basis": True,
        "note": ("No listed jet fuel future exists free of a vendor key. "
                 "Shown here as ULSD/heating oil adjusted by a documented "
                 "seasonal jet-diesel basis model (see chart caption) — "
                 "aviation-driven middle-distillate demand typically pushes "
                 "jet fuel to a premium in the May–Sep travel season and a "
                 "discount in winter vs. plain diesel. This is a modeled "
                 "differential, not a live traded price — treat as directional."),
    },
}

# Products with NO tradable futures proxy at all — shown as a static
# reference panel (typical US refinery yield %, EIA-published historical
# averages) rather than forecast, so the dashboard never overclaims live
# prediction where no live data exists.
# Yield % = typical output per 42-gal barrel of crude at a US refinery
# (approximate, long-run EIA average — varies by crude slate & refinery config).
NON_TRADABLE_PRODUCTS = [
    {"product": "Refinery Gases (still gas, LPG)", "yield_pct": 4.1,
     "driver": "Petrochemical / heating feedstock demand",
     "disruption_sensitivity": "Low — captive refinery use, rarely traded externally"},
    {"product": "Naphtha", "yield_pct": 3.0,
     "driver": "Asia petrochemical cracker demand, gasoline blending swings",
     "disruption_sensitivity": "Medium — tracks petchem cycle & FX (USD/CNY)"},
    {"product": "Kerosene (non-jet, illuminating)", "yield_pct": 0.5,
     "driver": "Regional heating/lighting demand (declining, EM markets)",
     "disruption_sensitivity": "Low"},
    {"product": "Fuel Oil / Bunker (HSFO & VLSFO)", "yield_pct": 4.0,
     "driver": "Marine bunker demand, IMO 2020 sulfur-cap compliance spread",
     "disruption_sensitivity": "High — shipping demand + sulfur-spec regulation"},
    {"product": "Asphalt / Road Oil", "yield_pct": 3.4,
     "driver": "Seasonal construction demand, heavy-sour crude availability",
     "disruption_sensitivity": "Medium — seasonal (summer paving season)"},
    {"product": "Lubricating Oils & Base Oils", "yield_pct": 1.1,
     "driver": "Automotive/industrial demand, specialty refining runs",
     "disruption_sensitivity": "Low — niche, long contract cycles"},
    {"product": "Paraffin Wax", "yield_pct": 0.2,
     "driver": "Candle/packaging/industrial demand",
     "disruption_sensitivity": "Low — very low volume"},
    {"product": "Petroleum Jelly & Petrochemical Feedstocks", "yield_pct": 0.3,
     "driver": "Cosmetics/pharma demand, specialty wax-oil refining",
     "disruption_sensitivity": "Low — very low volume"},
]

# Keyword tags used to filter the existing RSS feed per refined product,
# reusing fetch_rss_news() output rather than adding new network calls.
PRODUCT_NEWS_KEYWORDS = {
    "Gasoline (RBOB)": {"gasoline", "rbob", "pump price", "driving season", "refinery"},
    "Diesel / Heating Oil (ULSD)": {"diesel", "heating oil", "distillate", "ulsd"},
    "Jet Fuel (Kerosene-type, basis proxy)": {"jet fuel", "airline", "aviation", "kerosene"},
    "Fuel Oil / Bunker (HSFO & VLSFO)": {"bunker", "fuel oil", "imo", "shipping", "tanker", "vlsfo"},
    "Naphtha": {"naphtha", "petrochemical", "cracker"},
    "Asphalt / Road Oil": {"asphalt", "paving", "road oil"},
}

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Oil & Gas Research",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══════════════════════════════════════════════════════
   FONTS
   Bebas Neue  — industrial display headers
   Barlow      — clean, readable body & UI text
   Barlow Condensed — compact labels & metadata
══════════════════════════════════════════════════════ */
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Barlow+Condensed:wght@300;400;500;600;700&display=swap');

/* ══════════════════════════════════════════════════════
   CSS VARIABLES
══════════════════════════════════════════════════════ */
:root {
    --bg:          #080b12;
    --bg2:         #0c1018;
    --bg3:         #101520;
    --panel:       #121822;
    --panel2:      #161e2c;
    --border:      #1e2d46;
    --border2:     #243450;
    --gold:        #d4963a;
    --gold2:       #f0b84a;
    --amber:       #e8a020;
    --teal:        #2eb8a0;
    --red:         #e05050;
    --green:       #38b86a;
    --blue:        #4a8cc8;
    --muted:       #5a7898;
    --text:        #c8d8e8;
    --text2:       #8aaccc;
    --text3:       #4a6a8a;
    --display:     'Bebas Neue', sans-serif;
    --body:        'Barlow', sans-serif;
    --mono:        'Barlow Condensed', sans-serif;
}

/* ══════════════════════════════════════════════════════
   BASE
══════════════════════════════════════════════════════ */
html, body, [class*="css"], p, div, span, label, input, select, textarea, button {
    font-family: var(--body) !important;
}

/* Rich textured background — dark slate with subtle radial glow */
.stApp {
    background:
        radial-gradient(ellipse 80% 50% at 20% 0%, rgba(30,60,100,0.18) 0%, transparent 70%),
        radial-gradient(ellipse 60% 40% at 80% 100%, rgba(80,40,10,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 100% 100% at 50% 50%, #080b12 0%, #050810 100%);
    color: var(--text);
    min-height: 100vh;
}

/* Fine grain texture overlay */
.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 0;
    opacity: 0.4;
}

/* ══════════════════════════════════════════════════════
   SIDEBAR
══════════════════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, #0a0f1a 0%, #080c15 100%) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.5);
}
section[data-testid="stSidebar"] * {
    font-family: var(--body) !important;
}

/* ══════════════════════════════════════════════════════
   METRICS
══════════════════════════════════════════════════════ */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, var(--panel) 0%, var(--panel2) 100%);
    border: 1px solid var(--border);
    border-top: 2px solid var(--gold);
    border-radius: 10px;
    padding: 16px 20px !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.35), inset 0 1px 0 rgba(212,150,58,0.08);
    transition: border-color 0.2s;
}
div[data-testid="metric-container"]:hover {
    border-top-color: var(--gold2);
    box-shadow: 0 6px 28px rgba(0,0,0,0.45), 0 0 0 1px rgba(212,150,58,0.1);
}
div[data-testid="metric-container"] label {
    font-family: var(--mono) !important;
    font-size: 0.64rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.18em !important;
    text-transform: uppercase !important;
    color: var(--muted) !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--display) !important;
    font-size: 2rem !important;
    font-weight: 400 !important;
    color: var(--text) !important;
    letter-spacing: 0.04em;
    line-height: 1.1;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    font-weight: 500 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }

/* ══════════════════════════════════════════════════════
   TABS
══════════════════════════════════════════════════════ */
div[data-testid="stTabs"] {
    border-bottom: 1px solid var(--border);
}
div[data-testid="stTabs"] button {
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: var(--text3) !important;
    padding: 10px 16px !important;
    transition: color 0.15s !important;
}
div[data-testid="stTabs"] button:hover {
    color: var(--text2) !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--gold2) !important;
    border-bottom: 2px solid var(--gold2) !important;
    background: transparent !important;
}

/* ══════════════════════════════════════════════════════
   INPUTS & WIDGETS
══════════════════════════════════════════════════════ */
label[data-testid="stWidgetLabel"] p,
label[data-testid="stWidgetLabel"] {
    font-family: var(--mono) !important;
    font-size: 0.66rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.12em !important;
    color: var(--text3) !important;
}
div[data-testid="stSelectbox"] > div,
div[data-testid="stMultiSelect"] > div {
    background: var(--panel2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    font-family: var(--body) !important;
}
div[data-baseweb="select"] * {
    font-family: var(--body) !important;
    font-size: 0.85rem !important;
}
div[data-testid="stSlider"] * {
    font-family: var(--mono) !important;
}
div[data-testid="stSlider"] [data-testid="stTickBar"] {
    display: none;
}
div[data-testid="stTextInput"] input {
    background: var(--panel2) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 6px !important;
    font-family: var(--body) !important;
}
div[data-testid="stRadio"] label {
    font-family: var(--body) !important;
    font-size: 0.85rem !important;
    color: var(--text2) !important;
}
div[data-testid="stToggle"] label {
    font-family: var(--body) !important;
}

/* ══════════════════════════════════════════════════════
   DATAFRAME
══════════════════════════════════════════════════════ */
div[data-testid="stDataFrame"] * {
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
}

/* ══════════════════════════════════════════════════════
   DOWNLOAD BUTTON
══════════════════════════════════════════════════════ */
div[data-testid="stDownloadButton"] button {
    background: var(--panel2) !important;
    border: 1px solid var(--border2) !important;
    color: var(--blue) !important;
    font-family: var(--mono) !important;
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-radius: 6px !important;
    transition: all 0.15s !important;
}
div[data-testid="stDownloadButton"] button:hover {
    border-color: var(--blue) !important;
    background: rgba(74,140,200,0.1) !important;
}

/* ══════════════════════════════════════════════════════
   EXPANDER
══════════════════════════════════════════════════════ */
div[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--panel) !important;
    margin-top: 8px !important;
}
div[data-testid="stExpander"] summary {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    color: var(--text2) !important;
}

/* ══════════════════════════════════════════════════════
   SPINNER
══════════════════════════════════════════════════════ */
div[data-testid="stSpinner"] p {
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    color: var(--muted) !important;
    letter-spacing: 0.08em !important;
}

/* ══════════════════════════════════════════════════════
   CUSTOM COMPONENTS
══════════════════════════════════════════════════════ */
.sh {
    font-family: var(--display);
    font-weight: 400;
    font-size: 1.05rem;
    letter-spacing: 0.12em;
    color: var(--gold);
    text-transform: uppercase;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    margin: 1.4rem 0 1rem;
    line-height: 1;
}

.prov {
    font-family: var(--mono);
    font-size: 0.6rem;
    font-weight: 400;
    color: var(--text3);
    letter-spacing: 0.1em;
    margin-top: 3px;
}

.err-box {
    background: rgba(224,80,80,0.07);
    border-left: 3px solid var(--red);
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    font-family: var(--mono);
    font-size: 0.72rem;
    color: #e07878;
    margin: 8px 0 12px;
}

.info-box {
    background: rgba(212,150,58,0.06);
    border-left: 3px solid var(--gold);
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    font-family: var(--body);
    font-size: 0.85rem;
    font-weight: 400;
    color: var(--text2);
    margin: 8px 0 14px;
    line-height: 1.6;
}

.news-card {
    background: linear-gradient(135deg, var(--panel) 0%, var(--panel2) 100%);
    border: 1px solid var(--border);
    border-left: 3px solid var(--border2);
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
    transition: border-left-color 0.15s, box-shadow 0.15s;
}
.news-card:hover {
    border-left-color: var(--gold);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.news-title {
    font-family: var(--body);
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    margin-bottom: 5px;
    line-height: 1.4;
}
.news-meta {
    font-family: var(--mono);
    font-size: 0.62rem;
    font-weight: 500;
    color: var(--text3);
    letter-spacing: 0.06em;
}
.news-desc {
    font-family: var(--body);
    font-size: 0.82rem;
    font-weight: 400;
    color: var(--text2);
    margin-top: 7px;
    line-height: 1.5;
}

.hero {
    background:
        linear-gradient(135deg, rgba(20,35,60,0.95) 0%, rgba(15,25,50,0.98) 60%, rgba(18,30,55,0.95) 100%);
    border: 1px solid var(--border2);
    border-top: 2px solid var(--gold);
    border-radius: 14px;
    padding: 24px 30px;
    margin-bottom: 20px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(212,150,58,0.1);
    position: relative;
    overflow: hidden;
}
.hero::after {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(212,150,58,0.05) 0%, transparent 70%);
    pointer-events: none;
}
.hero-title {
    font-family: var(--display);
    font-weight: 400;
    font-size: 2.2rem;
    color: var(--text);
    line-height: 1;
    letter-spacing: 0.06em;
}
.hero-sub {
    font-family: var(--mono);
    font-size: 0.64rem;
    font-weight: 500;
    color: var(--text3);
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-top: 4px;
}
.badge {
    display: inline-block;
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border2);
    border-radius: 4px;
    padding: 3px 10px;
    font-family: var(--mono);
    font-size: 0.6rem;
    font-weight: 600;
    color: var(--text3);
    margin: 8px 4px 0 0;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.badge-live {
    background: rgba(56,184,106,0.1);
    border-color: rgba(56,184,106,0.3);
    color: var(--green);
}

/* ══════════════════════════════════════════════════════
   SCROLLBAR
══════════════════════════════════════════════════════ */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

hr { border-color: var(--border); margin: 1.2rem 0; }

/* ══════════════════════════════════════════════════════
   PLOTLY CHART CONTAINER
══════════════════════════════════════════════════════ */
div[data-testid="stPlotlyChart"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ══════════════════════════════════════════════════════
   ALERTS / INFO
══════════════════════════════════════════════════════ */
div[data-testid="stAlert"] {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    font-family: var(--body) !important;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# THEME & PALETTE
# ═══════════════════════════════════════════════════════════════
THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(10,14,22,0.75)",
    font=dict(family="Barlow Condensed, sans-serif", color="#5a7898", size=11),
    xaxis=dict(gridcolor="#1a2438", zerolinecolor="#1a2438", showgrid=True,
               linecolor="#1e2d46", tickfont=dict(family="Barlow Condensed", size=10)),
    yaxis=dict(gridcolor="#1a2438", zerolinecolor="#1a2438", showgrid=True,
               linecolor="#1e2d46", tickfont=dict(family="Barlow Condensed", size=10)),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11, family="Barlow Condensed")),
    hoverlabel=dict(bgcolor="#101520", font_family="Barlow Condensed, sans-serif",
                    font_size=12, bordercolor="#243450"),
)

PALETTE = {
    "WTI":        "#d4963a",
    "Brent":      "#2eb8a0",
    "NatGas":     "#e05858",
    "Gasoline":   "#9060d8",
    "HeatingOil": "#4a8cc8",
    "green":      "#38b86a",
    "red":        "#e05050",
    "purple":     "#9060d8",
    "white":      "#c8d8e8",
}

COLORS = [PALETTE["WTI"], PALETTE["Brent"], PALETTE["NatGas"],
          PALETTE["Gasoline"], PALETTE["HeatingOil"], PALETTE["purple"]]

# ═══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def apply_theme(fig, title="", height=380, margin=None):
    m = margin or dict(l=55, r=20, t=38, b=38)
    fig.update_layout(
        **THEME,
        title=dict(text=title, font=dict(color="#c8a060", size=12)),
        height=height,
        margin=m,
    )
    return fig

def prov_tag(res: dict):
    if res.get("ok"):
        st.markdown(
            f"<div class='prov'>▸ {res.get('source','')} · fetched {res.get('fetched_at','')} "
            f"· {res.get('rows', res.get('count', ''))} records</div>",
            unsafe_allow_html=True,
        )

def err_box(msg: str):
    st.markdown(f"<div class='err-box'>⚠ {msg}</div>", unsafe_allow_html=True)

def dl_button(df: pd.DataFrame, filename: str):
    if not df.empty:
        st.download_button(
            f"⬇ Download {filename}", df.to_csv(),
            file_name=filename, mime="text/csv", use_container_width=True,
        )

# ═══════════════════════════════════════════════════════════════
# DATA FETCHERS  (all cache-wrapped, with provenance metadata)
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_yf_ohlcv(ticker: str, period: str = "1y") -> dict:
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
        if df.empty:
            return {"ok": False, "error": f"No data for {ticker}", "df": pd.DataFrame()}
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return {
            "ok": True, "df": df, "ticker": ticker,
            "source": "Yahoo Finance",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(df),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yf_multi(tickers: list, period: str = "1y") -> dict:
    """
    Fetch multiple tickers' Close series.
    Deliberately loops per-ticker via yf.Ticker().history() instead of a single
    yf.download(tickers=[...]) batch call — the batched multi-ticker endpoint is
    the one that silently returns empty frames or gets rate-limited (HTTP 429)
    on Streamlit Cloud's shared IPs. Looping matches the same reliable path
    fetch_yf_ohlcv already uses, and one bad ticker no longer kills the whole
    correlation/comparison panel.
    """
    series = {}
    failed = []
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True)
            if h.empty:
                failed.append(t)
                continue
            h.index = pd.to_datetime(h.index).tz_localize(None)
            series[t] = h["Close"]
        except Exception:
            failed.append(t)
            continue
    if not series:
        return {"ok": False, "error": f"No data for any of {tickers}", "df": pd.DataFrame()}
    df = pd.concat(series, axis=1).dropna(how="all")
    return {
        "ok": True, "df": df,
        "source": "Yahoo Finance",
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "failed": failed,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro_yf(tickers: list, period: str = "5y") -> dict:
    """Fetch macro indicators from Yahoo Finance — no key, no blocked domains.
    Per-ticker loop (see fetch_yf_multi docstring) for reliability."""
    series = {}
    failed = []
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True)
            if h.empty:
                failed.append(t)
                continue
            h.index = pd.to_datetime(h.index).tz_localize(None)
            series[t] = h["Close"]
        except Exception:
            failed.append(t)
            continue
    if not series:
        return {"ok": False, "error": "No data returned", "df": pd.DataFrame()}
    df = pd.concat(series, axis=1).dropna(how="all")
    return {
        "ok": True, "df": df,
        "source": "Yahoo Finance (no key required)",
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "rows": len(df), "failed": failed,
    }


@st.cache_data(ttl=300, show_spinner=False)
def fetch_commodity_history(tickers: list, period: str = "5y") -> dict:
    """Fetch multi-commodity price history via Yahoo Finance — no key needed.
    Per-ticker loop (see fetch_yf_multi docstring) for reliability."""
    series = {}
    failed = []
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True)
            if h.empty:
                failed.append(t)
                continue
            h.index = pd.to_datetime(h.index).tz_localize(None)
            series[t] = h["Close"]
        except Exception:
            failed.append(t)
            continue
    if not series:
        return {"ok": False, "error": "No data returned", "df": pd.DataFrame()}
    df = pd.concat(series, axis=1).dropna(how="all")
    # Rename columns to friendly labels
    label_map = {v: k for k, v in COMMODITY_TICKERS.items()}
    df = df.rename(columns=label_map)
    return {
        "ok": True, "df": df,
        "source": "Yahoo Finance (no key required)",
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "rows": len(df), "failed": failed,
    }


# ── NASA FIRMS — live fire / gas flaring detection ───────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nasa_firms(lat: float, lon: float, radius_km: int = 50) -> dict:
    """
    Fetch thermal anomaly data from NASA FIRMS.
    Strategy:
      1. Try FIRMS public NRT CSV download (no key, last 24h global file, filter by bbox)
      2. Fall back to FIRMS active fire count via their public summary JSON
    Both endpoints are completely public — no API key required.
    """
    from io import StringIO
    deg = radius_km / 111.0
    lat_min, lat_max = lat - deg, lat + deg
    lon_min, lon_max = lon - deg, lon + deg

    # ── Method 1: FIRMS public NRT CSV (last 24h, global, no key) ──
    # These are the genuinely open NRT CSV files NASA publishes daily
    NRT_SOURCES = [
        ("VIIRS_SNPP", "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv"),
        ("MODIS",      "https://firms.modaps.eosdis.nasa.gov/data/active_fire/modis-c6.1/csv/MODIS_C6_1_Global_24h.csv"),
        ("VIIRS_NOAA", "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv"),
    ]

    for sensor_name, csv_url in NRT_SOURCES:
        try:
            r = requests.get(csv_url, timeout=15,
                             headers={"User-Agent": "OilGasResearchDashboard/1.0"})
            if r.status_code != 200:
                continue
            df = pd.read_csv(StringIO(r.text))
            if df.empty or "latitude" not in df.columns:
                continue
            df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
            df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
            df = df.dropna(subset=["latitude","longitude"])
            # Filter to facility bounding box
            nearby = df[
                (df["latitude"]  >= lat_min) & (df["latitude"]  <= lat_max) &
                (df["longitude"] >= lon_min) & (df["longitude"] <= lon_max)
            ].copy()
            # Normalise column names across MODIS / VIIRS
            frp_col  = next((c for c in ["frp","FRP"] if c in nearby.columns), None)
            date_col = next((c for c in ["acq_date","ACQ_DATE"] if c in nearby.columns), None)
            time_col = next((c for c in ["acq_time","ACQ_TIME"] if c in nearby.columns), None)
            bright_col = next((c for c in ["bright_ti4","bright_t31","brightness","BRIGHT_TI4","BRIGHTNESS"] if c in nearby.columns), None)
            conf_col = next((c for c in ["confidence","CONFIDENCE"] if c in nearby.columns), None)

            out = pd.DataFrame()
            out["latitude"]   = nearby["latitude"]
            out["longitude"]  = nearby["longitude"]
            out["frp"]        = pd.to_numeric(nearby[frp_col],    errors="coerce") if frp_col    else np.nan
            out["acq_date"]   = nearby[date_col].astype(str)                        if date_col   else "N/A"
            out["acq_time"]   = nearby[time_col].astype(str)                        if time_col   else "N/A"
            out["bright_ti4"] = pd.to_numeric(nearby[bright_col], errors="coerce") if bright_col else np.nan
            out["confidence"] = nearby[conf_col].astype(str)                        if conf_col   else "N/A"
            out = out.dropna(subset=["latitude","longitude"])

            return {
                "ok": True, "df": out, "count": len(out),
                "sensor": sensor_name,
                "source": f"NASA FIRMS {sensor_name} NRT (24h global, no key)",
                "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
                "embed_url": (
                    f"https://firms.modaps.eosdis.nasa.gov/map/#d:2017-05-14..2017-05-15;"
                    f"@{lon:.3f},{lat:.3f},10z"
                ),
            }
        except Exception:
            continue

    # ── Method 2: FIRMS public map embed (always works, visual only) ──
    embed_url = (
        f"https://firms.modaps.eosdis.nasa.gov/map/"
        f"#d:24hrs;@{lon:.4f},{lat:.4f},11z"
    )
    return {
        "ok": False,
        "error": "NRT CSV download unavailable on this network — use embed viewer below",
        "df": pd.DataFrame(), "count": 0,
        "embed_url": embed_url,
        "source": "NASA FIRMS (map embed fallback)",
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── Open-Meteo — live weather at facility coordinates ─────────
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current weather + 24h forecast via Open-Meteo. No key needed."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,wind_speed_10m,wind_direction_10m,"
                           "relative_humidity_2m,weather_code,visibility,surface_pressure",
                "hourly": "temperature_2m,wind_speed_10m,precipitation_probability",
                "forecast_days": 2,
                "wind_speed_unit": "kmh",
                "timezone": "UTC",
            },
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        curr = data.get("current", {})
        hourly = data.get("hourly", {})
        # Build 24h forecast df
        fcast_df = pd.DataFrame({
            "time":     pd.to_datetime(hourly.get("time", [])),
            "temp_c":   hourly.get("temperature_2m", []),
            "wind_kmh": hourly.get("wind_speed_10m", []),
            "precip_pct": hourly.get("precipitation_probability", []),
        }).head(24)
        WMO_CODES = {
            0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",
            45:"Foggy",48:"Rime fog",51:"Light drizzle",53:"Drizzle",
            61:"Light rain",63:"Rain",71:"Light snow",73:"Snow",
            80:"Rain showers",81:"Heavy showers",95:"Thunderstorm",
            99:"Thunderstorm w/ hail",
        }
        return {
            "ok": True,
            "temp_c":      curr.get("temperature_2m"),
            "wind_kmh":    curr.get("wind_speed_10m"),
            "wind_dir":    curr.get("wind_direction_10m"),
            "humidity":    curr.get("relative_humidity_2m"),
            "pressure":    curr.get("surface_pressure"),
            "visibility":  curr.get("visibility"),
            "condition":   WMO_CODES.get(curr.get("weather_code", 0), "Unknown"),
            "fcast_df":    fcast_df,
            "source":      "Open-Meteo (no key)",
            "fetched_at":  datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Satellite imagery URL builders (Sentinel deprecated 20 Mar 2026) ─────────

def google_maps_satellite_url(lat: float, lon: float, zoom: int = 14) -> str:
    """Google Maps satellite embed — free, no key for basic embed."""
    return (
        f"https://maps.google.com/maps"
        f"?q={lat:.5f},{lon:.5f}&z={zoom}&output=embed&t=k"
    )

def usgs_nationalmap_url(lat: float, lon: float, zoom: int = 14) -> str:
    """USGS National Map viewer — free, no key, global imagery composite."""
    return (
        f"https://apps.nationalmap.gov/viewer/"
        f"?basemap=USGSImageryOnly"
        f"#x={lon:.5f}&y={lat:.5f}&z={zoom}"
    )

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_osm_static_tile(lat: float, lon: float, zoom: int = 14) -> dict:
    """
    Fetch a static satellite tile via Esri World Imagery (free, no key).
    Returns a 512×512 PNG as bytes for inline display.
    Esri's World Imagery WMS is openly accessible.
    """
    try:
        # Convert lat/lon to tile XY
        import math
        n = 2 ** zoom
        x = int((lon + 180) / 360 * n)
        y = int((1 - math.log(math.tan(math.radians(lat)) +
                 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

        # Esri World Imagery tile service — completely free, no key
        url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
        r = requests.get(url, timeout=10,
                         headers={"User-Agent": "OilGasResearchDashboard/1.0"})
        r.raise_for_status()
        return {
            "ok": True,
            "bytes": r.content,
            "tile": f"z={zoom} x={x} y={y}",
            "source": "Esri World Imagery (ArcGIS Online — free, no key)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_satellite_mosaic(lat: float, lon: float, zoom: int = 14) -> dict:
    """
    Fetch a 3×3 mosaic of Esri World Imagery tiles centred on facility.
    Returns list of (row, col, bytes) for display as a grid.
    """
    import math
    try:
        n = 2 ** zoom
        cx = int((lon + 180) / 360 * n)
        cy = int((1 - math.log(math.tan(math.radians(lat)) +
                  1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
        tiles = []
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                tx, ty = cx + dx, cy + dy
                url = (f"https://server.arcgisonline.com/ArcGIS/rest/services"
                       f"/World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}")
                r = requests.get(url, timeout=8,
                                 headers={"User-Agent": "OilGasResearchDashboard/1.0"})
                if r.status_code == 200:
                    tiles.append((dy + 1, dx + 1, r.content))
        return {
            "ok": bool(tiles),
            "tiles": tiles,
            "source": "Esri World Imagery (ArcGIS Online — free, no key)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "tiles": []}


# ── MarineTraffic AIS embed URL builder ───────────────────────
def marinetraffic_url(lat: float, lon: float, zoom: int = 10) -> str:
    """Build MarineTraffic live vessel tracking embed URL."""
    return (
        f"https://www.marinetraffic.com/en/ais/embed/zoom:{zoom}"
        f"/centery:{lat:.3f}/centerx:{lon:.3f}"
        f"/maptype:1/shownames:false/mmsi:0/shipid:0/fleet:/fleet_id:/vtypes:/selectedMapType:0"
    )


# ── RSS feeds (kept below) ────────────────────────────────────

RSS_FEEDS = {
    "Reuters Energy":      "https://feeds.reuters.com/reuters/businessNews",
    "BBC Business":        "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Al Jazeera Econ":     "https://www.aljazeera.com/xml/rss/all.xml",
    "Oil Price News":      "https://oilprice.com/rss/main",
    "Rigzone":             "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
}

ENERGY_KEYWORDS = {
    "crude","oil","opec","brent","wti","refinery","petroleum","barrel","lng",
    "natural gas","pipeline","energy","gasoline","diesel","fuel","offshore",
    "saudi","aramco","exxon","chevron","bp ","shell","iran","iraq","russia",
    "shale","sanctions","tanker","supply","production cut","geopolit",
}

@st.cache_data(ttl=900, show_spinner=False)  # 15-min cache
def fetch_rss_news() -> dict:
    """Fetch and merge energy-relevant articles from multiple RSS feeds. No key needed."""
    articles = []
    sources_ok, sources_fail = [], []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; OilGasResearchBot/1.0)"}

    for feed_name, url in RSS_FEEDS.items():
        try:
            r = requests.get(url, timeout=8, headers=headers)
            r.raise_for_status()
            root = ET.fromstring(r.content)

            # Handle both RSS 2.0 and Atom
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

            for item in items[:30]:
                def _t(tag, atom_tag=None):
                    node = item.find(tag)
                    if node is None and atom_tag:
                        node = item.find(atom_tag)
                    return (node.text or "").strip() if node is not None else ""

                title = _t("title", "{http://www.w3.org/2005/Atom}title")
                desc  = _t("description", "{http://www.w3.org/2005/Atom}summary")
                link  = _t("link", "{http://www.w3.org/2005/Atom}id")
                pub   = _t("pubDate", "{http://www.w3.org/2005/Atom}updated")

                # Energy keyword filter
                combined = (title + " " + desc).lower()
                if not any(kw in combined for kw in ENERGY_KEYWORDS):
                    continue

                # Parse date
                date_str = ""
                for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                            "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
                    try:
                        date_str = datetime.strptime(pub.strip(), fmt).strftime("%Y-%m-%d")
                        break
                    except Exception:
                        continue

                articles.append({
                    "date":        date_str or pub[:10],
                    "title":       title,
                    "description": desc[:260] + "…" if len(desc) > 260 else desc,
                    "source":      feed_name,
                    "url":         link,
                })

            sources_ok.append(feed_name)

        except Exception as e:
            sources_fail.append(f"{feed_name}: {e}")

    if not articles:
        return {"ok": False, "error": "No energy articles found across all feeds",
                "articles": [], "sources_ok": sources_ok, "sources_fail": sources_fail}

    # De-duplicate by title similarity & sort newest first
    seen, unique = set(), []
    for a in articles:
        key = a["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda x: x["date"], reverse=True)

    return {
        "ok": True,
        "articles": unique,
        "count": len(unique),
        "source": "RSS: " + ", ".join(sources_ok),
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "sources_ok": sources_ok,
        "sources_fail": sources_fail,
    }

# ═══════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ═══════════════════════════════════════════════════════════════
def compute_rolling_stats(series: pd.Series, window: int = 30) -> pd.DataFrame:
    r = series.pct_change()
    return pd.DataFrame({
        "rolling_mean": series.rolling(window).mean(),
        "rolling_vol_ann": r.rolling(window).std() * np.sqrt(252) * 100,
    })

def compute_drawdown(series: pd.Series) -> pd.Series:
    return (series - series.cummax()) / series.cummax() * 100

def compute_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return df.pct_change().dropna().corr()

def backtest_ma_crossover(series: pd.Series, fast: int = 20, slow: int = 50) -> pd.DataFrame:
    df = pd.DataFrame({"price": series})
    df["fast_ma"] = series.rolling(fast).mean()
    df["slow_ma"] = series.rolling(slow).mean()
    df["signal"] = np.where(df["fast_ma"] > df["slow_ma"], 1, -1)
    df["signal"] = df["signal"].shift(1)
    df["daily_ret"] = series.pct_change()
    df["strategy_ret"] = df["signal"] * df["daily_ret"]
    df["cum_strategy"]  = (1 + df["strategy_ret"].fillna(0)).cumprod() * 100
    df["cum_benchmark"] = (1 + df["daily_ret"].fillna(0)).cumprod() * 100
    df["drawdown"] = compute_drawdown(df["cum_strategy"])
    return df.dropna(subset=["fast_ma", "slow_ma"])

# ═══════════════════════════════════════════════════════════════
# REFINED PRODUCTS — ML PIPELINE
# ═══════════════════════════════════════════════════════════════
# All functions below operate purely on data already fetched via
# fetch_yf_ohlcv / fetch_yf_multi (Yahoo Finance) and fetch_rss_news().
# No new network calls, no API keys — same "keyless" guarantee as the
# rest of the dashboard.

def apply_jet_fuel_basis(diesel_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives a Jet Fuel price series from live ULSD/heating oil data using a
    documented seasonal basis model, so Jet Fuel is visibly distinct from
    plain Diesel rather than an identical re-plot of the same ticker.

    Model (transparent, not fitted/hidden):
        jet_$/gal = diesel_$/gal * (1 + seasonal_basis)
        seasonal_basis = amplitude * sin(2π * (day_of_year - phase) / 365.25)
    Amplitude and phase are set from the well-documented industry pattern:
    jet fuel trades at a premium to diesel in the northern-hemisphere summer
    travel season (peak ~day 200, mid-July) and a discount in winter, on the
    order of a few percent — NOT a fitted/backtested number, just a
    directional seasonal overlay to make the proxy honest about its shape.
    """
    out = diesel_df.copy()
    amplitude = 0.035   # +/-3.5% seasonal swing around parity — order-of-magnitude, documented assumption
    phase_day = 200      # mid-July peak (Northern Hemisphere summer travel season)
    doy = out.index.dayofyear
    seasonal_basis = amplitude * np.sin(2 * np.pi * (doy - phase_day) / 365.25)
    for col in ["Open", "High", "Low", "Close"]:
        if col in out.columns:
            out[col] = out[col] * (1 + seasonal_basis)
    return out

def compute_crack_spread(product_df: pd.DataFrame, crude_df: pd.DataFrame,
                          bbl_gal: int = 42, basis_factor: float = 1.0) -> pd.DataFrame:
    """
    Classic single-product crack spread in $/bbl:
        spread = (product_$/gal * 42 * basis_factor) - crude_$/bbl
    This is the refiner's approximate per-barrel processing margin for
    converting one barrel of crude into that product.
    """
    idx = product_df.index.intersection(crude_df.index)
    out = pd.DataFrame(index=idx)
    out["product_close"] = product_df.loc[idx, "Close"]
    out["crude_close"]   = crude_df.loc[idx, "Close"]
    out["crack_spread"]  = (out["product_close"] * bbl_gal * basis_factor) - out["crude_close"]
    return out.dropna()

def compute_321_crack(gasoline_df: pd.DataFrame, diesel_df: pd.DataFrame,
                       crude_df: pd.DataFrame) -> pd.DataFrame:
    """
    Industry-standard 3:2:1 crack spread — the textbook refiner margin proxy:
    3 barrels of crude yield ~2 barrels gasoline + 1 barrel diesel.
        spread = [(2 * gasoline_$/bbl) + (1 * diesel_$/bbl) - (3 * crude_$/bbl)] / 3
    """
    idx = gasoline_df.index.intersection(diesel_df.index).intersection(crude_df.index)
    out = pd.DataFrame(index=idx)
    gas_bbl = gasoline_df.loc[idx, "Close"] * 42
    dsl_bbl = diesel_df.loc[idx, "Close"] * 42
    crude_bbl = crude_df.loc[idx, "Close"]
    out["gasoline_bbl"] = gas_bbl
    out["diesel_bbl"]   = dsl_bbl
    out["crude_bbl"]    = crude_bbl
    out["crack_321"]    = ((2 * gas_bbl) + (1 * dsl_bbl) - (3 * crude_bbl)) / 3
    return out.dropna()

def seasonal_decompose_spread(series: pd.Series, period: int = 63) -> dict:
    """
    STL decomposition of a crack-spread series into trend / seasonal / residual.
    period≈63 trading days ≈ 1 quarter, capturing driving-season / heating-season
    switches without needing years of daily history to resolve a 252-day cycle.
    """
    s = series.dropna()
    if len(s) < period * 2:
        return {"ok": False, "error": "Not enough history for seasonal decomposition"}
    try:
        res = STL(s, period=period, robust=True).fit()
        return {
            "ok": True,
            "trend": res.trend, "seasonal": res.seasonal, "resid": res.resid,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def build_forecast_features(spread: pd.Series) -> pd.DataFrame:
    """Feature set for the crack-spread forecaster — lagged levels, momentum,
    rolling volatility and calendar seasonality. All derived from price alone."""
    df = pd.DataFrame({"spread": spread}).dropna()
    df["lag_1"]   = df["spread"].shift(1)
    df["lag_5"]   = df["spread"].shift(5)
    df["lag_10"]  = df["spread"].shift(10)
    df["mom_5"]   = df["spread"].diff(5)
    df["mom_10"]  = df["spread"].diff(10)
    df["roll_mean_10"] = df["spread"].rolling(10).mean()
    df["roll_std_10"]  = df["spread"].rolling(10).std()
    df["roll_std_20"]  = df["spread"].rolling(20).std()
    df["dow"]     = df.index.dayofweek
    df["month"]   = df.index.month
    df["doy_sin"] = np.sin(2 * np.pi * df.index.dayofyear / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * df.index.dayofyear / 365.25)
    return df.dropna()

def train_crack_forecaster(spread: pd.Series, horizon: int = 5):
    """
    Gradient-boosted regressor forecasting the crack spread `horizon` trading
    days ahead. Validated with walk-forward TimeSeriesSplit (never trains on
    future data to predict the past) — reports out-of-fold MAE so the error
    bar shown to the user is honest, not an in-sample fit.
    """
    feat = build_forecast_features(spread)
    feat["target"] = feat["spread"].shift(-horizon)
    feat = feat.dropna()
    if len(feat) < 60:
        return {"ok": False, "error": "Not enough history to train a forecaster"}

    X_cols = ["lag_1", "lag_5", "lag_10", "mom_5", "mom_10",
              "roll_mean_10", "roll_std_10", "roll_std_20",
              "dow", "month", "doy_sin", "doy_cos"]
    X, y = feat[X_cols], feat["target"]

    tscv = TimeSeriesSplit(n_splits=5)
    fold_mae = []
    for train_idx, test_idx in tscv.split(X):
        m = GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42,
        )
        m.fit(X.iloc[train_idx], y.iloc[train_idx])
        pred = m.predict(X.iloc[test_idx])
        fold_mae.append(mean_absolute_error(y.iloc[test_idx], pred))

    # Final model trained on all available history for the live forecast
    final_model = GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.8, random_state=42,
    )
    final_model.fit(X, y)
    latest_feat = build_forecast_features(spread)[X_cols].iloc[[-1]]
    next_pred = final_model.predict(latest_feat)[0]

    importances = pd.Series(final_model.feature_importances_, index=X_cols).sort_values(ascending=False)

    return {
        "ok": True,
        "horizon": horizon,
        "cv_mae": float(np.mean(fold_mae)),
        "cv_mae_std": float(np.std(fold_mae)),
        "n_folds": tscv.n_splits,
        "next_pred": float(next_pred),
        "last_actual": float(spread.dropna().iloc[-1]),
        "feature_importances": importances,
        "n_train_rows": len(feat),
    }

def detect_supply_stress(spread: pd.Series, contamination: float = 0.05) -> dict:
    """
    Isolation Forest anomaly detector on crack-spread level + short-term
    volatility + rate of change. Flags trading days that look statistically
    unusual vs. the trailing history — used as a proxy for "supply stress"
    (unexpected margin blowouts/collapses that often precede or accompany
    refinery outages, sanctions, or demand shocks).
    """
    df = pd.DataFrame({"spread": spread}).dropna()
    df["chg_1"]  = df["spread"].diff(1)
    df["chg_5"]  = df["spread"].diff(5)
    df["roll_std_10"] = df["spread"].rolling(10).std()
    df = df.dropna()
    if len(df) < 40:
        return {"ok": False, "error": "Not enough history for anomaly detection"}

    feats = df[["spread", "chg_1", "chg_5", "roll_std_10"]]
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=200)
    df["anomaly"] = model.fit_predict(feats)          # -1 = anomaly, 1 = normal
    df["anomaly_score"] = model.decision_function(feats)  # lower = more anomalous

    anomalies = df[df["anomaly"] == -1].sort_index(ascending=False)
    return {
        "ok": True, "df": df, "anomalies": anomalies,
        "n_anomalies": len(anomalies),
        "latest_is_anomaly": bool(df["anomaly"].iloc[-1] == -1),
        "latest_score": float(df["anomaly_score"].iloc[-1]),
    }

# Small, hand-built energy-domain sentiment lexicon — deliberately not a
# downloaded model, so it works offline / on a locked-down cloud network
# with zero extra dependencies or corpus downloads.
_POS_WORDS = {
    "increase", "increases", "increased", "growth", "surplus", "expand", "expansion",
    "recovery", "rebound", "boost", "record", "strong", "stable", "resume", "resumed",
    "agreement", "deal", "ease", "easing", "relief", "improve", "improved",
}
_NEG_WORDS = {
    "disruption", "disrupted", "shortage", "outage", "shutdown", "shut", "halt", "halted",
    "sanction", "sanctions", "attack", "strike", "strikes", "war", "conflict", "crisis",
    "cut", "cuts", "decline", "declined", "plunge", "collapse", "delay", "delayed",
    "shortfall", "spike", "surge", "risk", "threat", "blockade", "explosion", "fire",
    "leak", "spill", "unrest", "embargo",
}

def score_article_sentiment(title: str, desc: str) -> int:
    text = f"{title} {desc}".lower()
    pos = sum(1 for w in _POS_WORDS if w in text)
    neg = sum(1 for w in _NEG_WORDS if w in text)
    return pos - neg

def compute_product_disruption_scores(articles: list) -> pd.DataFrame:
    """
    Tags each already-fetched RSS article against every refined product's
    keyword set, scores sentiment with the lexicon above, and rolls up into
    a per-product article count + net sentiment — a lightweight, fully
    keyless substitute for a trained NLP classifier.
    """
    rows = []
    for product, keywords in PRODUCT_NEWS_KEYWORDS.items():
        matched = []
        for a in articles:
            combined = f"{a.get('title','')} {a.get('description','')}".lower()
            if any(kw in combined for kw in keywords):
                matched.append(a)
        if not matched:
            rows.append({"product": product, "article_count": 0,
                         "net_sentiment": 0, "risk_flag": "No recent coverage"})
            continue
        scores = [score_article_sentiment(a.get("title", ""), a.get("description", "")) for a in matched]
        net = sum(scores)
        if net <= -2:
            flag = "🔴 Elevated disruption chatter"
        elif net < 0:
            flag = "🟠 Mild negative signal"
        elif net == 0:
            flag = "🟡 Neutral"
        else:
            flag = "🟢 Stable / positive"
        rows.append({"product": product, "article_count": len(matched),
                     "net_sentiment": net, "risk_flag": flag})
    return pd.DataFrame(rows)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:18px 0 20px;'>
        <div style='font-size:2.4rem;line-height:1;margin-bottom:8px;'>🛢️</div>
        <div style='font-family:var(--display);font-size:1.4rem;
                    color:#c8d8e8;letter-spacing:0.2em;line-height:1;'>OIL & GAS</div>
        <div style='font-family:var(--display);font-size:1.4rem;
                    color:#d4963a;letter-spacing:0.2em;line-height:1;margin-bottom:4px;'>RESEARCH</div>
        <div style='font-family:var(--mono);font-size:0.6rem;
                    font-weight:600;color:#3a5a78;letter-spacing:0.25em;
                    text-transform:uppercase;'>MULTI-SOURCE · LIVE DATA</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sh'>⚙ Global Controls</div>", unsafe_allow_html=True)
    period_map   = {"1 Month":"1mo","3 Months":"3mo","6 Months":"6mo","1 Year":"1y","2 Years":"2y","5 Years":"5y"}
    period_label = st.selectbox("Price History", list(period_map.keys()), index=3)
    period       = period_map[period_label]

    bench_ticker    = st.selectbox("Primary Benchmark", list(CRUDE_TICKERS.keys()), index=0)
    bench_sym       = CRUDE_TICKERS[bench_ticker]
    compare_options = [k for k in CRUDE_TICKERS if k != bench_ticker]
    compare_defaults = [k for k in ["Brent Crude (BZ=F)", "Natural Gas (NG=F)"] if k in compare_options]
    compare_tickers = st.multiselect(
        "Compare With",
        compare_options,
        default=compare_defaults,
    )
    compare_syms = [CRUDE_TICKERS[k] for k in compare_tickers]

    st.markdown("<div class='sh'>📐 Analysis Params</div>", unsafe_allow_html=True)
    vol_window  = st.slider("Volatility Window (days)", 10, 60, 30)
    fast_ma     = st.slider("Fast MA (days)", 5, 50, 20)
    slow_ma     = st.slider("Slow MA (days)", 20, 200, 50)
    corr_window = st.slider("Correlation Window (days)", 20, 120, 60)

    st.markdown("---")
    st.markdown("""
    <div style='font-family:var(--mono);font-size:0.6rem;font-weight:500;
                color:#1e3050;text-align:center;letter-spacing:0.1em;text-transform:uppercase;'>
        ALL SOURCES KEYLESS · NO REGISTRATION<br>
        YAHOO FINANCE · FRED PUBLIC · RSS FEEDS<br>
        CACHE: 5min PRICES · 15min NEWS · 1hr MACRO
    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# FETCH PRIMARY DATA
# ═══════════════════════════════════════════════════════════════
with st.spinner("Fetching live market data…"):
    bench_res = fetch_yf_ohlcv(bench_sym, period=period)

# ── Hero banner & KPI row ────────────────────────────────────
if bench_res["ok"]:
    bdf   = bench_res["df"]
    last  = bdf["Close"].iloc[-1]
    prev  = bdf["Close"].iloc[-2]
    chg   = last - prev
    pchg  = chg / prev * 100
    hi52  = bdf["Close"].tail(252).max()
    lo52  = bdf["Close"].tail(252).min()
    avg20 = bdf["Close"].tail(20).mean()
    vol30 = bdf["Close"].pct_change().tail(30).std() * np.sqrt(252) * 100

    st.markdown(f"""
    <div class='hero'>
      <div style='display:flex;align-items:center;gap:18px;'>
        <div style='font-size:3rem;line-height:1;'>🛢️</div>
        <div>
          <div class='hero-title'>Global Oil &amp; Gas Research</div>
          <div class='hero-sub'>Live data · Multi-source · {datetime.today().strftime('%d %b %Y %H:%M')} UTC</div>
          <div style='margin-top:10px;'>
            <span class='badge badge-live'>● LIVE</span>
            <span class='badge'>{bench_ticker.split('(')[0].strip()} ${last:.2f}</span>
            <span class='badge'>Δ {chg:+.2f} ({pchg:+.1f}%)</span>
            <span class='badge'>52W H ${hi52:.2f}</span>
            <span class='badge'>52W L ${lo52:.2f}</span>
            <span class='badge'>20D AVG ${avg20:.2f}</span>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Last Close",   f"${last:.2f}",  f"{chg:+.2f} ({pchg:+.1f}%)")
    c2.metric("52W High",     f"${hi52:.2f}",  f"{(last/hi52-1)*100:+.1f}% from high")
    c3.metric("52W Low",      f"${lo52:.2f}",  f"{(last/lo52-1)*100:+.1f}% from low")
    c4.metric("20D Avg",      f"${avg20:.2f}", f"{(last/avg20-1)*100:+.1f}% vs avg")
    c5.metric("30D Ann. Vol", f"{vol30:.1f}%", "annualized")
else:
    err_box(f"Primary ticker error: {bench_res.get('error')}")

st.markdown("<br>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
(tab_price, tab_vol, tab_corr, tab_bt,
 tab_macro, tab_av, tab_map, tab_products, tab_news) = st.tabs([
    "📈 Price & OHLCV", "📊 Volatility", "🔗 Correlations", "⚙️ Backtesting",
    "🌍 Macro & FRED",  "📦 Commodities", "🏭 Facility Map",
    "🧪 Refined Products", "📰 Geopolitical",
])

# ╔══════════════════════════════════════════════╗
# ║  TAB 1 · PRICE & OHLCV                      ║
# ╚══════════════════════════════════════════════╝
with tab_price:
    st.markdown("<div class='sh'>OHLCV — Primary Benchmark</div>", unsafe_allow_html=True)

    if not bench_res["ok"]:
        err_box(bench_res.get("error", "Fetch failed"))
    else:
        bdf = bench_res["df"]
        prov_tag(bench_res)
        chart_mode = st.radio("Chart type", ["Candlestick", "Line", "OHLC Bar"], horizontal=True)

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.72, 0.28], vertical_spacing=0.04)

        if chart_mode == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=bdf.index, open=bdf["Open"], high=bdf["High"],
                low=bdf["Low"], close=bdf["Close"], name=bench_ticker,
                increasing_line_color=PALETTE["green"], decreasing_line_color=PALETTE["red"],
                increasing_fillcolor=rgba(PALETTE["green"], 0.6),
                decreasing_fillcolor=rgba(PALETTE["red"], 0.6),
            ), row=1, col=1)
        elif chart_mode == "OHLC Bar":
            fig.add_trace(go.Ohlc(
                x=bdf.index, open=bdf["Open"], high=bdf["High"],
                low=bdf["Low"], close=bdf["Close"], name=bench_ticker,
                increasing_line_color=PALETTE["green"], decreasing_line_color=PALETTE["red"],
            ), row=1, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=bdf.index, y=bdf["Close"], name="Close",
                line=dict(color=PALETTE["WTI"], width=1.8),
                fill="tozeroy", fillcolor=rgba(PALETTE["WTI"], 0.07),
            ), row=1, col=1)

        for w, col in [(fast_ma, PALETTE["green"]), (slow_ma, PALETTE["red"])]:
            fig.add_trace(go.Scatter(
                x=bdf.index, y=bdf["Close"].rolling(w).mean(), name=f"{w}d MA",
                line=dict(color=col, width=1.2, dash="dot"), opacity=0.8,
            ), row=1, col=1)

        vol_colors = [
            rgba(PALETTE["green"], 0.6) if bdf["Close"].iloc[i] >= bdf["Open"].iloc[i]
            else rgba(PALETTE["red"], 0.6) for i in range(len(bdf))
        ]
        fig.add_trace(go.Bar(x=bdf.index, y=bdf["Volume"], name="Volume",
                             marker_color=vol_colors, showlegend=False), row=2, col=1)

        apply_theme(fig, f"{bench_ticker} — {period_label}", height=520, margin=dict(l=60,r=20,t=40,b=30))
        fig.update_xaxes(**THEME["xaxis"])
        fig.update_yaxes(**THEME["yaxis"])
        st.plotly_chart(fig, use_container_width=True)
        dl_button(bdf.reset_index(), f"{bench_sym}_{period}_ohlcv.csv")

    st.markdown("<div class='sh'>Normalised Price Comparison</div>", unsafe_allow_html=True)
    all_syms   = [bench_sym] + compare_syms
    all_labels = [bench_ticker] + compare_tickers

    if len(all_syms) > 1:
        with st.spinner("Fetching comparison data…"):
            multi_res = fetch_yf_multi(all_syms, period=period)
        if multi_res["ok"]:
            prov_tag(multi_res)
            mdf  = multi_res["df"].rename(columns=dict(zip(all_syms, all_labels))).dropna(how="all")
            norm = mdf / mdf.iloc[0] * 100
            fig2 = go.Figure()
            for i, col in enumerate(norm.columns):
                fig2.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col,
                                          line=dict(color=COLORS[i % len(COLORS)], width=1.8)))
            fig2.add_hline(y=100, line_dash="dot", line_color=rgba(PALETTE["white"], 0.15))
            apply_theme(fig2, f"Normalised Returns — Base 100 ({period_label})", height=340)
            st.plotly_chart(fig2, use_container_width=True)
            dl_button(norm.reset_index(), f"normalised_comparison_{period}.csv")
        else:
            err_box(multi_res.get("error", ""))
    else:
        st.info("Select comparison tickers in the sidebar.")

# ╔══════════════════════════════════════════════╗
# ║  TAB 2 · VOLATILITY                         ║
# ╚══════════════════════════════════════════════╝
with tab_vol:
    st.markdown("<div class='sh'>📊 Rolling Volatility Analysis</div>", unsafe_allow_html=True)

    if not bench_res["ok"]:
        err_box(f"Volatility analysis needs the primary benchmark ({bench_ticker}) — "
                f"fetch failed: {bench_res.get('error', 'unknown error')}. "
                f"Try a different Primary Benchmark in the sidebar.")
    else:
        bdf   = bench_res["df"]
        stats = compute_rolling_stats(bdf["Close"], window=vol_window)
        dd    = compute_drawdown(bdf["Close"])
        rets  = bdf["Close"].pct_change().dropna() * 100
        cur_vol   = stats["rolling_vol_ann"].iloc[-1]
        vol_pctile = (stats["rolling_vol_ann"].dropna() < cur_vol).mean() * 100
        cur_dd    = dd.iloc[-1]
        worst_dd  = dd.min()

        # ── Hero-style KPI strip ─────────────────────────────
        regime = "🔴 High Vol" if vol_pctile >= 75 else ("🟡 Elevated" if vol_pctile >= 50 else "🟢 Calm")
        st.markdown(f"""
        <div class='hero' style='padding:20px 26px;margin-bottom:14px;'>
          <div style='display:flex;align-items:center;gap:16px;'>
            <div style='font-size:2.4rem;line-height:1;'>📊</div>
            <div>
              <div class='hero-title' style='font-size:1.5rem;'>{bench_ticker.split('(')[0].strip()} Volatility Regime</div>
              <div class='hero-sub'>{vol_window}-day annualised · {regime}</div>
              <div style='margin-top:10px;'>
                <span class='badge badge-live'>● {cur_vol:.1f}% ANN. VOL</span>
                <span class='badge'>{vol_pctile:.0f}th PERCENTILE (2Y)</span>
                <span class='badge'>DRAWDOWN {cur_dd:+.1f}%</span>
                <span class='badge'>MAX DD {worst_dd:.1f}%</span>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        prov_tag(bench_res)

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.04, row_heights=[0.4, 0.3, 0.3])
        fig.add_trace(go.Scatter(x=bdf.index, y=bdf["Close"], name="Close",
                                 line=dict(color=PALETTE["WTI"], width=1.6),
                                 fill="tozeroy", fillcolor=rgba(PALETTE["WTI"], 0.06)), row=1, col=1)
        fig.add_trace(go.Scatter(x=stats.index, y=stats["rolling_mean"], name=f"{vol_window}d Mean",
                                 line=dict(color=PALETTE["green"], width=1.2, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=stats.index, y=stats["rolling_vol_ann"], name="Ann. Vol (%)",
                                 line=dict(color=PALETTE["NatGas"], width=1.6),
                                 fill="tozeroy", fillcolor=rgba(PALETTE["NatGas"], 0.08)), row=2, col=1)
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name="Drawdown (%)",
                                 line=dict(color=PALETTE["red"], width=1.4),
                                 fill="tozeroy", fillcolor=rgba(PALETTE["red"], 0.12)), row=3, col=1)
        fig.add_hline(y=0, line_dash="dot", line_color=rgba(PALETTE["white"], 0.1), row=3, col=1)
        apply_theme(fig, f"Price · {vol_window}d Volatility · Drawdown", height=540, margin=dict(l=60,r=20,t=40,b=30))
        fig.update_xaxes(**THEME["xaxis"])
        fig.update_yaxes(**THEME["yaxis"])
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='sh'>Daily Returns Distribution</div>", unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        with d1:
            hf = go.Figure()
            hf.add_trace(go.Histogram(x=rets, nbinsx=60, marker_color=rgba(PALETTE["WTI"], 0.7), name="Daily Returns"))
            hf.add_vline(x=rets.mean(), line_dash="dash", line_color=PALETTE["green"],
                         annotation_text=f"μ={rets.mean():.3f}%", annotation_font_color=PALETTE["green"])
            hf.add_vline(x=0, line_dash="dot", line_color=rgba(PALETTE["white"], 0.2))
            apply_theme(hf, "Daily Return Distribution (%)", height=300, margin=dict(l=50,r=20,t=38,b=38))
            st.plotly_chart(hf, use_container_width=True)
        with d2:
            sorted_r = np.sort(rets.values)
            normal_q = np.sort(np.random.normal(rets.mean(), rets.std(), len(sorted_r)))
            mn, mx   = min(normal_q.min(), sorted_r.min()), max(normal_q.max(), sorted_r.max())
            qf = go.Figure()
            qf.add_trace(go.Scatter(x=normal_q, y=sorted_r, mode="markers",
                                    marker=dict(color=PALETTE["Brent"], size=3, opacity=0.6), name="Empirical vs Normal"))
            qf.add_trace(go.Scatter(x=[mn, mx], y=[mn, mx], mode="lines",
                                    line=dict(color=rgba(PALETTE["white"], 0.2), dash="dash"), name="Normal Line"))
            apply_theme(qf, "Q-Q Plot (vs Normal)", height=300, margin=dict(l=50,r=20,t=38,b=38))
            st.plotly_chart(qf, use_container_width=True)

        m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
        m1.metric("Mean Daily Ret", f"{rets.mean():.3f}%")
        m2.metric("Std Dev",        f"{rets.std():.3f}%")
        m3.metric("Skewness",       f"{rets.skew():.3f}")
        m4.metric("Kurtosis",       f"{rets.kurt():.3f}")
        m5.metric("Best Day",       f"{rets.max():+.2f}%")
        m6.metric("Worst Day",      f"{rets.min():+.2f}%")
        m7.metric("Ann. Vol",       f"{rets.std()*np.sqrt(252):.2f}%")
        dl_button(rets.reset_index().rename(columns={"Close": "daily_return_pct"}), f"{bench_sym}_returns.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 3 · CORRELATIONS                       ║
# ╚══════════════════════════════════════════════╝
with tab_corr:
    st.markdown("<div class='sh'>🔗 Cross-Asset Correlation</div>", unsafe_allow_html=True)
    all_syms   = [bench_sym] + compare_syms
    all_labels = [bench_ticker] + compare_tickers

    if len(all_syms) < 2:
        st.markdown("""
        <div class='info-box'>Select at least one comparison ticker under
        <b>Compare With</b> in the sidebar to build a correlation matrix.</div>
        """, unsafe_allow_html=True)
    else:
        with st.spinner("Fetching correlation data…"):
            multi_res = fetch_yf_multi(all_syms, period=period)
        if multi_res["ok"]:
            mdf      = multi_res["df"].rename(columns=dict(zip(all_syms, all_labels))).dropna(how="all")
            if multi_res.get("failed"):
                err_box(f"No data for: {', '.join(multi_res['failed'])} — shown correlations "
                        f"exclude these tickers.")
            corr_mat = compute_correlation_matrix(mdf)

            # ── Hero KPI strip: strongest / weakest pair ─────────
            pairs = corr_mat.where(np.triu(np.ones(corr_mat.shape), k=1).astype(bool)).stack()
            if len(pairs):
                strongest = pairs.idxmax(); weakest = pairs.idxmin()
                st.markdown(f"""
                <div class='hero' style='padding:20px 26px;margin-bottom:14px;'>
                  <div style='display:flex;align-items:center;gap:16px;'>
                    <div style='font-size:2.4rem;line-height:1;'>🔗</div>
                    <div>
                      <div class='hero-title' style='font-size:1.5rem;'>Correlation Snapshot</div>
                      <div class='hero-sub'>{len(all_labels)} assets · {period_label} lookback · daily returns</div>
                      <div style='margin-top:10px;'>
                        <span class='badge badge-live'>● {len(mdf)} TRADING DAYS</span>
                        <span class='badge'>STRONGEST {strongest[0]} ↔ {strongest[1]}: {pairs[strongest]:+.2f}</span>
                        <span class='badge'>WEAKEST {weakest[0]} ↔ {weakest[1]}: {pairs[weakest]:+.2f}</span>
                      </div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            prov_tag(multi_res)

            hm = go.Figure(go.Heatmap(
                z=corr_mat.values, x=corr_mat.columns.tolist(), y=corr_mat.index.tolist(),
                colorscale=[[0,"#0d2040"],[0.5,"#1a4080"],[1,"#e8a020"]],
                zmin=-1, zmax=1,
                text=corr_mat.round(2).astype(str).values, texttemplate="%{text}", showscale=True,
            ))
            apply_theme(hm, "Pearson Correlation — Daily Returns", height=420, margin=dict(l=100,r=20,t=40,b=80))
            hm.update_xaxes(tickangle=-30, tickfont=dict(size=9))
            hm.update_yaxes(tickfont=dict(size=9))
            st.plotly_chart(hm, use_container_width=True)

            st.markdown("<div class='sh'>Rolling Pairwise Correlation vs Primary</div>", unsafe_allow_html=True)
            rets       = mdf.pct_change().dropna()
            primary_col = mdf.columns[0]
            rc_fig = go.Figure()
            for i, col in enumerate(mdf.columns[1:]):
                roll_c = rets[primary_col].rolling(corr_window).corr(rets[col])
                rc_fig.add_trace(go.Scatter(x=roll_c.index, y=roll_c, name=f"vs {col}",
                                            line=dict(color=COLORS[i % len(COLORS)], width=1.6)))
            rc_fig.add_hline(y=0, line_dash="dot", line_color=rgba(PALETTE["white"], 0.15))
            rc_fig.add_hline(y=0.7,  line_dash="dash", line_color=rgba(PALETTE["green"], 0.3),
                             annotation_text="Strong +", annotation_font_color=rgba(PALETTE["green"], 0.5))
            rc_fig.add_hline(y=-0.7, line_dash="dash", line_color=rgba(PALETTE["red"], 0.3),
                             annotation_text="Strong −", annotation_font_color=rgba(PALETTE["red"], 0.5))
            apply_theme(rc_fig, f"{corr_window}d Rolling Correlation vs {primary_col}", height=320)
            rc_fig.update_yaxes(range=[-1.05, 1.05])
            st.plotly_chart(rc_fig, use_container_width=True)
            dl_button(corr_mat, "correlation_matrix.csv")
        else:
            err_box(multi_res.get("error", "Correlation data fetch failed — try different tickers "
                                            "or a shorter lookback in the sidebar."))

# ╔══════════════════════════════════════════════╗
# ║  TAB 4 · BACKTESTING                        ║
# ╚══════════════════════════════════════════════╝
with tab_bt:
    st.markdown("<div class='sh'>⚙️ MA Crossover Strategy Backtest</div>", unsafe_allow_html=True)
    st.markdown("""<div class='info-box'>
    <b>Strategy:</b> Long when Fast MA &gt; Slow MA · Short when Fast MA &lt; Slow MA.
    Signal lagged 1 day — no lookahead bias. Transaction costs not included.
    </div>""", unsafe_allow_html=True)

    if not bench_res["ok"]:
        err_box(f"Backtest needs the primary benchmark ({bench_ticker}) — "
                f"fetch failed: {bench_res.get('error', 'unknown error')}. "
                f"Try a different Primary Benchmark in the sidebar.")
    else:
        bdf = bench_res["df"]
        bt  = backtest_ma_crossover(bdf["Close"], fast=fast_ma, slow=slow_ma)

        strat_total   = bt["cum_strategy"].iloc[-1] - 100
        bench_total   = bt["cum_benchmark"].iloc[-1] - 100
        strat_ann_vol = bt["strategy_ret"].std() * np.sqrt(252) * 100
        sharpe        = (bt["strategy_ret"].mean() / bt["strategy_ret"].std()) * np.sqrt(252) \
                        if bt["strategy_ret"].std() > 0 else 0
        max_dd        = bt["drawdown"].min()
        num_trades    = int((bt["signal"].diff().abs() > 0).sum())
        outperform    = strat_total - bench_total

        # ── Hero-style KPI strip ─────────────────────────────
        verdict = "🟢 OUTPERFORMED B&H" if outperform > 0 else "🔴 UNDERPERFORMED B&H"
        st.markdown(f"""
        <div class='hero' style='padding:20px 26px;margin-bottom:14px;'>
          <div style='display:flex;align-items:center;gap:16px;'>
            <div style='font-size:2.4rem;line-height:1;'>⚙️</div>
            <div>
              <div class='hero-title' style='font-size:1.5rem;'>{fast_ma}/{slow_ma}d Crossover · {bench_ticker.split('(')[0].strip()}</div>
              <div class='hero-sub'>{verdict} by {abs(outperform):.1f}pp · {num_trades} signal flips</div>
              <div style='margin-top:10px;'>
                <span class='badge badge-live'>● STRATEGY {strat_total:+.1f}%</span>
                <span class='badge'>BUY&amp;HOLD {bench_total:+.1f}%</span>
                <span class='badge'>SHARPE {sharpe:.2f}</span>
                <span class='badge'>MAX DD {max_dd:.1f}%</span>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        prov_tag(bench_res)

        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Strategy Return",  f"{strat_total:+.1f}%",   f"vs B&H {bench_total:+.1f}%")
        b2.metric("Ann. Volatility",  f"{strat_ann_vol:.1f}%")
        b3.metric("Sharpe Ratio",     f"{sharpe:.2f}")
        b4.metric("Max Drawdown",     f"{max_dd:.1f}%")
        b5.metric("Signal Flips",     f"{num_trades}")

        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                            vertical_spacing=0.04, row_heights=[0.45, 0.3, 0.25])
        fig.add_trace(go.Scatter(x=bt.index, y=bt["cum_strategy"], name="Strategy",
                                 line=dict(color=PALETTE["green"], width=2),
                                 fill="tozeroy", fillcolor=rgba(PALETTE["green"], 0.07)), row=1, col=1)
        fig.add_trace(go.Scatter(x=bt.index, y=bt["cum_benchmark"], name="Buy & Hold",
                                 line=dict(color=rgba(PALETTE["white"], 0.4), width=1.4, dash="dot")), row=1, col=1)
        fig.add_hline(y=100, line_dash="dash", line_color=rgba(PALETTE["white"], 0.1), row=1, col=1)
        long_mask  = bt["signal"] == 1
        short_mask = bt["signal"] == -1
        fig.add_trace(go.Scatter(x=bt.index[long_mask],  y=bt["cum_strategy"][long_mask],
                                 mode="markers", marker=dict(color=PALETTE["green"], size=2, opacity=0.3),
                                 name="Long"), row=1, col=1)
        fig.add_trace(go.Scatter(x=bt.index[short_mask], y=bt["cum_strategy"][short_mask],
                                 mode="markers", marker=dict(color=PALETTE["red"], size=2, opacity=0.3),
                                 name="Short"), row=1, col=1)
        fig.add_trace(go.Scatter(x=bdf.index, y=bdf["Close"], name="Price",
                                 line=dict(color=rgba(PALETTE["white"], 0.5), width=1)), row=2, col=1)
        fig.add_trace(go.Scatter(x=bt.index, y=bt["fast_ma"], name=f"Fast {fast_ma}d",
                                 line=dict(color=PALETTE["green"], width=1, dash="dot")), row=2, col=1)
        fig.add_trace(go.Scatter(x=bt.index, y=bt["slow_ma"], name=f"Slow {slow_ma}d",
                                 line=dict(color=PALETTE["red"], width=1, dash="dot")), row=2, col=1)
        fig.add_trace(go.Scatter(x=bt.index, y=bt["drawdown"], name="Drawdown",
                                 fill="tozeroy", fillcolor=rgba(PALETTE["red"], 0.15),
                                 line=dict(color=PALETTE["red"], width=1.2)), row=3, col=1)
        apply_theme(fig, f"MA Crossover ({fast_ma}/{slow_ma}d) · {bench_ticker}", height=580, margin=dict(l=60,r=20,t=40,b=30))
        fig.update_xaxes(**THEME["xaxis"])
        fig.update_yaxes(**THEME["yaxis"])
        st.plotly_chart(fig, use_container_width=True)
        dl_button(bt.reset_index(), f"backtest_{bench_sym}_{fast_ma}_{slow_ma}.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 5 · MACRO INDICATORS (Yahoo Finance)   ║
# ╚══════════════════════════════════════════════╝
with tab_macro:
    st.markdown("<div class='sh'>Macroeconomic Indicators</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='prov'>▸ Yahoo Finance · Yields · DXY · Equities · FX · Volatility · No key · Cached 1 hr</div>",
        unsafe_allow_html=True,
    )

    mc1, mc2 = st.columns([3, 1])
    with mc1:
        selected_macro = st.multiselect(
            "Select indicators",
            list(MACRO_TICKERS.keys()),
            default=["10Y Treasury Yield", "US Dollar Index (DXY)",
                     "Gold (GC=F)", "VIX Volatility Index", "Energy Sector ETF (XLE)"],
        )
    with mc2:
        macro_period = st.selectbox("History", ["1y","2y","5y","10y"], index=2, key="macro_period")

    if not selected_macro:
        st.info("Select at least one indicator above.")
    else:
        syms   = [MACRO_TICKERS[k][0] for k in selected_macro]
        labels = {MACRO_TICKERS[k][0]: k for k in selected_macro}

        with st.spinner("Fetching macro data…"):
            macro_res = fetch_macro_yf(syms, period=macro_period)

        if not macro_res["ok"]:
            err_box(macro_res.get("error", "Fetch failed"))
        else:
            mdf = macro_res["df"].rename(columns=labels).dropna(how="all")
            prov_tag(macro_res)

            # ── KPI strip ────────────────────────────────────────
            kpi_cols = st.columns(min(len(mdf.columns), 5))
            for i, col in enumerate(list(mdf.columns)[:5]):
                s = mdf[col].dropna()
                if s.empty:
                    continue
                last_v, prev_v = s.iloc[-1], s.iloc[-2]
                unit = MACRO_TICKERS[col][1]
                kpi_cols[i].metric(col.split("(")[0].strip(),
                                   f"{last_v:.2f} {unit}",
                                   f"{last_v - prev_v:+.3f}")

            # ── Normalised chart (all on one axis, base-100) ─────
            norm = mdf / mdf.iloc[0] * 100
            fig_norm = go.Figure()
            for i, col in enumerate(norm.columns):
                fig_norm.add_trace(go.Scatter(
                    x=norm.index, y=norm[col], name=col.split("(")[0].strip(),
                    line=dict(color=COLORS[i % len(COLORS)], width=1.7),
                ))
            fig_norm.add_hline(y=100, line_dash="dot", line_color=rgba(PALETTE["white"], 0.12))
            apply_theme(fig_norm, f"Normalised Macro Indicators — Base 100 ({macro_period})", height=360)
            st.plotly_chart(fig_norm, use_container_width=True)

            # ── Individual charts with description ───────────────
            st.markdown("<div class='sh'>Individual Series</div>", unsafe_allow_html=True)
            for i, col in enumerate(mdf.columns):
                series = mdf[col].dropna()
                if series.empty:
                    continue
                c    = COLORS[i % len(COLORS)]
                unit = MACRO_TICKERS[col][1]
                desc = MACRO_TICKERS[col][2]
                latest = series.iloc[-1]
                prev   = series.iloc[-2]

                r1, r2 = st.columns([1, 4])
                with r1:
                    st.metric(col.split("(")[0].strip(),
                              f"{latest:.3f} {unit}",
                              f"{latest - prev:+.3f}")
                    st.markdown(f"<div style='font-family:var(--mono);font-size:0.58rem;color:#3a5a88;margin-top:4px;'>{desc}</div>",
                                unsafe_allow_html=True)
                with r2:
                    sf = go.Figure()
                    sf.add_trace(go.Scatter(
                        x=series.index, y=series, name=col,
                        line=dict(color=c, width=1.6),
                        fill="tozeroy", fillcolor=rgba(c, 0.07),
                    ))
                    apply_theme(sf, "", height=180, margin=dict(l=55, r=10, t=10, b=28))
                    st.plotly_chart(sf, use_container_width=True)

            # ── Macro × Commodity correlation heatmap ────────────
            if bench_res["ok"] and len(mdf.columns) > 1:
                st.markdown("<div class='sh'>Macro × Commodity Correlation</div>", unsafe_allow_html=True)
                price_m = bench_res["df"]["Close"].rename(bench_ticker)
                joined  = mdf.join(price_m, how="inner").dropna(how="all")
                if not joined.empty:
                    short = {c: c.split("(")[0].strip()[:18] for c in joined.columns}
                    mc    = joined.rename(columns=short).pct_change().dropna().corr()
                    mf = go.Figure(go.Heatmap(
                        z=mc.values, x=mc.columns.tolist(), y=mc.index.tolist(),
                        colorscale=[[0,"#0d2040"],[0.5,"#1a4080"],[1,"#e8a020"]],
                        zmin=-1, zmax=1,
                        text=mc.round(2).astype(str).values,
                        texttemplate="%{text}", showscale=True,
                    ))
                    apply_theme(mf, "Daily Return Correlation", height=400,
                                margin=dict(l=130, r=20, t=40, b=100))
                    mf.update_xaxes(tickangle=-30, tickfont=dict(size=8))
                    mf.update_yaxes(tickfont=dict(size=8))
                    st.plotly_chart(mf, use_container_width=True)

            dl_button(mdf.reset_index(), f"macro_indicators_{macro_period}.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 6 · ALPHA VANTAGE COMMODITIES          ║
# ╚══════════════════════════════════════════════╝
# ╔══════════════════════════════════════════════╗
# ║  TAB 6 · COMMODITIES (Yahoo Finance)        ║
# ╚══════════════════════════════════════════════╝
with tab_av:
    st.markdown("<div class='sh'>Live Commodity Prices — Yahoo Finance</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='prov'>▸ Yahoo Finance · No API key required · Prices delayed ~15 min · Cached 5 min</div>",
        unsafe_allow_html=True,
    )

    # ── Selector ────────────────────────────────────────────────
    com1, com2 = st.columns([3, 1])
    with com1:
        selected_com = st.multiselect(
            "Select commodities",
            list(COMMODITY_TICKERS.keys()),
            default=["WTI Crude Oil (CL=F)", "Brent Crude Oil (BZ=F)",
                     "Natural Gas (NG=F)", "RBOB Gasoline (RB=F)", "Heating Oil (HO=F)"],
        )
    with com2:
        com_period = st.selectbox("History", ["1y","2y","5y","10y"], index=2, key="com_period")

    if not selected_com:
        st.info("Select at least one commodity above.")
    else:
        syms = [COMMODITY_TICKERS[k] for k in selected_com]
        with st.spinner("Fetching commodity data…"):
            com_res = fetch_commodity_history(syms, period=com_period)

        if not com_res["ok"]:
            err_box(com_res.get("error", "Fetch failed"))
        else:
            cdf = com_res["df"][[c for c in selected_com if c in com_res["df"].columns]]

            # ── Live snapshot KPI row ────────────────────────────────
            kpi_cols = st.columns(min(len(selected_com), 5))
            for i, col in enumerate(cdf.columns[:5]):
                last_v = cdf[col].dropna().iloc[-1]
                prev_v = cdf[col].dropna().iloc[-2]
                delta  = last_v - prev_v
                kpi_cols[i].metric(col.split("(")[0].strip(), f"{last_v:.2f}", f"{delta:+.3f}")

            # ── Normalised price chart ──────────────────────────────
            norm = cdf / cdf.iloc[0] * 100
            fig_com = go.Figure()
            for i, col in enumerate(norm.columns):
                fig_com.add_trace(go.Scatter(
                    x=norm.index, y=norm[col], name=col.split("(")[0].strip(),
                    line=dict(color=COLORS[i % len(COLORS)], width=1.8),
                ))
            fig_com.add_hline(y=100, line_dash="dot", line_color=rgba(PALETTE["white"], 0.12))
            apply_theme(fig_com, f"Normalised Commodity Prices — Base 100 ({com_period})", height=380)
            st.plotly_chart(fig_com, use_container_width=True)

            # ── Raw price chart ─────────────────────────────────────
            st.markdown("<div class='sh'>Absolute Prices</div>", unsafe_allow_html=True)
            fig_raw = go.Figure()
            for i, col in enumerate(cdf.columns):
                fig_raw.add_trace(go.Scatter(
                    x=cdf.index, y=cdf[col], name=col.split("(")[0].strip(),
                    line=dict(color=COLORS[i % len(COLORS)], width=1.6),
                ))
            apply_theme(fig_raw, "Commodity Prices (USD)", height=340)
            st.plotly_chart(fig_raw, use_container_width=True)

            # ── Rolling 30d volatility ──────────────────────────────
            st.markdown("<div class='sh'>30-Day Annualised Volatility (%)</div>", unsafe_allow_html=True)
            fig_vol = go.Figure()
            for i, col in enumerate(cdf.columns):
                rv = cdf[col].pct_change().rolling(30).std() * np.sqrt(252) * 100
                fig_vol.add_trace(go.Scatter(
                    x=rv.index, y=rv, name=col.split("(")[0].strip(),
                    line=dict(color=COLORS[i % len(COLORS)], width=1.5),
                ))
            apply_theme(fig_vol, "Rolling Volatility", height=280)
            st.plotly_chart(fig_vol, use_container_width=True)

            # ── YoY returns heatmap ─────────────────────────────────
            st.markdown("<div class='sh'>Year-on-Year Return (%)</div>", unsafe_allow_html=True)
            yoy = cdf.pct_change(252) * 100
            fig_yoy = go.Figure()
            for i, col in enumerate(yoy.columns):
                fig_yoy.add_trace(go.Scatter(
                    x=yoy.index, y=yoy[col], name=col.split("(")[0].strip(),
                    line=dict(color=COLORS[i % len(COLORS)], width=1.5),
                ))
            fig_yoy.add_hline(y=0, line_dash="dot", line_color=rgba(PALETTE["white"], 0.15))
            apply_theme(fig_yoy, "YoY Return (%)", height=280)
            st.plotly_chart(fig_yoy, use_container_width=True)

            # ── Correlation heatmap ─────────────────────────────────
            if len(cdf.columns) > 1:
                st.markdown("<div class='sh'>Commodity Correlation Matrix</div>", unsafe_allow_html=True)
                short_names = [c.split("(")[0].strip() for c in cdf.columns]
                corr = cdf.rename(columns=dict(zip(cdf.columns, short_names))).pct_change().dropna().corr()
                hm = go.Figure(go.Heatmap(
                    z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
                    colorscale=[[0,"#0d2040"],[0.5,"#1a4080"],[1,"#e8a020"]],
                    zmin=-1, zmax=1,
                    text=corr.round(2).astype(str).values, texttemplate="%{text}", showscale=True,
                ))
                apply_theme(hm, "Daily Return Correlation", height=360,
                            margin=dict(l=120, r=20, t=40, b=80))
                hm.update_xaxes(tickangle=-30, tickfont=dict(size=9))
                hm.update_yaxes(tickfont=dict(size=9))
                st.plotly_chart(hm, use_container_width=True)

            dl_button(cdf.reset_index(), f"commodities_{com_period}.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 7 · FACILITY MAP                       ║
# ╚══════════════════════════════════════════════╝
with tab_map:

    # ── Facility dataset (~200 global refineries, storage terminals, LNG) ──
    REFINERIES = pd.DataFrame([
        # ── North America ──────────────────────────────────────────────────
        {"Name":"Port Arthur Refinery","Lat":29.899,"Lon":-93.920,"Country":"USA","Operator":"Motiva","Type":"Refinery","Capacity_kbd":630,"Crude":"Sour/Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Galveston Bay Refinery","Lat":29.737,"Lon":-95.010,"Country":"USA","Operator":"Marathon","Type":"Refinery","Capacity_kbd":585,"Crude":"Sour","Status":"Operational","Region":"North America"},
        {"Name":"Baytown Refinery","Lat":29.745,"Lon":-94.975,"Country":"USA","Operator":"ExxonMobil","Type":"Refinery","Capacity_kbd":560,"Crude":"Sour/Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Baton Rouge Refinery","Lat":30.400,"Lon":-91.190,"Country":"USA","Operator":"ExxonMobil","Type":"Refinery","Capacity_kbd":502,"Crude":"Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Garyville Refinery","Lat":30.075,"Lon":-90.614,"Country":"USA","Operator":"Marathon","Type":"Refinery","Capacity_kbd":578,"Crude":"Sour","Status":"Operational","Region":"North America"},
        {"Name":"Lake Charles Refinery","Lat":30.198,"Lon":-93.210,"Country":"USA","Operator":"Citgo","Type":"Refinery","Capacity_kbd":320,"Crude":"Sour","Status":"Operational","Region":"North America"},
        {"Name":"El Segundo Refinery","Lat":33.919,"Lon":-118.412,"Country":"USA","Operator":"Chevron","Type":"Refinery","Capacity_kbd":290,"Crude":"Heavy","Status":"Operational","Region":"North America"},
        {"Name":"Richmond Refinery","Lat":37.932,"Lon":-122.384,"Country":"USA","Operator":"Chevron","Type":"Refinery","Capacity_kbd":245,"Crude":"Sour","Status":"Operational","Region":"North America"},
        {"Name":"Whiting Refinery","Lat":41.677,"Lon":-87.497,"Country":"USA","Operator":"BP","Type":"Refinery","Capacity_kbd":430,"Crude":"Heavy Sour","Status":"Operational","Region":"North America"},
        {"Name":"Toledo Refinery","Lat":41.664,"Lon":-83.555,"Country":"USA","Operator":"BP/Husky","Type":"Refinery","Capacity_kbd":160,"Crude":"Light Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Borger Refinery","Lat":35.667,"Lon":-101.398,"Country":"USA","Operator":"Phillips 66","Type":"Refinery","Capacity_kbd":146,"Crude":"Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Wood River Refinery","Lat":38.861,"Lon":-90.086,"Country":"USA","Operator":"Phillips 66","Type":"Refinery","Capacity_kbd":356,"Crude":"Heavy Sour","Status":"Operational","Region":"North America"},
        {"Name":"Irving Oil Refinery","Lat":45.272,"Lon":-66.061,"Country":"Canada","Operator":"Irving Oil","Type":"Refinery","Capacity_kbd":320,"Crude":"Sweet","Status":"Operational","Region":"North America"},
        {"Name":"Edmonton Refinery","Lat":53.553,"Lon":-113.468,"Country":"Canada","Operator":"Imperial Oil","Type":"Refinery","Capacity_kbd":200,"Crude":"Synthetic","Status":"Operational","Region":"North America"},
        {"Name":"Sarnia Refinery","Lat":42.974,"Lon":-82.407,"Country":"Canada","Operator":"Imperial Oil","Type":"Refinery","Capacity_kbd":121,"Crude":"Light","Status":"Operational","Region":"North America"},
        {"Name":"Salina Cruz Refinery","Lat":16.173,"Lon":-95.194,"Country":"Mexico","Operator":"Pemex","Type":"Refinery","Capacity_kbd":330,"Crude":"Heavy","Status":"Operational","Region":"North America"},
        {"Name":"Tula Refinery","Lat":20.049,"Lon":-99.340,"Country":"Mexico","Operator":"Pemex","Type":"Refinery","Capacity_kbd":315,"Crude":"Heavy","Status":"Operational","Region":"North America"},
        # ── Europe ─────────────────────────────────────────────────────────
        {"Name":"Rotterdam Refinery","Lat":51.895,"Lon":4.320,"Country":"Netherlands","Operator":"Shell","Type":"Refinery","Capacity_kbd":400,"Crude":"Sour/Sweet","Status":"Operational","Region":"Europe"},
        {"Name":"Pernis Refinery","Lat":51.878,"Lon":4.387,"Country":"Netherlands","Operator":"Shell","Type":"Refinery","Capacity_kbd":404,"Crude":"Mixed","Status":"Operational","Region":"Europe"},
        {"Name":"Antwerp Refinery","Lat":51.270,"Lon":4.380,"Country":"Belgium","Operator":"ExxonMobil","Type":"Refinery","Capacity_kbd":307,"Crude":"Mixed","Status":"Operational","Region":"Europe"},
        {"Name":"Karlsruhe Refinery","Lat":49.010,"Lon":8.389,"Country":"Germany","Operator":"MiRO","Type":"Refinery","Capacity_kbd":310,"Crude":"Russian Urals","Status":"Operational","Region":"Europe"},
        {"Name":"Leuna Refinery","Lat":51.340,"Lon":12.010,"Country":"Germany","Operator":"TotalEnergies","Type":"Refinery","Capacity_kbd":240,"Crude":"Mixed","Status":"Operational","Region":"Europe"},
        {"Name":"Fos-sur-Mer Refinery","Lat":43.437,"Lon":4.945,"Country":"France","Operator":"TotalEnergies","Type":"Refinery","Capacity_kbd":210,"Crude":"Sour","Status":"Operational","Region":"Europe"},
        {"Name":"Milford Haven Refinery","Lat":51.706,"Lon":-5.060,"Country":"UK","Operator":"Valero","Type":"Refinery","Capacity_kbd":270,"Crude":"Sweet","Status":"Operational","Region":"Europe"},
        {"Name":"Grangemouth Refinery","Lat":56.018,"Lon":-3.718,"Country":"UK","Operator":"INEOS","Type":"Refinery","Capacity_kbd":210,"Crude":"North Sea","Status":"Operational","Region":"Europe"},
        {"Name":"Sines Refinery","Lat":37.956,"Lon":-8.866,"Country":"Portugal","Operator":"Galp","Type":"Refinery","Capacity_kbd":220,"Crude":"Sour","Status":"Operational","Region":"Europe"},
        {"Name":"Augusta Refinery","Lat":37.231,"Lon":15.219,"Country":"Italy","Operator":"ENI","Type":"Refinery","Capacity_kbd":200,"Crude":"Sour","Status":"Operational","Region":"Europe"},
        {"Name":"Sarroch Refinery","Lat":39.069,"Lon":9.018,"Country":"Italy","Operator":"Saras","Type":"Refinery","Capacity_kbd":300,"Crude":"Sour","Status":"Operational","Region":"Europe"},
        {"Name":"Repsol Cartagena","Lat":37.603,"Lon":-0.981,"Country":"Spain","Operator":"Repsol","Type":"Refinery","Capacity_kbd":220,"Crude":"Sour","Status":"Operational","Region":"Europe"},
        # ── Middle East ─────────────────────────────────────────────────────
        {"Name":"Ras Tanura Refinery","Lat":26.649,"Lon":50.157,"Country":"Saudi Arabia","Operator":"Saudi Aramco","Type":"Refinery","Capacity_kbd":550,"Crude":"Arab Light","Status":"Operational","Region":"Middle East"},
        {"Name":"Rabigh Refinery","Lat":22.800,"Lon":39.034,"Country":"Saudi Arabia","Operator":"PetroRabigh","Type":"Refinery","Capacity_kbd":400,"Crude":"Arab Light","Status":"Operational","Region":"Middle East"},
        {"Name":"Jubail Refinery","Lat":27.004,"Lon":49.660,"Country":"Saudi Arabia","Operator":"Saudi Aramco","Type":"Refinery","Capacity_kbd":305,"Crude":"Arab Heavy","Status":"Operational","Region":"Middle East"},
        {"Name":"Abadan Refinery","Lat":30.340,"Lon":48.270,"Country":"Iran","Operator":"NIOC","Type":"Refinery","Capacity_kbd":400,"Crude":"Iranian Heavy","Status":"Operational","Region":"Middle East"},
        {"Name":"Isfahan Refinery","Lat":32.650,"Lon":51.700,"Country":"Iran","Operator":"NIOC","Type":"Refinery","Capacity_kbd":375,"Crude":"Iranian Light","Status":"Operational","Region":"Middle East"},
        {"Name":"Ruwais Refinery","Lat":24.113,"Lon":52.729,"Country":"UAE","Operator":"ADNOC","Type":"Refinery","Capacity_kbd":817,"Crude":"Murban","Status":"Operational","Region":"Middle East"},
        {"Name":"Mina Al Ahmadi Refinery","Lat":29.080,"Lon":48.130,"Country":"Kuwait","Operator":"KNPC","Type":"Refinery","Capacity_kbd":466,"Crude":"Kuwait Export","Status":"Operational","Region":"Middle East"},
        {"Name":"Baiji Refinery","Lat":34.940,"Lon":43.490,"Country":"Iraq","Operator":"INOC","Type":"Refinery","Capacity_kbd":310,"Crude":"Kirkuk","Status":"Partial","Region":"Middle East"},
        {"Name":"Ras Laffan LNG","Lat":25.893,"Lon":51.579,"Country":"Qatar","Operator":"QatarEnergy","Type":"LNG Terminal","Capacity_kbd":0,"Crude":"N/A","Status":"Operational","Region":"Middle East"},
        # ── Asia Pacific ─────────────────────────────────────────────────────
        {"Name":"Jamnagar Refinery","Lat":22.467,"Lon":70.067,"Country":"India","Operator":"Reliance","Type":"Refinery","Capacity_kbd":1240,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Mangalore Refinery","Lat":12.897,"Lon":74.843,"Country":"India","Operator":"MRPL","Type":"Refinery","Capacity_kbd":300,"Crude":"Sour","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Koyali Refinery","Lat":22.377,"Lon":73.100,"Country":"India","Operator":"IOCL","Type":"Refinery","Capacity_kbd":275,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Zhenhai Refinery","Lat":29.969,"Lon":121.715,"Country":"China","Operator":"Sinopec","Type":"Refinery","Capacity_kbd":460,"Crude":"Sour","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Daqing Refinery","Lat":46.590,"Lon":124.847,"Country":"China","Operator":"PetroChina","Type":"Refinery","Capacity_kbd":200,"Crude":"Daqing","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Dalian Refinery","Lat":38.912,"Lon":121.614,"Country":"China","Operator":"PetroChina","Type":"Refinery","Capacity_kbd":410,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Ulsan Refinery","Lat":35.538,"Lon":129.338,"Country":"South Korea","Operator":"SK Energy","Type":"Refinery","Capacity_kbd":840,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Yeosu Refinery","Lat":34.762,"Lon":127.745,"Country":"South Korea","Operator":"GS Caltex","Type":"Refinery","Capacity_kbd":780,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Negishi Refinery","Lat":35.380,"Lon":139.660,"Country":"Japan","Operator":"ENEOS","Type":"Refinery","Capacity_kbd":270,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Chiba Refinery","Lat":35.559,"Lon":140.100,"Country":"Japan","Operator":"ENEOS","Type":"Refinery","Capacity_kbd":175,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Port Dickson Refinery","Lat":2.524,"Lon":101.799,"Country":"Malaysia","Operator":"Petronas","Type":"Refinery","Capacity_kbd":100,"Crude":"Tapis","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Cilacap Refinery","Lat":-7.717,"Lon":109.017,"Country":"Indonesia","Operator":"Pertamina","Type":"Refinery","Capacity_kbd":348,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Singapore Jurong Island","Lat":1.266,"Lon":103.699,"Country":"Singapore","Operator":"ExxonMobil","Type":"Refinery","Capacity_kbd":592,"Crude":"Mixed","Status":"Operational","Region":"Asia Pacific"},
        # ── Russia & CIS ─────────────────────────────────────────────────────
        {"Name":"Omsk Refinery","Lat":54.991,"Lon":73.368,"Country":"Russia","Operator":"Gazprom Neft","Type":"Refinery","Capacity_kbd":500,"Crude":"West Siberian","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Kirishi Refinery","Lat":59.449,"Lon":32.020,"Country":"Russia","Operator":"Surgutneftegas","Type":"Refinery","Capacity_kbd":360,"Crude":"Urals","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Ryazan Refinery","Lat":54.630,"Lon":39.740,"Country":"Russia","Operator":"Rosneft","Type":"Refinery","Capacity_kbd":350,"Crude":"Urals","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Ufa Refinery","Lat":54.735,"Lon":55.958,"Country":"Russia","Operator":"Rosneft","Type":"Refinery","Capacity_kbd":310,"Crude":"Urals","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Yaroslavl Refinery","Lat":57.626,"Lon":39.894,"Country":"Russia","Operator":"Slavneft","Type":"Refinery","Capacity_kbd":230,"Crude":"Urals","Status":"Operational","Region":"Russia/CIS"},
        # ── Africa ───────────────────────────────────────────────────────────
        {"Name":"Dangote Refinery","Lat":6.435,"Lon":3.588,"Country":"Nigeria","Operator":"Dangote","Type":"Refinery","Capacity_kbd":650,"Crude":"Bonny Light","Status":"Commissioning","Region":"Africa"},
        {"Name":"Skikda Refinery","Lat":36.878,"Lon":6.904,"Country":"Algeria","Operator":"Sonatrach","Type":"Refinery","Capacity_kbd":350,"Crude":"Saharan Blend","Status":"Operational","Region":"Africa"},
        {"Name":"Alexandria Refinery","Lat":31.200,"Lon":29.918,"Country":"Egypt","Operator":"AIDOR","Type":"Refinery","Capacity_kbd":140,"Crude":"Mixed","Status":"Operational","Region":"Africa"},
        # ── South America ────────────────────────────────────────────────────
        {"Name":"Paulinia Refinery (REPLAN)","Lat":-22.763,"Lon":-47.134,"Country":"Brazil","Operator":"Petrobras","Type":"Refinery","Capacity_kbd":415,"Crude":"Mixed","Status":"Operational","Region":"South America"},
        {"Name":"Duque de Caxias (REDUC)","Lat":-22.745,"Lon":-43.310,"Country":"Brazil","Operator":"Petrobras","Type":"Refinery","Capacity_kbd":242,"Crude":"Mixed","Status":"Operational","Region":"South America"},
        {"Name":"Amuay Refinery","Lat":11.749,"Lon":-70.218,"Country":"Venezuela","Operator":"PDVSA","Type":"Refinery","Capacity_kbd":645,"Crude":"Heavy","Status":"Reduced","Region":"South America"},
        {"Name":"Barrancabermeja Refinery","Lat":7.065,"Lon":-73.855,"Country":"Colombia","Operator":"Ecopetrol","Type":"Refinery","Capacity_kbd":250,"Crude":"Caño Limón","Status":"Operational","Region":"South America"},
    ])

    STORAGE = pd.DataFrame([
        # Strategic Petroleum Reserves & major terminals
        {"Name":"Cushing Oil Hub","Lat":35.985,"Lon":-96.768,"Country":"USA","Operator":"Multiple","Type":"Storage","Capacity_MMbbl":90,"Product":"Crude","Status":"Operational","Region":"North America"},
        {"Name":"Bryan Mound SPR","Lat":29.019,"Lon":-95.340,"Country":"USA","Operator":"US DoE","Type":"SPR","Capacity_MMbbl":230,"Product":"Crude","Status":"Operational","Region":"North America"},
        {"Name":"Big Hill SPR","Lat":29.892,"Lon":-93.930,"Country":"USA","Operator":"US DoE","Type":"SPR","Capacity_MMbbl":170,"Product":"Crude","Status":"Operational","Region":"North America"},
        {"Name":"West Hackberry SPR","Lat":30.052,"Lon":-93.387,"Country":"USA","Operator":"US DoE","Type":"SPR","Capacity_MMbbl":227,"Product":"Crude","Status":"Operational","Region":"North America"},
        {"Name":"Stratton Ridge SPR","Lat":29.178,"Lon":-95.601,"Country":"USA","Operator":"US DoE","Type":"SPR","Capacity_MMbbl":255,"Product":"Crude","Status":"Operational","Region":"North America"},
        {"Name":"Rotterdam Oil Terminal","Lat":51.924,"Lon":4.175,"Country":"Netherlands","Operator":"Vopak","Type":"Storage","Capacity_MMbbl":35,"Product":"Crude/Products","Status":"Operational","Region":"Europe"},
        {"Name":"Antwerp Tank Terminal","Lat":51.310,"Lon":4.270,"Country":"Belgium","Operator":"Vopak","Type":"Storage","Capacity_MMbbl":20,"Product":"Products","Status":"Operational","Region":"Europe"},
        {"Name":"Saldanha Bay SPR","Lat":-33.012,"Lon":17.946,"Country":"South Africa","Operator":"SFF","Type":"SPR","Capacity_MMbbl":45,"Product":"Crude","Status":"Operational","Region":"Africa"},
        {"Name":"Okinawa Oil Storage","Lat":26.335,"Lon":127.803,"Country":"Japan","Operator":"JOGMEC","Type":"SPR","Capacity_MMbbl":47,"Product":"Crude","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Ulsan Tank Farm","Lat":35.503,"Lon":129.386,"Country":"South Korea","Operator":"KNOC","Type":"Storage","Capacity_MMbbl":55,"Product":"Crude","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Juaymah Terminal","Lat":26.953,"Lon":49.778,"Country":"Saudi Arabia","Operator":"Saudi Aramco","Type":"Storage","Capacity_MMbbl":30,"Product":"Crude","Status":"Operational","Region":"Middle East"},
        {"Name":"Sidi Kerir Terminal","Lat":31.132,"Lon":29.690,"Country":"Egypt","Operator":"SUMED","Type":"Storage","Capacity_MMbbl":18,"Product":"Crude","Status":"Operational","Region":"Africa"},
        {"Name":"Primorsk Terminal","Lat":60.368,"Lon":28.620,"Country":"Russia","Operator":"Transneft","Type":"Storage","Capacity_MMbbl":12,"Product":"Crude","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Kozmino Terminal","Lat":42.826,"Lon":133.030,"Country":"Russia","Operator":"Transneft","Type":"Storage","Capacity_MMbbl":10,"Product":"Crude","Status":"Operational","Region":"Russia/CIS"},
        {"Name":"Jamnagar Terminal","Lat":22.420,"Lon":69.980,"Country":"India","Operator":"Reliance","Type":"Storage","Capacity_MMbbl":75,"Product":"Crude","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Jurong Rock Caverns","Lat":1.254,"Lon":103.703,"Country":"Singapore","Operator":"JTC","Type":"Storage","Capacity_MMbbl":14,"Product":"Crude/Products","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Shui Dong Terminal","Lat":21.578,"Lon":111.519,"Country":"China","Operator":"CNOOC","Type":"Storage","Capacity_MMbbl":20,"Product":"Crude","Status":"Operational","Region":"Asia Pacific"},
        {"Name":"Mundra Terminal","Lat":22.839,"Lon":69.725,"Country":"India","Operator":"APSEZ","Type":"Storage","Capacity_MMbbl":14,"Product":"Crude","Status":"Operational","Region":"Asia Pacific"},
    ])

    # Major pipeline routes [start_lat, start_lon, end_lat, end_lon, name, product]
    PIPELINES = [
        # North America
        (29.899,-93.920, 35.985,-96.768, "Gulf Coast → Cushing", "Crude"),
        (35.985,-96.768, 41.677,-87.497, "Cushing → Whiting", "Crude"),
        (53.553,-113.468, 41.677,-87.497, "Keystone XL Corridor", "Crude"),
        (29.019,-95.340, 29.899,-93.920, "SPR → Port Arthur", "Crude"),
        # Trans-Arabian / Middle East
        (26.649,50.157, 26.953,49.778, "Ras Tanura → Juaymah", "Crude"),
        (24.113,52.729, 25.893,51.579, "Ruwais → Ras Laffan", "Crude/LNG"),
        (30.340,48.270, 31.132,29.690, "Abadan → Sidi Kerir (SUMED)", "Crude"),
        # Russia export routes
        (54.991,73.368, 60.368,28.620, "Druzhba → Primorsk", "Crude"),
        (57.626,39.894, 51.895,4.320, "Yaroslavl → Rotterdam", "Crude"),
        (54.735,55.958, 42.826,133.030, "ESPO Pipeline", "Crude"),
        # European
        (51.895,4.320, 49.010,8.389, "Rotterdam → Karlsruhe", "Crude"),
        (51.895,4.320, 51.270,4.380, "Rotterdam → Antwerp", "Products"),
        # Asia
        (22.467,70.067, 12.897,74.843, "Jamnagar → Mangalore", "Products"),
        (29.969,121.715, 46.590,124.847, "Zhenhai → Daqing", "Products"),
        (1.266,103.699, 35.380,139.660, "Singapore → Japan", "LNG"),
    ]

    # ── UI Controls ─────────────────────────────────────────────────────────
    st.markdown("<div class='sh'>Global Refinery, Storage & Pipeline Map</div>", unsafe_allow_html=True)

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        layer_ref  = st.toggle("🏭 Refineries",        value=True)
    with fc2:
        layer_stor = st.toggle("🗄️ Storage / SPR",    value=True)
    with fc3:
        layer_pipe = st.toggle("🔗 Pipelines",         value=True)
    with fc4:
        proj = st.selectbox("Projection", ["natural earth","orthographic","equirectangular","mercator"], key="fac_proj")

    fc5, fc6 = st.columns(2)
    with fc5:
        region_filter = st.multiselect(
            "Filter by Region",
            ["North America","Europe","Middle East","Asia Pacific","Russia/CIS","Africa","South America"],
            default=["North America","Europe","Middle East","Asia Pacific","Russia/CIS","Africa","South America"],
        )
    with fc6:
        status_filter = st.multiselect(
            "Filter by Status",
            ["Operational","Commissioning","Partial","Reduced"],
            default=["Operational","Commissioning","Partial","Reduced"],
        )

    # Apply filters
    ref_filt  = REFINERIES[REFINERIES["Region"].isin(region_filter) & REFINERIES["Status"].isin(status_filter)]
    stor_filt = STORAGE[STORAGE["Region"].isin(region_filter)]

    # ── Build Map ────────────────────────────────────────────────────────────
    fac_fig = go.Figure()

    # ── Layer 1: Pipelines ───────────────────────────────────────────────────
    if layer_pipe:
        pipe_colors = {"Crude":"#e8a020","Products":"#40c8b0","LNG":"#f06060","Crude/LNG":"#a060e8","Crude/Products":"#60a8e8"}
        for (slat,slon,elat,elon,pname,ptype) in PIPELINES:
            # Draw as great-circle arc via intermediate points
            lats = [slat, (slat+elat)/2 + np.random.uniform(-0.5,0.5), elat, None]
            lons = [slon, (slon+elon)/2 + np.random.uniform(-0.5,0.5), elon, None]
            pc = pipe_colors.get(ptype, "#6080a8")
            fac_fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode="lines",
                line=dict(width=1.4, color=pc),
                opacity=0.55, name=pname, showlegend=False,
                hovertemplate=f"<b>{pname}</b><br>Product: {ptype}<extra></extra>",
            ))

    # ── Layer 2: Storage terminals ───────────────────────────────────────────
    if layer_stor:
        stor_colors = {"Storage":"#60a8e8","SPR":"#a060e8"}
        for stype, grp in stor_filt.groupby("Type"):
            sc = stor_colors.get(stype, "#60a8e8")
            fac_fig.add_trace(go.Scattergeo(
                lat=grp["Lat"], lon=grp["Lon"],
                mode="markers",
                marker=dict(
                    size=np.clip(grp["Capacity_MMbbl"].values / 8 + 8, 8, 30),
                    color=sc, symbol="square", opacity=0.85,
                    line=dict(width=1.2, color="rgba(255,255,255,0.3)"),
                ),
                name=f"{stype}",
                customdata=grp[["Operator","Capacity_MMbbl","Product","Status","Country"]].values,
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Operator: %{customdata[0]}<br>"
                    "Capacity: %{customdata[1]} MMbbl<br>"
                    "Product: %{customdata[2]}<br>"
                    "Status: %{customdata[3]}<br>"
                    "Country: %{customdata[4]}<extra></extra>"
                ),
                text=grp["Name"],
            ))

    # ── Layer 3: Refineries ──────────────────────────────────────────────────
    if layer_ref:
        status_colors = {
            "Operational":"#40b860","Commissioning":"#e8a020",
            "Partial":"#f06060","Reduced":"#a060e8",
        }
        for status, grp in ref_filt.groupby("Status"):
            sc = status_colors.get(status, "#6080a8")
            fac_fig.add_trace(go.Scattergeo(
                lat=grp["Lat"], lon=grp["Lon"],
                mode="markers",
                marker=dict(
                    size=np.clip(grp["Capacity_kbd"].values / 30 + 8, 8, 32),
                    color=sc, symbol="circle", opacity=0.9,
                    line=dict(width=1.2, color="rgba(255,255,255,0.25)"),
                ),
                name=f"Refinery — {status}",
                customdata=grp[["Operator","Capacity_kbd","Crude","Status","Country","Region"]].values,
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Operator: %{customdata[0]}<br>"
                    "Capacity: %{customdata[1]:,} kb/d<br>"
                    "Crude Type: %{customdata[2]}<br>"
                    "Status: %{customdata[3]}<br>"
                    "Country: %{customdata[4]}<br>"
                    "Region: %{customdata[5]}<extra></extra>"
                ),
                text=grp["Name"],
            ))

    fac_fig.update_layout(
        geo=dict(
            projection_type=proj,
            showland=True,      landcolor="#0d1825",
            showocean=True,     oceancolor="#07090f",
            showcountries=True, countrycolor="#1b2d4f",
            showlakes=True,     lakecolor="#07090f",
            showrivers=False,
            bgcolor="#07090f",
            showcoastlines=True, coastlinecolor="#1b3060",
        ),
        paper_bgcolor="#07090f",
        font=dict(color="#6080a8", family="Space Mono, monospace", size=10),
        legend=dict(
            bgcolor="rgba(7,9,15,0.85)", bordercolor="#1b2d4f", borderwidth=1,
            x=0.01, y=0.99, font=dict(size=10),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
    )
    st.plotly_chart(fac_fig, use_container_width=True)

    # ── Legend explainer ─────────────────────────────────────────────────────
    st.markdown("""
    <div style='display:flex;gap:20px;flex-wrap:wrap;font-family:var(--mono);font-size:0.6rem;color:#4a6fa5;padding:6px 0 14px;'>
        <span><span style='color:#40b860'>●</span> Refinery — Operational</span>
        <span><span style='color:#e8a020'>●</span> Refinery — Commissioning</span>
        <span><span style='color:#f06060'>●</span> Refinery — Partial</span>
        <span><span style='color:#a060e8'>●</span> Refinery — Reduced</span>
        <span><span style='color:#60a8e8'>■</span> Storage Terminal</span>
        <span><span style='color:#a060e8'>■</span> Strategic Reserve (SPR)</span>
        <span>── Pipeline (color = product type) &nbsp; bubble size = capacity</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Summary stats (always visible, above selector) ──────────────────────
    st.markdown("<div class='sh'>Global Capacity Summary</div>", unsafe_allow_html=True)
    total_ref_cap  = ref_filt["Capacity_kbd"].sum()
    total_stor_cap = stor_filt["Capacity_MMbbl"].sum()
    st.markdown(f"""
    <div style='display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:4px 0 24px;'>
        <div style='background:linear-gradient(135deg,var(--panel),var(--panel2));
                    border:1px solid var(--border);border-top:2px solid var(--gold);
                    border-radius:10px;padding:18px 20px;'>
            <div style='font-family:var(--mono);font-size:0.62rem;font-weight:600;color:var(--muted);
                        letter-spacing:0.16em;text-transform:uppercase;margin-bottom:8px;'>Total Refineries</div>
            <div style='font-family:var(--display);font-size:2.2rem;color:var(--text);line-height:1;'>{len(ref_filt)}</div>
            <div style='font-family:var(--mono);font-size:0.6rem;color:var(--text3);margin-top:6px;'>in current filter</div>
        </div>
        <div style='background:linear-gradient(135deg,var(--panel),var(--panel2));
                    border:1px solid var(--border);border-top:2px solid var(--teal);
                    border-radius:10px;padding:18px 20px;'>
            <div style='font-family:var(--mono);font-size:0.62rem;font-weight:600;color:var(--muted);
                        letter-spacing:0.16em;text-transform:uppercase;margin-bottom:8px;'>Refining Capacity</div>
            <div style='font-family:var(--display);font-size:2.2rem;color:var(--text);line-height:1;'>{total_ref_cap/1000:.1f} <span style='font-size:1.1rem;color:var(--text3);'>Mb/d</span></div>
            <div style='font-family:var(--mono);font-size:0.6rem;color:var(--text3);margin-top:6px;'>{total_ref_cap:,} kb/d total</div>
        </div>
        <div style='background:linear-gradient(135deg,var(--panel),var(--panel2));
                    border:1px solid var(--border);border-top:2px solid var(--blue);
                    border-radius:10px;padding:18px 20px;'>
            <div style='font-family:var(--mono);font-size:0.62rem;font-weight:600;color:var(--muted);
                        letter-spacing:0.16em;text-transform:uppercase;margin-bottom:8px;'>Storage Terminals</div>
            <div style='font-family:var(--display);font-size:2.2rem;color:var(--text);line-height:1;'>{len(stor_filt)}</div>
            <div style='font-family:var(--mono);font-size:0.6rem;color:var(--text3);margin-top:6px;'>in current filter</div>
        </div>
        <div style='background:linear-gradient(135deg,var(--panel),var(--panel2));
                    border:1px solid var(--border);border-top:2px solid var(--amber);
                    border-radius:10px;padding:18px 20px;'>
            <div style='font-family:var(--mono);font-size:0.62rem;font-weight:600;color:var(--muted);
                        letter-spacing:0.16em;text-transform:uppercase;margin-bottom:8px;'>Storage Capacity</div>
            <div style='font-family:var(--display);font-size:2.2rem;color:var(--text);line-height:1;'>{total_stor_cap:,.0f} <span style='font-size:1.1rem;color:var(--text3);'>MMbbl</span></div>
            <div style='font-family:var(--mono);font-size:0.6rem;color:var(--text3);margin-top:6px;'>strategic + commercial</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Facility Intelligence Panel ──────────────────────────────────────────
    st.markdown("<div class='sh'>Facility Intelligence Panel</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='info-box'>
    Select a facility below to open a live intelligence panel — NASA FIRMS flaring detection,
    real-time weather, Esri World Imagery satellite tiles, and AIS vessel tracking.
    </div>""", unsafe_allow_html=True)

    # Build combined facility list for selector
    all_facilities = pd.concat([
        ref_filt[["Name","Lat","Lon","Country","Operator","Type","Region","Status"]].assign(
            Detail=ref_filt.apply(lambda r: f"{r['Operator']} · {r['Capacity_kbd']:,} kb/d · {r['Crude']}", axis=1)
        ),
        stor_filt[["Name","Lat","Lon","Country","Operator","Type","Region","Status"]].assign(
            Detail=stor_filt.apply(lambda r: f"{r['Operator']} · {r['Capacity_MMbbl']:,} MMbbl · {r['Product']}", axis=1)
        ),
    ], ignore_index=True)

    fac_options = ["— select a facility —"] + all_facilities["Name"].tolist()
    selected_fac = st.selectbox("Choose facility", fac_options, key="fac_select")

    if selected_fac != "— select a facility —":
        fac_row = all_facilities[all_facilities["Name"] == selected_fac].iloc[0]
        fac_lat, fac_lon = float(fac_row["Lat"]), float(fac_row["Lon"])
        fac_type = fac_row["Type"]

        STATUS_DOT = {"Operational":"🟢","Commissioning":"🟡","Partial":"🟠",
                      "Reduced":"🔴","SPR":"🛡️","Storage":"🗄️"}
        dot = STATUS_DOT.get(fac_row["Status"], "⚪")

        # ── Facility header ──────────────────────────────────────
        st.markdown(f"""
        <div style='background:#0d1825;border:1px solid #1b2d4f;border-radius:10px;
                    padding:18px 22px;margin:10px 0 18px;'>
            <div style='font-family:var(--display);font-weight:800;font-size:1.3rem;
                        color:#e8dfc8;'>{dot} {selected_fac}</div>
            <div style='font-family:var(--mono);font-size:0.62rem;color:#3a5a88;
                        margin:4px 0 10px;'>{fac_row["Country"]} · {fac_row["Region"]} · {fac_type}</div>
            <div style='font-size:0.82rem;color:#8aaccc;'>
                <b style='color:#c8a060;'>Operator</b>&nbsp; {fac_row["Operator"]} &nbsp;·&nbsp;
                <b style='color:#c8a060;'>Details</b>&nbsp; {fac_row["Detail"]} &nbsp;·&nbsp;
                <b style='color:#c8a060;'>Coords</b>&nbsp;
                <span style='font-family:var(--mono);font-size:0.72rem;'>
                {fac_lat:.4f}°, {fac_lon:.4f}°</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ════════════════════════════════════════════
        # PANEL COLUMNS: left = data, right = visuals
        # ════════════════════════════════════════════
        # ── Intelligence Panel — tabbed layout (no column height overlap) ───
        panel_tab1, panel_tab2, panel_tab3, panel_tab4 = st.tabs([
            "🌤 Weather", "🔥 NASA FIRMS", "🛰 Satellite", "🚢 AIS Tracking"
        ])

        with panel_tab1:

            # ── Live Weather ────────────────────────────────────
            st.markdown("<div class='sh'>🌤 Live Weather — Open-Meteo</div>", unsafe_allow_html=True)
            with st.spinner("Fetching weather…"):
                wx = fetch_weather(fac_lat, fac_lon)

            if wx.get("ok"):
                st.markdown(f"""
                <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                            padding:16px 18px;margin-bottom:12px;'>
                    <div style='font-size:2rem;font-weight:800;color:#e8dfc8;font-family:var(--display);'>
                        {wx["temp_c"]:.1f}°C
                        <span style='font-size:0.9rem;color:#6080a8;font-weight:400;'>{wx["condition"]}</span>
                    </div>
                    <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;
                                font-family:var(--mono);font-size:0.65rem;color:#8aaccc;'>
                        <div><span style='color:#c8a060;'>WIND</span><br>
                             {wx["wind_kmh"]:.0f} km/h @ {wx["wind_dir"]:.0f}°</div>
                        <div><span style='color:#c8a060;'>HUMIDITY</span><br>{wx["humidity"]}%</div>
                        <div><span style='color:#c8a060;'>PRESSURE</span><br>{wx["pressure"]:.0f} hPa</div>
                        <div><span style='color:#c8a060;'>VISIBILITY</span><br>
                             {wx["visibility"]/1000:.1f} km</div>
                    </div>
                </div>
                <div style='font-family:var(--mono);font-size:0.55rem;color:#2a4060;'>
                ▸ {wx["source"]} · {wx["fetched_at"]}</div>
                """, unsafe_allow_html=True)

                # 24h forecast sparklines
                fdf_wx = wx["fcast_df"]
                if not fdf_wx.empty:
                    fig_wx = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                          vertical_spacing=0.08, row_heights=[0.5, 0.5])
                    fig_wx.add_trace(go.Scatter(
                        x=fdf_wx["time"], y=fdf_wx["wind_kmh"], name="Wind (km/h)",
                        line=dict(color=PALETTE["Brent"], width=1.6),
                        fill="tozeroy", fillcolor=rgba(PALETTE["Brent"], 0.1),
                    ), row=1, col=1)
                    fig_wx.add_trace(go.Bar(
                        x=fdf_wx["time"], y=fdf_wx["precip_pct"], name="Precip %",
                        marker_color=rgba(PALETTE["NatGas"], 0.6),
                    ), row=2, col=1)
                    apply_theme(fig_wx, "24h Forecast", height=220,
                                margin=dict(l=45, r=10, t=28, b=28))
                    fig_wx.update_xaxes(**THEME["xaxis"])
                    fig_wx.update_yaxes(**THEME["yaxis"])
                    st.plotly_chart(fig_wx, use_container_width=True)
            else:
                err_box(f"Weather: {wx.get('error','')}")


        with panel_tab2:
            # ── NASA FIRMS Thermal Anomalies ─────────────────────
            st.markdown("<div class='sh'>🔥 NASA FIRMS — Thermal Anomaly Detection</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:var(--mono);font-size:0.58rem;color:var(--text3);"
                "margin-bottom:8px;'>VIIRS + MODIS NRT · Last 24h · ~50km radius · No key</div>",
                unsafe_allow_html=True,
            )
            with st.spinner("Querying NASA FIRMS…"):
                firms = fetch_nasa_firms(fac_lat, fac_lon, radius_km=50)

            if firms.get("ok"):
                if firms["count"] == 0:
                    st.markdown("""
                    <div style='background:rgba(56,184,106,0.07);border:1px solid rgba(56,184,106,0.2);
                                border-radius:8px;padding:14px 16px;
                                font-family:var(--mono);font-size:0.72rem;color:#38b86a;'>
                        ✓ No thermal anomalies in last 24h within 50 km.<br>
                        <span style='color:var(--text3);font-size:0.62rem;'>Normal baseline.</span>
                    </div>""", unsafe_allow_html=True)
                else:
                    df_f = firms["df"]
                    avg_frp = df_f["frp"].mean()
                    max_frp = df_f["frp"].max()
                    severity = "🔴 HIGH" if max_frp > 500 else ("🟡 MODERATE" if max_frp > 100 else "🟢 LOW")
                    st.markdown(f"""
                    <div style='background:rgba(224,80,80,0.07);border:1px solid rgba(224,80,80,0.25);
                                border-radius:8px;padding:14px 16px;margin-bottom:10px;'>
                        <div style='font-family:var(--body);font-weight:600;font-size:0.95rem;
                                    color:#e05858;'>{firms["count"]} thermal anomalies detected</div>
                        <div style='font-family:var(--mono);font-size:0.62rem;color:#a08060;margin-top:6px;'>
                            Severity: {severity} &nbsp;·&nbsp; Sensor: {firms.get("sensor","")} <br>
                            Avg FRP: {avg_frp:.1f} MW &nbsp;·&nbsp; Peak FRP: {max_frp:.1f} MW
                        </div>
                    </div>""", unsafe_allow_html=True)

                    fig_firms = go.Figure()
                    fig_firms.add_trace(go.Scattergeo(
                        lat=[fac_lat], lon=[fac_lon], mode="markers",
                        marker=dict(size=14, color=PALETTE["WTI"], symbol="star"),
                        name="Facility",
                    ))
                    fig_firms.add_trace(go.Scattergeo(
                        lat=df_f["latitude"], lon=df_f["longitude"], mode="markers",
                        marker=dict(
                            size=np.clip(df_f["frp"].fillna(10) / 20 + 5, 5, 20),
                            color=df_f["frp"].fillna(0),
                            colorscale=[[0,"#ff6b6b"],[0.5,"#ff0000"],[1,"#ffffff"]],
                            opacity=0.85, showscale=True,
                            colorbar=dict(thickness=10,
                                          title=dict(text="FRP MW", font=dict(size=9)),
                                          tickfont=dict(size=8)),
                        ),
                        name="Hotspot",
                        hovertemplate="FRP: %{marker.color:.0f} MW<br>%{lat:.3f}, %{lon:.3f}<extra></extra>",
                    ))
                    deg_r = 0.6
                    fig_firms.update_layout(
                        geo=dict(
                            projection_type="mercator", showland=True, landcolor="#0d1825",
                            showocean=True, oceancolor="#07090f",
                            showcountries=True, countrycolor="#1b2d4f", bgcolor="#07090f",
                            lonaxis=dict(range=[fac_lon-deg_r, fac_lon+deg_r]),
                            lataxis=dict(range=[fac_lat-deg_r, fac_lat+deg_r]),
                        ),
                        paper_bgcolor="#07090f",
                        font=dict(color="#5a7898", family="Barlow Condensed", size=9),
                        margin=dict(l=0,r=0,t=0,b=0), height=260,
                        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9)),
                    )
                    st.plotly_chart(fig_firms, use_container_width=True)
                    st.dataframe(
                        df_f[["acq_date","acq_time","frp","bright_ti4","confidence"]]
                        .rename(columns={"acq_date":"Date","acq_time":"Time",
                                         "frp":"FRP (MW)","bright_ti4":"Brightness (K)",
                                         "confidence":"Confidence"})
                        .sort_values("FRP (MW)", ascending=False).head(10),
                        use_container_width=True, hide_index=True,
                    )
                st.markdown(
                    f"<div class='prov'>▸ {firms['source']} · {firms['fetched_at']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                # CSV blocked — show interactive FIRMS map embed instead
                embed_url = firms.get(
                    "embed_url",
                    f"https://firms.modaps.eosdis.nasa.gov/map/#d:24hrs;@{fac_lon:.4f},{fac_lat:.4f},11z"
                )
                st.markdown(f"""
                <div style='font-family:var(--mono);font-size:0.62rem;color:var(--text3);margin-bottom:6px;'>
                    NRT CSV unavailable on this network · Showing NASA FIRMS interactive map.
                    Fire detections update every 3–12 hours from satellite passes.
                </div>
                <div style='border:1px solid var(--border);border-radius:8px;overflow:hidden;'>
                    <iframe src="{embed_url}" width="100%" height="320"
                        style="border:none;display:block;" loading="lazy"
                        title="NASA FIRMS Active Fire Map">
                    </iframe>
                </div>
                <div class='prov' style='margin-top:4px;'>
                    ▸ NASA FIRMS Active Fire Map · VIIRS + MODIS · No key ·
                    <a href="{embed_url}" target="_blank" style='color:var(--gold);'>Open full screen ↗</a>
                </div>""", unsafe_allow_html=True)



        with panel_tab3:

            # ── Satellite Imagery ────────────────────────────────
            st.markdown("<div class='sh'>🛰 Satellite Imagery</div>", unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:var(--mono);font-size:0.58rem;color:#3a5a88;"
                "margin-bottom:8px;'>Esri World Imagery (ArcGIS) · Free · No key · "
                "Sub-metre resolution where available</div>",
                unsafe_allow_html=True,
            )

            sat_zoom = st.slider("Zoom level", 10, 17, 14, key="sat_zoom")

            # Fetch 3×3 tile mosaic from Esri World Imagery
            with st.spinner("Loading satellite tiles…"):
                mosaic = fetch_satellite_mosaic(fac_lat, fac_lon, zoom=sat_zoom)

            if mosaic["ok"] and mosaic["tiles"]:
                import io
                try:
                    from PIL import Image
                    # Stitch 3×3 grid into single image
                    tile_size = 256
                    grid = Image.new("RGB", (tile_size * 3, tile_size * 3))
                    for row, col, tile_bytes in mosaic["tiles"]:
                        tile_img = Image.open(io.BytesIO(tile_bytes)).convert("RGB")
                        grid.paste(tile_img, (col * tile_size, row * tile_size))
                    # Annotate centre crosshair
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(grid)
                    cx, cy = tile_size * 3 // 2, tile_size * 3 // 2
                    draw.ellipse([cx-8, cy-8, cx+8, cy+8], outline="#e8a020", width=2)
                    draw.line([cx-14, cy, cx+14, cy], fill="#e8a020", width=1)
                    draw.line([cx, cy-14, cx, cy+14], fill="#e8a020", width=1)
                    buf = io.BytesIO()
                    grid.save(buf, format="PNG")
                    st.image(buf.getvalue(), use_container_width=True,
                             caption=f"{selected_fac} · {fac_lat:.4f}°, {fac_lon:.4f}° · zoom {sat_zoom}")
                    st.markdown(
                        f"<div class='prov'>▸ {mosaic['source']} · {mosaic['fetched_at']} "
                        f"· 3×3 tile mosaic</div>",
                        unsafe_allow_html=True,
                    )
                except ImportError:
                    # Pillow not available — show centre tile only
                    centre_tile = next(
                        (b for r,c,b in mosaic["tiles"] if r==1 and c==1), None
                    )
                    if centre_tile:
                        st.image(centre_tile, use_container_width=True,
                                 caption=f"{selected_fac} · zoom {sat_zoom}")
                    st.markdown(
                        f"<div class='prov'>▸ {mosaic['source']} · centre tile only "
                        f"(install Pillow for full mosaic)</div>",
                        unsafe_allow_html=True,
                    )
            else:
                err_box(f"Satellite tiles: {mosaic.get('error','fetch failed')}")

            # External viewers
            gmaps_url = google_maps_satellite_url(fac_lat, fac_lon, zoom=sat_zoom)
            st.markdown(f"""
            <div style='display:flex;gap:10px;margin:8px 0 20px;flex-wrap:wrap;'>
                <a href="{gmaps_url.replace('output=embed&','')}"
                   target="_blank"
                   style='font-family:var(--mono);font-size:0.6rem;
                          color:#e8a020;text-decoration:none;
                          background:#0d1825;border:1px solid #1b2d4f;
                          border-radius:4px;padding:5px 12px;'>
                   🗺 Open in Google Maps ↗
                </a>
                <a href="https://livingatlas.arcgis.com/wayback/#active=18150&ext={fac_lon-0.03},{fac_lat-0.02},{fac_lon+0.03},{fac_lat+0.02}"
                   target="_blank"
                   style='font-family:var(--mono);font-size:0.6rem;
                          color:#e8a020;text-decoration:none;
                          background:#0d1825;border:1px solid #1b2d4f;
                          border-radius:4px;padding:5px 12px;'>
                   📅 Esri Wayback (historical imagery) ↗
                </a>
                <a href="https://earthengine.google.com/timelapse#v={fac_lat:.4f},{fac_lon:.4f},12,latLng"
                   target="_blank"
                   style='font-family:var(--mono);font-size:0.6rem;
                          color:#e8a020;text-decoration:none;
                          background:#0d1825;border:1px solid #1b2d4f;
                          border-radius:4px;padding:5px 12px;'>
                   ⏱ Google Earth Timelapse ↗
                </a>
            </div>""", unsafe_allow_html=True)


        with panel_tab4:
            # ── AIS Vessel Tracking ──────────────────────────────
            st.markdown("<div class='sh'>🚢 AIS Live Vessel Tracking — MarineTraffic</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:var(--mono);font-size:0.58rem;color:#3a5a88;"
                "margin-bottom:8px;'>Live AIS positions · Tankers, product carriers & LNG vessels "
                "near this terminal · Updates every ~2 min</div>",
                unsafe_allow_html=True,
            )
            ais_zoom = st.slider("AIS map zoom", 7, 14, 10, key="ais_zoom")
            ais_url = marinetraffic_url(fac_lat, fac_lon, zoom=ais_zoom)

            st.markdown(f"""
            <div style='border:1px solid #1b2d4f;border-radius:8px;overflow:hidden;
                        margin-bottom:6px;'>
                <iframe src="{ais_url}"
                    width="100%" height="400"
                    style="border:none;display:block;"
                    loading="lazy"
                    title="AIS vessel tracking — {selected_fac}">
                </iframe>
            </div>
            <div style='font-family:var(--mono);font-size:0.55rem;color:#2a4060;'>
                ▸ MarineTraffic AIS · IMO/MMSI broadcast data ·
                <a href="https://www.marinetraffic.com/en/ais/home/centerx:{fac_lon:.3f}/centery:{fac_lat:.3f}/zoom:{ais_zoom}"
                target="_blank" style='color:#e8a020;'>Open full screen ↗</a>
            </div>""", unsafe_allow_html=True)


        # ── Facility Detail Cards — inside if block, after columns ────────────
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.expander("📋 Full Facility Database — Refineries & Storage"):
            card_tab1, card_tab2 = st.tabs(["🏭 Refineries", "🗄️ Storage & SPR"])

            with card_tab1:
                card_region = st.selectbox("Region", ["All"] + sorted(REFINERIES["Region"].unique()), key="card_reg")
                card_status = st.selectbox("Status", ["All"] + sorted(REFINERIES["Status"].unique()), key="card_stat")
                card_df = REFINERIES.copy()
                if card_region != "All":
                    card_df = card_df[card_df["Region"] == card_region]
                if card_status != "All":
                    card_df = card_df[card_df["Status"] == card_status]
                card_df = card_df.sort_values("Capacity_kbd", ascending=False)
                STATUS_DOT2 = {"Operational":"🟢","Commissioning":"🟡","Partial":"🟠","Reduced":"🔴"}
                cols_per_row = 3
                for row_start in range(0, len(card_df), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for ci, (_, row) in enumerate(card_df.iloc[row_start:row_start+cols_per_row].iterrows()):
                        dot2 = STATUS_DOT2.get(row["Status"], "⚪")
                        with cols[ci]:
                            st.markdown(f"""
                            <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                                        padding:14px 16px;margin-bottom:10px;min-height:160px;'>
                                <div style='font-family:var(--display);font-size:0.88rem;color:#dde3ee;margin-bottom:6px;'>{dot2} {row["Name"]}</div>
                                <div style='font-family:var(--mono);font-size:0.6rem;color:#3a5a88;margin-bottom:8px;'>{row["Country"]} · {row["Region"]}</div>
                                <div style='font-size:0.78rem;color:#8aaccc;line-height:1.7;'>
                                    <b style='color:#c8a060;'>Operator</b> {row["Operator"]}<br>
                                    <b style='color:#c8a060;'>Capacity</b> {row["Capacity_kbd"]:,} kb/d<br>
                                    <b style='color:#c8a060;'>Crude</b> {row["Crude"]}<br>
                                    <b style='color:#c8a060;'>Status</b> {row["Status"]}
                                </div>
                            </div>""", unsafe_allow_html=True)
                dl_button(card_df, "refineries_global.csv")

            with card_tab2:
                stor_region2 = st.selectbox("Region", ["All"] + sorted(STORAGE["Region"].unique()), key="stor_reg2")
                stor_df2 = STORAGE if stor_region2 == "All" else STORAGE[STORAGE["Region"] == stor_region2]
                stor_df2 = stor_df2.sort_values("Capacity_MMbbl", ascending=False)
                for row_start in range(0, len(stor_df2), cols_per_row):
                    cols = st.columns(cols_per_row)
                    for ci, (_, row) in enumerate(stor_df2.iloc[row_start:row_start+cols_per_row].iterrows()):
                        stype_icon = "🛡️" if row["Type"] == "SPR" else "🗄️"
                        with cols[ci]:
                            st.markdown(f"""
                            <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                                        padding:14px 16px;margin-bottom:10px;min-height:150px;'>
                                <div style='font-family:var(--display);font-size:0.88rem;color:#dde3ee;margin-bottom:6px;'>{stype_icon} {row["Name"]}</div>
                                <div style='font-family:var(--mono);font-size:0.6rem;color:#3a5a88;margin-bottom:8px;'>{row["Country"]} · {row["Type"]}</div>
                                <div style='font-size:0.78rem;color:#8aaccc;line-height:1.7;'>
                                    <b style='color:#c8a060;'>Operator</b> {row["Operator"]}<br>
                                    <b style='color:#c8a060;'>Capacity</b> {row["Capacity_MMbbl"]:,} MMbbl<br>
                                    <b style='color:#c8a060;'>Product</b> {row["Product"]}<br>
                                    <b style='color:#c8a060;'>Status</b> {row["Status"]}
                                </div>
                            </div>""", unsafe_allow_html=True)
                dl_button(stor_df2, "storage_terminals_global.csv")


# ╔══════════════════════════════════════════════╗
# ║  TAB 8 · REFINED PRODUCTS (ML)              ║
# ╚══════════════════════════════════════════════╝
with tab_products:
    st.markdown("<div class='sh'>⚗️ Downstream Refined Product Intelligence</div>", unsafe_allow_html=True)

    with st.spinner("Fetching refined-product & crude series…"):
        gasoline_res = fetch_yf_ohlcv("RB=F", period="2y")
        diesel_res   = fetch_yf_ohlcv("HO=F", period="2y")
        crude_for_products_res = fetch_yf_ohlcv(bench_sym, period="2y")

    if not (gasoline_res["ok"] and diesel_res["ok"] and crude_for_products_res["ok"]):
        err_box("One or more product/crude series failed to fetch — refined-products "
                "analysis needs Gasoline, Diesel and the selected benchmark crude. "
                "Try refreshing or picking a different Primary Benchmark in the sidebar.")
    else:
        gdf, ddf, cdf = gasoline_res["df"], diesel_res["df"], crude_for_products_res["df"]
        jdf = apply_jet_fuel_basis(ddf)   # seasonal jet-fuel proxy, distinct from raw diesel

        gas_last  = gdf["Close"].iloc[-1]
        dsl_last  = ddf["Close"].iloc[-1]
        jet_last  = jdf["Close"].iloc[-1]
        gas_chg   = (gdf["Close"].iloc[-1] / gdf["Close"].iloc[-2] - 1) * 100
        dsl_chg   = (ddf["Close"].iloc[-1] / ddf["Close"].iloc[-2] - 1) * 100
        crack321  = compute_321_crack(gdf, ddf, cdf)
        c321_last = crack321["crack_321"].iloc[-1]

        # ── Hero banner ───────────────────────────────────────
        st.markdown(f"""
        <div class='hero' style='padding:22px 28px;margin-bottom:16px;'>
          <div style='display:flex;align-items:center;gap:18px;'>
            <div style='font-size:3rem;line-height:1;'>⚗️</div>
            <div>
              <div class='hero-title'>Refined Product Intelligence</div>
              <div class='hero-sub'>Live crack spreads · ML forecast · Supply stress detection · {datetime.today().strftime('%d %b %Y')}</div>
              <div style='margin-top:10px;'>
                <span class='badge badge-live'>● LIVE</span>
                <span class='badge'>RBOB ${gas_last:.2f}/gal ({gas_chg:+.1f}%)</span>
                <span class='badge'>ULSD/DIESEL ${dsl_last:.2f}/gal ({dsl_chg:+.1f}%)</span>
                <span class='badge'>JET (MODELED) ${jet_last:.2f}/gal</span>
                <span class='badge'>3:2:1 CRACK ${c321_last:.2f}/bbl</span>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class='info-box'>
        Crude oil is a single input to a <b>joint-output</b> refining process — every barrel
        is cracked into a fixed slate of products simultaneously. Only two refined products
        have a free, keyless, tradable futures price (RBOB Gasoline &amp; NY Harbor Heating
        Oil / ULSD). Jet Fuel is derived from live ULSD with a documented seasonal basis
        (see chart below) so it's directionally distinct, not a duplicate of Diesel.
        Products with no tradable proxy at all (Naphtha, Fuel Oil, Asphalt, Lubricants, Wax,
        Petroleum Jelly, etc.) are shown as a static EIA-benchmark reference panel instead
        of a fabricated forecast.
        </div>
        """, unsafe_allow_html=True)

        # ── Live multi-product comparison (normalised) ──────────
        st.markdown("<div class='sh'>📈 Live Product Comparison — Normalised to 100</div>", unsafe_allow_html=True)
        norm = pd.DataFrame({
            "Gasoline (RBOB)": gdf["Close"] / gdf["Close"].iloc[0] * 100,
            "Diesel / ULSD":   ddf["Close"] / ddf["Close"].iloc[0] * 100,
            "Jet Fuel (modeled)": jdf["Close"] / jdf["Close"].iloc[0] * 100,
            f"{bench_ticker.split('(')[0].strip()} (Crude)": cdf["Close"] / cdf["Close"].iloc[0] * 100,
        }).dropna()
        cmp_colors = [PALETTE["Gasoline"], PALETTE["HeatingOil"], PALETTE["NatGas"], PALETTE["WTI"]]
        fig_cmp = go.Figure()
        for i, col in enumerate(norm.columns):
            fig_cmp.add_trace(go.Scatter(x=norm.index, y=norm[col], name=col,
                                         line=dict(color=cmp_colors[i % len(cmp_colors)], width=1.8)))
        fig_cmp.add_hline(y=100, line_dash="dot", line_color=rgba(PALETTE["white"], 0.15))
        apply_theme(fig_cmp, "Gasoline vs Diesel vs Jet Fuel (modeled) vs Crude — 2Y", height=380)
        st.plotly_chart(fig_cmp, use_container_width=True)
        st.markdown(
            "<div class='prov'>▸ Gasoline &amp; Diesel: live Yahoo Finance futures (RB=F, HO=F) · "
            "Jet Fuel: ULSD × seasonal jet-diesel basis model (±3.5% amplitude, peak mid-July) — "
            "modeled, not a live traded price</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div class='sh'>📐 Model Controls</div>", unsafe_allow_html=True)
        pc1, pc2 = st.columns(2)
        with pc1:
            product_choice = st.selectbox(
                "Product to forecast",
                list(TRADABLE_PRODUCTS.keys()),
                index=0,
            )
        with pc2:
            forecast_horizon = st.slider("Forecast horizon (trading days ahead)", 1, 20, 5)

        meta = TRADABLE_PRODUCTS[product_choice]

        # Reuse the already-fetched series instead of re-fetching (faster, and
        # guarantees the Jet Fuel basis transform is applied where relevant).
        if meta.get("synthetic_basis"):
            pdf = jdf
        elif meta["ticker"] == "RB=F":
            pdf = gdf
        else:
            pdf = ddf

        spread_df = compute_crack_spread(
            pdf, cdf, bbl_gal=meta["bbl_gal"], basis_factor=meta.get("basis_factor", 1.0)
        )
        st.markdown(f"<div class='prov'>▸ {meta['note']}</div>", unsafe_allow_html=True)

        prod_color = PALETTE["Gasoline"] if "Gasoline" in product_choice else (
            PALETTE["NatGas"] if "Jet" in product_choice else PALETTE["HeatingOil"])

        # ── Crack spread chart ─────────────────────────────
        st.markdown(f"<div class='sh' style='font-size:0.85rem;'>Crack Spread History ($/bbl) — {product_choice}</div>",
                    unsafe_allow_html=True)
        fig_spread = go.Figure()
        fig_spread.add_trace(go.Scatter(
            x=spread_df.index, y=spread_df["crack_spread"],
            mode="lines", line=dict(color=prod_color, width=1.8),
            fill="tozeroy", fillcolor=rgba(prod_color, 0.1),
            name="Crack spread",
        ))
        apply_theme(fig_spread, title=f"{product_choice} crack spread vs {bench_ticker}", height=340)
        st.plotly_chart(fig_spread, use_container_width=True)

        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Latest crack spread", f"${spread_df['crack_spread'].iloc[-1]:.2f}/bbl")
        sc2.metric("30D avg", f"${spread_df['crack_spread'].tail(30).mean():.2f}/bbl")
        sc3.metric("30D volatility (σ)", f"${spread_df['crack_spread'].tail(30).std():.2f}/bbl")

        # ── ML forecast ─────────────────────────────────────
        st.markdown("<div class='sh' style='font-size:0.85rem;'>🤖 ML Forecast — Gradient Boosted Regressor</div>",
                    unsafe_allow_html=True)
        with st.spinner("Training walk-forward validated forecaster…"):
            fc = train_crack_forecaster(spread_df["crack_spread"], horizon=forecast_horizon)

        if not fc["ok"]:
            err_box(fc.get("error", "Forecast failed"))
        else:
            delta = fc["next_pred"] - fc["last_actual"]
            direction = "🟢 UP" if delta > 0 else ("🔴 DOWN" if delta < 0 else "🟡 FLAT")
            st.markdown(f"""
            <div class='hero' style='padding:16px 22px;margin-bottom:10px;'>
              <div style='display:flex;align-items:center;gap:14px;'>
                <div style='font-size:1.8rem;'>🤖</div>
                <div>
                  <div class='hero-title' style='font-size:1.15rem;'>{direction} {abs(delta):.2f} predicted over {forecast_horizon}d</div>
                  <div class='hero-sub'>GradientBoostingRegressor · walk-forward validated</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            fcol1, fcol2, fcol3 = st.columns(3)
            fcol1.metric("Last actual", f"${fc['last_actual']:.2f}/bbl")
            fcol2.metric(f"Predicted (+{forecast_horizon}d)", f"${fc['next_pred']:.2f}/bbl",
                         f"{delta:+.2f}")
            fcol3.metric("Walk-forward MAE", f"±${fc['cv_mae']:.2f}/bbl",
                         f"{fc['n_folds']}-fold CV")
            st.markdown(
                f"<div class='prov'>▸ Trained on {fc['n_train_rows']} rows · TimeSeriesSplit "
                f"walk-forward validation (never trains on future data to predict the past) · "
                f"MAE std across folds ±${fc['cv_mae_std']:.2f}</div>",
                unsafe_allow_html=True,
            )

            with st.expander("📊 Feature importances"):
                imp_df = fc["feature_importances"].reset_index()
                imp_df.columns = ["feature", "importance"]
                fig_imp = go.Figure(go.Bar(
                    x=imp_df["importance"], y=imp_df["feature"], orientation="h",
                    marker_color=prod_color,
                ))
                apply_theme(fig_imp, title="What drives the forecast", height=320)
                st.plotly_chart(fig_imp, use_container_width=True)

        # ── Seasonal decomposition ──────────────────────────
        with st.expander("📅 Seasonal decomposition (STL)"):
            decomp = seasonal_decompose_spread(spread_df["crack_spread"])
            if not decomp["ok"]:
                err_box(decomp.get("error"))
            else:
                fig_dc = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                        subplot_titles=("Trend", "Seasonal (quarterly cycle)", "Residual"))
                fig_dc.add_trace(go.Scatter(x=decomp["trend"].index, y=decomp["trend"],
                                             line=dict(color=PALETTE["WTI"])), row=1, col=1)
                fig_dc.add_trace(go.Scatter(x=decomp["seasonal"].index, y=decomp["seasonal"],
                                             line=dict(color=PALETTE["Brent"])), row=2, col=1)
                fig_dc.add_trace(go.Scatter(x=decomp["resid"].index, y=decomp["resid"],
                                             line=dict(color=PALETTE["purple"])), row=3, col=1)
                apply_theme(fig_dc, height=520)
                fig_dc.update_layout(showlegend=False)
                st.plotly_chart(fig_dc, use_container_width=True)
                st.markdown(
                    "<div class='prov'>▸ STL period = 63 trading days (~1 quarter) to "
                    "capture driving-season / heating-season switches</div>",
                    unsafe_allow_html=True,
                )

        # ── Supply stress / anomaly detection ───────────────
        st.markdown("<div class='sh' style='font-size:0.85rem;'>🚨 Supply Stress Detector — Isolation Forest</div>",
                    unsafe_allow_html=True)
        stress = detect_supply_stress(spread_df["crack_spread"])
        if not stress["ok"]:
            err_box(stress.get("error"))
        else:
            if stress["latest_is_anomaly"]:
                err_box(f"Latest session flagged as anomalous (score {stress['latest_score']:.3f}) — "
                        f"crack spread is moving outside its normal statistical range.")
            else:
                st.markdown(
                    f"<div class='info-box'>Latest session is within normal range "
                    f"(anomaly score {stress['latest_score']:.3f}). "
                    f"{stress['n_anomalies']} anomalous sessions detected in the trailing history.</div>",
                    unsafe_allow_html=True,
                )
            sdf = stress["df"]
            fig_anom = go.Figure()
            fig_anom.add_trace(go.Scatter(
                x=sdf.index, y=sdf["spread"], mode="lines",
                line=dict(color=PALETTE["white"], width=1.2), name="Crack spread",
            ))
            anom_pts = sdf[sdf["anomaly"] == -1]
            fig_anom.add_trace(go.Scatter(
                x=anom_pts.index, y=anom_pts["spread"], mode="markers",
                marker=dict(color=PALETTE["red"], size=7, symbol="x"),
                name="Flagged anomaly",
            ))
            apply_theme(fig_anom, title="Anomalous crack-spread sessions", height=340)
            st.plotly_chart(fig_anom, use_container_width=True)
            dl_button(stress["anomalies"].reset_index(), f"{meta['ticker']}_supply_stress_flags.csv")

        st.markdown("---")

        # ── Per-product news-derived disruption score ───────────
        st.markdown("<div class='sh'>📰 Per-Product Disruption Signal (from live RSS feed)</div>",
                    unsafe_allow_html=True)
        news_res_products = fetch_rss_news()
        if not news_res_products["ok"]:
            err_box("News feed unavailable — disruption signal needs the RSS feeds "
                    "used in the Geopolitical tab.")
        else:
            disr_df = compute_product_disruption_scores(news_res_products["articles"])
            flag_colors = {
                "🔴 Elevated disruption chatter": PALETTE["red"],
                "🟠 Mild negative signal": PALETTE["WTI"],
                "🟡 Neutral": "#c8a060",
                "🟢 Stable / positive": PALETTE["green"],
                "No recent coverage": PALETTE["white"],
            }
            dcols = st.columns(len(disr_df)) if len(disr_df) <= 6 else st.columns(3)
            for i, (_, row) in enumerate(disr_df.iterrows()):
                col = dcols[i % len(dcols)]
                clr = flag_colors.get(row["risk_flag"], PALETTE["white"])
                with col:
                    st.markdown(f"""
                    <div style='background:linear-gradient(135deg, var(--panel) 0%, var(--panel2) 100%);
                                border:1px solid var(--border); border-top:2px solid {clr};
                                border-radius:10px; padding:12px 14px; margin-bottom:10px; min-height:118px;'>
                        <div style='font-family:var(--body); font-weight:600; font-size:0.8rem;
                                    color:var(--text); margin-bottom:6px;'>{row['product']}</div>
                        <div style='font-family:var(--mono); font-size:0.62rem; color:{clr};
                                    letter-spacing:0.05em; margin-bottom:4px;'>{row['risk_flag']}</div>
                        <div style='font-family:var(--mono); font-size:0.6rem; color:var(--text3);'>
                            {row['article_count']} articles · net sentiment {row['net_sentiment']:+d}
                        </div>
                    </div>""", unsafe_allow_html=True)
            st.markdown(
                "<div class='prov'>▸ Lightweight lexicon-based sentiment over "
                f"{news_res_products.get('count','')} live articles (Reuters/BBC/Al Jazeera/"
                "OilPrice/Rigzone) — a keyless, dependency-free substitute for a trained "
                "NLP classifier. Not investment advice.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── Non-tradable product reference panel ─────────────────
        st.markdown("<div class='sh'>📋 Non-Tradable Products — Reference Panel</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='info-box'>
        These products have no free live futures price, so no forecast is shown for
        them — showing a fabricated prediction here would overstate what the free data
        actually supports. Typical yield % is a long-run US refinery average
        (EIA-published order of magnitude); actual output varies by crude slate and
        refinery configuration.
        </div>
        """, unsafe_allow_html=True)
        ref_df = pd.DataFrame(NON_TRADABLE_PRODUCTS)
        sens_colors = {"High": PALETTE["red"], "Medium": PALETTE["WTI"], "Low": PALETTE["green"]}
        rcols = st.columns(4)
        for i, row in enumerate(NON_TRADABLE_PRODUCTS):
            sens_word = row["disruption_sensitivity"].split(" ")[0].replace("—", "").strip()
            clr = sens_colors.get(sens_word, PALETTE["white"])
            with rcols[i % 4]:
                st.markdown(f"""
                <div style='background:linear-gradient(135deg, var(--panel) 0%, var(--panel2) 100%);
                            border:1px solid var(--border); border-left:3px solid {clr};
                            border-radius:8px; padding:12px 14px; margin-bottom:12px; min-height:150px;'>
                    <div style='font-family:var(--body); font-weight:600; font-size:0.78rem;
                                color:var(--text); margin-bottom:6px;'>{row['product']}</div>
                    <div style='font-family:var(--mono); font-size:0.68rem; color:var(--gold);
                                margin-bottom:6px;'>{row['yield_pct']}% typical yield/bbl</div>
                    <div style='font-family:var(--body); font-size:0.68rem; color:var(--text2);
                                margin-bottom:6px; line-height:1.4;'>{row['driver']}</div>
                    <div style='font-family:var(--mono); font-size:0.6rem; color:{clr};'>
                        {row['disruption_sensitivity']}</div>
                </div>""", unsafe_allow_html=True)
        dl_button(ref_df, "non_tradable_product_reference.csv")


# ╔══════════════════════════════════════════════╗
# ║  TAB 9 · GEOPOLITICAL NEWS                  ║
# ╚══════════════════════════════════════════════╝
# ╔══════════════════════════════════════════════╗
# ║  TAB 9 · GEOPOLITICAL (Live RSS)            ║
# ╚══════════════════════════════════════════════╝
with tab_news:
    st.markdown("<div class='sh'>📰 Live Energy & Geopolitical News</div>", unsafe_allow_html=True)

    with st.spinner("Fetching live news feeds…"):
        news_res = fetch_rss_news()

    if not news_res["ok"]:
        err_box(news_res.get("error", "All RSS feeds failed"))
        # ── Static curated fallback ──────────────────────────────
        st.markdown("<div class='sh'>Key Geopolitical Events — Historical Log</div>", unsafe_allow_html=True)
        for date, desc, dot in GEO_EVENTS:
            st.markdown(f"""
            <div class='news-card'>
                <div class='news-title'>{dot} {desc}</div>
                <div class='news-meta'>📅 {date} · Geopolitical Event Log</div>
            </div>""", unsafe_allow_html=True)
    else:
        articles = news_res["articles"]

        # ── Sentiment scoring for hero + per-card coloring ────────
        for a in articles:
            a["_sent"] = score_article_sentiment(a.get("title", ""), a.get("description", ""))
        net_sent = sum(a["_sent"] for a in articles)
        neg_count = sum(1 for a in articles if a["_sent"] < 0)
        pos_count = sum(1 for a in articles if a["_sent"] > 0)
        mood = "🔴 RISK-OFF" if net_sent <= -4 else ("🟠 CAUTIOUS" if net_sent < 0 else
               ("🟡 NEUTRAL" if net_sent == 0 else "🟢 CONSTRUCTIVE"))
        most_negative = min(articles, key=lambda a: a["_sent"]) if articles else None

        # ── Hero banner ────────────────────────────────────────
        st.markdown(f"""
        <div class='hero' style='padding:22px 28px;margin-bottom:16px;'>
          <div style='display:flex;align-items:center;gap:18px;'>
            <div style='font-size:3rem;line-height:1;'>🌍</div>
            <div>
              <div class='hero-title'>Geopolitical News Pulse</div>
              <div class='hero-sub'>{mood} · {datetime.today().strftime('%d %b %Y %H:%M')} UTC</div>
              <div style='margin-top:10px;'>
                <span class='badge badge-live'>● {len(articles)} LIVE ARTICLES</span>
                <span class='badge'>🔴 {neg_count} NEGATIVE</span>
                <span class='badge'>🟢 {pos_count} POSITIVE</span>
                <span class='badge'>NET SENTIMENT {net_sent:+d}</span>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Feed health status ───────────────────────────────────
        if news_res.get("sources_ok") or news_res.get("sources_fail"):
            health_parts = []
            for s in news_res.get("sources_ok", []):
                health_parts.append(f"<span style='color:#40b860'>✓ {s}</span>")
            for s in news_res.get("sources_fail", []):
                short = s.split(":")[0]
                health_parts.append(f"<span style='color:#e05050'>✗ {short}</span>")
            st.markdown(
                "<div style='font-family:var(--mono);font-size:0.6rem;margin-bottom:14px;"
                "letter-spacing:0.05em;'>SOURCE HEALTH &nbsp; "
                + " &nbsp;·&nbsp; ".join(health_parts) + "</div>",
                unsafe_allow_html=True,
            )

        # ── Top risk headline callout ─────────────────────────────
        if most_negative and most_negative["_sent"] < 0:
            st.markdown(f"""
            <div class='err-box' style='padding:14px 18px;'>
                <b>⚠ Top risk headline:</b> {most_negative.get('title','')}
                <span style='color:#5a7898;'> — {most_negative.get('source','')} · {most_negative.get('date','')}</span>
            </div>""", unsafe_allow_html=True)

        # ── Price chart with news event markers ──────────────────
        if bench_res["ok"] and articles:
            st.markdown("<div class='sh'>Price Chart with News Event Markers</div>", unsafe_allow_html=True)
            bdf = bench_res["df"]
            fig_n = go.Figure()
            fig_n.add_trace(go.Scatter(
                x=bdf.index, y=bdf["Close"], name="Price",
                line=dict(color=PALETTE["WTI"], width=1.8),
                fill="tozeroy", fillcolor=rgba(PALETTE["WTI"], 0.05),
            ))
            news_dates = list({a["date"] for a in articles if a["date"]})
            for date_str in news_dates:
                try:
                    idx = bdf.index.asof(pd.to_datetime(date_str))
                    if pd.notna(idx) and idx in bdf.index:
                        fig_n.add_vline(
                            x=idx,
                            line_color=rgba(PALETTE["NatGas"], 0.3),
                            line_width=1, line_dash="dot",
                        )
                except Exception:
                    pass
            apply_theme(fig_n, f"{bench_ticker} — News Event Overlay (dotted = news day)", height=300)
            st.plotly_chart(fig_n, use_container_width=True)

        # ── Source filter ────────────────────────────────────────
        st.markdown("<div class='sh'>🗞 Live Feed</div>", unsafe_allow_html=True)
        all_sources = sorted({a["source"] for a in articles})
        n1, n2 = st.columns([3, 1])
        with n1:
            src_filter = st.multiselect("Filter by source", all_sources, default=all_sources)
        with n2:
            n_show = st.slider("Articles to show", 4, 40, 16, step=2)

        filtered = [a for a in articles if a["source"] in src_filter][:n_show]
        st.markdown(
            f"<div class='prov'>Showing {len(filtered)} of {len(articles)} energy articles · "
            f"fetched {news_res.get('fetched_at','')}</div>",
            unsafe_allow_html=True,
        )

        # ── Article cards — 2-col grid, sentiment-colored border ──
        SOURCE_ICONS = {
            "Reuters Energy": "📡", "BBC Business": "🇬🇧", "Al Jazeera Econ": "🕌",
            "Oil Price News": "🛢️", "Rigzone": "🏗️",
        }
        news_cols = st.columns(2)
        for i, a in enumerate(filtered):
            sent = a["_sent"]
            border_clr = (PALETTE["red"] if sent <= -2 else
                          PALETTE["WTI"] if sent < 0 else
                          PALETTE["green"] if sent > 0 else "#3a5a78")
            sent_label = ("🔴 Elevated risk" if sent <= -2 else "🟠 Negative" if sent < 0
                          else "🟢 Positive" if sent > 0 else "🟡 Neutral")
            icon = SOURCE_ICONS.get(a.get("source", ""), "📰")
            url_html = (
                f"<a href='{a['url']}' target='_blank' style='color:#e8a020;font-size:0.62rem;"
                f"text-decoration:none;'>↗ Read full article</a>"
                if a.get("url") else ""
            )
            with news_cols[i % 2]:
                st.markdown(f"""
                <div class='news-card' style='border-left:3px solid {border_clr}; min-height:158px;'>
                    <div style='display:flex;justify-content:space-between;align-items:flex-start;'>
                        <div class='news-title' style='max-width:82%;'>{icon} {a.get('title','')}</div>
                    </div>
                    <div class='news-meta'>📅 {a.get('date','')} &nbsp;·&nbsp; {a.get('source','')}
                        &nbsp;·&nbsp; <span style='color:{border_clr};'>{sent_label}</span></div>
                    <div class='news-desc'>{a.get('description','')}</div>
                    <div style='margin-top:8px;'>{url_html}</div>
                </div>""", unsafe_allow_html=True)

        # ── Historical event log at the bottom ───────────────────
        with st.expander("📌 Historical Geopolitical Event Log"):
            ev_cols = st.columns(2)
            for i, (date, desc, dot) in enumerate(GEO_EVENTS):
                with ev_cols[i % 2]:
                    st.markdown(f"""
                    <div class='news-card'>
                        <div class='news-title'>{dot} {desc}</div>
                        <div class='news-meta'>📅 {date} · Geopolitical Event Log</div>
                    </div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;font-family:var(--mono);font-size:0.58rem;color:#1a2a40;padding:8px 0;'>
    DATA SOURCES: Yahoo Finance — prices, yields, FX, volatility, ETFs · RSS: Reuters · BBC · Al Jazeera · OilPrice · Rigzone<br>
    100% keyless — no API registration, no blocked domains · Prices ~15 min delayed · News cached 15 min<br>
    Last render: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</div>
""", unsafe_allow_html=True)
