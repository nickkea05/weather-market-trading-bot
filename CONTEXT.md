# Polymarket 15-Minute Crypto Volatility Strategy

## The Market

Polymarket offers 15-minute binary markets on BTC and ETH price movement. Each interval has two outcomes:
- **Up**: BTC/ETH finishes above the starting price
- **Down**: BTC/ETH finishes below the starting price

At settlement, winning tickets pay $1, losing tickets pay $0. Markets run 24/7 with new intervals every 15 minutes.

## The Inefficiency

Polymarket is dominated by retail traders who overreact to short-term price movements. When BTC drops 0.3%, traders panic-sell Up tickets, pushing prices to extremes (e.g., 35¢/65¢) even though a 0.3% move over 15 minutes has minimal predictive value for the final outcome.

The key insight: **over a 15-minute window, crypto prices are far more likely to oscillate than to trend in one direction.** The market overprices momentum and underprices mean reversion.

## The Strategy

This is **probabilistic arbitrage**—not pure arbitrage, but a high-probability system for accumulating positions on both sides at a combined cost under $1.

### Core Principle

If we buy Up shares at an average of 45¢ and Down shares at an average of 52¢, our combined cost is 97¢. At settlement, one side pays $1. We profit 3¢ per share regardless of outcome.

The challenge: both sides aren't always cheap simultaneously. We rely on volatility to create buying opportunities on each side at different moments during the interval.

### Two-Layer Decision System

**Layer 1: Volume Control (Should I buy?)**

Based on implied volatility and time remaining. The probability of price swinging enough to complete an arbitrage position decreases as the interval progresses.

Evidence from analyzed bot data:
- 71.7% of trades occur in minutes 0-4
- 16.4% in minutes 5-9
- 11.9% in minutes 10-14
- Nearly zero trades in final 2 minutes

The bot front-loads volume when confidence in volatility is highest, then tapers off as time decay reduces the probability of favorable swings.

**Layer 2: Allocation Logic (What should I buy?)**

Given Layer 1 says "buy," Layer 2 determines which side:

1. If no position or balanced position → buy the cheaper side (under 50¢)
   - This aligns with mean reversion expectation
   - If Up is 40¢, we expect price to revert, making Down available around 50-55¢
   - Buying the expensive side first would assume continued momentum, contradicting our core thesis

2. If unbalanced position → buy whichever side improves the position
   - Moves combined average toward sub-$1
   - Balances share counts to maximize guaranteed profit

### Risk Management

- **Exposure cap**: Maximum unhedged capital on any single side
- **Time-based aggression**: Aggressive early, conservative late
- **Position-aware sizing**: Each buy considers current position state

## Evidence From Reverse Engineering

Analysis of a successful bot ("gabagool") trading these markets revealed:

1. **Consistent profitability**: Combined averages between 96-99¢ across all analyzed intervals
2. **Time decay behavior**: Dramatic reduction in trading activity as intervals progress
3. **Both-sides accumulation**: Always ends with positions on Up and Down
4. **No price threshold for entry**: Trades occur at all price levels, not just extremes (42% of trades within 5¢ of 50¢)
5. **Rapid early accumulation**: Hundreds of trades in first few minutes, near-zero in final minutes

## Why This Market

- **Capital velocity**: 96 potential intervals per day vs 2-5 for sports arbitrage
- **Single platform**: No cross-platform matching complexity
- **Guaranteed volatility**: Crypto markets are inherently volatile
- **Short timeframe**: 15 minutes is too brief for sustained trends
- **Inefficient pricing**: Retail-dominated market hasn't been arbitraged by sophisticated players yet

## Success Metrics

- Combined average cost under $1 at settlement
- Worst-case profit (minimum of Up shares or Down shares, minus total cost) > 0
- Win rate across intervals (target: 90%+)
- Average edge per interval (target: 1-3%)