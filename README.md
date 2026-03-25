# Polymarket Weather Edge Finder

CLI tool that detects mispriced Polymarket weather markets by comparing orderbook-implied distributions against real-time temperature forecasts. Pulls live data from the Polymarket Gamma API, flags edge opportunities using fair value models adjusted for city volatility, and supports manual (Wunderground) and automated (Open-Meteo) forecasts across 35 global cities.

## How It Works

Polymarket runs daily weather markets for ~35 cities worldwide. Each market resolves to the highest temperature recorded at a specific weather station (via Wunderground). Markets use 2°F buckets for US cities and 1°C buckets for international cities.

This tool continuously tracks those orderbooks, compares the market's implied temperature center against your forecast, and flags when they disagree — indicating a potential mispricing.

## Codebase Structure

```
src/
├── main.py            # Entry point — CLI loop, display, commands
├── cities.py          # City definitions (35 cities with coords, ICAO, timezone, volatility)
├── polymarket.py      # Polymarket Gamma API — fetches events, prices, bucket data
├── refresh.py         # Orderbook refresh logic, market center calculation
├── autoupdate.py      # Background thread — auto-refresh every 5 min, date rotation at noon
├── fair_value.py      # Probability distribution model — assigns fair values per bucket
├── forecast_api.py    # Open-Meteo integration — automated temperature estimates
└── data/              # Local cache (gitignored)
    └── cache.json
scripts/               # Throwaway test scripts (gitignored)
```

### Key Modules

**`polymarket.py`** — Constructs event slugs, fetches market data from the Gamma API. Uses `outcomePrices` from the Gamma response (not the CLOB `/book` endpoint, which returns empty books for neg-risk multi-outcome weather markets).

**`fair_value.py`** — Given a forecast temperature, assigns probability to each bucket using a peaked distribution. Wider for volatile/interior cities (Denver, Seoul), tighter for coastal/tropical (Miami, Singapore).

**`autoupdate.py`** — Runs in a background thread. Checks each city's local time against a noon cutoff — once it's past noon local, the tool switches to showing the next day's market. Auto-refreshes orderbooks every 5 minutes.

**`forecast_api.py`** — Pulls daily max temperature estimates from Open-Meteo (free, no API key). Used as a baseline to scan all cities for obvious mispricings before manual Wunderground checks.

## CLI Commands

| Command | Description |
|---------|-------------|
| `f <city> <temp>` | Input forecast in °F (auto-converts to °C for international cities) |
| `c <city>` | Clear forecast for a city |
| `o` | Overview table — all cities with centers, forecasts, estimates, gaps |
| `d <city>` | Detailed analysis — bucket-level prices, fair values, edge signals |
| `a` | Scan for price discrepancies across all cities with forecasts |
| `p / p <city>` | Show Wunderground + Polymarket links |
| `r` | Refresh all orderbooks |
| `q` | Quit |

## Market Coverage

### US Cities (°F, 2°F buckets)
New York, Chicago, Dallas, Miami, Denver, San Francisco, Seattle, Austin, Houston, Los Angeles, Atlanta

### International Cities (°C, 1°C buckets)
Seoul, Shanghai, Tokyo, Wellington, Lucknow, London, Warsaw, Paris, Singapore, Ankara, Hong Kong, Shenzhen, Buenos Aires, Beijing, Chengdu, Wuhan, Chongqing, Toronto, Madrid, Munich, São Paulo, Milan, Tel Aviv, Taipei
