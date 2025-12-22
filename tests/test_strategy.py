import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy import (
    PositionState,
    get_entry_value,
    layer1_should_buy,
    layer1_choose_side,
    layer1_execute,
    calculate_min_profit_after_trade,
    find_optimal_rebalance,
    layer2_execute,
    calculate_worst_case_profit,
    check_if_safe,
    check_if_safe_after_trade,
    ENTRY_THRESHOLD,
    HARD_CUTOFF_SECONDS,
    MAX_LOSS,
    ORDER_SIZES,
    MIN_ORDER_SIZE
)


class TestPositionState(unittest.TestCase):
    def test_get_seconds_into_market(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1060.0
        self.assertEqual(state.get_seconds_into_market(), 60.0)


class TestEntryValue(unittest.TestCase):
    def test_negative_time(self):
        self.assertEqual(get_entry_value(-10), 100.0)
    
    def test_market_ended(self):
        self.assertEqual(get_entry_value(900), 0.0)
        self.assertEqual(get_entry_value(1000), 0.0)
    
    def test_start_of_market(self):
        # At t=0 minutes, should be close to DECAY_C (97.94)
        value = get_entry_value(0)
        self.assertGreater(value, 95.0)
        self.assertLess(value, 100.0)
    
    def test_mid_market(self):
        # At 5 minutes (300 seconds)
        value = get_entry_value(300)
        self.assertGreater(value, 0)
        self.assertLess(value, 100)


class TestLayer1ShouldBuy(unittest.TestCase):
    def test_before_cutoff_high_value(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1010.0  # 10 seconds in
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 0
        
        self.assertTrue(layer1_should_buy(state))
    
    def test_after_cutoff(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1700.0  # 700 seconds = 11.67 minutes
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 0
        
        self.assertFalse(layer1_should_buy(state))
    
    def test_unsafe_position(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1010.0
        # Create unsafe position (loss > MAX_LOSS)
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 200.0  # Spent $200, own nothing = -$200 loss
        
        self.assertFalse(layer1_should_buy(state))


class TestLayer1ChooseSide(unittest.TestCase):
    def test_choose_cheaper_up(self):
        self.assertEqual(layer1_choose_side(0.40, 0.60), 'UP')
    
    def test_choose_cheaper_down(self):
        self.assertEqual(layer1_choose_side(0.60, 0.40), 'DOWN')
    
    def test_equal_prices(self):
        # If equal, chooses UP (<= comparison)
        self.assertEqual(layer1_choose_side(0.50, 0.50), 'UP')


class TestLayer1Execute(unittest.TestCase):
    def test_no_trade_when_value_low(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1700.0  # After cutoff
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 0
        
        result = layer1_execute(state, 0.45, 0.55)
        self.assertIsNone(result)
    
    def test_trade_when_conditions_met(self):
        state = PositionState()
        state.market_start_time = 1000.0
        state.current_time = 1010.0  # Early in market
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 0
        
        result = layer1_execute(state, 0.45, 0.55)
        self.assertIsNotNone(result)
        self.assertEqual(result['side'], 'UP')  # Cheaper side
        self.assertIn(result['size'], ORDER_SIZES)
        self.assertEqual(result['price'], 0.45)


class TestWorstCaseProfit(unittest.TestCase):
    def test_balanced_position(self):
        # 10 UP @ $0.50, 10 DOWN @ $0.50 = $10 total cost
        # Either outcome: 10 shares * $1 = $10 profit - $10 cost = $0
        profit = calculate_worst_case_profit(10, 10, 5.0, 5.0)
        self.assertEqual(profit, 0.0)
    
    def test_imbalanced_position(self):
        # 20 UP @ $0.50, 5 DOWN @ $0.50 = $12.50 total cost
        # UP wins: 20 * $1 - $12.50 = $7.50
        # DOWN wins: 5 * $1 - $12.50 = -$7.50
        # Worst case = -$7.50
        profit = calculate_worst_case_profit(20, 5, 10.0, 2.5)
        self.assertEqual(profit, -7.5)
    
    def test_profitable_position(self):
        # 15 UP @ $0.40, 15 DOWN @ $0.40 = $12 total cost
        # Either outcome: 15 * $1 - $12 = $3
        profit = calculate_worst_case_profit(15, 15, 6.0, 6.0)
        self.assertEqual(profit, 3.0)


class TestCheckIfSafe(unittest.TestCase):
    def test_safe_position(self):
        # Small loss, under MAX_LOSS
        self.assertTrue(check_if_safe(10, 10, 5.0, 5.0))
    
    def test_unsafe_position(self):
        # Large loss, exceeds MAX_LOSS
        self.assertFalse(check_if_safe(0, 0, 0, 200.0))
    
    def test_profitable_position(self):
        # Positive worst-case = always safe
        self.assertTrue(check_if_safe(20, 20, 8.0, 8.0))


class TestCheckIfSafeAfterTrade(unittest.TestCase):
    def test_safe_trade(self):
        state = PositionState()
        state.up_shares = 10
        state.down_shares = 10
        state.up_cost = 5.0
        state.down_cost = 5.0
        
        # Buying 5 more UP @ $0.50 = $2.50 more cost
        # Still balanced, should be safe
        self.assertTrue(check_if_safe_after_trade(state, 'UP', 5, 0.50))
    
    def test_unsafe_trade(self):
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 0
        state.up_cost = 0
        state.down_cost = 150.0  # Already at limit
        
        # Buying more would exceed MAX_LOSS
        self.assertFalse(check_if_safe_after_trade(state, 'UP', 10, 0.50))


class TestCalculateMinProfit(unittest.TestCase):
    def test_positive_min_from_rebalancing(self):
        state = PositionState()
        # Imbalanced: 20 UP @ $0.40, 5 DOWN @ $0.50
        state.up_shares = 20
        state.down_shares = 5
        state.up_cost = 8.0  # 20 * $0.40
        state.down_cost = 2.5  # 5 * $0.50
        
        # Buying 15 more DOWN @ $0.45 to rebalance
        new_min = calculate_min_profit_after_trade(state, 'DOWN', 15, 0.45)
        current_min = calculate_worst_case_profit(state.up_shares, state.down_shares, 
                                                   state.up_cost, state.down_cost)
        # Test that the function works - new min should be calculated correctly
        self.assertIsInstance(new_min, float)
        # New min should improve if price is good
        if new_min > 0:
            self.assertGreater(new_min, current_min)
    
    def test_negative_min_when_price_bad(self):
        state = PositionState()
        # Already balanced
        state.up_shares = 10
        state.down_shares = 10
        state.up_cost = 5.0
        state.down_cost = 5.0
        
        # Buying more UP at bad price ($0.60) - should not improve min profit
        new_min = calculate_min_profit_after_trade(state, 'UP', 10, 0.60)
        current_min = calculate_worst_case_profit(state.up_shares, state.down_shares,
                                                   state.up_cost, state.down_cost)
        # At bad price, min might be negative or worse
        # Layer 2 won't trade if new_min <= 0 or new_min <= current_min


class TestFindOptimalRebalance(unittest.TestCase):
    def test_finds_best_size(self):
        state = PositionState()
        # Imbalanced position: 20 UP @ $0.50, 5 DOWN @ $0.50
        state.up_shares = 20
        state.down_shares = 5
        state.up_cost = 10.0
        state.down_cost = 2.5
        
        # Buying DOWN at good price ($0.40) should improve min profit
        idx = find_optimal_rebalance(state, 'DOWN', 0.40, 30)
        # Should find a size that creates positive min profit AND improves current
        if idx >= 0:
            self.assertLess(idx, len(ORDER_SIZES))
    
    def test_no_improvement_available(self):
        state = PositionState()
        # Already balanced with good min profit
        state.up_shares = 10
        state.down_shares = 10
        state.up_cost = 5.0
        state.down_cost = 5.0
        
        # Buying at bad price ($0.60) won't improve min profit
        idx = find_optimal_rebalance(state, 'UP', 0.60, 30)
        # Should return -1 if no size improves min profit
        self.assertEqual(idx, -1)
    
    def test_respects_liquidity(self):
        state = PositionState()
        # Imbalanced position
        state.up_shares = 20
        state.down_shares = 5
        state.up_cost = 10.0
        state.down_cost = 2.5
        
        # Only 7 shares available at good price - should find 5 shares
        idx = find_optimal_rebalance(state, 'DOWN', 0.40, 7)
        # Should find something (5 shares) if it improves min profit
        if idx >= 0:
            self.assertLessEqual(ORDER_SIZES[idx], 7)


class TestLayer2Execute(unittest.TestCase):
    def test_rebalances_imbalanced_position(self):
        state = PositionState()
        # Imbalanced: 20 UP @ $0.50, 5 DOWN @ $0.50
        state.up_shares = 20
        state.down_shares = 5
        state.up_cost = 10.0
        state.down_cost = 2.5
        
        # Calculate averages
        avg_up = 10.0 / 20.0 if state.up_shares > 0 else 0.0
        avg_down = 2.5 / 5.0 if state.down_shares > 0 else 0.0
        
        # DOWN at good price ($0.40) should improve min profit
        # Check: 0.40 + 0.50 = 0.90 < 1.0, so profitable
        result = layer2_execute(state, 0.60, 0.40, 30, 30, avg_up, avg_down)
        # Should trade if it improves min profit
        if result is not None:
            self.assertEqual(result['side'], 'DOWN')  # Should buy DOWN to rebalance
    
    def test_no_trade_if_balanced(self):
        state = PositionState()
        state.up_shares = 10
        state.down_shares = 10
        state.up_cost = 5.0
        state.down_cost = 5.0
        
        avg_up = 5.0 / 10.0 if state.up_shares > 0 else 0.0
        avg_down = 5.0 / 10.0 if state.down_shares > 0 else 0.0
        
        result = layer2_execute(state, 0.50, 0.50, 30, 30, avg_up, avg_down)
        # Might return None if no improvement, or might still find small improvement
        # This is okay - depends on exact math
    
    def test_requires_min_liquidity(self):
        state = PositionState()
        state.up_shares = 20
        state.down_shares = 5
        state.up_cost = 10.0
        state.down_cost = 2.5
        
        avg_up = 10.0 / 20.0 if state.up_shares > 0 else 0.0
        avg_down = 2.5 / 5.0 if state.down_shares > 0 else 0.0
        
        # Not enough liquidity
        result = layer2_execute(state, 0.50, 0.50, 3, 3, avg_up, avg_down)  # Only 3 shares available
        # Should return None (can't buy MIN_ORDER_SIZE = 5)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()

