# BTC Volatility Farmer

Statistical arbitrage trading bot for Polymarket BTC 15-minute markets.

## Strategy

- **ACCUMULATE**: Time-based entry (first 5 minutes)
- **ARB**: Opportunistic arbitrage (first 10 minutes)
- Focuses on creating arbitrage opportunities and maintaining balanced positions

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```
POLYMARKET_API_KEY=your_key
POLYMARKET_API_SECRET=your_secret
POLYMARKET_PASSPHRASE=your_passphrase
```

3. Run paper trading:
```bash
python src/paper_trade.py
```

## Railway Deployment

1. Connect GitHub repo to Railway
2. Add environment variables in Railway dashboard
3. Deploy - Railway will auto-detect `Procfile` and start the bot

See `RAILWAY_DEPLOY.md` for detailed instructions.

## Analysis Tools

- `test_all_markets.py` - Test strategy on historical markets
- `statistical_significance_test.py` - Statistical analysis
- `overfitting_risk_analysis.py` - Overfitting risk assessment
- `monte_carlo_capital_analysis.py` - Capital requirements analysis

