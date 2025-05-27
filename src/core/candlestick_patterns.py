import numpy as np
import pandas as pd
import talib
from typing import Dict, List, Tuple, Optional

class CandlestickPatternAnalyzer:
    """Class for analyzing candlestick patterns using TA-Lib"""
    
    def __init__(self):
        """Initialize the candlestick pattern analyzer"""
        # Define all candlestick patterns available in TA-Lib
        self.patterns = {
            # Bullish patterns
            'CDL3WHITESOLDIERS': {'name': 'Three White Soldiers', 'bullish': True},
            'CDLMORNINGSTAR': {'name': 'Morning Star', 'bullish': True},
            'CDLPIERCING': {'name': 'Piercing Pattern', 'bullish': True},
            'CDLHAMMER': {'name': 'Hammer', 'bullish': True},
            'CDLINVERTEDHAMMER': {'name': 'Inverted Hammer', 'bullish': True},
            'CDLENGULFING': {'name': 'Bullish Engulfing', 'bullish': True},
            'CDLHARAMI': {'name': 'Harami', 'bullish': True},
            'CDLMORNINGDOJISTAR': {'name': 'Morning Doji Star', 'bullish': True},
            'CDLBELTHOLD': {'name': 'Belt-hold', 'bullish': True},
            'CDLHOMINGPIGEON': {'name': 'Homing Pigeon', 'bullish': True},
            'CDLMATHOLD': {'name': 'Mat Hold', 'bullish': True},
            
            # Bearish patterns
            'CDL3BLACKCROWS': {'name': 'Three Black Crows', 'bullish': False},
            'CDLEVENINGSTAR': {'name': 'Evening Star', 'bullish': False},
            'CDLHANGINGMAN': {'name': 'Hanging Man', 'bullish': False},
            'CDLSHOOTINGSTAR': {'name': 'Shooting Star', 'bullish': False},
            'CDLDARKCLOUDCOVER': {'name': 'Dark Cloud Cover', 'bullish': False},
            'CDLEVENINGDOJISTAR': {'name': 'Evening Doji Star', 'bullish': False},
            'CDLGRAVESTONEDOJI': {'name': 'Gravestone Doji', 'bullish': False},
            
            # Neutral/reversal patterns
            'CDLDOJI': {'name': 'Doji', 'bullish': None},
            'CDLSPINNINGTOP': {'name': 'Spinning Top', 'bullish': None},
            'CDLMARUBOZU': {'name': 'Marubozu', 'bullish': None},
            'CDLHIGHWAVE': {'name': 'High-Wave', 'bullish': None},
            'CDLLONGLINE': {'name': 'Long Line', 'bullish': None},
            'CDLSHORTLINE': {'name': 'Short Line', 'bullish': None},
            'CDLRICKSHAWMAN': {'name': 'Rickshaw Man', 'bullish': None},
            'CDLTASUKIGAP': {'name': 'Tasuki Gap', 'bullish': None},
            'CDLGAPSIDESIDEWHITE': {'name': 'Up/Down-gap side-by-side white lines', 'bullish': None},
        }
        
        # Define high-confidence patterns
        self.high_confidence_patterns = [
            'CDL3WHITESOLDIERS', 'CDL3BLACKCROWS', 'CDLMORNINGSTAR', 'CDLEVENINGSTAR',
            'CDLMORNINGDOJISTAR', 'CDLEVENINGDOJISTAR', 'CDLENGULFING'
        ]
    
    def detect_patterns(self, ohlc_data: pd.DataFrame) -> Dict:
        """Detect candlestick patterns in the given OHLC data
        
        Args:
            ohlc_data: DataFrame with 'open', 'high', 'low', 'close' columns
            
        Returns:
            Dictionary with detected patterns
        """
        if not all(col in ohlc_data.columns for col in ['open', 'high', 'low', 'close']):
            raise ValueError("DataFrame must contain 'open', 'high', 'low', 'close' columns")
        
        # Extract OHLC data
        open_data = ohlc_data['open'].values
        high_data = ohlc_data['high'].values
        low_data = ohlc_data['low'].values
        close_data = ohlc_data['close'].values
        
        # Detect patterns
        pattern_results = {}
        for pattern_func, pattern_info in self.patterns.items():
            # Get the TA-Lib function by name
            talib_func = getattr(talib, pattern_func)
            
            # Apply the function to the OHLC data
            result = talib_func(open_data, high_data, low_data, close_data)
            
            # Store the results
            pattern_results[pattern_func] = {
                'name': pattern_info['name'],
                'bullish': pattern_info['bullish'],
                'signals': result.tolist(),
                'latest': result[-1] if len(result) > 0 else 0
            }
        
        return pattern_results
    
    def analyze_patterns(self, pattern_results: Dict) -> Dict:
        """Analyze the detected patterns to generate insights
        
        Args:
            pattern_results: Dictionary with pattern detection results
            
        Returns:
            Dictionary with pattern analysis
        """
        # Count bullish and bearish patterns in the latest candle
        bullish_count = 0
        bearish_count = 0
        neutral_count = 0
        high_confidence_bullish = 0
        high_confidence_bearish = 0
        
        detected_patterns = []
        
        for pattern_func, result in pattern_results.items():
            latest_signal = result['latest']
            
            # Skip if no pattern detected
            if latest_signal == 0:
                continue
            
            pattern_name = result['name']
            is_bullish = result['bullish']
            signal_strength = abs(latest_signal)
            
            # Add to detected patterns list
            detected_patterns.append({
                'name': pattern_name,
                'bullish': True if latest_signal > 0 else (False if latest_signal < 0 else None),
                'strength': signal_strength
            })
            
            # Count by pattern type
            if latest_signal > 0:  # Bullish signal
                bullish_count += 1
                if pattern_func in self.high_confidence_patterns:
                    high_confidence_bullish += 1
            elif latest_signal < 0:  # Bearish signal
                bearish_count += 1
                if pattern_func in self.high_confidence_patterns:
                    high_confidence_bearish += 1
            else:  # Neutral signal (should not happen with non-zero values)
                neutral_count += 1
        
        # Sort detected patterns by strength
        detected_patterns.sort(key=lambda x: x['strength'], reverse=True)
        
        # Generate overall signal
        overall_signal = 'neutral'
        signal_strength = 0
        
        # Determine signal based on high confidence patterns first
        if high_confidence_bullish > high_confidence_bearish:
            overall_signal = 'bullish'
            signal_strength = min(high_confidence_bullish / len(self.high_confidence_patterns) * 100, 100)
        elif high_confidence_bearish > high_confidence_bullish:
            overall_signal = 'bearish'
            signal_strength = min(high_confidence_bearish / len(self.high_confidence_patterns) * 100, 100)
        # If no high confidence patterns, use the count of all patterns
        elif bullish_count > bearish_count:
            overall_signal = 'bullish'
            signal_strength = min((bullish_count - bearish_count) / len(self.patterns) * 100, 100)
        elif bearish_count > bullish_count:
            overall_signal = 'bearish'
            signal_strength = min((bearish_count - bullish_count) / len(self.patterns) * 100, 100)
        
        return {
            'overall_signal': overall_signal,
            'signal_strength': signal_strength,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'high_confidence_bullish': high_confidence_bullish,
            'high_confidence_bearish': high_confidence_bearish,
            'detected_patterns': detected_patterns
        }
    
    def get_pattern_features(self, ohlc_data: pd.DataFrame) -> List[float]:
        """Extract candlestick pattern features for the RL agent
        
        Args:
            ohlc_data: DataFrame with OHLC data
            
        Returns:
            List of pattern-related features
        """
        # Detect patterns
        pattern_results = self.detect_patterns(ohlc_data)
        
        # Analyze patterns
        analysis = self.analyze_patterns(pattern_results)
        
        # Extract features
        features = [
            # Overall signal as a numeric value (-1 to 1)
            1.0 if analysis['overall_signal'] == 'bullish' else (-1.0 if analysis['overall_signal'] == 'bearish' else 0.0),
            
            # Signal strength (0-100) normalized to 0-1
            analysis['signal_strength'] / 100.0,
            
            # Ratio of bullish to total patterns
            analysis['bullish_count'] / max(analysis['bullish_count'] + analysis['bearish_count'], 1),
            
            # Ratio of bearish to total patterns
            analysis['bearish_count'] / max(analysis['bullish_count'] + analysis['bearish_count'], 1),
            
            # Ratio of high confidence bullish patterns
            analysis['high_confidence_bullish'] / max(len(self.high_confidence_patterns), 1),
            
            # Ratio of high confidence bearish patterns
            analysis['high_confidence_bearish'] / max(len(self.high_confidence_patterns), 1),
        ]
        
        return features
    
    def get_trading_signal(self, ohlc_data: pd.DataFrame) -> Dict:
        """Generate a trading signal based on candlestick patterns
        
        Args:
            ohlc_data: DataFrame with OHLC data
            
        Returns:
            Dictionary with trading signal information
        """
        # Detect and analyze patterns
        pattern_results = self.detect_patterns(ohlc_data)
        analysis = self.analyze_patterns(pattern_results)
        
        # Determine action based on signal and strength
        action = 'hold'
        confidence = 'low'
        
        if analysis['overall_signal'] == 'bullish':
            if analysis['signal_strength'] > 75:
                action = 'strong_buy'
                confidence = 'high'
            elif analysis['signal_strength'] > 50:
                action = 'buy'
                confidence = 'medium'
            elif analysis['signal_strength'] > 25:
                action = 'weak_buy'
                confidence = 'low'
        elif analysis['overall_signal'] == 'bearish':
            if analysis['signal_strength'] > 75:
                action = 'strong_sell'
                confidence = 'high'
            elif analysis['signal_strength'] > 50:
                action = 'sell'
                confidence = 'medium'
            elif analysis['signal_strength'] > 25:
                action = 'weak_sell'
                confidence = 'low'
        
        # Get the top 3 patterns that contributed to the signal
        top_patterns = analysis['detected_patterns'][:3] if analysis['detected_patterns'] else []
        
        return {
            'action': action,
            'confidence': confidence,
            'signal': analysis['overall_signal'],
            'strength': analysis['signal_strength'],
            'top_patterns': top_patterns
        }

# Example usage
if __name__ == "__main__":
    # Create sample OHLC data
    data = {
        'open': [100, 102, 104, 103, 105],
        'high': [104, 106, 107, 105, 108],
        'low': [98, 100, 102, 101, 103],
        'close': [102, 104, 103, 105, 107]
    }
    df = pd.DataFrame(data)
    
    # Create analyzer and detect patterns
    analyzer = CandlestickPatternAnalyzer()
    patterns = analyzer.detect_patterns(df)
    analysis = analyzer.analyze_patterns(patterns)
    features = analyzer.get_pattern_features(df)
    signal = analyzer.get_trading_signal(df)
    
    print(f"Pattern Features for RL: {features}")
    print(f"Trading Signal: {signal['action']} ({signal['confidence']} confidence)")
    print(f"Overall Signal: {analysis['overall_signal']} (Strength: {analysis['signal_strength']:.2f}%)")
    print("\nDetected Patterns:")
    for pattern in analysis['detected_patterns']:
        print(f"{pattern['name']}: {'Bullish' if pattern['bullish'] else 'Bearish'} (Strength: {pattern['strength']})")