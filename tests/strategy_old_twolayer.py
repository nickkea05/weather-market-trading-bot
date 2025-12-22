from typing import Optional

# =============================================================================
# CONSTANTS
# =============================================================================

# --- Layer 1: Entry Value Decay ---
ENTRY_THRESHOLD = 50              # Below this, Layer 1 doesn't trigger
HARD_CUTOFF_SECONDS = 600         # 10 minutes - Layer 1 never triggers after
LAYER1_PRICE_THRESHOLD = 0.50     # Only buy if price < this (to keep averages low)

# Decay coefficients: value = A*t^2 + B*t + C (t in minutes)
DECAY_A = -0.371064
DECAY_B = -1.397701
DECAY_C = 97.939697
# Conservative bounds if not profitable: DECAY_A = -0.53, DECAY_B = -3.4

# --- Order Sizing (Money-Based, Flexible) ---
# Gabagool analysis: Max ~$18.60, median ~$3.88, most trades $2-10
# 92% of trades are non-round amounts (flexible, not fixed increments)
# In first minute: 63 trades, $278.55 total = ~$4.42 per trade average
BASE_ORDER_AMOUNT = 5.0                # Base amount in USDC (increased to match gabagool spending)
MAX_AMOUNT_PER_TRADE = 18.0            # Max USDC per trade (based on gabagool analysis)
MIN_ORDER_AMOUNT = 1.0                 # Minimum USDC per trade
# Amounts are flexible - can use any value between MIN and MAX
# For simplicity, we'll use increments of $0.50 for testing, but can be more granular

# --- Timing ---
TICK_INTERVAL_SEC = 1  # Process market data every 1 second (increased frequency for more trades)

# --- Safety ---
MAX_LOSS = 100.0  # Max acceptable worst-case loss

# --- Layer 2: Rebalancing ---
# Bias coefficients: bias_strength = A*t^2 + B*t + C (t in minutes)
# Based on predictability analysis:
#   - 0-5.5 min: ~50% accuracy → no bias (0.0)
#   - 5.5-11 min: 80-90% accuracy → moderate bias (0.05-0.10)
#   - 11+ min: 90-100% accuracy → strong bias (0.10-0.15)
# Bias is applied as a multiplier to average profit for the likely winner side
BIAS_START_MINUTES = 5.5  # When bias starts (80%+ accuracy)
BIAS_MAX_MINUTES = 11.0   # When bias reaches maximum (90%+ accuracy)
BIAS_MAX_STRENGTH = 0.15   # Maximum bias multiplier (15% boost to likely winner)
LAYER2_BALANCE_THRESHOLD = 0.10  # Layer 2 triggers if balance ratio > this
LAYER2_COMBINED_AVG_LIMIT = 1.02  # Layer 2 only fires if combined avg < this


# Calculate bias coefficients to go from 0 at BIAS_START to BIAS_MAX at BIAS_MAX_MINUTES
# Using linear interpolation: bias = (t - BIAS_START) / (BIAS_MAX - BIAS_START) * BIAS_MAX_STRENGTH
# For t < BIAS_START: bias = 0
# For t >= BIAS_MAX: bias = BIAS_MAX_STRENGTH


# =============================================================================
# POSITION STATE CLASS
# =============================================================================

# Tracks current position state
# Updated on every trade/tick
class PositionState:
    def __init__(self):
        # Position
        self.up_shares: float = 0
        self.down_shares: float = 0
        self.up_cost: float = 0
        self.down_cost: float = 0
        
        # Timing (set from datastream/main)
        self.market_start_time: float = 0
        self.current_time: float = 0
    
    # Returns seconds elapsed since market opened
    def get_seconds_into_market(self) -> float:
        return self.current_time - self.market_start_time


# =============================================================================
# UTILITY FUNCTIONS (for reporting/analysis only, not used in trading logic)
# =============================================================================

# calculate_balance_ratio
# state: Current position state
# Returns the deviation from perfect 50/50 balance
# 0.0 = perfectly balanced (50% UP, 50% DOWN)
# 1.0 = completely imbalanced (100% one side, 0% other)
# Example: 710 UP / 440 DOWN
#   - up_ratio = 710/(710+440) = 0.617 (61.7% UP)
#   - deviation = abs(0.617 - 0.5) = 0.117
#   - balance_ratio = 0.117 * 2.0 = 0.234 (23.4% imbalanced)
# NOTE: This function is ONLY for reporting/analysis. It is NOT used in any trading decisions.
def calculate_balance_ratio(state: PositionState) -> float:
    total_shares = state.up_shares + state.down_shares
    if total_shares == 0:
        return 0.0  # No position yet, considered balanced
    
    up_ratio = state.up_shares / total_shares
    
    # Return the deviation from 50/50, scaled to 0.0-1.0 range
    # abs(up_ratio - 0.5) gives 0.0-0.5 range, multiply by 2 to get 0.0-1.0
    return abs(up_ratio - 0.5) * 2.0


