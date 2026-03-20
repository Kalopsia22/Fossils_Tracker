# 🛢️ Global Oil & Gas Research Dashboard

A professional-grade, single-file Streamlit application for real-time research and analysis of global crude oil and natural gas markets. Every data source is **100% keyless** — no API registration required to run the app.

---

## Screenshot

> Deploy to Streamlit Cloud and open the app to see the full dashboard in action.

---

## Features

### 8 Research Tabs

| Tab | Description |
|---|---|
| **📈 Price & OHLCV** | Live candlestick / OHLC / line charts with volume, moving averages, and normalised multi-asset comparison |
| **📊 Volatility** | Rolling annualised volatility, drawdown series, daily return distribution, Q-Q plot, and descriptive statistics |
| **🔗 Correlations** | Pearson correlation heatmap and rolling pairwise correlation of selected assets |
| **⚙️ Backtesting** | MA crossover strategy backtest with Sharpe ratio, max drawdown, equity curve, and signal markers — no lookahead bias |
| **🌍 Macro & FRED** | Live macroeconomic indicators: yields, DXY, gold, copper, VIX, FX rates via Yahoo Finance |
| **📦 Commodities** | Multi-commodity price history, YoY returns, rolling volatility, and correlation matrix |
| **🏭 Facility Map** | Interactive global map of ~65 refineries, 18 storage terminals, and 15 pipeline corridors with facility intelligence panel |
| **📰 Geopolitical** | Live energy news aggregated from 5 RSS feeds, filtered by energy keywords, with price event overlays |

---

### Facility Intelligence Panel

Select any refinery or storage terminal from the dropdown to open a 4-tab intelligence panel:

| Panel Tab | Source | Data |
|---|---|---|
| 🌤 **Weather** | Open-Meteo | Current conditions + 24h wind & precipitation forecast |
| 🔥 **NASA FIRMS** | NASA NRT | Thermal anomaly detection (VIIRS + MODIS), 24h global, 50km radius |
| 🛰 **Satellite** | Esri World Imagery | 3×3 tile mosaic at selectable zoom, plus links to Google Maps, Esri Wayback, and Google Earth Timelapse |
| 🚢 **AIS Tracking** | MarineTraffic | Live vessel positions near the selected terminal |

---

## Data Sources

All sources are free and require no API keys or registration.

| Source | What it provides | Key required |
|---|---|---|
| **Yahoo Finance** | OHLCV futures (WTI, Brent, NatGas, Gasoline, Heating Oil), ETFs, macro indicators, FX | ❌ None |
| **NASA FIRMS** | Active fire / gas flaring NRT CSV (VIIRS S-NPP, NOAA-20, MODIS) | ❌ None |
| **Open-Meteo** | Current weather + 48h forecast at any coordinate | ❌ None |
| **Esri World Imagery** | Satellite tile imagery (ArcGIS Online public service) | ❌ None |
| **MarineTraffic** | AIS vessel tracking embed | ❌ None (embed) |
| **Reuters RSS** | Energy & business news | ❌ None |
| **BBC Business RSS** | International energy policy news | ❌ None |
| **Al Jazeera RSS** | MENA/OPEC geopolitical news | ❌ None |
| **OilPrice.com RSS** | Upstream/downstream news | ❌ None |
| **Rigzone RSS** | Drilling, production, offshore news | ❌ None |

---

## Instruments Covered

**Futures & ETFs**
- WTI Crude (CL=F), Brent Crude (BZ=F), Natural Gas (NG=F)
- RBOB Gasoline (RB=F), Heating Oil (HO=F)
- Copper (HG=F), Gold (GC=F)
- US Oil ETF (USO), Natural Gas ETF (UNG), Energy Sector ETF (XLE)

**Macro Indicators (via Yahoo Finance)**
- 10Y / 2Y / 30Y Treasury Yields (^TNX, ^IRX, ^TYX)
- US Dollar Index (DX-Y.NYB)
- S&P 500 (^GSPC), VIX (^VIX)
- EUR/USD, USD/CNY

**Facility Data (curated)**
- 65 major refineries across 7 regions with operator, capacity, crude type, and status
- 18 strategic petroleum reserves and commercial storage terminals
- 15 major pipeline corridors

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip

### Installation

```bash
# 1. Clone or download the repository
git clone https://github.com/your-username/oil-gas-dashboard.git
cd oil-gas-dashboard

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run oil_gas_research.py
```

### Dependencies

```
streamlit>=1.32.0
plotly>=5.20.0
pandas>=2.0.0
numpy>=1.26.0
requests>=2.31.0
yfinance>=0.2.36
Pillow>=10.0.0
```

---

## Deploying to Streamlit Cloud

