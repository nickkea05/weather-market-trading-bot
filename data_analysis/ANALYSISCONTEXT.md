# Analysis Strategy Context

## Purpose

This document outlines our statistical analysis approach for reverse-engineering optimal trading parameters from market data and gabagool's trades. The goal is to derive quantifiable values that directly inform Layer 1 (Volume Control) decisions in our bot.

---

## What We Are Tracking

### Market Data (WebSocket Stream)
For each 15-minute market, we capture tick-by-tick:
- **Up best ask price**: Current cheapest price to buy Up
- **Down best ask price**: Current cheapest price to buy Down
- **Combined cost**: Sum of both (arb exists when < $1.00)
- **Timestamp**: Millisecond precision for time-into-market calculations

### Gabagool Trades (API Fetch)
For each market, we capture all of gabagool's trades:
- **Entry time**: When in the market they entered
- **Side**: Up or Down
- **Price**: What they paid
- **Size**: Position size in shares
- **USDC size**: Dollar amount

### Derived Metrics
From raw data, we calculate:
- **Future arb probability**: At time T, does an arb opportunity exist at any T+n?
- **Time-to-arb**: If arb exists, how long until it appears?
- **Price volatility**: Range of price movement within intervals

---

## Statistical Principles We Will Use

### 1. Confidence Intervals (t-distribution)

**Why**: With small sample sizes (12-50 markets), we cannot assume normal distribution. The t-distribution accounts for uncertainty with limited data.

**Application**: Every metric we calculate will have a confidence interval. "Arb probability at minute 5 is 95% (CI: 88%-99%)" is more useful than just "95%".

**Formula**: CI = mean ± (t_critical × standard_error)

### 2. Bootstrap Resampling

**Why**: Non-parametric method that works without distribution assumptions. Particularly useful for small, potentially skewed datasets.

**Application**: 
- Resample our markets with replacement 1000+ times
- Calculate the metric on each resample
- Use percentiles (2.5th, 97.5th) as confidence bounds

### 3. Survival Analysis (Kaplan-Meier)

**Why**: Not just "does arb exist" but "when does it appear". This informs how long we can wait before giving up on a position.

**Application**: 
- Time-to-arb distribution
- Probability of arb appearing by minute X
- Median wait time for arb completion

### 4. Regression Modeling

**Why**: Quantify the relationship between predictors (time, entry price, volatility) and outcome (arb probability).

**Application**:
- Logistic regression: P(arb) = f(time, price, ...)
- Coefficients become direct parameters for bot logic

### 5. Variance Decomposition

**Why**: Understand where noise comes from. High between-market variance means we need more samples. High within-market variance means timing matters more.

**Application**:
- Between-market variance: How different are markets from each other?
- Within-market variance: How much does arb probability fluctuate during a single market?

### 6. Correlation Analysis

**Why**: Measure how gabagool's behavior relates to market conditions and outcomes.

**Application**:
- Spearman correlation (non-parametric, better for small samples)
- Correlate entry timing with final profit
- Correlate entry price with arb completion rate

### 7. Effect Size (Cohen's d)

**Why**: Statistical significance is not practical significance. Effect size tells us if a difference actually matters.

**Application**:
- Is the difference between minute 3 and minute 10 arb rates meaningful?
- d > 0.8 indicates large, actionable difference

---

## Current Analysis Implementation

### Alpha Decay Visualization (`visualize.py`)

Currently tracks:
- Per-minute arb probability across all markets
- Individual market curves (Monte Carlo view of variance)
- Average decay curve (equal weight per market)

Output: Clear decay pattern showing safe zone (0-8 min) vs danger zone (12-15 min)

---

## Key Metrics to Discover

### 1. Time Decay Curve

**What**: Probability of future arb existing at each minute into the market.

**Format**: 
```
minute -> probability (with CI)
0 -> 100% (CI: 98-100%)
5 -> 100% (CI: 95-100%)
10 -> 83% (CI: 65-95%)
14 -> 34% (CI: 15-55%)
```

**Use in bot**: Determines the "should I still be trading?" decision.

### 2. Expected Value by Entry Time

**What**: Given entry at minute T, what is the expected profit?

**Calculation**: 
```
EV(T) = P(arb at T) × avg_profit_when_arb - P(no_arb at T) × avg_loss_when_no_arb
```