# calculate_balance_ratio_after_trade
# state: Current position state
# side: 'UP' or 'DOWN'
# shares: Number of shares to buy
# Returns balance ratio after the trade
def calculate_balance_ratio_after_trade(state: PositionState, side: str, shares: float) -> float:
    new_up_shares = state.up_shares + (shares if side == 'UP' else 0)
    new_down_shares = state.down_shares + (shares if side == 'DOWN' else 0)
    total_shares = new_up_shares + new_down_shares
    
    if total_shares == 0:
        return 0.0
    
    up_ratio = new_up_shares / total_shares
    return abs(up_ratio - 0.5) * 2.0


# =============================================================================
# LAYER 1 FUNCTIONS
# =============================================================================

# get_entry_value
# seconds_into_market: Time elapsed since market opened
# Calculates entry value using polynomial decay
# Returns value on 0-100 scale
def get_entry_value(seconds_into_market: float) -> float:
    if seconds_into_market < 0:
        return 100.0
    if seconds_into_market >= 900:  # 15 minutes
        return 0.0
    
    t = seconds_into_market / 60.0  # Convert to minutes
    value = DECAY_A * (t ** 2) + DECAY_B * t + DECAY_C
    return max(0.0, min(100.0, value))


# layer1_should_buy
# state: Current position state
# Checks: current safety, time cutoff, entry value threshold
# Returns True if Layer 1 recommends buying
def layer1_should_buy(state: PositionState) -> bool:
    if not check_if_safe(state.up_shares, state.down_shares, 
                         state.up_cost, state.down_cost):
        return False
    
    seconds = state.get_seconds_into_market()
    
    if seconds >= HARD_CUTOFF_SECONDS:
        return False
    
    return get_entry_value(seconds) >= ENTRY_THRESHOLD


# layer1_choose_side
# state: Current position state
# up_price: Current UP best ask
# down_price: Current DOWN best ask
# Returns 'UP' or 'DOWN' - considers both price and balance
# Primary: buy the cheaper side
# Secondary: if imbalanced (balance_ratio > 0.10), prefer minority side
def layer1_choose_side(state: PositionState, up_price: float, down_price: float) -> str:
    # Calculate balance ratio
    total_shares = state.up_shares + state.down_shares
    
    if total_shares == 0:
        # No position yet, just buy the cheaper side
        return 'UP' if up_price <= down_price else 'DOWN'
    
    # Check if we're significantly imbalanced
    balance_ratio = calculate_balance_ratio(state)
    up_ratio = state.up_shares / total_shares
    
    # If very imbalanced (> 10%), prefer minority side even if slightly more expensive
    if balance_ratio > LAYER2_BALANCE_THRESHOLD:
        minority_side = 'UP' if up_ratio < 0.5 else 'DOWN'
        majority_price = up_price if minority_side == 'UP' else down_price
        
        # Only override if minority side is within 5 cents of the cheaper side
        price_diff = abs(up_price - down_price)
        if price_diff < 0.05:
            return minority_side
    
    # Default: buy the cheaper side
    return 'UP' if up_price <= down_price else 'DOWN'


