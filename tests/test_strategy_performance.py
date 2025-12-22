import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from strategy import (
    PositionState,
    layer1_execute,
    layer2_execute
)


def create_test_state():
    """Create a typical position state for testing."""
    state = PositionState()
    state.market_start_time = 1000.0
    state.current_time = 1010.0  # 10 seconds into market
    state.up_shares = 15
    state.down_shares = 10
    state.up_cost = 7.5
    state.down_cost = 5.0
    return state


def benchmark_layer1():
    """Benchmark layer1_execute performance."""
    state = create_test_state()
    up_price = 0.45
    down_price = 0.55
    
    # Warmup
    for _ in range(10):
        layer1_execute(state, up_price, down_price)
    
    # Actual benchmark
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        layer1_execute(state, up_price, down_price)
    
    end = time.perf_counter()
    total_time = end - start
    avg_time = (total_time / iterations) * 1000  # Convert to milliseconds
    
    return total_time, avg_time, iterations


def benchmark_layer2():
    """Benchmark layer2_execute performance."""
    state = create_test_state()
    up_price = 0.45
    down_price = 0.55
    up_liquidity = 30
    down_liquidity = 30
    
    # Calculate averages
    avg_up = state.up_cost / state.up_shares if state.up_shares > 0 else 0.0
    avg_down = state.down_cost / state.down_shares if state.down_shares > 0 else 0.0
    
    # Warmup
    for _ in range(10):
        layer2_execute(state, up_price, down_price, up_liquidity, down_liquidity, avg_up, avg_down)
    
    # Actual benchmark
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        layer2_execute(state, up_price, down_price, up_liquidity, down_liquidity, avg_up, avg_down)
    
    end = time.perf_counter()
    total_time = end - start
    avg_time = (total_time / iterations) * 1000  # Convert to milliseconds
    
    return total_time, avg_time, iterations


def benchmark_both_layers():
    """Benchmark both layers together (realistic main.py scenario)."""
    state = create_test_state()
    up_price = 0.45
    down_price = 0.55
    up_liquidity = 30
    down_liquidity = 30
    
    # Calculate averages
    avg_up = state.up_cost / state.up_shares if state.up_shares > 0 else 0.0
    avg_down = state.down_cost / state.down_shares if state.down_shares > 0 else 0.0
    
    # Warmup
    for _ in range(10):
        layer1_execute(state, up_price, down_price)
        layer2_execute(state, up_price, down_price, up_liquidity, down_liquidity, avg_up, avg_down)
    
    # Actual benchmark
    iterations = 10000
    start = time.perf_counter()
    
    for _ in range(iterations):
        layer1_execute(state, up_price, down_price)
        layer2_execute(state, up_price, down_price, up_liquidity, down_liquidity, avg_up, avg_down)
    
    end = time.perf_counter()
    total_time = end - start
    avg_time = (total_time / iterations) * 1000  # Convert to milliseconds
    
    return total_time, avg_time, iterations


if __name__ == '__main__':
    print("=" * 60)
    print("STRATEGY PERFORMANCE BENCHMARK")
    print("=" * 60)
    print()
    
    # Layer 1
    print("Layer 1 (layer1_execute):")
    total, avg, iters = benchmark_layer1()
    print(f"  Iterations: {iters:,}")
    print(f"  Total time: {total:.4f} seconds")
    print(f"  Average per call: {avg:.4f} ms")
    print(f"  Calls per second: {iters / total:,.0f}")
    print()
    
    # Layer 2
    print("Layer 2 (layer2_execute):")
    total, avg, iters = benchmark_layer2()
    print(f"  Iterations: {iters:,}")
    print(f"  Total time: {total:.4f} seconds")
    print(f"  Average per call: {avg:.4f} ms")
    print(f"  Calls per second: {iters / total:,.0f}")
    print()
    
    # Both layers (realistic scenario)
    print("Both Layers (Layer 1 + Layer 2):")
    total, avg, iters = benchmark_both_layers()
    print(f"  Iterations: {iters:,}")
    print(f"  Total time: {total:.4f} seconds")
    print(f"  Average per tick: {avg:.4f} ms")
    print(f"  Ticks per second: {iters / total:,.0f}")
    print()
    
    print("=" * 60)
    print("INTERPRETATION:")
    print("=" * 60)
    print("Your bot runs every 2 seconds (TICK_INTERVAL_SEC = 2)")
    print("Each tick calls both Layer 1 and Layer 2")
    print("If average time << 2000ms, you have plenty of headroom")
    print("=" * 60)

