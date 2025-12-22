"""
Unified Strategy with Independent Trading Decisions
- ACCUMULATE: Time-based entry value decay (buys cheaper side)
- ARB: Opportunistic cross-arbitrage (buy if cheaper than opposite avg)
- REBALANCE: Risk management (force balance when imbalanced)
"""

from typing import Optional, List

# =============================================================================
# CONSTANTS
# =============================================================================

MAX_LOSS = 200.0  # Stop loss - prevent excessive drawdown
TRADE_AMOUNT = 1  # Fixed trade amount for ACCUMULATE and REBALANCE (smaller = more frequent trades)
MAX_ARB_AMOUNT = 10  # Max amount for ARB trades (aggressive, capture opportunity before ask gone)
REBALANCE_THRESHOLD = 0.05  # Very tight - keep within 47.5-52.5% split

# Entry Value Decay (for ACCUMULATE)
ENTRY_THRESHOLD = 50              # Below this, ACCUMULATE doesn't trigger
HARD_CUTOFF_SECONDS = 300       # 5 minutes - ACCUMULATE never triggers after
ARB_CUTOFF_SECONDS = 1000         # 10 minutes - ARB never triggers after
DECAY_A = -0.371064
DECAY_B = -1.397701
DECAY_C = 97.939697



# Winning Side Accumulation (late game, bet on likely winner to improve worst case)
WINNER_ACCUMULATE_START_MINUTES = 10.0  # Start accumulating likely winner after minute 10
WINNER_PRICE_THRESHOLD = 0.60  # Consider a side "likely winner" if price > this
WINNER_BIAS_MAX = 2.0  # Maximum bias multiplier at minute 15

# =============================================================================
# POSITION STATE
# =============================================================================

class PositionState:
    def __init__(self, market_start_time: float):
        self.up_shares = 0.0
        self.down_shares = 0.0
        self.up_cost = 0.0
        self.down_cost = 0.0
        self.market_start_time = market_start_time
        self.current_time = market_start_time
    
    def get_seconds_into_market(self) -> float:
        return self.current_time - self.market_start_time


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_min_profit(up_shares: float, down_shares: float, up_cost: float, down_cost: float) -> float:
    """Calculate worst-case profit."""
    total_cost = up_cost + down_cost
    if up_shares == 0 or down_shares == 0:
        return -total_cost
    
    # If UP wins: we get up_shares at $1.00
    profit_if_up_wins = up_shares - total_cost
    # If DOWN wins: we get down_shares at $1.00
    profit_if_down_wins = down_shares - total_cost
    
    return min(profit_if_up_wins, profit_if_down_wins)


def calculate_balance_ratio(up_shares: float, down_shares: float) -> float:
    """Calculate imbalance (0 = balanced, 1 = completely imbalanced)."""
    total = up_shares + down_shares
    if total == 0:
        return 0.0
    return abs(up_shares - down_shares) / total


def calculate_combined_avg(up_shares: float, down_shares: float, up_cost: float, down_cost: float) -> float:
    """Calculate combined average."""
    if up_shares == 0 or down_shares == 0:
        return float('inf')
    return (up_cost / up_shares) + (down_cost / down_shares)


def calculate_entry_value(seconds_into_market: float) -> float:
    """Calculate entry value based on time decay (quadratic decay curve)."""
    t = seconds_into_market / 60.0  # Convert to minutes
    value = DECAY_A * (t ** 2) + DECAY_B * t + DECAY_C
    return max(0.0, min(100.0, value))


def calculate_rebalance_threshold(seconds_into_market: float) -> float:
    """Calculate rebalance threshold (loose early, tight late)."""
    t = seconds_into_market / 60.0  # Convert to minutes
    
    # Before minute 12: stay at early threshold
    if t < REBALANCE_TIGHTEN_TIME:
        return REBALANCE_THRESHOLD_EARLY
    
    # After minute 12: linearly tighten to late threshold by minute 15
    progress = (t - REBALANCE_TIGHTEN_TIME) / (15.0 - REBALANCE_TIGHTEN_TIME)
    progress = min(1.0, progress)
    threshold = REBALANCE_THRESHOLD_EARLY - progress * (REBALANCE_THRESHOLD_EARLY - REBALANCE_THRESHOLD_LATE)
    return threshold