# layer1_execute
# state: Current position state
# up_price: Current UP best ask
# down_price: Current DOWN best ask
# Main Layer 1 function - checks time value, picks cheaper side, finds safe amount
# Returns {'side', 'size', 'price', 'amount', 'layer'} or None
# size = shares, amount = USDC spent
# Uses flexible amounts: tries BASE_ORDER_AMOUNT, then scales up to MAX_AMOUNT_PER_TRADE
def layer1_execute(state: PositionState, up_price: float, down_price: float) -> dict:
    if not layer1_should_buy(state):
        return None
    
    side = layer1_choose_side(state, up_price, down_price)
    price = up_price if side == 'UP' else down_price
    
    # Only buy if price is under the threshold (to keep averages low)
    if price >= LAYER1_PRICE_THRESHOLD:
        return None
    
    # Try flexible amounts: start with BASE, then try increasing amounts
    # Use increments of $0.50 for granularity (can be made more flexible)
    safe_amount = None
    
    # Try from BASE up to MAX, in $0.50 increments - take the FIRST (smallest) safe amount
    for amount in [BASE_ORDER_AMOUNT + i * 0.5 for i in range(int((MAX_AMOUNT_PER_TRADE - BASE_ORDER_AMOUNT) / 0.5) + 1)]:
        if amount < MIN_ORDER_AMOUNT:
            continue
        if amount > MAX_AMOUNT_PER_TRADE:
            break
        
        # Calculate shares from amount
        shares = amount / price
        
        if check_if_safe_after_trade(state, side, shares, price):
            safe_amount = amount
            break
    
    if safe_amount is None:
        return None
    
    shares = safe_amount / price
    
    return {
        'side': side,
        'size': shares,
        'price': price,
        'amount': safe_amount,
        'layer': 1
    }


# =============================================================================
# LAYER 2 BIAS FUNCTIONS
# =============================================================================

# get_bias_strength
# seconds_into_market: Time elapsed since market opened
# Returns bias strength multiplier (0.0 to BIAS_MAX_STRENGTH)
# Based on predictability analysis: bias starts at 5.5 min, max at 11 min
def get_bias_strength(seconds_into_market: float) -> float:
    if seconds_into_market < 0:
        return 0.0
    
    t = seconds_into_market / 60.0  # Convert to minutes
    
    if t < BIAS_START_MINUTES:
        return 0.0  # No bias early in market
    
    if t >= BIAS_MAX_MINUTES:
        return BIAS_MAX_STRENGTH  # Maximum bias after 11 minutes
    
    # Linear interpolation between BIAS_START and BIAS_MAX
    progress = (t - BIAS_START_MINUTES) / (BIAS_MAX_MINUTES - BIAS_START_MINUTES)
    return progress * BIAS_MAX_STRENGTH


# get_likely_winner
# up_price: Current UP best ask
# down_price: Current DOWN best ask
# Returns 'UP', 'DOWN', or None
# Likely winner is the side with price > 0.50 (more likely to win)
def get_likely_winner(up_price: float, down_price: float) -> str:
    if up_price > 0.50:
        return 'UP'
    elif down_price > 0.50:
        return 'DOWN'
    else:
        # If both are <= 0.50, return the higher one (closer to winning)
        return 'UP' if up_price >= down_price else 'DOWN'


# =============================================================================
# LAYER 2 FUNCTIONS
# =============================================================================

# get_rebalance_value
# Measures value of rebalancing vs buying expensive side
# Early: high value when imbalanced (want to rebalance)
# Late: low value (don't care about balance, care about momentum)
# Returns 0-100 scale
def get_rebalance_value(seconds_into_market: float, balance_ratio: float) -> float:
    """
    Calculate rebalance value based on time and current balance.
    
    balance_ratio: 0.0 (balanced) to 1.0 (all one side)
    
    Early in market: High value when imbalanced → rebalance
    Late in market: Low value → focus on momentum (buy expensive side)
    """
    t = seconds_into_market / 60.0  # Convert to minutes
    
    # After 11 minutes, don't rebalance at all
    if t >= BIAS_MAX_MINUTES:
        return 0.0
    
    # Time weight: 1.0 early, decays to 0.0 at BIAS_MAX_MINUTES
    if t < BIAS_START_MINUTES:
        time_weight = 1.0  # Full rebalancing priority early
    else:
        # Linear decay from 1.0 to 0.0
        progress = (t - BIAS_START_MINUTES) / (BIAS_MAX_MINUTES - BIAS_START_MINUTES)
        time_weight = 1.0 - progress
    
    # Balance value: higher imbalance = higher value
    balance_value = balance_ratio * 100.0  # 0 to 100
    
    return balance_value * time_weight


# layer2_choose_side
# Simple: buy the minority side to improve balance
# Returns 'UP', 'DOWN', or None
def layer2_choose_side(state: PositionState, up_price: float, down_price: float) -> Optional[str]:
    """
    Choose which side to buy for Layer 2.
    Always returns minority side (to improve balance).
    Layer 2 execution will check if it's profitable.
    """
    # Calculate current balance
    total_shares = state.up_shares + state.down_shares
    
    if total_shares == 0:
        return None  # No position yet
    
    up_ratio = state.up_shares / total_shares
    
    # Buy the minority side (the one we have less of)
    return 'UP' if up_ratio < 0.5 else 'DOWN'


