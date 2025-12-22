"""Diagnostic test to check arbitrage logic in replay scenarios"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy import (
    PositionState,
    find_optimal_rebalance,
    layer2_execute,
    calculate_worst_case_profit
)


def test_diagnostic_scenario():
    """Diagnostic test - prints detailed output for debugging"""
    print("\n" + "="*80)
    print("DIAGNOSTIC TEST: Checking arbitrage logic")
    print("="*80)
    
    # Scenario from replay: After 6 DOWN trades, trying to buy UP
    state = PositionState()
    state.up_shares = 0
    state.down_shares = 226.93
    state.up_cost = 0
    state.down_cost = 100.0
    
    # Calculate averages
    avg_up = state.up_cost / state.up_shares if state.up_shares > 0 else 0.0
    avg_down = state.down_cost / state.down_shares if state.down_shares > 0 else 0.0
    
    print(f"\nPosition State:")
    print(f"  UP: {state.up_shares:.2f} shares, ${state.up_cost:.2f} cost")
    print(f"  DOWN: {state.down_shares:.2f} shares, ${state.down_cost:.2f} cost")
    print(f"  Avg UP: ${avg_up:.3f}")
    print(f"  Avg DOWN: ${avg_down:.3f}")
    
    current_min = calculate_worst_case_profit(
        state.up_shares, state.down_shares, state.up_cost, state.down_cost
    )
    print(f"  Current Worst Case: ${current_min:.2f}")
    
    # Test buying UP at $0.55
    up_price = 0.55
    print(f"\nTesting: Buy UP at ${up_price:.3f}")
    print(f"  Arbitrage check: ${up_price:.3f} + ${avg_down:.3f} = ${up_price + avg_down:.3f}")
    
    if state.down_shares > 0 and avg_down > 0:
        arb_passes = (up_price + avg_down) < 1.0
        print(f"  Arbitrage: {'PASS' if arb_passes else 'FAIL'}")
    else:
        print(f"  Arbitrage: N/A (no opposite shares)")
        arb_passes = True  # No check needed
    
    # Try to find optimal rebalance
    amount, new_min, new_best = find_optimal_rebalance(
        state, 'UP', up_price, 1000, avg_up, avg_down
    )
    
    print(f"\nResult from find_optimal_rebalance:")
    if amount is not None:
        print(f"  [PASS] Found trade: ${amount:.2f}")
        print(f"  New worst case: ${new_min:.2f} (improvement: ${new_min - current_min:.2f})")
        print(f"  New best case: ${new_best:.2f}")
    else:
        print(f"  [FAIL] No trade found")
        print(f"  Reason: Either no arbitrage OR doesn't improve worst case")
    
    # Test with layer2_execute
    print(f"\nTesting with layer2_execute:")
    result = layer2_execute(state, up_price, 0.45, 1000, 1000)
    
    if result is not None:
        print(f"  [PASS] Layer 2 would trade: {result['side']} {result['size']:.2f} shares @ ${result['price']:.3f} = ${result['amount']:.2f}")
    else:
        print(f"  [FAIL] Layer 2 would NOT trade")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    test_diagnostic_scenario()

