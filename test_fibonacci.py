#!/usr/bin/env python3
"""
Quick test for Fibonacci indicator implementation.
"""

import sys
import os
import numpy as np

# Add src to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.fibonacci_calculator import (
    calculate_fibonacci_retracement,
    calculate_fibonacci_extension,
    format_fibonacci_for_api,
    find_swing_points
)

def test_fibonacci_retracement():
    """Test Fibonacci retracement calculation."""
    print("=== Testing Fibonacci Retracement ===")
    
    # Test case: uptrend from 42000 to 45000
    high_price = 45000.0
    low_price = 42000.0
    
    retracement = calculate_fibonacci_retracement(high_price, low_price)
    
    print(f"Price range: ${low_price} to ${high_price}")
    print("Retracement levels:")
    for level, price in retracement.items():
        print(f"  {level}: ${price:.2f}")
    
    # Expected: 0.0% = 45000, 50.0% = 43500, 100.0% = 42000
    assert abs(retracement["0.0%"] - 45000.0) < 0.01
    assert abs(retracement["50.0%"] - 43500.0) < 0.01
    assert abs(retracement["100.0%"] - 42000.0) < 0.01
    print("✓ Retracement calculation correct")


def test_fibonacci_extension():
    """Test Fibonacci extension calculation."""
    print("\n=== Testing Fibonacci Extension ===")
    
    # Test case: A-B-C pattern
    point_a = 40000.0  # Starting low
    point_b = 45000.0  # Swing high  
    point_c = 43000.0  # Retracement
    
    extensions = calculate_fibonacci_extension(point_a, point_b, point_c)
    
    print(f"Pattern: A=${point_a} -> B=${point_b} -> C=${point_c}")
    print("Extension levels:")
    for level, price in extensions.items():
        print(f"  {level}: ${price:.2f}")
    
    # AB range = 5000, so 161.8% extension from C should be 43000 + (5000 * 1.618) = 51090
    expected_161_8 = point_c + (abs(point_b - point_a) * 1.618)
    assert abs(extensions["161.8%"] - expected_161_8) < 0.01
    print("✓ Extension calculation correct")


def test_swing_point_detection():
    """Test swing point detection."""
    print("\n=== Testing Swing Point Detection ===")
    
    # Create sample price data with clear swing points
    highs = np.array([100, 102, 105, 103, 101, 104, 108, 106, 104, 107, 110, 108, 106])
    lows = np.array([99, 100, 103, 101, 99, 102, 106, 104, 102, 105, 108, 106, 104])
    
    swing_highs, swing_lows = find_swing_points(highs, lows, window=2)
    
    print(f"Detected swing highs at indices: {swing_highs}")
    print(f"Detected swing lows at indices: {swing_lows}")
    print(f"Swing high prices: {[highs[i] for i in swing_highs]}")
    print(f"Swing low prices: {[lows[i] for i in swing_lows]}")
    
    # Should detect at least some swing points
    assert len(swing_highs) > 0, "Should detect at least one swing high"
    assert len(swing_lows) > 0, "Should detect at least one swing low"
    print("✓ Swing point detection working")


def test_api_format():
    """Test API formatting function."""
    print("\n=== Testing API Format Function ===")
    
    # Create sample data
    highs = np.array([44000, 44500, 45000, 44800, 44200, 44600, 45200, 44900, 44300])
    lows = np.array([43500, 44000, 44500, 44300, 43900, 44100, 44700, 44400, 43800])
    timestamps = [1704067200000 + i * 3600000 for i in range(len(highs))]
    
    result = format_fibonacci_for_api(highs, lows, timestamps, window=2)
    
    print("API Response structure:")
    print(f"  Indicator: {result.get('indicator')}")
    print(f"  Trend: {result.get('trend')}")
    print(f"  Swing High: {result.get('swing_high')}")
    print(f"  Swing Low: {result.get('swing_low')}")
    print(f"  Retracement levels count: {len(result.get('retracement_levels', []))}")
    print(f"  Extension levels count: {len(result.get('extension_levels', []))}")
    
    # Basic structure validation
    assert result["indicator"] == "FIBONACCI"
    assert "trend" in result
    assert "swing_high" in result
    assert "swing_low" in result
    assert "retracement_levels" in result
    print("✓ API format correct")


if __name__ == "__main__":
    print("Testing Fibonacci Implementation\n")
    
    try:
        test_fibonacci_retracement()
        test_fibonacci_extension()  
        test_swing_point_detection()
        test_api_format()
        
        print("\n🎉 All tests passed! Fibonacci implementation ready.")
        print("\nYou can now use the API endpoint:")
        print("GET /api/indicators/BTCUSDT?type=FIBONACCI&interval=1h&window=5")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)