def calculate_winner_bias(seconds_into_market: float) -> float:
    """Calculate winning side bias (inverse decay - increases over time)."""
    t = seconds_into_market / 60.0  # Convert to minutes
    
    # Don't activate until after WINNER_ACCUMULATE_START_MINUTES
    if t < WINNER_ACCUMULATE_START_MINUTES:
        return 0.0
    
    # Linear increase from 0 at minute 10 to WINNER_BIAS_MAX at minute 15
    progress = (t - WINNER_ACCUMULATE_START_MINUTES) / (15.0 - WINNER_ACCUMULATE_START_MINUTES)
    bias = progress * WINNER_BIAS_MAX
    return min(WINNER_BIAS_MAX, bias)


# =============================================================================
# MAIN TRADING LOGIC
# =============================================================================

def execute_trade(state: PositionState, up_price: float, down_price: float,
                  up_liquidity: float, down_liquidity: float) -> List[dict]:
    """
    Independent trading decisions (all can fire simultaneously):
    1. ACCUMULATE: If entry value > threshold, buy cheaper side (time-based, early game, stops at 5 min)
    2. ARB: If down_avg + up_price < 1.00, buy it (opportunistic arbitrage, stops at 10 min)
    
    Returns a LIST of trades (can be 0-2 trades per tick)
    """
    
    trades = []
    current_balance = calculate_balance_ratio(state.up_shares, state.down_shares)
    seconds_into_market = state.get_seconds_into_market()
    
    # === QUESTION 1: Should we ACCUMULATE? ===
    # Buy the cheaper side if entry value is high enough (only every 2 seconds, stops at 5 min)
    if seconds_into_market < HARD_CUTOFF_SECONDS:
        seconds = int(seconds_into_market)
        entry_value = calculate_entry_value(seconds_into_market)
        if entry_value > ENTRY_THRESHOLD and seconds % 2 == 0:
            cheaper_side = 'UP' if up_price <= down_price else 'DOWN'
            cheaper_price = up_price if cheaper_side == 'UP' else down_price
            
            shares = TRADE_AMOUNT / cheaper_price
            new_up_shares = state.up_shares + (shares if cheaper_side == 'UP' else 0)
            new_down_shares = state.down_shares + (shares if cheaper_side == 'DOWN' else 0)
            new_up_cost = state.up_cost + (TRADE_AMOUNT if cheaper_side == 'UP' else 0)
            new_down_cost = state.down_cost + (TRADE_AMOUNT if cheaper_side == 'DOWN' else 0)
            
            trades.append({
                'side': cheaper_side,
                'size': shares,
                'price': cheaper_price,
                'amount': TRADE_AMOUNT,
                'reason': 'ACCUMULATE'
            })
    
    # === QUESTION 2: Should we ARB? ===
    # Only buy the lagging side (fewer shares) to make ARB both profitable AND rebalancing
    if seconds_into_market < ARB_CUTOFF_SECONDS:
        # Determine which side is lagging (has fewer shares)
        if state.up_shares < state.down_shares:
            lagging_side = 'UP'
        elif state.down_shares < state.up_shares:
            lagging_side = 'DOWN'
        else:
            # Equal shares - pick the cheaper side
            lagging_side = 'UP' if up_price <= down_price else 'DOWN'
        
        # Adaptive ARB threshold: stricter early (first 5 min), looser later (last 10 min)
        if seconds_into_market < 300:  # First 5 minutes
            arb_threshold = 0.93
        else:  # Last 10 minutes (after 5 minutes)
            arb_threshold = 0.99
        
        # Only check arbitrage for the lagging side
        if lagging_side == 'UP' and state.down_shares > 0:
            down_avg = state.down_cost / state.down_shares
            if (down_avg + up_price) < arb_threshold:
                amount = MAX_ARB_AMOUNT
                shares = amount / up_price
                trades.append({
                    'side': 'UP',
                    'size': shares,
                    'price': up_price,
                    'amount': amount,
                    'reason': 'ARB'
                })
        elif lagging_side == 'DOWN' and state.up_shares > 0:
            up_avg = state.up_cost / state.up_shares
            if (up_avg + down_price) < arb_threshold:
                amount = MAX_ARB_AMOUNT
                shares = amount / down_price
                trades.append({
                    'side': 'DOWN',
                    'size': shares,
                    'price': down_price,
                    'amount': amount,
                    'reason': 'ARB'
                })
    
    # Return all trades (can be 0-2 now: ACCUMULATE, ARB)
    return trades


# Tick interval constant
TICK_INTERVAL_SEC = 1

