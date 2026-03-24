# Polymarket Weather Edge Finder — Project Spec

## Overview

Build a local CLI tool that continuously tracks Polymarket weather market orderbooks and lets me manually input weather forecasts to find mispriced markets. The tool does NOT need complex statistical models — it simply flags when the Polymarket market center is significantly different from my inputted forecast.

I am based in **Madrid, Spain (CET/CEST timezone)**. All time logic should be relative to my local time.

## Core Concept

Polymarket runs daily weather markets for ~35 cities worldwide. Each market resolves to the highest temperature recorded at a specific weather station (via Wunderground) on a given date. Markets use either °F (US cities) or °C (international) with 1-2 degree buckets.

My edge: I manually check 4-5 weather sources for the station-specific forecast and input it here. The tool compares my forecast against where Polymarket's probability mass is centered. If there's a 2°F+ (or 1°C+) gap, it flags it.

## Slug Structure

Market URLs follow this pattern:
```
https://polymarket.com/event/highest-temperature-in-{city-slug}-on-{month}-{day}-{year}
```

Examples:
- `highest-temperature-in-nyc-on-march-25-2026`
- `highest-temperature-in-nyc-on-march-26-2026`
- `highest-temperature-in-seoul-on-march-25-2026`
- `highest-temperature-in-dallas-on-march-25-2026`

The tool should be able to construct these slugs automatically from the city list and target date.

## City List & Resolution Stations

Track these markets. Each has a specific Wunderground resolution station:

### US Cities (temperatures in °F, 2°F buckets)
| City | Slug Name | Resolution Station | ICAO | Wunderground URL |
|------|-----------|-------------------|------|-----------------|
| New York | nyc | LaGuardia Airport | KLGA | /history/daily/us/ny/new-york-city/KLGA |
| Chicago | chicago | O'Hare International | KORD | /history/daily/us/il/chicago/KORD |
| Dallas | dallas | Love Field | KDAL | /history/daily/us/tx/dallas/KDAL |
| Miami | miami | Miami International | KMIA | /history/daily/us/fl/miami/KMIA |
| Denver | denver | Buckley Space Force Base | KBKF | /history/daily/us/co/aurora/KBKF |
| San Francisco | san-francisco | SFO International | KSFO | /history/daily/us/ca/san-francisco/KSFO |
| Seattle | seattle | SeaTac Airport | KSEA | /history/daily/us/wa/seattle/KSEA |
| Austin | austin | Bergstrom Airport | KAUS | /history/daily/us/tx/austin/KAUS |
| Houston | houston | Hobby Airport | KHOU | /history/daily/us/tx/houston/KHOU |
| Los Angeles | los-angeles | LAX (likely) | KLAX | /history/daily/us/ca/los-angeles/KLAX |
| Atlanta | atlanta | Hartsfield-Jackson (likely) | KATL | /history/daily/us/ga/atlanta/KATL |

### International Cities (temperatures in °C, 1°C buckets)
| City | Slug Name | Timezone Offset from UTC |
|------|-----------|------------------------|
| Seoul | seoul | +9 |
| Shanghai | shanghai | +8 |
| Tokyo | tokyo | +9 |
| Wellington | wellington | +13 |
| Lucknow | lucknow | +5.5 |
| London | london | +0 |
| Warsaw | warsaw | +1 |
| Paris | paris | +1 |
| Singapore | singapore | +8 |
| Ankara | ankara | +3 |
| Hong Kong | hong-kong | +8 |
| Shenzhen | shenzhen | +8 |
| Buenos Aires | buenos-aires | -3 |
| Beijing | beijing | +8 |
| Chengdu | chengdu | +8 |
| Wuhan | wuhan | +8 |
| Chongqing | chongqing | +8 |
| Toronto | toronto | -5 |
| Madrid | madrid | +1 |
| Munich | munich | +1 |
| Sao Paulo | sao-paulo | -3 |
| Milan | milan | +1 |
| Tel Aviv | tel-aviv | +2 |
| Taipei | taipei | +8 |

## Date/Time Logic — CRITICAL

I'm in Madrid. The tool should always show me the NEXT relevant market for each city based on that city's local time.

**Rule: Once it's past 8:00 AM local time in a city, switch to showing the NEXT day's market for that city.**

Why: After 8am local, today's market is about to resolve (afternoon high is imminent). I want to be looking at tomorrow's market which is still tradeable with a forecast edge.