# calculate_min_profit_after_trade
# Helper function: calculates worst-case profit after a trade
def calculate_min_profit_after_trade(state: PositionState, side: str, size: float, price: float) -> float:
    new_up_shares = state.up_shares + (size if side == 'UP' else 0)
    new_down_shares = state.down_shares + (size if side == 'DOWN' else 0)
    new_up_cost = state.up_cost + (size * price if side == 'UP' else 0)
    new_down_cost = state.down_cost + (size * price if side == 'DOWN' else 0)
    
    return calculate_worst_case_profit(new_up_shares, new_down_shares, new_up_cost, new_down_cost)




def get_max_combined_avg_for_balance(balance_ratio: float) -> float:
    """
    Get the maximum allowed combined average.
    
    Flat limit of 1.02. This gives Layer 2 enough flexibility to rebalance
    even in volatile markets while maintaining reasonable profit margin.
    
    1.01 was too tight - couldn't keep up with rebalancing in some markets.
    """
    return 1.02


# layer2_execute
# Main Layer 2 function - opportunistic rebalancing
# Only fires if it can BOTH increase min profit AND keep combined avg under dynamic limit
# Returns {'side', 'size', 'price', 'amount', 'layer'} or None
def layer2_execute(state: PositionState, up_price: float, down_price: float,
                   up_liquidity: float, down_liquidity: float) -> Optional[dict]:
    """
    Layer 2: Pure risk management rebalancing.
    
    CORE PRINCIPLE:
    - Layer 1 handles VALUE/PROFITABILITY (buy cheap side when good entry)
    - Layer 2 handles RISK MANAGEMENT (keep balanced, period)
    
    Layer 2 ONLY cares about:
    1. Buying minority side when imbalanced
    2. Keeping combined average under threshold (prevents guaranteed loss)
    
    Does NOT require improving min profit - rebalancing is valuable even if it
    doesn't immediately help profitability, because it sets up future opportunities
    and maintains a safer position for capturing value.
    """
    # Safety check first
    if not check_if_safe(state.up_shares, state.down_shares,
                         state.up_cost, state.down_cost):
        return None
    
    # Determine which side to buy (minority side)
    side = layer2_choose_side(state, up_price, down_price)
    if side is None:
        return None
    
    # Get price and liquidity for chosen side
    price = up_price if side == 'UP' else down_price
    liquidity = up_liquidity if side == 'UP' else down_liquidity
    
    if liquidity <= 0:
        return None
    
    # Get maximum allowed combined average (flat 1.02 for now)
    max_combined_avg = get_max_combined_avg_for_balance(0.0)
    
    # Find the BEST amount to rebalance - maximize rebalancing effect
    best_amount = None
    best_balance_improvement = 0.0
    best_shares = 0
    
    current_total = state.up_shares + state.down_shares
    current_balance_ratio = abs(state.up_shares - state.down_shares) / current_total if current_total > 0 else 0.0
    
    # Try all amounts from MIN to MAX, find the one that best rebalances
    for amount in [MIN_ORDER_AMOUNT + i * 0.5 for i in range(int((MAX_AMOUNT_PER_TRADE - MIN_ORDER_AMOUNT) / 0.5) + 1)]:
        if amount > MAX_AMOUNT_PER_TRADE:
            break
        
        shares = amount / price
        
        # Check liquidity constraint
        if shares > liquidity:
            continue
        
        # Calculate new position after trade
        new_up_shares = state.up_shares + (shares if side == 'UP' else 0)
        new_down_shares = state.down_shares + (shares if side == 'DOWN' else 0)
        new_up_cost = state.up_cost + (amount if side == 'UP' else 0)
        new_down_cost = state.down_cost + (amount if side == 'DOWN' else 0)
        
        # Check: Would combined average stay under threshold?
        new_avg_up = new_up_cost / new_up_shares if new_up_shares > 0 else 0.0
        new_avg_down = new_down_cost / new_down_shares if new_down_shares > 0 else 0.0
        combined_avg = new_avg_up + new_avg_down
        
        if combined_avg >= max_combined_avg:
            continue  # Would push us over limit, skip
        
        # Safety check
        new_min = calculate_worst_case_profit(new_up_shares, new_down_shares, new_up_cost, new_down_cost)
        if new_min < -MAX_LOSS:
            continue
        
        # Calculate balance improvement (how much closer to 50/50)
        new_total = new_up_shares + new_down_shares
        new_balance_ratio = abs(new_up_shares - new_down_shares) / new_total if new_total > 0 else 0.0
        balance_improvement = current_balance_ratio - new_balance_ratio
        
        # Track if this is the best rebalancing amount so far
        if balance_improvement > best_balance_improvement:
            best_amount = amount
            best_balance_improvement = balance_improvement
            best_shares = shares
    
    # Return the BEST rebalancing trade
    if best_amount is not None:
        return {
            'side': side,
            'size': best_shares,
            'price': price,
            'amount': best_amount,
            'layer': 2
        }
    
    return None


