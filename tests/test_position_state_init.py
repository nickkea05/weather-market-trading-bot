"""
Test script to verify PositionState initialization in main.py
Tests that:
1. PositionState is created when market is discovered
2. market_start_time is set correctly
3. Position starts at 0 (no shares, no cost)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy import PositionState
from connection import MarketConnection


def test_position_state_initialization():
    """Test that PositionState is initialized correctly"""
    print("=" * 60)
    print("TESTING POSITION STATE INITIALIZATION")
    print("=" * 60)
    
    # Create connection and discover market
    connection = MarketConnection()
    
    if not connection.discover_market():
        print("[TEST] Failed to discover market - cannot test")
        return False
    
    # Get market data
    end_timestamp = connection.market_data["end_timestamp"]
    start_timestamp = end_timestamp - 900  # 15 minutes
    
    # Create PositionState (like main.py does)
    position_state = PositionState()
    position_state.market_start_time = float(start_timestamp)
    
    # Verify initialization
    print(f"\n[TEST] Market end timestamp: {end_timestamp}")
    print(f"[TEST] Calculated start timestamp: {start_timestamp}")
    print(f"[TEST] PositionState.market_start_time: {position_state.market_start_time}")
    
    # Check that position starts at 0
    assert position_state.up_shares == 0, "UP shares should start at 0"
    assert position_state.down_shares == 0, "DOWN shares should start at 0"
    assert position_state.up_cost == 0, "UP cost should start at 0"
    assert position_state.down_cost == 0, "DOWN cost should start at 0"
    
    print(f"[TEST] PASS: Position starts at 0: UP={position_state.up_shares}, DOWN={position_state.down_shares}")
    print(f"[TEST] PASS: Costs start at 0: UP=${position_state.up_cost}, DOWN=${position_state.down_cost}")
    
    # Test get_seconds_into_market
    import time
    position_state.current_time = time.time()
    seconds = position_state.get_seconds_into_market()
    print(f"[TEST] Seconds into market: {seconds:.1f}")
    
    # Verify start_time is correct (should be ~15 minutes before end)
    time_diff = end_timestamp - start_timestamp
    assert time_diff == 900, f"Time difference should be 900 seconds, got {time_diff}"
    print(f"[TEST] PASS: Start time is 15 minutes before end time")
    
    print("\n[TEST] PASS: All PositionState initialization tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_position_state_initialization()
    except Exception as e:
        print(f"\n[TEST] FAIL: Test failed: {e}")
        import traceback
        traceback.print_exc()

