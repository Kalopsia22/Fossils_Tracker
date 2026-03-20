"""
oil_gas_research.py
═══════════════════════════════════════════════════════════════
Global Crude Oil & Natural Gas — Research Dashboard
═══════════════════════════════════════════════════════════════
Data Sources:
  • Yahoo Finance   — OHLCV futures & ETFs  (no key required)
  • FRED            — Macro indicators       (free key: fred.stlouisfed.org)
  • Alpha Vantage   — Commodity series       (free key: alphavantage.co)
  • NewsAPI         — Geopolitical news      (free key: newsapi.org)

Run locally:
  pip install -r requirements.txt
  streamlit run oil_gas_research.py

Streamlit Cloud — add to .streamlit/secrets.toml:
  FRED_KEY = "your_key"
  AV_KEY   = "your_key"
  NEWS_KEY = "your_key"
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
from datetime import datetime, timedelta

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

FRED_SERIES = {
    "US CPI (Energy)":          "CPIENGSL",
    "US CPI (All)":             "CPIAUCSL",
    "Fed Funds Rate":           "FEDFUNDS",
    "US Dollar Index (DXY)":    "DTWEXBGS",
    "10Y Treasury Yield":       "DGS10",
    "US Unemployment Rate":     "UNRATE",
    "US Industrial Production": "INDPRO",
    "US Petroleum Consumption": "TOTALNSA",
}

ALPHA_SERIES = {
    "Brent Crude (Monthly)":  ("BRENT",       "monthly"),
    "WTI Crude (Monthly)":    ("WTI",          "monthly"),
    "Natural Gas (Monthly)":  ("NATURAL_GAS",  "monthly"),
    "Copper (Monthly)":       ("COPPER",       "monthly"),
    "Aluminum (Monthly)":     ("ALUMINUM",     "monthly"),
}

FIELDS_DF = pd.DataFrame({
    "Field":    ["Ghawar","Burgan","Ahvaz","Permian Basin","Rumaila","Safaniya",
                 "Cantarell","Samotlor","Daqing","Pembina",
                 "North Field","Siberian Gas","Marcellus Shale","Haynesville",
                 "Groningen","Barnett","Appalachian","Yamal LNG"],
    "Lat":      [24.8,29.0,31.3,32.0,30.4,27.9,19.7,61.5,46.6,52.8,
                 25.9,61.0,41.5,32.0,53.3,32.8,38.5,71.0],
    "Lon":      [49.5,47.8,49.5,-102.0,47.1,49.5,-91.9,68.4,124.7,-114.5,
                 51.4,73.0,-77.5,-93.5,6.8,-97.4,-81.5,68.8],
    "Type":     ["Crude","Crude","Crude","Crude","Crude","Crude",
                 "Crude","Crude","Crude","Crude",
                 "Natural Gas","Natural Gas","Natural Gas","Natural Gas",
                 "Natural Gas","Natural Gas","Natural Gas","LNG"],
    "Reserves": [75,66,65,55,43,37,18,14,7,8,
                 900,1688,141,75,2.7,44,32,5],
    "Country":  ["Saudi Arabia","Kuwait","Iran","USA","Iraq","Saudi Arabia",
                 "Mexico","Russia","China","Canada",
                 "Qatar","Russia","USA","USA",
                 "Netherlands","USA","USA","Russia"],
    "Status":   ["Active","Active","Active","Active","Active","Active",
                 "Declining","Declining","Active","Active",
                 "Active","Active","Active","Active",
                 "Depleting","Active","Active","Active"],
})

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
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.stApp { background: #07090f; color: #dde3ee; }

section[data-testid="stSidebar"] {
    background: #0b0e18 !important;
    border-right: 1px solid #161d30;
}
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0e1525 0%, #111c32 100%);
    border: 1px solid #1b2d4f;
    border-radius: 8px;
    padding: 14px 18px !important;
}
div[data-testid="metric-container"] label {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.62rem !important;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #4a6fa5 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.65rem !important;
    font-weight: 800;
    color: #e8dfc8 !important;
}
div[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }
div[data-testid="stTabs"] button {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #3a5a88 !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #e8a020 !important;
    border-bottom: 2px solid #e8a020 !important;
    background: transparent !important;
}
.sh {
    font-family: 'Syne', sans-serif;
    font-weight: 700;
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    color: #c8a060;
    text-transform: uppercase;
    padding-bottom: 6px;
    border-bottom: 1px solid #161d30;
    margin: 1.2rem 0 0.8rem;
}
.prov {
    font-family: 'Space Mono', monospace;
    font-size: 0.58rem;
    color: #2a4060;
    letter-spacing: 0.08em;
    margin-top: 2px;
}
.err-box {
    background: #1a0808;
    border-left: 3px solid #c0392b;
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: #e07070;
    margin: 6px 0 10px;
}
.info-box {
    background: #0d1825;
    border-left: 3px solid #e8a020;
    border-radius: 0 6px 6px 0;
    padding: 12px 16px;
    font-size: 0.84rem;
    color: #8aaccc;
    margin: 6px 0 12px;
}
.news-card {
    background: #0d1220;
    border: 1px solid #161d30;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.news-title { font-weight: 700; font-size: 0.9rem; color: #dde3ee; margin-bottom: 4px; }
.news-meta  { font-family: 'Space Mono', monospace; font-size: 0.6rem; color: #3a5a88; }
.news-desc  { font-size: 0.8rem; color: #7a9ab8; margin-top: 6px; }
.hero {
    background: linear-gradient(135deg, #0a1020 0%, #0f1d38 60%, #0a1020 100%);
    border: 1px solid #1b2d4f;
    border-radius: 10px;
    padding: 20px 26px;
    margin-bottom: 18px;
}
.hero-title { font-weight: 800; font-size: 1.7rem; color: #e8dfc8; line-height: 1.1; }
.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.62rem;
    color: #3a5a88;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-top: 3px;
}
.badge {
    display: inline-block;
    background: #111c32;
    border: 1px solid #1b3060;
    border-radius: 20px;
    padding: 3px 11px;
    font-family: 'Space Mono', monospace;
    font-size: 0.58rem;
    color: #4a7ab8;
    margin: 8px 4px 0 0;
    letter-spacing: 0.08em;
}
.badge-live { background: #0d1f14; border-color: #1f5030; color: #40b860; }
div[data-testid="stDownloadButton"] button {
    background: #0d1825 !important;
    border: 1px solid #1b2d4f !important;
    color: #4a7ab8 !important;
    font-family: 'Space Mono', monospace !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.08em;
}
hr { border-color: #161d30; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #07090f; }
::-webkit-scrollbar-thumb { background: #161d30; border-radius: 3px; }
label[data-testid="stWidgetLabel"] p {
    font-family: 'Space Mono', monospace !important;
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #3a5a88 !important;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# THEME & PALETTE
# ═══════════════════════════════════════════════════════════════
THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(8,12,22,0.7)",
    font=dict(family="Space Mono, monospace", color="#6080a8", size=10),
    xaxis=dict(gridcolor="#111828", zerolinecolor="#111828", showgrid=True, linecolor="#161d30"),
    yaxis=dict(gridcolor="#111828", zerolinecolor="#111828", showgrid=True, linecolor="#161d30"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    hoverlabel=dict(bgcolor="#0d1525", font_family="Space Mono, monospace", font_size=11),
)

PALETTE = {
    "WTI": "#e8a020", "Brent": "#40c8b0", "NatGas": "#f06060",
    "Gasoline": "#a060e8", "HeatingOil": "#60a8e8",
    "green": "#40b860", "red": "#e05050", "purple": "#a060e8", "white": "#dde3ee",
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
    try:
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
        if raw.empty:
            return {"ok": False, "error": "No data", "df": pd.DataFrame()}
        df = raw["Close"].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) \
             else raw[["Close"]].rename(columns={"Close": tickers[0]})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return {
            "ok": True, "df": df,
            "source": "Yahoo Finance",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fred(series_id: str, api_key: str, start: str = "2010-01-01") -> dict:
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": api_key,
                    "file_type": "json", "observation_start": start, "sort_order": "asc"},
            timeout=10,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if not obs:
            return {"ok": False, "error": "Empty response", "df": pd.DataFrame()}
        df = pd.DataFrame(obs)[["date", "value"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().set_index("date")
        df.columns = [series_id]
        return {
            "ok": True, "df": df, "series_id": series_id,
            "source": "Federal Reserve Bank of St. Louis (FRED)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(df),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fred_multi(series_ids: list, api_key: str, start: str = "2015-01-01") -> dict:
    frames, errors = [], []
    for sid in series_ids:
        res = fetch_fred(sid, api_key, start)
        (frames if res["ok"] else errors).append(res["df"] if res["ok"] else f"{sid}: {res['error']}")
    if not frames:
        return {"ok": False, "error": "; ".join(errors), "df": pd.DataFrame()}
    return {
        "ok": True, "df": pd.concat(frames, axis=1).sort_index(),
        "source": "FRED",
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "errors": errors,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_alpha_commodity(commodity: str, interval: str, api_key: str) -> dict:
    try:
        r = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": commodity, "interval": interval, "apikey": api_key},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if "data" not in data:
            return {"ok": False, "error": data.get("Note") or data.get("Information") or "Unknown", "df": pd.DataFrame()}
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().set_index("date").sort_index()
        df.columns = [commodity]
        return {
            "ok": True, "df": df, "commodity": commodity,
            "source": "Alpha Vantage",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(df),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news(api_key: str, query: str = "oil gas energy OPEC crude", days_back: int = 30) -> dict:
    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d"),
                "sortBy": "publishedAt", "language": "en", "pageSize": 50, "apiKey": api_key,
            },
            timeout=10,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])
        if not articles:
            return {"ok": False, "error": "No articles found", "articles": []}
        cleaned = [{
            "date": pd.to_datetime(a.get("publishedAt", "")).strftime("%Y-%m-%d") if a.get("publishedAt") else "",
            "title": a.get("title", ""),
            "source": a.get("source", {}).get("name", ""),
            "url": a.get("url", ""),
            "description": a.get("description", ""),
        } for a in articles]
        return {
            "ok": True, "articles": cleaned,
            "source": "NewsAPI",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "count": len(cleaned),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "articles": []}

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
# SIDEBAR
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:10px 0 16px;'>
        <div style='font-size:2.2rem'>🛢️</div>
        <div style='font-family:Syne,sans-serif;font-weight:800;font-size:1rem;color:#e8dfc8;letter-spacing:0.04em;'>OIL & GAS RESEARCH</div>
        <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#3a5a88;letter-spacing:0.15em;'>MULTI-SOURCE · LIVE DATA</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sh'>🔑 API Keys</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family:Space Mono,monospace;font-size:0.6rem;color:#2a4060;margin-bottom:8px;'>Store in .streamlit/secrets.toml for Cloud</div>", unsafe_allow_html=True)

    def _key(label, secret, url):
        val = st.secrets.get(secret, "") if hasattr(st, "secrets") else ""
        return st.text_input(label, value=val, type="password", help=f"Free key at {url}")

    fred_key = _key("FRED API Key",      "FRED_KEY", "fred.stlouisfed.org/docs/api/api_key.html")
    av_key   = _key("Alpha Vantage Key", "AV_KEY",   "alphavantage.co/support/#api-key")
    news_key = _key("NewsAPI Key",       "NEWS_KEY", "newsapi.org/register")

    st.markdown("<div class='sh'>⚙ Global Controls</div>", unsafe_allow_html=True)
    period_map   = {"1 Month":"1mo","3 Months":"3mo","6 Months":"6mo","1 Year":"1y","2 Years":"2y","5 Years":"5y"}
    period_label = st.selectbox("Price History", list(period_map.keys()), index=3)
    period       = period_map[period_label]

    bench_ticker    = st.selectbox("Primary Benchmark", list(CRUDE_TICKERS.keys()), index=0)
    bench_sym       = CRUDE_TICKERS[bench_ticker]
    compare_tickers = st.multiselect(
        "Compare With",
        [k for k in CRUDE_TICKERS if k != bench_ticker],
        default=["Brent Crude (BZ=F)", "Natural Gas (NG=F)"],
    )
    compare_syms = [CRUDE_TICKERS[k] for k in compare_tickers]

    st.markdown("<div class='sh'>📐 Analysis Params</div>", unsafe_allow_html=True)
    vol_window  = st.slider("Volatility Window (days)", 10, 60, 30)
    fast_ma     = st.slider("Fast MA (days)", 5, 50, 20)
    slow_ma     = st.slider("Slow MA (days)", 20, 200, 50)
    corr_window = st.slider("Correlation Window (days)", 20, 120, 60)

    st.markdown("<div class='sh'>📰 News Filter</div>", unsafe_allow_html=True)
    news_query = st.text_input("Search terms", "oil gas OPEC crude energy")
    news_days  = st.slider("Days back", 7, 90, 30)

    st.markdown("---")
    st.markdown("""
    <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#1a2a40;text-align:center;'>
        YAHOO FINANCE · NO KEY REQUIRED<br>FRED · AV · NEWSAPI · FREE TIERS<br>
        CACHE: 5min PRICES · 1hr MACRO
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
      <div style='display:flex;align-items:center;gap:14px;'>
        <div style='font-size:2.6rem;line-height:1;'>🛢️</div>
        <div>
          <div class='hero-title'>Global Oil & Gas — Research Dashboard</div>
          <div class='hero-sub'>Live data · Multi-source · {datetime.today().strftime('%d %b %Y %H:%M')} UTC</div>
          <div>
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
 tab_macro, tab_av, tab_map, tab_news) = st.tabs([
    "📈 Price & OHLCV", "📊 Volatility", "🔗 Correlations", "⚙️ Backtesting",
    "🌍 Macro & FRED",  "🛢️ AV Commodities", "🗺️ Field Map", "📰 Geopolitical",
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
    st.markdown("<div class='sh'>Rolling Volatility Analysis</div>", unsafe_allow_html=True)

    if bench_res["ok"]:
        bdf   = bench_res["df"]
        prov_tag(bench_res)
        stats = compute_rolling_stats(bdf["Close"], window=vol_window)
        dd    = compute_drawdown(bdf["Close"])

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
        rets = bdf["Close"].pct_change().dropna() * 100
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

        st.dataframe(pd.DataFrame({
            "Metric": ["Mean Daily Return","Std Dev","Skewness","Kurtosis","Best Day","Worst Day","Ann. Volatility"],
            "Value":  [f"{rets.mean():.3f}%", f"{rets.std():.3f}%", f"{rets.skew():.3f}",
                       f"{rets.kurt():.3f}", f"{rets.max():+.2f}%", f"{rets.min():+.2f}%",
                       f"{rets.std()*np.sqrt(252):.2f}%"],
        }), use_container_width=True, hide_index=True)
        dl_button(rets.reset_index().rename(columns={"Close": "daily_return_pct"}), f"{bench_sym}_returns.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 3 · CORRELATIONS                       ║
# ╚══════════════════════════════════════════════╝
with tab_corr:
    st.markdown("<div class='sh'>Cross-Asset Correlation</div>", unsafe_allow_html=True)
    all_syms   = [bench_sym] + compare_syms
    all_labels = [bench_ticker] + compare_tickers

    if len(all_syms) < 2:
        st.info("Select at least one comparison ticker in the sidebar.")
    else:
        with st.spinner("Fetching correlation data…"):
            multi_res = fetch_yf_multi(all_syms, period=period)
        if multi_res["ok"]:
            prov_tag(multi_res)
            mdf      = multi_res["df"].rename(columns=dict(zip(all_syms, all_labels))).dropna(how="all")
            corr_mat = compute_correlation_matrix(mdf)

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
            err_box(multi_res.get("error", ""))

# ╔══════════════════════════════════════════════╗
# ║  TAB 4 · BACKTESTING                        ║
# ╚══════════════════════════════════════════════╝
with tab_bt:
    st.markdown("<div class='sh'>MA Crossover Strategy Backtest</div>", unsafe_allow_html=True)
    st.markdown("""<div class='info-box'>
    <b>Strategy:</b> Long when Fast MA &gt; Slow MA · Short when Fast MA &lt; Slow MA.
    Signal lagged 1 day — no lookahead bias. Transaction costs not included.
    </div>""", unsafe_allow_html=True)

    if bench_res["ok"]:
        prov_tag(bench_res)
        bdf = bench_res["df"]
        bt  = backtest_ma_crossover(bdf["Close"], fast=fast_ma, slow=slow_ma)

        strat_total   = bt["cum_strategy"].iloc[-1] - 100
        bench_total   = bt["cum_benchmark"].iloc[-1] - 100
        strat_ann_vol = bt["strategy_ret"].std() * np.sqrt(252) * 100
        sharpe        = (bt["strategy_ret"].mean() / bt["strategy_ret"].std()) * np.sqrt(252) \
                        if bt["strategy_ret"].std() > 0 else 0
        max_dd        = bt["drawdown"].min()
        num_trades    = int((bt["signal"].diff().abs() > 0).sum())

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
    else:
        err_box(bench_res.get("error", ""))

# ╔══════════════════════════════════════════════╗
# ║  TAB 5 · MACRO & FRED                       ║
# ╚══════════════════════════════════════════════╝
with tab_macro:
    st.markdown("<div class='sh'>Macroeconomic Indicators — FRED</div>", unsafe_allow_html=True)

    if not fred_key:
        st.markdown("""<div class='info-box'>
        Enter your <b>FRED API key</b> in the sidebar.<br>
        Free key: <a href='https://fred.stlouisfed.org/docs/api/api_key.html' style='color:#e8a020;'>fred.stlouisfed.org</a>
        </div>""", unsafe_allow_html=True)
    else:
        selected_fred = st.multiselect("Select FRED Series", list(FRED_SERIES.keys()),
                                       default=["US CPI (Energy)","Fed Funds Rate","US Dollar Index (DXY)","10Y Treasury Yield"])
        if selected_fred:
            with st.spinner("Fetching FRED data…"):
                fred_res = fetch_fred_multi([FRED_SERIES[k] for k in selected_fred], fred_key)
            if fred_res["ok"]:
                prov_tag(fred_res)
                fdf = fred_res["df"].rename(columns={v:k for k,v in FRED_SERIES.items()})
                if fred_res.get("errors"):
                    err_box("Some series failed: " + "; ".join(fred_res["errors"]))
                for i, col in enumerate(fdf.columns):
                    series = fdf[col].dropna()
                    if series.empty:
                        continue
                    c = COLORS[i % len(COLORS)]
                    sf = go.Figure()
                    sf.add_trace(go.Scatter(x=series.index, y=series, name=col,
                                            line=dict(color=c, width=1.6),
                                            fill="tozeroy", fillcolor=rgba(c, 0.07)))
                    apply_theme(sf, col, height=220, margin=dict(l=60,r=20,t=36,b=30))
                    st.plotly_chart(sf, use_container_width=True)

                if bench_res["ok"]:
                    st.markdown("<div class='sh'>Macro vs Commodity Price Correlation</div>", unsafe_allow_html=True)
                    price_m = bench_res["df"]["Close"].resample("ME").last().rename(bench_ticker)
                    joined  = fdf.join(price_m, how="inner").dropna(how="all")
                    if not joined.empty:
                        mc = joined.pct_change().dropna().corr()
                        mf = go.Figure(go.Heatmap(
                            z=mc.values, x=mc.columns.tolist(), y=mc.index.tolist(),
                            colorscale=[[0,"#0d2040"],[0.5,"#1a4080"],[1,"#e8a020"]],
                            zmin=-1, zmax=1,
                            text=mc.round(2).astype(str).values, texttemplate="%{text}", showscale=True,
                        ))
                        apply_theme(mf, "Macro × Commodity Correlation (monthly returns)", height=420, margin=dict(l=120,r=20,t=40,b=100))
                        mf.update_xaxes(tickangle=-30, tickfont=dict(size=8))
                        mf.update_yaxes(tickfont=dict(size=8))
                        st.plotly_chart(mf, use_container_width=True)
                dl_button(fdf.reset_index(), "fred_macro_data.csv")
            else:
                err_box(fred_res.get("error", ""))

# ╔══════════════════════════════════════════════╗
# ║  TAB 6 · ALPHA VANTAGE COMMODITIES          ║
# ╚══════════════════════════════════════════════╝
with tab_av:
    st.markdown("<div class='sh'>Commodity Price Series — Alpha Vantage</div>", unsafe_allow_html=True)

    if not av_key:
        st.markdown("""<div class='info-box'>
        Enter your <b>Alpha Vantage API key</b> in the sidebar.<br>
        Free key: <a href='https://www.alphavantage.co/support/#api-key' style='color:#e8a020;'>alphavantage.co</a>
        </div>""", unsafe_allow_html=True)
    else:
        selected_av = st.multiselect("Select Commodities", list(ALPHA_SERIES.keys()),
                                     default=["Brent Crude (Monthly)","Natural Gas (Monthly)"])
        if selected_av:
            frames = []
            for label in selected_av:
                func, interval = ALPHA_SERIES[label]
                with st.spinner(f"Fetching {label}…"):
                    res = fetch_alpha_commodity(func, interval, av_key)
                if res["ok"]:
                    prov_tag(res)
                    frames.append(res["df"].rename(columns={func: label}))
                else:
                    err_box(f"{label}: {res.get('error','')}")
            if frames:
                av_df = pd.concat(frames, axis=1).sort_index()
                fig_av = go.Figure()
                for i, col in enumerate(av_df.columns):
                    fig_av.add_trace(go.Scatter(x=av_df.index, y=av_df[col], name=col,
                                                line=dict(color=COLORS[i % len(COLORS)], width=1.8)))
                apply_theme(fig_av, "Alpha Vantage — Commodity Prices (Monthly)", height=380)
                st.plotly_chart(fig_av, use_container_width=True)

                yoy = av_df.pct_change(12) * 100
                fig_yoy = go.Figure()
                for i, col in enumerate(yoy.columns):
                    fig_yoy.add_trace(go.Scatter(x=yoy.index, y=yoy[col], name=col,
                                                 line=dict(color=COLORS[i % len(COLORS)], width=1.6)))
                fig_yoy.add_hline(y=0, line_dash="dot", line_color=rgba(PALETTE["white"], 0.15))
                apply_theme(fig_yoy, "Year-on-Year Change (%)", height=300)
                st.plotly_chart(fig_yoy, use_container_width=True)
                dl_button(av_df.reset_index(), "alpha_vantage_commodities.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 7 · FIELD MAP                          ║
# ╚══════════════════════════════════════════════╝
with tab_map:
    st.markdown("<div class='sh'>Major Global Oil & Gas Fields</div>", unsafe_allow_html=True)

    m1, m2 = st.columns([2,1])
    with m1:
        ftype_filter = st.radio("Field type", ["All","Crude","Natural Gas","LNG"], horizontal=True)
    with m2:
        proj = st.selectbox("Projection", ["natural earth","orthographic","equirectangular","mercator"])

    fdf = FIELDS_DF if ftype_filter == "All" else FIELDS_DF[FIELDS_DF["Type"] == ftype_filter]
    color_map  = {"Crude":"#e8a020","Natural Gas":"#f06060","LNG":"#40c8b0"}
    symbol_map = {"Crude":"circle","Natural Gas":"diamond","LNG":"star"}

    map_fig = go.Figure()
    for ftype, grp in fdf.groupby("Type"):
        map_fig.add_trace(go.Scattergeo(
            lat=grp["Lat"], lon=grp["Lon"],
            mode="markers+text", text=grp["Field"],
            textposition="top center",
            textfont=dict(size=8, color="rgba(220,220,220,0.6)", family="Space Mono"),
            marker=dict(
                size=np.clip(grp["Reserves"].values / 15 + 8, 8, 40),
                color=color_map[ftype], symbol=symbol_map[ftype], opacity=0.85,
                line=dict(width=1, color="rgba(255,255,255,0.2)"),
            ),
            name=ftype,
            hovertemplate="<b>%{text}</b><br>Reserves: %{customdata[0]:,} Gboe/Bcm<br>Country: %{customdata[1]}<br>Status: %{customdata[2]}<extra></extra>",
            customdata=grp[["Reserves","Country","Status"]].values,
        ))
    map_fig.update_layout(
        geo=dict(projection_type=proj, showland=True, landcolor="#111e30",
                 showocean=True, oceancolor="#07090f",
                 showcountries=True, countrycolor="#1b2d4f",
                 showlakes=False, bgcolor="#07090f"),
        paper_bgcolor="#07090f",
        font=dict(color="#6080a8", family="Space Mono, monospace", size=10),
        legend=dict(bgcolor="rgba(7,9,15,0.8)", bordercolor="#1b2d4f", borderwidth=1),
        margin=dict(l=0,r=0,t=30,b=0), height=540,
        title=dict(text="Major Oil & Gas Fields — bubble size ∝ reserves", font=dict(color="#c8a060", size=12)),
    )
    st.plotly_chart(map_fig, use_container_width=True)
    st.dataframe(fdf.rename(columns={"Reserves":"Reserves (Gboe/Bcm)"}), use_container_width=True, hide_index=True)
    dl_button(fdf, "global_fields.csv")

# ╔══════════════════════════════════════════════╗
# ║  TAB 8 · GEOPOLITICAL NEWS                  ║
# ╚══════════════════════════════════════════════╝
with tab_news:
    st.markdown("<div class='sh'>Geopolitical & Market News</div>", unsafe_allow_html=True)

    if not news_key:
        st.markdown("""<div class='info-box'>
        Enter your <b>NewsAPI key</b> in the sidebar for live articles.<br>
        Free key (100 req/day): <a href='https://newsapi.org/register' style='color:#e8a020;'>newsapi.org</a>
        </div>""", unsafe_allow_html=True)
        st.markdown("<div class='sh'>Key Geopolitical Events — Oil Price Impact</div>", unsafe_allow_html=True)
        for date, desc, dot in GEO_EVENTS:
            st.markdown(f"""
            <div class='news-card'>
                <div class='news-title'>{dot} {desc}</div>
                <div class='news-meta'>📅 {date} · Geopolitical Event Log</div>
            </div>""", unsafe_allow_html=True)
    else:
        with st.spinner("Fetching energy news…"):
            news_res = fetch_news(news_key, query=news_query, days_back=news_days)
        if news_res["ok"]:
            st.markdown(
                f"<div class='prov'>▸ {news_res['source']} · {news_res['fetched_at']} · {news_res['count']} articles</div>",
                unsafe_allow_html=True,
            )
            if bench_res["ok"]:
                bdf        = bench_res["df"]
                news_dates = list({a["date"] for a in news_res["articles"] if a["date"]})
                fig_n = go.Figure()
                fig_n.add_trace(go.Scatter(x=bdf.index, y=bdf["Close"], name="Price",
                                           line=dict(color=PALETTE["WTI"], width=1.8)))
                for date_str in news_dates:
                    try:
                        idx = bdf.index.asof(pd.to_datetime(date_str))
                        if pd.notna(idx) and idx in bdf.index:
                            fig_n.add_vline(x=idx, line_color=rgba(PALETTE["NatGas"], 0.25),
                                            line_width=1, line_dash="dot")
                    except Exception:
                        pass
                apply_theme(fig_n, f"{bench_ticker} with News Event Markers", height=280)
                st.plotly_chart(fig_n, use_container_width=True)

            st.markdown("<div class='sh'>Latest Articles</div>", unsafe_allow_html=True)
            for a in news_res["articles"][:30]:
                url_html = f"<a href='{a['url']}' style='color:#e8a020;font-size:0.6rem;'>↗ Read</a>" if a.get("url") else ""
                st.markdown(f"""
                <div class='news-card'>
                    <div class='news-title'>{a.get('title','')}</div>
                    <div class='news-meta'>📅 {a.get('date','')} · 📰 {a.get('source','')} &nbsp; {url_html}</div>
                    <div class='news-desc'>{a.get('description','')}</div>
                </div>""", unsafe_allow_html=True)
        else:
            err_box(news_res.get("error", ""))
            st.info("Could not fetch live news. Check your API key or query terms.")

# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style='text-align:center;font-family:Space Mono,monospace;font-size:0.58rem;color:#1a2a40;padding:8px 0;'>
    DATA SOURCES: Yahoo Finance · FRED (St. Louis Fed) · Alpha Vantage · NewsAPI<br>
    Yahoo Finance requires no key · FRED / AV / News require free-tier registration<br>
    Prices delayed ~15 min · Macro updated daily · News cached 30 min<br>
    Last render: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</div>
""", unsafe_allow_html=True)
