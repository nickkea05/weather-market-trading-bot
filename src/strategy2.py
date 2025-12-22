"""
Strategy 2: Expected Value Weighted ARB
- ACCUMULATE: Time-based entry value decay (buys cheaper side)
- ARB: Opportunistic cross-arbitrage (buy both sides if profitable, price-weighted by expected value)
"""

from typing import Optional, List

# =============================================================================
# CONSTANTS
# =============================================================================

MAX_LOSS = 200.0  # Stop loss - prevent excessive drawdown
TRADE_AMOUNT = .25  # Fixed trade amount for ACCUMULATE and REBALANCE (smaller = more frequent trades)
MAX_ARB_AMOUNT = 1  # Max amount for ARB trades (aggressive, capture opportunity before ask gone)

# Entry Value Decay (for ACCUMULATE)
ENTRY_THRESHOLD = 50              # Below this, ACCUMULATE doesn't trigger
HARD_CUTOFF_SECONDS = 300        # 7 minutes - ACCUMULATE never triggers after
ARB_CUTOFF_SECONDS = 300       # ~16.7 minutes - ARB never triggers after
DECAY_A = -0.371064
DECAY_B = -1.397701
DECAY_C = 97.939697

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
        self.accumulate_streak = 0  # Track consecutive ACCUMULATE trades without ARB
    
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


# =============================================================================
# MAIN TRADING LOGIC
# =============================================================================

def execute_trade(state: PositionState, up_price: float, down_price: float,
                  up_liquidity: float, down_liquidity: float) -> List[dict]:
    """
    Independent trading decisions (all can fire simultaneously):
    1. ACCUMULATE: If entry value > threshold, buy cheaper side (time-based, early game, stops at 7 min)
    2. ARB: Check both sides independently - buy if combined avg < threshold (price-weighted by expected value)
    
    Returns a LIST of trades (can be 0-2 trades per tick)
    """
    
    trades = []
    seconds_into_market = state.get_seconds_into_market()
    
    # === QUESTION 1: Should we ACCUMULATE? ===
    # Buy the cheaper side if entry value is high enough (only every 2 seconds, stops at 7 min)
    if seconds_into_market < HARD_CUTOFF_SECONDS:
        seconds = int(seconds_into_market)
        entry_value = calculate_entry_value(seconds_into_market)
        if entry_value > ENTRY_THRESHOLD and seconds % 2 == 0:
            cheaper_side = 'UP' if up_price <= down_price else 'DOWN'
            cheaper_price = up_price if cheaper_side == 'UP' else down_price
            
            shares = TRADE_AMOUNT / cheaper_price
            
            trades.append({
                'side': cheaper_side,
                'size': shares,
                'price': cheaper_price,
                'amount': TRADE_AMOUNT,
                'reason': 'ACCUMULATE'
            })
    
    # === QUESTION 2: Should we ARB? ===
    # Check both sides independently - buy if sum (down_avg + up_price) < 1.00
    # Buy full MAX_ARB_AMOUNT when arbitrage opportunity exists
    if seconds_into_market < ARB_CUTOFF_SECONDS:
        # Check UP side: if down_avg + up_price < 1.00, buy UP
        if state.down_shares > 0:
            down_avg = state.down_cost / state.down_shares
            if (down_avg + up_price) < 1.00:
                amount = MAX_ARB_AMOUNT
                shares = amount / up_price
                trades.append({
                    'side': 'UP',
                    'size': shares,
                    'price': up_price,
                    'amount': amount,
                    'reason': 'ARB'
                })
        
        # Check DOWN side: if up_avg + down_price < 1.00, buy DOWN
        if state.up_shares > 0:
            up_avg = state.up_cost / state.up_shares
            if (up_avg + down_price) < 1.00:
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