1. Push the repository to GitHub (both `oil_gas_research.py` and `requirements.txt` in the root)
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set the main file path to `oil_gas_research.py`
4. Click **Deploy** — no secrets or environment variables needed

> **Note:** NASA FIRMS NRT CSV downloads may be blocked on some cloud networks. If this occurs, the app automatically falls back to an embedded interactive FIRMS map.

---

## Project Structure

```
oil-gas-dashboard/
├── oil_gas_research.py   # Complete single-file application (~2400 lines)
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

The app is intentionally a single file for easy deployment and portability. It is structured internally as:

```
oil_gas_research.py
├── Imports
├── Constants          (tickers, macro series, facility data, geo events)
├── Page config + CSS  (Bebas Neue + Barlow typography, dark theme)
├── Plot theme         (Plotly dark theme, colour palette)
├── Utility functions  (rgba, apply_theme, prov_tag, dl_button)
├── Data fetchers      (Yahoo Finance, NASA FIRMS, Open-Meteo, Esri, RSS)
├── Analysis functions (volatility, drawdown, correlation, MA backtest)
├── Sidebar            (controls, benchmarks, analysis parameters)
├── Hero + KPI strip
└── 8 tab bodies
```

---

## Sidebar Controls

| Control | Description |
|---|---|
| **Price History** | Lookback window: 1mo / 3mo / 6mo / 1y / 2y / 5y |
| **Primary Benchmark** | The main instrument shown in Price, Volatility, and Backtest tabs |
| **Compare With** | Additional tickers for the normalised comparison and correlation tabs |
| **Volatility Window** | Rolling window in days for annualised volatility calculation |
| **Fast / Slow MA** | Moving average periods for the crossover backtest strategy |
| **Correlation Window** | Rolling window for pairwise correlation chart |

---

## Analysis Methodology

### MA Crossover Backtest
- **Long** when Fast MA > Slow MA; **Short** when Fast MA < Slow MA
- Signal is lagged by 1 day to prevent lookahead bias
- Transaction costs not included
- Metrics: total return vs buy-and-hold, annualised volatility, Sharpe ratio, max drawdown, number of signal flips

### Volatility
- Annualised using `daily_std × √252`
- Rolling window configurable from 10 to 60 days

### Correlation
- Pearson correlation on daily percentage returns
- Rolling pairwise correlation with configurable window

### NASA FIRMS Thermal Anomalies
- Queries three public NRT CSV files (VIIRS S-NPP, NOAA-20 VIIRS, MODIS)
- Filters to a 50 km bounding box around the selected facility
- Fire Radiative Power (FRP) in megawatts used as severity proxy
- Persistent detections at refineries indicate routine gas flaring

---

## Caching Strategy

| Data Type | Cache TTL |
|---|---|
| OHLCV prices | 5 minutes |
| Multi-ticker comparison | 5 minutes |
| Commodity history | 5 minutes |
| Weather | 30 minutes |
| RSS news feeds | 15 minutes |
| NASA FIRMS | 1 hour |
| Satellite tiles | 1 hour |
| Macro indicators | 1 hour |

---

## Design

- **Background:** Layered radial gradient (cool blue-indigo + warm amber) with SVG fractal noise grain overlay
- **Display font:** [Bebas Neue](https://fonts.google.com/specimen/Bebas+Neue) — headers, metric values, section titles
- **Body font:** [Barlow](https://fonts.google.com/specimen/Barlow) — body text, news cards, descriptions
- **Label font:** [Barlow Condensed](https://fonts.google.com/specimen/Barlow+Condensed) — widget labels, metadata, chart axes
- **Accent colour:** `#d4963a` (petroleum amber / gold)

---

## Known Limitations

| Limitation | Details |
|---|---|
| Prices delayed ~15 min | Yahoo Finance free tier; not suitable for live trading |
| NASA FIRMS 24h only | NRT CSV covers last 24 hours; not a historical archive |
| AIS embed | MarineTraffic free embed has limited vessel detail vs paid API |
| Satellite imagery | Esri tiles are periodically updated composites, not truly live |
| Facility data | Curated static dataset; capacity figures may not reflect current operational status |

---

## License

MIT License — free to use, modify, and distribute.

---

## Acknowledgements

- [Yahoo Finance](https://finance.yahoo.com) via [yfinance](https://github.com/ranaroussi/yfinance)
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov) — Fire Information for Resource Management System
- [Open-Meteo](https://open-meteo.com) — Open-source weather API
- [Esri ArcGIS Online](https://www.arcgis.com) — World Imagery tile service
- [MarineTraffic](https://www.marinetraffic.com) — AIS vessel tracking
- [Streamlit](https://streamlit.io) — App framework
- [Plotly](https://plotly.com) — Interactive charts