**Format**:
```
minute -> EV per dollar risked (with CI)
0 -> +$0.03 (CI: +$0.02 to +$0.04)
10 -> +$0.01 (CI: -$0.01 to +$0.02)
14 -> -$0.02 (CI: -$0.05 to +$0.01)
```

**Use in bot**: If EV < threshold, stop trading this interval.

### 3. Volatility/Noise Bounds

**What**: The typical range of price movement within a market.

**Metrics**:
- Standard deviation of price changes
- Max drawdown (worst price swing against position)
- 95th percentile adverse move

**Format**:
```
Typical swing: ±$0.08 from entry
95th percentile adverse move: $0.15
Max observed: $0.22
```

**Use in bot**: Informs position sizing and mental stop-loss. If we enter at $0.45 and price moves to $0.60, is this normal noise or should we be concerned?

### 4. Optimal Entry Window

**What**: The time range where trading has positive expected value.

**Format**:
```
Recommended window: 0 to 9 minutes (CI: 7-11 minutes)
Hard cutoff: 12 minutes (below 50% arb probability)
```

**Use in bot**: Layer 1 time-based gate.

### 5. Price Sensitivity Thresholds

**What**: At what price levels is arb most/least likely?

**Format**:
```
Entry at $0.30-0.40: 92% arb rate
Entry at $0.45-0.55: 78% arb rate  
Entry at $0.60-0.70: 85% arb rate
```

**Use in bot**: Potentially avoid the "no man's land" around 50¢ where neither side dips.

### 6. Gabagool Correlation Metrics

**What**: How does gabagool's behavior correlate with success?

**Metrics**:
- Entry time distribution vs arb rate
- Position sizing patterns
- Side selection logic

**Use in bot**: Validate our logic against proven successful behavior.

---

## Hard Values Required for Layer 1 Bot Logic

These are the specific quantifiable parameters our bot needs from this analysis:

| Parameter | Description | Example Value | How It's Used |
|-----------|-------------|---------------|---------------|
| `TIME_CUTOFF_HARD` | Minute after which we never trade | 12 | `if minutes_elapsed > TIME_CUTOFF_HARD: return False` |
| `TIME_CUTOFF_SOFT` | Minute after which we reduce aggression | 9 | Reduce position sizing multiplier |
| `MIN_ARB_PROBABILITY` | Minimum acceptable arb probability to trade | 0.70 | `if arb_prob < MIN_ARB_PROBABILITY: return False` |
| `ARB_PROB_BY_MINUTE` | Array of probabilities for each minute | [1.0, 1.0, 1.0, ..., 0.34] | Lookup table for time-based decisions |
| `EV_THRESHOLD` | Minimum expected value to continue trading | 0.005 ($0.005 per $1 risked) | `if ev < EV_THRESHOLD: return False` |
| `MAX_ADVERSE_MOVE` | 95th percentile price move against us | 0.15 | Position sizing / risk calc |
| `TYPICAL_VOLATILITY` | Standard deviation of price swings | 0.08 | Expected noise, don't panic sell |
| `CONFIDENCE_LEVEL` | How conservative our estimates are | 0.95 (95% CI lower bound) | Use lower CI bound for safety |
| `MIN_SAMPLE_SIZE` | Markets needed before trusting estimates | 20 | Don't deploy bot until n > MIN_SAMPLE |
| `DECAY_RATE` | Rate at which arb probability declines per minute | -0.05 (5% per min after minute 9) | Continuous decay model |

---

## Analysis Pipeline (Future Implementation)

1. **Data Collection** (running): `test_csv_stream.py` captures market + gabagool data
2. **Batch Analysis**: Process all markets, calculate all metrics
3. **Confidence Estimation**: Bootstrap + t-distribution CIs on every metric
4. **Parameter Export**: Generate `bot_parameters.json` with all hard values
5. **Continuous Update**: As new markets are collected, re-run analysis, update parameters
6. **Drift Detection**: Alert if market behavior changes significantly from training data

---

## Notes

- All analysis uses equal weighting per market (not per data point) to avoid bias from markets with more ticks
- Confidence intervals are essential given small sample sizes
- Parameters should be updated weekly as more data accumulates
- Conservative estimates (lower CI bounds) should be used for production bot

