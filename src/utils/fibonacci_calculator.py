"""
Fibonacci Retracement and Extension Calculator

This module provides functions to calculate Fibonacci retracement and extension levels
for technical analysis in trading applications.

Since TA-Lib does not include Fibonacci functions, this provides a custom implementation.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# Standard Fibonacci ratios
FIBONACCI_RETRACEMENT_LEVELS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
FIBONACCI_EXTENSION_LEVELS = [1.0, 1.236, 1.382, 1.5, 1.618, 2.0, 2.618]


def find_swing_points(highs: np.ndarray, lows: np.ndarray, window: int = 5) -> Tuple[List[int], List[int]]:
    """
    Find swing high and low points in price data.
    
    Args:
        highs: Array of high prices
        lows: Array of low prices  
        window: Number of periods to look back/forward for confirmation
        
    Returns:
        Tuple of (swing_high_indices, swing_low_indices)
    """
    swing_highs = []
    swing_lows = []
    
    for i in range(window, len(highs) - window):
        # Check for swing high
        is_swing_high = True
        for j in range(i - window, i + window + 1):
            if j != i and highs[j] >= highs[i]:
                is_swing_high = False
                break
        if is_swing_high:
            swing_highs.append(i)
            
        # Check for swing low  
        is_swing_low = True
        for j in range(i - window, i + window + 1):
            if j != i and lows[j] <= lows[i]:
                is_swing_low = False
                break
        if is_swing_low:
            swing_lows.append(i)
    
    return swing_highs, swing_lows


def calculate_fibonacci_retracement(high_price: float, low_price: float, 
                                  levels: List[float] = None) -> Dict[str, float]:
    """
    Calculate Fibonacci retracement levels for a price move.
    
    Args:
        high_price: The swing high price
        low_price: The swing low price  
        levels: Custom Fibonacci levels (default: standard retracement levels)
        
    Returns:
        Dictionary with level percentages as keys and price levels as values
    """
    if levels is None:
        levels = FIBONACCI_RETRACEMENT_LEVELS
        
    price_range = high_price - low_price
    fib_levels = {}
    
    for level in levels:
        if high_price > low_price:  # Uptrend retracement
            price_level = high_price - (price_range * level)
        else:  # Downtrend retracement  
            price_level = low_price + (abs(price_range) * level)
            
        fib_levels[f"{level:.1%}"] = round(price_level, 8)
    
    return fib_levels


def calculate_fibonacci_extension(point_a: float, point_b: float, point_c: float,
                                levels: List[float] = None) -> Dict[str, float]:
    """
    Calculate Fibonacci extension levels for a 3-point move (A-B-C pattern).
    
    Args:
        point_a: Starting price point
        point_b: Intermediate price point (swing high/low)
        point_c: Current retracement point
        levels: Custom Fibonacci extension levels
        
    Returns:
        Dictionary with level percentages as keys and projected price levels as values
    """
    if levels is None:
        levels = FIBONACCI_EXTENSION_LEVELS
        
    ab_range = abs(point_b - point_a)
    fib_extensions = {}
    
    for level in levels:
        if point_b > point_a:  # Upward move, project from point C
            extension_level = point_c + (ab_range * level)
        else:  # Downward move, project from point C
            extension_level = point_c - (ab_range * level)
            
        fib_extensions[f"{level:.1%}"] = round(extension_level, 8)
    
    return fib_extensions


def get_recent_swing_points(highs: np.ndarray, lows: np.ndarray, 
                          timestamps: List[int], window: int = 5, 
                          max_points: int = 10) -> Dict:
    """
    Get the most recent swing points for Fibonacci analysis.
    
    Args:
        highs: Array of high prices
        lows: Array of low prices
        timestamps: Array of timestamps
        window: Swing detection window
        max_points: Maximum number of swing points to return
        
    Returns:
        Dictionary containing recent swing highs and lows with timestamps
    """
    swing_high_indices, swing_low_indices = find_swing_points(highs, lows, window)
    
    # Get recent swing points
    recent_highs = []
    for idx in swing_high_indices[-max_points:]:
        recent_highs.append({
            "timestamp": timestamps[idx],
            "index": idx,
            "price": float(highs[idx])
        })
    
    recent_lows = []
    for idx in swing_low_indices[-max_points:]:
        recent_lows.append({
            "timestamp": timestamps[idx], 
            "index": idx,
            "price": float(lows[idx])
        })
    
    return {
        "swing_highs": recent_highs,
        "swing_lows": recent_lows
    }


def calculate_auto_fibonacci(highs: np.ndarray, lows: np.ndarray, 
                           timestamps: List[int], window: int = 5) -> Dict:
    """
    Automatically calculate Fibonacci levels based on recent swing points.
    
    Args:
        highs: Array of high prices
        lows: Array of low prices  
        timestamps: Array of timestamps
        window: Swing detection window
        
    Returns:
        Dictionary containing Fibonacci retracement and extension levels
    """
    try:
        swing_high_indices, swing_low_indices = find_swing_points(highs, lows, window)
        
        if len(swing_high_indices) < 1 or len(swing_low_indices) < 1:
            return {"error": "Insufficient swing points found"}
        
        # Get most recent significant swing high and low
        latest_high_idx = swing_high_indices[-1]
        latest_low_idx = swing_low_indices[-1]
        
        latest_high = float(highs[latest_high_idx])
        latest_low = float(lows[latest_low_idx])
        
        # Determine trend direction based on which is more recent
        if latest_high_idx > latest_low_idx:
            # Recent high after low - potential uptrend
            trend = "uptrend"
            retracement_levels = calculate_fibonacci_retracement(latest_high, latest_low)
        else:
            # Recent low after high - potential downtrend  
            trend = "downtrend"
            retracement_levels = calculate_fibonacci_retracement(latest_low, latest_high)
        
        # Calculate extensions if we have enough points
        extensions = {}
        if len(swing_high_indices) >= 2 and len(swing_low_indices) >= 2:
            try:
                if trend == "uptrend" and len(swing_low_indices) >= 2:
                    # A-B-C pattern: previous low -> high -> current low  
                    prev_low_idx = swing_low_indices[-2]
                    point_a = float(lows[prev_low_idx])
                    point_b = latest_high
                    point_c = latest_low
                    extensions = calculate_fibonacci_extension(point_a, point_b, point_c)
                elif trend == "downtrend" and len(swing_high_indices) >= 2:
                    # A-B-C pattern: previous high -> low -> current high
                    prev_high_idx = swing_high_indices[-2] 
                    point_a = float(highs[prev_high_idx])
                    point_b = latest_low
                    point_c = latest_high
                    extensions = calculate_fibonacci_extension(point_a, point_b, point_c)
            except Exception as e:
                logger.warning(f"Could not calculate extensions: {e}")
                extensions = {}
        
        return {
            "trend": trend,
            "swing_high": {
                "price": latest_high,
                "timestamp": timestamps[latest_high_idx],
                "index": latest_high_idx
            },
            "swing_low": {
                "price": latest_low, 
                "timestamp": timestamps[latest_low_idx],
                "index": latest_low_idx
            },
            "retracement_levels": retracement_levels,
            "extension_levels": extensions,
            "calculation_timestamp": timestamps[-1] if timestamps else None
        }
        
    except Exception as e:
        logger.error(f"Error calculating auto Fibonacci: {e}")
        return {"error": str(e)}


def format_fibonacci_for_api(highs: np.ndarray, lows: np.ndarray, 
                           timestamps: List[int], window: int = 5) -> Dict:
    """
    Format Fibonacci calculations for API response matching existing indicator pattern.
    
    Args:
        highs: Array of high prices
        lows: Array of low prices
        timestamps: Array of timestamps  
        window: Swing detection window
        
    Returns:
        API-formatted dictionary with Fibonacci levels
    """
    fibonacci_data = calculate_auto_fibonacci(highs, lows, timestamps, window)
    
    if "error" in fibonacci_data:
        return fibonacci_data
    
    # Format retracement levels for API
    retracement_values = []
    for level_pct, price in fibonacci_data["retracement_levels"].items():
        retracement_values.append({
            "level": level_pct,
            "price": price,
            "timestamp": fibonacci_data["calculation_timestamp"]
        })
    
    # Format extension levels for API  
    extension_values = []
    for level_pct, price in fibonacci_data["extension_levels"].items():
        extension_values.append({
            "level": level_pct,
            "price": price,
            "timestamp": fibonacci_data["calculation_timestamp"]
        })
    
    return {
        "indicator": "FIBONACCI",
        "trend": fibonacci_data["trend"],
        "swing_high": fibonacci_data["swing_high"],
        "swing_low": fibonacci_data["swing_low"], 
        "retracement_levels": retracement_values,
        "extension_levels": extension_values,
        "window": window
    }