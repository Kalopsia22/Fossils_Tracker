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
def fetch_macro_yf(tickers: list, period: str = "5y") -> dict:
    """Fetch macro indicators from Yahoo Finance — no key, no blocked domains."""
    try:
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
        if raw.empty:
            return {"ok": False, "error": "No data returned", "df": pd.DataFrame()}
        df = raw["Close"].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) \
             else raw[["Close"]].rename(columns={"Close": tickers[0]})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return {
            "ok": True, "df": df,
            "source": "Yahoo Finance (no key required)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(df),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_commodity_history(tickers: list, period: str = "5y") -> dict:
    """Fetch multi-commodity price history via Yahoo Finance — no key needed."""
    try:
        raw = yf.download(tickers, period=period, auto_adjust=True, progress=False)
        if raw.empty:
            return {"ok": False, "error": "No data returned", "df": pd.DataFrame()}
        df = raw["Close"].dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) \
             else raw[["Close"]].rename(columns={"Close": tickers[0]})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        # Rename columns to friendly labels
        label_map = {v: k for k, v in COMMODITY_TICKERS.items()}
        df = df.rename(columns=label_map)
        return {
            "ok": True, "df": df,
            "source": "Yahoo Finance (no key required)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "rows": len(df),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame()}


# ── NASA FIRMS — live fire / gas flaring detection ───────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nasa_firms(lat: float, lon: float, radius_km: int = 50) -> dict:
    """
    Query NASA FIRMS (Fire Information for Resource Management System).
    Uses the public CSV endpoint — no API key required.
    Returns recent thermal anomalies within radius_km of a facility.
    """
    try:
        # FIRMS public CSV: last 7 days, VIIRS S-NPP 375m sensor
        url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/c6b4a8e9d3f7e2a1b5c9d2e4f6a8b0c2/VIIRS_SNPP_NRT"
        # bbox: lon-r, lat-r, lon+r, lat+r  (approx 1 deg ≈ 111 km)
        deg = radius_km / 111.0
        bbox = f"{lon-deg:.3f},{lat-deg:.3f},{lon+deg:.3f},{lat+deg:.3f}"
        r = requests.get(f"{url}/{bbox}/7", timeout=10,
                         headers={"User-Agent": "OilGasResearchDashboard/1.0"})
        if r.status_code != 200 or not r.text.strip():
            return {"ok": False, "error": f"HTTP {r.status_code}", "df": pd.DataFrame(), "count": 0}
        from io import StringIO
        df = pd.read_csv(StringIO(r.text))
        if df.empty or "latitude" not in df.columns:
            return {"ok": True, "df": pd.DataFrame(), "count": 0,
                    "source": "NASA FIRMS VIIRS S-NPP",
                    "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
        df = df[["latitude","longitude","bright_ti4","frp","acq_date","acq_time","confidence"]].copy()
        df["bright_ti4"] = pd.to_numeric(df["bright_ti4"], errors="coerce")
        df["frp"]        = pd.to_numeric(df["frp"],        errors="coerce")
        return {
            "ok": True, "df": df, "count": len(df),
            "source": "NASA FIRMS VIIRS S-NPP NRT (7-day)",
            "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "df": pd.DataFrame(), "count": 0}


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


# ── Sentinel Hub EO Browser iframe URL builder ────────────────
def sentinel_hub_url(lat: float, lon: float, zoom: int = 13) -> str:
    """
    Build a Sentinel Hub EO Browser URL for recent true-colour imagery.
    Opens as an iframe — no API key needed for the browser view.
    """
    return (
        f"https://apps.sentinel-hub.com/eo-browser/"
        f"?zoom={zoom}&lat={lat:.4f}&lng={lon:.4f}"
        f"&themeId=DEFAULT-THEME"
        f"&visualizationUrl=https%3A%2F%2Fservices.sentinel-hub.com%2Fogc%2Fwms%2Fbd86bcc0-f318-402b-a145-015f85b9427e"
        f"&datasetId=S2L2A&fromTime=2024-01-01T00%3A00%3A00.000Z"
        f"&toTime={datetime.utcnow().strftime('%Y-%m-%dT%H%%3A%M%%3A%S')}.000Z"
        f"&layerId=1_TRUE_COLOR"
    )


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

    st.markdown("---")
    st.markdown("""
    <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#1a2a40;text-align:center;'>
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
    "🌍 Macro & FRED",  "📦 Commodities", "🏭 Facility Map", "📰 Geopolitical",
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
                    st.markdown(f"<div style='font-family:Space Mono,monospace;font-size:0.58rem;color:#3a5a88;margin-top:4px;'>{desc}</div>",
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
    <div style='display:flex;gap:20px;flex-wrap:wrap;font-family:Space Mono,monospace;font-size:0.6rem;color:#4a6fa5;padding:6px 0 14px;'>
        <span><span style='color:#40b860'>●</span> Refinery — Operational</span>
        <span><span style='color:#e8a020'>●</span> Refinery — Commissioning</span>
        <span><span style='color:#f06060'>●</span> Refinery — Partial</span>
        <span><span style='color:#a060e8'>●</span> Refinery — Reduced</span>
        <span><span style='color:#60a8e8'>■</span> Storage Terminal</span>
        <span><span style='color:#a060e8'>■</span> Strategic Reserve (SPR)</span>
        <span>── Pipeline (color = product type) &nbsp; bubble size = capacity</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Facility Intelligence Panel ──────────────────────────────────────────
    st.markdown("<div class='sh'>Facility Intelligence Panel</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='info-box'>
    Select a facility below to open a live intelligence panel — NASA FIRMS flaring detection,
    real-time weather, Sentinel-2 satellite imagery, and AIS vessel tracking.
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
            <div style='font-family:Syne,sans-serif;font-weight:800;font-size:1.3rem;
                        color:#e8dfc8;'>{dot} {selected_fac}</div>
            <div style='font-family:Space Mono,monospace;font-size:0.62rem;color:#3a5a88;
                        margin:4px 0 10px;'>{fac_row["Country"]} · {fac_row["Region"]} · {fac_type}</div>
            <div style='font-size:0.82rem;color:#8aaccc;'>
                <b style='color:#c8a060;'>Operator</b>&nbsp; {fac_row["Operator"]} &nbsp;·&nbsp;
                <b style='color:#c8a060;'>Details</b>&nbsp; {fac_row["Detail"]} &nbsp;·&nbsp;
                <b style='color:#c8a060;'>Coords</b>&nbsp;
                <span style='font-family:Space Mono,monospace;font-size:0.72rem;'>
                {fac_lat:.4f}°, {fac_lon:.4f}°</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ════════════════════════════════════════════
        # PANEL COLUMNS: left = data, right = visuals
        # ════════════════════════════════════════════
        left_col, right_col = st.columns([1, 1], gap="large")

        # ── LEFT: Weather + NASA FIRMS ───────────────────────────
        with left_col:

            # ── Live Weather ────────────────────────────────────
            st.markdown("<div class='sh'>🌤 Live Weather — Open-Meteo</div>", unsafe_allow_html=True)
            with st.spinner("Fetching weather…"):
                wx = fetch_weather(fac_lat, fac_lon)

            if wx.get("ok"):
                st.markdown(f"""
                <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                            padding:16px 18px;margin-bottom:12px;'>
                    <div style='font-size:2rem;font-weight:800;color:#e8dfc8;font-family:Syne,sans-serif;'>
                        {wx["temp_c"]:.1f}°C
                        <span style='font-size:0.9rem;color:#6080a8;font-weight:400;'>{wx["condition"]}</span>
                    </div>
                    <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;
                                font-family:Space Mono,monospace;font-size:0.65rem;color:#8aaccc;'>
                        <div><span style='color:#c8a060;'>WIND</span><br>
                             {wx["wind_kmh"]:.0f} km/h @ {wx["wind_dir"]:.0f}°</div>
                        <div><span style='color:#c8a060;'>HUMIDITY</span><br>{wx["humidity"]}%</div>
                        <div><span style='color:#c8a060;'>PRESSURE</span><br>{wx["pressure"]:.0f} hPa</div>
                        <div><span style='color:#c8a060;'>VISIBILITY</span><br>
                             {wx["visibility"]/1000:.1f} km</div>
                    </div>
                </div>
                <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#2a4060;'>
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

            # ── NASA FIRMS Thermal Anomalies ─────────────────────
            st.markdown("<div class='sh'>🔥 NASA FIRMS — Thermal Anomaly Detection</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:Space Mono,monospace;font-size:0.58rem;color:#3a5a88;"
                "margin-bottom:8px;'>VIIRS S-NPP 375m · Last 7 days · ~50km radius</div>",
                unsafe_allow_html=True,
            )
            with st.spinner("Querying NASA FIRMS…"):
                firms = fetch_nasa_firms(fac_lat, fac_lon, radius_km=50)

            if firms.get("ok"):
                if firms["count"] == 0:
                    st.markdown("""
                    <div style='background:#0d1a0d;border:1px solid #1b3a1b;border-radius:8px;
                                padding:14px;font-family:Space Mono,monospace;font-size:0.7rem;
                                color:#40b860;'>
                        ✓ No thermal anomalies detected in last 7 days within 50 km.<br>
                        Normal flaring / operational baseline.
                    </div>""", unsafe_allow_html=True)
                else:
                    df_f = firms["df"]
                    avg_frp  = df_f["frp"].mean()
                    max_frp  = df_f["frp"].max()
                    severity = "🔴 HIGH" if max_frp > 500 else ("🟡 MODERATE" if max_frp > 100 else "🟢 LOW")
                    st.markdown(f"""
                    <div style='background:#1a0d08;border:1px solid #3a2010;border-radius:8px;
                                padding:14px;margin-bottom:10px;'>
                        <div style='font-family:Syne,sans-serif;font-weight:700;font-size:0.95rem;
                                    color:#f06060;'>{firms["count"]} thermal anomalies detected</div>
                        <div style='font-family:Space Mono,monospace;font-size:0.62rem;color:#a08060;
                                    margin-top:6px;'>
                            Severity: {severity}<br>
                            Avg FRP: {avg_frp:.1f} MW &nbsp;·&nbsp; Peak FRP: {max_frp:.1f} MW<br>
                            Dates: {df_f["acq_date"].min()} → {df_f["acq_date"].max()}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    # Mini map of hotspots relative to facility
                    fig_firms = go.Figure()
                    fig_firms.add_trace(go.Scattergeo(
                        lat=[fac_lat], lon=[fac_lon],
                        mode="markers", marker=dict(size=14, color="#e8a020",
                                                    symbol="star", opacity=1),
                        name="Facility",
                    ))
                    fig_firms.add_trace(go.Scattergeo(
                        lat=df_f["latitude"], lon=df_f["longitude"],
                        mode="markers",
                        marker=dict(
                            size=np.clip(df_f["frp"].fillna(10) / 20 + 5, 5, 20),
                            color=df_f["frp"].fillna(0),
                            colorscale=[[0,"#ff6b6b"],[0.5,"#ff0000"],[1,"#ffffff"]],
                            opacity=0.85,
                            showscale=True,
                            colorbar=dict(title="FRP (MW)", thickness=10,
                                          titlefont=dict(size=9), tickfont=dict(size=8)),
                        ),
                        name="Thermal anomaly",
                        hovertemplate="FRP: %{marker.color:.0f} MW<br>%{lat:.3f}, %{lon:.3f}<extra></extra>",
                    ))
                    deg = 0.6
                    fig_firms.update_layout(
                        geo=dict(
                            projection_type="mercator",
                            showland=True, landcolor="#0d1825",
                            showocean=True, oceancolor="#07090f",
                            showcountries=True, countrycolor="#1b2d4f",
                            bgcolor="#07090f",
                            lonaxis=dict(range=[fac_lon-deg, fac_lon+deg]),
                            lataxis=dict(range=[fac_lat-deg, fac_lat+deg]),
                        ),
                        paper_bgcolor="#07090f",
                        font=dict(color="#6080a8", family="Space Mono,monospace", size=9),
                        margin=dict(l=0, r=0, t=0, b=0), height=280,
                        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9)),
                    )
                    st.plotly_chart(fig_firms, use_container_width=True)
                    st.dataframe(
                        df_f[["acq_date","acq_time","frp","bright_ti4","confidence"]].rename(columns={
                            "acq_date":"Date","acq_time":"Time (UTC)",
                            "frp":"FRP (MW)","bright_ti4":"Brightness (K)","confidence":"Confidence",
                        }).sort_values("FRP (MW)", ascending=False).head(10),
                        use_container_width=True, hide_index=True,
                    )
                st.markdown(
                    f"<div class='prov'>▸ {firms['source']} · {firms['fetched_at']}</div>",
                    unsafe_allow_html=True,
                )
            else:
                err_box(f"NASA FIRMS: {firms.get('error','')}")
                st.markdown("""
                <div class='info-box'>NASA FIRMS may be temporarily unavailable or the
                domain may be restricted on this deployment. Try again shortly.</div>""",
                unsafe_allow_html=True)

        # ── RIGHT: Sentinel Hub + AIS ────────────────────────────
        with right_col:

            # ── Sentinel Hub Satellite Imagery ───────────────────
            st.markdown("<div class='sh'>🛰 Sentinel-2 Satellite Imagery</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:Space Mono,monospace;font-size:0.58rem;color:#3a5a88;"
                "margin-bottom:8px;'>ESA Copernicus · 10m resolution · ~5 day revisit · "
                "True colour composite — opens interactive viewer</div>",
                unsafe_allow_html=True,
            )
            sat_zoom = st.slider("Satellite zoom", 10, 16, 13, key="sat_zoom")
            sentinel_url = sentinel_hub_url(fac_lat, fac_lon, zoom=sat_zoom)

            st.markdown(f"""
            <div style='border:1px solid #1b2d4f;border-radius:8px;overflow:hidden;
                        margin-bottom:6px;'>
                <iframe src="{sentinel_url}"
                    width="100%" height="420"
                    style="border:none;display:block;"
                    loading="lazy"
                    title="Sentinel-2 imagery — {selected_fac}">
                </iframe>
            </div>
            <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#2a4060;
                        margin-bottom:16px;'>
                ▸ Sentinel Hub EO Browser · ESA Copernicus Programme · No key required
                · <a href="{sentinel_url}" target="_blank"
                style='color:#e8a020;'>Open full screen ↗</a>
            </div>""", unsafe_allow_html=True)

            # ── AIS Vessel Tracking ──────────────────────────────
            st.markdown("<div class='sh'>🚢 AIS Live Vessel Tracking — MarineTraffic</div>",
                        unsafe_allow_html=True)
            st.markdown(
                "<div style='font-family:Space Mono,monospace;font-size:0.58rem;color:#3a5a88;"
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
                    width="100%" height="420"
                    style="border:none;display:block;"
                    loading="lazy"
                    title="AIS vessel tracking — {selected_fac}">
                </iframe>
            </div>
            <div style='font-family:Space Mono,monospace;font-size:0.55rem;color:#2a4060;'>
                ▸ MarineTraffic AIS · IMO/MMSI broadcast data ·
                <a href="https://www.marinetraffic.com/en/ais/home/centerx:{fac_lon:.3f}/centery:{fac_lat:.3f}/zoom:{ais_zoom}"
                target="_blank" style='color:#e8a020;'>Open full screen ↗</a>
            </div>""", unsafe_allow_html=True)

    # ── Facility Detail Cards (collapsed) ────────────────────────────────────
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

            STATUS_DOT = {"Operational":"🟢","Commissioning":"🟡","Partial":"🟠","Reduced":"🔴"}
            cols_per_row = 3
            for row_start in range(0, len(card_df), cols_per_row):
                cols = st.columns(cols_per_row)
                for ci, (_, row) in enumerate(card_df.iloc[row_start:row_start+cols_per_row].iterrows()):
                    dot = STATUS_DOT.get(row["Status"], "⚪")
                    with cols[ci]:
                        st.markdown(f"""
                        <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                                    padding:14px 16px;margin-bottom:10px;min-height:160px;'>
                            <div style='font-family:Syne,sans-serif;font-weight:700;font-size:0.88rem;
                                        color:#dde3ee;margin-bottom:6px;'>{dot} {row["Name"]}</div>
                            <div style='font-family:Space Mono,monospace;font-size:0.6rem;color:#3a5a88;margin-bottom:8px;'>
                                {row["Country"]} · {row["Region"]}
                            </div>
                            <div style='font-size:0.78rem;color:#8aaccc;line-height:1.7;'>
                                <b style='color:#c8a060;'>Operator</b> {row["Operator"]}<br>
                                <b style='color:#c8a060;'>Capacity</b> {row["Capacity_kbd"]:,} kb/d<br>
                                <b style='color:#c8a060;'>Crude Type</b> {row["Crude"]}<br>
                                <b style='color:#c8a060;'>Status</b> {row["Status"]}
                            </div>
                        </div>""", unsafe_allow_html=True)
            dl_button(card_df, "refineries_global.csv")

        with card_tab2:
            stor_region = st.selectbox("Region", ["All"] + sorted(STORAGE["Region"].unique()), key="stor_reg")
            stor_df = STORAGE if stor_region == "All" else STORAGE[STORAGE["Region"] == stor_region]
            stor_df = stor_df.sort_values("Capacity_MMbbl", ascending=False)
            cols_per_row = 3
            for row_start in range(0, len(stor_df), cols_per_row):
                cols = st.columns(cols_per_row)
                for ci, (_, row) in enumerate(stor_df.iloc[row_start:row_start+cols_per_row].iterrows()):
                    stype_icon = "🛡️" if row["Type"] == "SPR" else "🗄️"
                    with cols[ci]:
                        st.markdown(f"""
                        <div style='background:#0d1220;border:1px solid #1b2d4f;border-radius:8px;
                                    padding:14px 16px;margin-bottom:10px;min-height:150px;'>
                            <div style='font-family:Syne,sans-serif;font-weight:700;font-size:0.88rem;
                                        color:#dde3ee;margin-bottom:6px;'>{stype_icon} {row["Name"]}</div>
                            <div style='font-family:Space Mono,monospace;font-size:0.6rem;color:#3a5a88;margin-bottom:8px;'>
                                {row["Country"]} · {row["Type"]}
                            </div>
                            <div style='font-size:0.78rem;color:#8aaccc;line-height:1.7;'>
                                <b style='color:#c8a060;'>Operator</b> {row["Operator"]}<br>
                                <b style='color:#c8a060;'>Capacity</b> {row["Capacity_MMbbl"]:,} MMbbl<br>
                                <b style='color:#c8a060;'>Product</b> {row["Product"]}<br>
                                <b style='color:#c8a060;'>Status</b> {row["Status"]}
                            </div>
                        </div>""", unsafe_allow_html=True)
            dl_button(stor_df, "storage_terminals_global.csv")

    # ── Summary stats ────────────────────────────────────────────────────────
    st.markdown("<div class='sh'>Global Capacity Summary</div>", unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Total Refineries",       f"{len(ref_filt)}",                               "in current filter")
    s2.metric("Total Refining Capacity",f"{ref_filt['Capacity_kbd'].sum():,} kb/d",       f"{ref_filt['Capacity_kbd'].sum()/1000:.1f} Mb/d")
    s3.metric("Storage Terminals",      f"{len(stor_filt)}",                              "in current filter")
    s4.metric("Total Storage Capacity", f"{stor_filt['Capacity_MMbbl'].sum():,} MMbbl",   "strategic + commercial")

# ╔══════════════════════════════════════════════╗
# ║  TAB 8 · GEOPOLITICAL NEWS                  ║
# ╚══════════════════════════════════════════════╝
# ╔══════════════════════════════════════════════╗
# ║  TAB 8 · GEOPOLITICAL (Live RSS)            ║
# ╚══════════════════════════════════════════════╝
with tab_news:
    st.markdown("<div class='sh'>Live Energy & Geopolitical News</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='prov'>▸ Reuters · BBC · Al Jazeera · OilPrice.com · Rigzone · No API key · Cached 15 min</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Fetching live news feeds…"):
        news_res = fetch_rss_news()

    # ── Feed health status ───────────────────────────────────────
    if news_res.get("sources_ok") or news_res.get("sources_fail"):
        health_parts = []
        for s in news_res.get("sources_ok", []):
            health_parts.append(f"<span style='color:#40b860'>✓ {s}</span>")
        for s in news_res.get("sources_fail", []):
            short = s.split(":")[0]
            health_parts.append(f"<span style='color:#e05050'>✗ {short}</span>")
        st.markdown(
            "<div style='font-family:Space Mono,monospace;font-size:0.58rem;margin-bottom:10px;'>"
            + " &nbsp;·&nbsp; ".join(health_parts) + "</div>",
            unsafe_allow_html=True,
        )

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
            # Pin one vline per unique date that has news
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
        all_sources = sorted({a["source"] for a in articles})
        n1, n2 = st.columns([3, 1])
        with n1:
            src_filter = st.multiselect("Filter by source", all_sources, default=all_sources)
        with n2:
            n_show = st.slider("Articles to show", 5, 50, 20)

        filtered = [a for a in articles if a["source"] in src_filter][:n_show]

        # ── Article cards ────────────────────────────────────────
        st.markdown(
            f"<div class='prov'>Showing {len(filtered)} of {len(articles)} energy articles · "
            f"fetched {news_res.get('fetched_at','')}</div>",
            unsafe_allow_html=True,
        )
        for a in filtered:
            url_html = (
                f"<a href='{a['url']}' target='_blank' style='color:#e8a020;font-size:0.6rem;'>↗ Read full article</a>"
                if a.get("url") else ""
            )
            st.markdown(f"""
            <div class='news-card'>
                <div class='news-title'>{a.get('title','')}</div>
                <div class='news-meta'>📅 {a.get('date','')} &nbsp;·&nbsp; 📰 {a.get('source','')} &nbsp; {url_html}</div>
                <div class='news-desc'>{a.get('description','')}</div>
            </div>""", unsafe_allow_html=True)

        # ── Historical event log at the bottom ───────────────────
        with st.expander("📌 Historical Geopolitical Event Log"):
            for date, desc, dot in GEO_EVENTS:
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
<div style='text-align:center;font-family:Space Mono,monospace;font-size:0.58rem;color:#1a2a40;padding:8px 0;'>
    DATA SOURCES: Yahoo Finance — prices, yields, FX, volatility, ETFs · RSS: Reuters · BBC · Al Jazeera · OilPrice · Rigzone<br>
    100% keyless — no API registration, no blocked domains · Prices ~15 min delayed · News cached 15 min<br>
    Last render: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
</div>
""", unsafe_allow_html=True)
