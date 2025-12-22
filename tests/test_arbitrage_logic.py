import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy import (
    PositionState,
    find_optimal_rebalance,
    layer2_execute,
    calculate_worst_case_profit,
    MAX_AMOUNT_PER_TRADE,
    MIN_ORDER_AMOUNT,
    MAX_LOSS
)


class TestArbitrageLogic(unittest.TestCase):
    """Test that arbitrage logic correctly identifies profitable trades"""
    
    def test_buy_up_with_down_shares_arbitrage_pass(self):
        """Buying UP when we have DOWN shares - arbitrage check passes"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100  # We have DOWN shares
        state.up_cost = 0
        state.down_cost = 50.0  # avg_down = 0.50
        
        # Buying UP at $0.40: 0.40 + 0.50 = 0.90 < 1.0 ✓ (arbitrage!)
        avg_up = 0.0
        avg_down = 0.50
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.40, 1000, avg_up, avg_down
        )
        
        # Should find a trade (arbitrage exists and should improve worst case)
        self.assertIsNotNone(amount, "Should find trade when arbitrage exists")
        self.assertGreater(new_min, calculate_worst_case_profit(
            state.up_shares, state.down_shares, state.up_cost, state.down_cost
        ), "Should improve worst case profit")
    
    def test_buy_up_with_down_shares_arbitrage_fail(self):
        """Buying UP when we have DOWN shares - arbitrage check fails"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100
        state.up_cost = 0
        state.down_cost = 50.0  # avg_down = 0.50
        
        # Buying UP at $0.60: 0.60 + 0.50 = 1.10 >= 1.0 ✗ (no arbitrage!)
        avg_up = 0.0
        avg_down = 0.50
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.60, 1000, avg_up, avg_down
        )
        
        # Should NOT find a trade (no arbitrage)
        self.assertIsNone(amount, "Should NOT find trade when no arbitrage exists")
    
    def test_buy_down_with_up_shares_arbitrage_pass(self):
        """Buying DOWN when we have UP shares - arbitrage check passes"""
        state = PositionState()
        state.up_shares = 100  # We have UP shares
        state.down_shares = 0
        state.up_cost = 45.0  # avg_up = 0.45
        state.down_cost = 0
        
        # Buying DOWN at $0.50: 0.50 + 0.45 = 0.95 < 1.0 ✓ (arbitrage!)
        avg_up = 0.45
        avg_down = 0.0
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'DOWN', 0.50, 1000, avg_up, avg_down
        )
        
        # Should find a trade
        self.assertIsNotNone(amount, "Should find trade when arbitrage exists")
    
    def test_buy_down_with_up_shares_arbitrage_fail(self):
        """Buying DOWN when we have UP shares - arbitrage check fails"""
        state = PositionState()
        state.up_shares = 100
        state.down_shares = 0
        state.up_cost = 60.0  # avg_up = 0.60
        state.down_cost = 0
        
        # Buying DOWN at $0.50: 0.50 + 0.60 = 1.10 >= 1.0 ✗ (no arbitrage!)
        avg_up = 0.60
        avg_down = 0.0
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'DOWN', 0.50, 1000, avg_up, avg_down
        )
        
        # Should NOT find a trade
        self.assertIsNone(amount, "Should NOT find trade when no arbitrage exists")
    
    def test_buy_up_no_down_shares_allowed(self):
        """Buying UP when we have NO DOWN shares - should be allowed (no arb check)"""
        state = PositionState()
        state.up_shares = 50  # Only UP shares
        state.down_shares = 0  # No DOWN shares
        state.up_cost = 25.0
        state.down_cost = 0
        
        # Should be allowed to buy more UP (creating position, not rebalancing)
        avg_up = 0.50
        avg_down = 0.0
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.40, 1000, avg_up, avg_down
        )
        
        # Should find a trade if it improves worst case (no arb check needed)
        # Note: This might return None if it doesn't improve worst case
        # But the key is it's not blocked by arbitrage check
    
    def test_buy_down_no_up_shares_allowed(self):
        """Buying DOWN when we have NO UP shares - should be allowed (no arb check)"""
        state = PositionState()
        state.up_shares = 0  # No UP shares
        state.down_shares = 50  # Only DOWN shares
        state.up_cost = 0
        state.down_cost = 25.0
        
        avg_up = 0.0
        avg_down = 0.50
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'DOWN', 0.40, 1000, avg_up, avg_down
        )
        
        # Should be allowed (no arb check when no opposite shares)
    
    def test_arbitrage_exactly_one_dollar_fails(self):
        """Arbitrage check: exactly $1.00 should fail (needs to be < 1.0)"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100
        state.up_cost = 0
        state.down_cost = 50.0  # avg_down = 0.50
        
        # Buying UP at $0.50: 0.50 + 0.50 = 1.00 (exactly 1.0, should fail)
        avg_up = 0.0
        avg_down = 0.50
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.50, 1000, avg_up, avg_down
        )
        
        # Should NOT find trade (1.00 >= 1.0)
        self.assertIsNone(amount, "Exactly $1.00 should fail arbitrage check")
    
    def test_arbitrage_slightly_below_one_dollar_passes(self):
        """Arbitrage check: $0.999 should pass"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100
        state.up_cost = 0
        state.down_cost = 49.95  # avg_down = 0.4995
        
        # Buying UP at $0.50: 0.50 + 0.4995 = 0.9995 < 1.0 ✓
        avg_up = 0.0
        avg_down = 0.4995
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.50, 1000, avg_up, avg_down
        )
        
        # Should find trade if it improves worst case
        # (Might be None if it doesn't improve worst case, but not blocked by arb check)
    
    def test_layer2_execute_respects_arbitrage(self):
        """layer2_execute should respect arbitrage logic"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100
        state.up_cost = 0
        state.down_cost = 50.0  # avg_down = 0.50
        
        # UP at $0.40: 0.40 + 0.50 = 0.90 < 1.0 ✓ (arbitrage!)
        # DOWN at $0.60: 0.60 + 0.00 = 0.60 < 1.0 but no UP shares, so no arb check
        
        result = layer2_execute(state, 0.40, 0.60, 1000, 1000)
        
        # Should trade UP side (has arbitrage)
        if result is not None:
            self.assertEqual(result['side'], 'UP')
    
    def test_layer2_execute_rejects_no_arbitrage(self):
        """layer2_execute should reject trades without arbitrage"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 100
        state.up_cost = 0
        state.down_cost = 50.0  # avg_down = 0.50
        
        # UP at $0.60: 0.60 + 0.50 = 1.10 >= 1.0 ✗ (no arbitrage!)
        # DOWN at $0.40: 0.40 + 0.00 = 0.40 but no UP shares
        
        result = layer2_execute(state, 0.60, 0.40, 1000, 1000)
        
        # Should NOT trade UP (no arbitrage)
        # Might trade DOWN if it improves worst case (no arb check when no opposite shares)
        if result is not None:
            self.assertNotEqual(result['side'], 'UP', "Should not trade UP without arbitrage")
    
    def test_arbitrage_must_also_improve_worst_case(self):
        """Even with arbitrage, must improve worst case profit"""
        state = PositionState()
        state.up_shares = 10
        state.down_shares = 10
        state.up_cost = 5.0  # avg_up = 0.50
        state.down_cost = 5.0  # avg_down = 0.50
        
        # Current worst case: min(10*1 - 10, 10*1 - 10) = 0
        # Buying UP at $0.40: 0.40 + 0.50 = 0.90 < 1.0 ✓ (arbitrage!)
        # But if buying more UP doesn't improve worst case, should not trade
        
        avg_up = 0.50
        avg_down = 0.50
        
        # Try buying UP - might not improve worst case if already balanced
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.40, 1000, avg_up, avg_down
        )
        
        # If amount is found, it must improve worst case
        if amount is not None:
            current_min = calculate_worst_case_profit(
                state.up_shares, state.down_shares, state.up_cost, state.down_cost
            )
            self.assertGreater(new_min, current_min, "Must improve worst case profit")
    
    def test_realistic_scenario_1(self):
        """Realistic scenario: Rebalancing with arbitrage"""
        state = PositionState()
        state.up_shares = 200
        state.down_shares = 100  # Imbalanced
        state.up_cost = 100.0  # avg_up = 0.50
        state.down_cost = 45.0  # avg_down = 0.45
        
        # Buying DOWN at $0.40: 0.40 + 0.50 = 0.90 < 1.0 ✓ (arbitrage!)
        avg_up = 0.50
        avg_down = 0.45
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'DOWN', 0.40, 1000, avg_up, avg_down
        )
        
        # Should find trade (arbitrage + should improve worst case by rebalancing)
        self.assertIsNotNone(amount, "Should find rebalancing trade with arbitrage")
    
    def test_realistic_scenario_2(self):
        """Realistic scenario: No arbitrage, should not trade"""
        state = PositionState()
        state.up_shares = 200
        state.down_shares = 100
        state.up_cost = 100.0  # avg_up = 0.50
        state.down_cost = 45.0  # avg_down = 0.45
        
        # Buying DOWN at $0.60: 0.60 + 0.50 = 1.10 >= 1.0 ✗ (no arbitrage!)
        avg_up = 0.50
        avg_down = 0.45
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'DOWN', 0.60, 1000, avg_up, avg_down
        )
        
        # Should NOT find trade (no arbitrage)
        self.assertIsNone(amount, "Should NOT trade without arbitrage")
    
    def test_replay_scenario_layer2_first_trade(self):
        """Test scenario from replay: First Layer 2 trade (UP at $0.55 with DOWN at $0.45 avg)"""
        state = PositionState()
        # After several DOWN trades, we have:
        state.up_shares = 0
        state.down_shares = 226.93  # From replay
        state.up_cost = 0
        state.down_cost = 100.0  # avg_down = 100/226.93 ≈ 0.441
        
        # UP at $0.55: 0.55 + 0.441 = 0.991 < 1.0 ✓ (arbitrage!)
        avg_up = 0.0
        avg_down = 0.441
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.55, 1000, avg_up, avg_down
        )
        
        # Should find trade (arbitrage exists)
        self.assertIsNotNone(amount, "Should find Layer 2 trade with arbitrage")
        self.assertGreater(new_min, calculate_worst_case_profit(
            state.up_shares, state.down_shares, state.up_cost, state.down_cost
        ), "Should improve worst case")
    
    def test_debug_output_scenario(self):
        """Test the exact scenario from debug output where arb check passed"""
        state = PositionState()
        state.up_shares = 0
        state.down_shares = 226.93
        state.up_cost = 0
        state.down_cost = 100.0  # avg_down ≈ 0.441
        
        # From debug: "UP trade arb: $0.550 + $0.441 = $0.991 PASS"
        avg_up = 0.0
        avg_down = 0.441
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.55, 1000, avg_up, avg_down
        )
        
        # This should definitely work
        self.assertIsNotNone(amount, "Debug showed arb passed, should find trade")
        print(f"\n[TEST] Found trade: ${amount:.2f}, new_min: ${new_min:.2f}")
    
    def test_arbitrage_passes_but_worst_case_doesnt_improve(self):
        """Test case where arbitrage passes but worst case doesn't improve"""
        state = PositionState()
        # Already have a good balanced position
        state.up_shares = 100
        state.down_shares = 100
        state.up_cost = 50.0  # avg_up = 0.50
        state.down_cost = 50.0  # avg_down = 0.50
        
        # Current worst case: min(100*1 - 100, 100*1 - 100) = 0
        # Buying more UP at $0.40: 0.40 + 0.50 = 0.90 < 1.0 ✓ (arbitrage!)
        # But does it improve worst case?
        # New: 150 UP @ $0.40 avg, 100 DOWN @ $0.50 avg
        # New worst case: min(150*1 - 110, 100*1 - 110) = min(40, -10) = -10
        # This would make worst case WORSE, so should not trade
        
        avg_up = 0.50
        avg_down = 0.50
        
        amount, new_min, new_best = find_optimal_rebalance(
            state, 'UP', 0.40, 1000, avg_up, avg_down
        )
        
        # Should NOT trade even though arbitrage exists (doesn't improve worst case)
        # Actually, let me recalculate - if we buy $18 of UP at $0.40, that's 45 shares
        # New: 145 UP @ (50+18)/145 = 0.469, 100 DOWN @ 0.50
        # New worst case: min(145*1 - 118, 100*1 - 118) = min(27, -18) = -18
        # So worst case goes from 0 to -18, which is worse
        
        # But wait, the function tries different amounts. Let me check if a smaller amount improves it.
        # Actually, the function should find the amount that maximizes worst case improvement
        # If no amount improves it, should return None
        
        # This test verifies that arbitrage alone isn't enough
        current_min = calculate_worst_case_profit(
            state.up_shares, state.down_shares, state.up_cost, state.down_cost
        )
        
        if amount is not None:
            # If it found a trade, it must improve worst case
            self.assertGreater(new_min, current_min, 
                             "If trade found, must improve worst case even with arbitrage")
        else:
            # If no trade found, that's okay - arbitrage exists but doesn't improve worst case
            print(f"\n[TEST] No trade found - arbitrage exists but doesn't improve worst case")


if __name__ == '__main__':
    unittest.main()

