# Strategy Theory: Two-Layer Buy System

**Status:** Theoretical framework, not yet validated with data  
**Last Updated:** December 16, 2025

---

## Overview

Our hypothesis is that gabagool's trading system operates on two distinct layers that work together to determine buying decisions. Each layer outputs a "value" score, and their relative weights shift based on time into the market.

---

## Layer 1: Volume Control (Entry Value)

**Purpose:** Determine if NOW is a good time to be buying at all, based purely on market timing.

**Core Logic:**
```
entry_value = arb_probability[minute] × future_volatility[minute] (normalized)
```

**Layer 1 asks:** "Given where we are in the market's lifecycle, is buying generally valuable?"

**Key Values Used:**
- `ARB_PROBABILITY_BY_MINUTE` - lookup table from analysis
- `FUTURE_VOLATILITY_BY_MINUTE` - remaining price range
- `ENTRY_VALUE_THRESHOLD` - minimum score to consider buying

**Characteristics:**
- Simple O(1) lookup
- Time-based, not price-based
- Doesn't consider current position or balance
- High value early, decays over time

**Output:** Entry value score (0-100)

---

## Layer 2: Rebalancing Logic

**Purpose:** Determine if buying NOW is optimal given our current position and future expectations.

**Two-Stage Decision:**

### Stage 2A: "Is rebalancing possible?"
- Do we have an imbalance that needs addressing?
- Is there liquidity available on the side we need?
- Is there enough time remaining to execute?

### Stage 2B: "Is rebalancing NOW optimal?"
Compare present opportunity vs expected future opportunity:

```
buy_now_value = improvement_to_worst_case(current_price, current_imbalance)

wait_value = P(better_price_exists) × E[improvement_at_better_price]
           - P(no_arb_if_wait) × cost_of_missing_arb
           
Decision: buy_now_value vs wait_value × safety_factor
```

**Key Values Used:**

| Category | Values |
|----------|--------|
| Current State | `current_price`, `current_imbalance`, `available_liquidity`, `worst_case_profit` |
| Future Projections | `P(better_price)`, `E[min_future_price]`, `E[time_to_better]`, `future_volatility` |
| Risk/Urgency | `time_remaining`, `P(no_arb_if_wait)`, `rebalance_urgency` |

**Uncertainty Handling:**
- Future projections use confidence intervals
- t-values for small sample sizes
- Conservative estimates (use lower bound of CI for optimistic projections)

**Output:** Rebalancing value score (incorporating risk-adjusted comparison of now vs later)

---

## Parallel Layer System (UPDATED THEORY)

**Key Insight:** The two layers work SIMULTANEOUSLY and INDEPENDENTLY. It's not "either/or" with weighted alternatives - both can trigger buys on their own.

```
if layer1_says_buy() OR layer2_says_buy():
    execute_buy()
```

### Evidence from Trade Frequency Analysis

**Minutes 0-2:**
- Entry value is HIGHEST
- But trade frequency is NOT highest
- Why? Layer 1 says "buy!" but Layer 2 has nothing to rebalance yet (small position)
- Result: Only Layer 1 signals, fewer total trades

**Minutes 3-7:**
- Entry value still high
- Trade frequency is HIGHEST
- Why? Layer 1 still active AND Layer 2 now has position to rebalance
- Result: BOTH layers triggering trades = peak activity

**Minutes 7-15:**
- Trade frequency declines at SAME RATE as entry value
- But stays ABOVE the entry value line
- Why? Layer 1 declining (follows entry value), Layer 2 stays constant
- The GAP between lines = Layer 2 rebalancing trades

### Proposed Structure

```
# Layer 1: Time-based volume building
layer1_buy = entry_value[minute] > ENTRY_THRESHOLD

# Layer 2: Position-based rebalancing  
layer2_buy = imbalance > IMBALANCE_THRESHOLD AND acceptable_price

# Either layer can trigger a buy
if layer1_buy OR layer2_buy:
    execute_buy()
```

### What This Explains

| Observation | Explanation |
|-------------|-------------|
| Trades < Entry Value (min 0-2) | Only Layer 1 active, no position to rebalance |
| Trades peak (min 3-7) | Both layers firing simultaneously |
| Trades > Entry Value (min 8+) | Layer 1 declining, but Layer 2 constant |
| Trade line parallel to entry line (late) | Layer 1 driving shape, Layer 2 adding offset |

---

## Position Sizing (Separate from Buy Decision)

Once we decide TO buy, determining HOW MUCH is separate (and simpler):

**Factors:**
- Available liquidity at current price
- Current imbalance magnitude
- Time remaining (more aggressive sizing early)
- Risk parameters (max position per market)

This is more mechanical and less about market analysis.

---

## Rate Limiting

**Observed:** ~2-second intervals between trades on same side

**Interpretation:** System constraint, not strategic decision

**Implementation:** After any buy, wait minimum 2 seconds before next same-side buy

---

## Key Insights from Analysis

1. **Price doesn't matter for entry** - 0.93 correlation between opportunity distribution and gabagool buys. He buys wherever prices happen to be.

2. **Time is everything for Layer 1** - Entry value drops from 100 to near 0 by minute 14

3. **Gaps in trading = imbalance limits, not market conditions** - When he pauses even in good conditions, it's likely due to position constraints

4. **Late buying = rebalancing** - Any buying after minute 11-12 is almost certainly position optimization, not new opportunity entry

5. **0.80 correlation between Entry Value and Trade Frequency** - Our Layer 1 metric explains ~80% of his trading pattern. The remaining ~20% is likely Layer 2 (rebalancing)

6. **Layers are PARALLEL, not weighted** - Both layers work simultaneously. Trade frequency = Layer 1 signals + Layer 2 signals. This explains why:
   - Trades are BELOW entry value early (only Layer 1)
   - Trades PEAK in middle (both layers)
   - Trades are ABOVE entry value late (Layer 2 adding constant offset)

---

## Validation Roadmap

### Day 1 (Tomorrow): Analysis + Master Sheet
- Analyze all collected data comprehensively
- Extract exact values for all lookup tables
- Define confidence intervals for uncertain parameters
- Create master parameter sheet for bot

### Day 2: First Draft Implementation
- Code paper trading version (no real trades)
- Feed same market data to our bot
- Compare our buy decisions to gabagool's actual buys
- Calculate correlation coefficient

### Day 3+: Delta Analysis + Refinement
- Identify where our decisions diverge from gabagool's
- Analyze patterns in divergence
- Adjust parameters/logic to improve correlation
- Iterate until correlation is satisfactory

---

## Open Questions

1. What is the exact weight decay function for Layer 1 vs Layer 2?
2. What imbalance threshold triggers Layer 2 intervention?
3. How does gabagool determine "acceptable premium" for rebalancing?
4. Is there a minimum position size before rebalancing matters?
5. Does he have different parameters for UP vs DOWN sides?

---

## Appendix: Values We Have vs Need

### Have (from analysis)
- [x] Entry value by minute (arb_prob × volatility)
- [x] Future volatility by minute
- [x] Arb probability by minute
- [x] Trade interval (~2 seconds)
- [x] Price distribution (doesn't matter)

### Need (to determine)
- [ ] Layer weight function parameters
- [ ] Imbalance threshold for Layer 2 activation
- [ ] Acceptable premium for rebalancing
- [ ] Position sizing parameters
- [ ] Safety factor / risk tolerance values