# =============================================================================
# SAFETY / EXPOSURE FUNCTIONS
# =============================================================================

# calculate_worst_case_profit
# up_shares: Number of UP shares owned
# down_shares: Number of DOWN shares owned
# up_cost: Total $ spent on UP
# down_cost: Total $ spent on DOWN
# Returns the minimum profit across both outcomes (UP wins vs DOWN wins)
def calculate_worst_case_profit(up_shares: float, down_shares: float, 
                                 up_cost: float, down_cost: float) -> float:
    total_cost = up_cost + down_cost
    profit_if_up_wins = up_shares * 1.0 - total_cost
    profit_if_down_wins = down_shares * 1.0 - total_cost
    return min(profit_if_up_wins, profit_if_down_wins)


# calculate_average_profit
# up_shares: Number of UP shares owned
# down_shares: Number of DOWN shares owned
# up_cost: Total $ spent on UP
# down_cost: Total $ spent on DOWN
# up_price: Current market price for UP (used as probability weight)
# down_price: Current market price for DOWN (used as probability weight)
# bias_strength: Optional bias multiplier (0.0 to BIAS_MAX_STRENGTH) to favor likely winner
# likely_winner: Optional 'UP' or 'DOWN' to apply bias to
# Returns weighted average profit: (profit_if_up * prob_up) + (profit_if_down * prob_down)
# Where prob_up = up_price and prob_down = down_price (market's implied probabilities)
# If bias is provided, applies (1 + bias_strength) multiplier to the likely winner's profit
def calculate_average_profit(up_shares: float, down_shares: float,
                              up_cost: float, down_cost: float,
                              up_price: float, down_price: float,
                              bias_strength: float = 0.0,
                              likely_winner: str = None) -> float:
    total_cost = up_cost + down_cost
    profit_if_up_wins = up_shares * 1.0 - total_cost
    profit_if_down_wins = down_shares * 1.0 - total_cost
    
    # Apply bias to likely winner if provided
    if bias_strength > 0.0 and likely_winner:
        bias_multiplier = 1.0 + bias_strength
        if likely_winner == 'UP':
            profit_if_up_wins *= bias_multiplier
        elif likely_winner == 'DOWN':
            profit_if_down_wins *= bias_multiplier
    
    # Market prices represent implied probabilities
    prob_up = up_price
    prob_down = down_price
    
    # Weighted average (expected value)
    avg_profit = (profit_if_up_wins * prob_up) + (profit_if_down_wins * prob_down)
    return avg_profit


# check_if_safe
# up_shares: Number of UP shares owned
# down_shares: Number of DOWN shares owned
# up_cost: Total $ spent on UP
# down_cost: Total $ spent on DOWN
# Returns True if worst-case loss doesn't exceed MAX_LOSS
def check_if_safe(up_shares: float, down_shares: float,
                  up_cost: float, down_cost: float) -> bool:
    worst_case = calculate_worst_case_profit(up_shares, down_shares, up_cost, down_cost)
    return worst_case >= -MAX_LOSS


# check_if_safe_after_trade
# state: Current position state
# side: 'UP' or 'DOWN'
# shares: Number of shares to buy
# price: Price per share
# Simulates trade, returns True if position would still be safe after
def check_if_safe_after_trade(state: PositionState, side: str, 
                               shares: float, price: float) -> bool:
    new_up_shares = state.up_shares + (shares if side == 'UP' else 0)
    new_down_shares = state.down_shares + (shares if side == 'DOWN' else 0)
    new_up_cost = state.up_cost + (shares * price if side == 'UP' else 0)
    new_down_cost = state.down_cost + (shares * price if side == 'DOWN' else 0)
    
    return check_if_safe(new_up_shares, new_down_shares, new_up_cost, new_down_cost)
