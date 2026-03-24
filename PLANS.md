# Development Plans

## Planned Features

### Portfolio & Position Sizing
- `p <amount>` command to set current portfolio/bankroll size
- Kelly criterion calculator: given edge % and probability, recommend optimal bet size
- Fractional Kelly support (half-Kelly, quarter-Kelly) for conservative sizing
- Show recommended position size directly in `d <city>` detail view
- Track running exposure across all open positions

### Enhanced Analysis
- Multi-source forecast input (allow weighting multiple forecast sources)
- Historical accuracy tracking — log forecasts vs actual resolution, build calibration score
- Volatility-adjusted fair values (use actual station variance, not just coastal/interior heuristic)
- Show Wunderground resolution page link in detail view

### Automation
- Auto-fetch METAR/TAF data from weather stations as a baseline forecast
- Alert mode — push notification when edge > threshold appears
- Scheduled runs (cron-friendly mode that outputs findings and exits)

### Trading Integration
- Read-only Polymarket position viewer (see what you're holding)
- P&L tracker — input trades manually, track resolved market outcomes
- Export edge signals to CSV/JSON for external analysis