**Example (if it's Tuesday March 25 at 10pm Madrid time = CET):**
- Seoul (Wednesday 6am KST) → Show March 25 market (still before 8am there)
- Actually wait, 10pm CET = 6am KST next day... 
- The logic: convert my current time to each city's local time. If city local time > 8am, show tomorrow's market. If < 8am, show today's market.

**Display clearly which date each market is for so I don't accidentally input a forecast for the wrong day.**

## Polymarket CLOB API Integration

Use the Polymarket Gamma API and CLOB API (no authentication needed for reading):

```
# Get market data by slug
GET https://gamma-api.polymarket.com/events?slug={event-slug}

# Response contains condition_ids and token_ids for each outcome
# Use these to fetch orderbook data from CLOB API

GET https://clob.polymarket.com/book?token_id={token_id}
```

For each market, the tool needs to:
1. Fetch all outcome buckets and their current best bid/ask prices
2. Determine the "market center" — the bucket with the highest YES price
3. Calculate the implied temperature range the market is pricing

## My Workflow

### Step 1: Tool shows me all active markets with their current centers
```
=== MARKETS FOR MARCH 26 (viewing from Madrid, March 25 10pm) ===

NYC (KLGA)        Market center: 50-51°F (35¢)    [Your forecast: ___]
Chicago (KORD)    Market center: 66-67°F (28¢)    [Your forecast: ___]  
Seoul (RKSI)      Market center: 14°C (32¢)       [Your forecast: ___]
Tokyo (RJTT)      Market center: 15°C (40¢)       [Your forecast: ___]
...
```

### Step 2: I manually input forecasts from my weather source checks
I type in a forecast for each city I've checked. The tool stores it.

### Step 3: Tool flags mismatches
```
🚨 EDGE DETECTED — Seoul
   Your forecast: 12°C
   Market center: 14°C  
   Gap: 2°C
   12°C bucket price: 11¢
   13°C bucket price: 17¢
   Cost to cover 11-14°C: 57¢ (potential arb if < $1)

✅ No edge — NYC  
   Your forecast: 51°F
   Market center: 50-51°F
   Gap: 0°F

🚨 EDGE DETECTED — Dallas
   Your forecast: 89°F
   Market center: 86-87°F
   Gap: 2-3°F  
   88-89°F bucket price: 26¢
```

### Step 4: For flagged edges, I come to Claude for final analysis and position sizing

## Key Features

### Auto-refresh orderbooks
Poll orderbooks every 5 minutes for all active markets. Don't need to display the full orderbook — just track:
- Market center (highest-probability bucket)
- Price of each bucket
- Total cost to cover the 3-4 most likely buckets (for arb detection)

### Arbitrage detection
If the total cost of buying YES on 3-4 adjacent buckets that cover the likely range sums to less than ~70¢, flag it as a potential arbitrage opportunity. This happens when markets are slow to reprice after forecast changes (like the Seoul situation).

### Forecast input persistence
Save my inputted forecasts so I don't have to re-enter them. Clear them when the market date passes.

### Simple display
No charts, no complex UI. Just a clean terminal output showing:
- All markets with their centers
- My forecasts where entered
- Flagged edges with the gap size
- Any arbitrage opportunities

## What This Tool Does NOT Do
- No automated trading
- No complex distribution math
- No weather API integration (I input forecasts manually)
- No position sizing (I do that separately with Claude)
- No historical analysis

## Tech Stack Suggestion
- Python (I'm comfortable with it)
- Simple CLI / terminal interface
- Requests library for API calls
- Could use Rich library for nice terminal formatting
- JSON file for storing forecasts and city config
- Run as a continuous loop with 5-minute refresh

## Example Session

```
$ python weather_edge.py

🌡️  Polymarket Weather Edge Finder
📍 Madrid time: March 25, 2026 10:14 PM CET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Showing markets for each city's next trading day:

CITY              DATE     CENTER    YOUR FCST  GAP    STATUS
─────────────────────────────────────────────────────────────
Seoul (RKSI)     Mar 26   14°C @32¢    12°C    -2°C   🚨 EDGE
Tokyo (RJTT)     Mar 26   15°C @40¢     —       —     ⬜ No forecast
Shanghai         Mar 26   17°C @42¢     —       —     ⬜ No forecast
NYC (KLGA)       Mar 26   52°F @30¢    51°F    -1°F   ✅ Fair
Chicago (KORD)   Mar 26   64°F @28¢    68°F    +4°F   🚨 EDGE
Dallas (KDAL)    Mar 26   87°F @34¢    89°F    +2°F   🚨 EDGE
...

Commands:
  f <city> <temp>  — Input forecast (e.g., "f seoul 12")
  r                — Refresh orderbooks now
  a                — Show arbitrage opportunities  
  d <city>         — Show detailed view for a city
  q                — Quit

> f tokyo 14
✅ Tokyo forecast set to 14°C for March 26

> a
━━━ ARBITRAGE SCANNER ━━━
Seoul Mar 26: Buckets 11-14°C total cost = 57¢ → 43¢ guaranteed profit ⚠️
No other arbitrage opportunities found.

> d seoul
━━━ Seoul (RKSI) — March 26 Detail ━━━
Resolution: wunderground.com/history/daily/kr/incheon/RKSI
Your forecast: 12°C

Bucket    Price    
10°C      0.6¢     
11°C      3.9¢    
12°C     11.9¢    ← YOUR FORECAST
13°C     17.0¢    
14°C     28.0¢    ← MARKET CENTER
15°C+    44.0¢    

Gap: Market centered 2°C above your forecast
Arb check: 11+12+13+14 = 60.8¢ < $1 → ARBITRAGE EXISTS
```

## Final Notes

- The Polymarket CLOB API is public and doesn't need auth for reading orderbooks
- Markets typically have $2K-20K volume — low liquidity
- New markets open ~4 days before resolution
- I'll be running this tool daily, spending ~30 min checking forecasts and scanning for edges
- The goal is to find 1-3 mispriced markets per day, then bring those to Claude for deeper analysis