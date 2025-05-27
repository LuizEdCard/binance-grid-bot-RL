import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import ccxt
import time

class AltcoinCorrelationAnalyzer:
    """Class for analyzing correlations between Bitcoin and major altcoins"""
    
    def __init__(self, timeframes=['1h', '4h', '1d'], window_sizes=[14, 30, 90]):
        """Initialize the correlation analyzer
        
        Args:
            timeframes: List of timeframes to analyze
            window_sizes: List of window sizes (in periods) for correlation calculation
        """
        self.exchange = ccxt.binance()
        self.altcoins = ['ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOT', 'DOGE', 'AVAX', 'MATIC', 'LINK']
        self.timeframes = timeframes
        self.window_sizes = window_sizes
        self.correlation_data = {}
        self.regime_thresholds = {
            'high_correlation': 0.7,
            'medium_correlation': 0.4,
            'low_correlation': 0.2
        }
    
    def fetch_historical_data(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """Fetch historical OHLCV data for a symbol
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe for the data
            limit: Number of candles to fetch
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()
    
    def calculate_correlation(self, btc_data: pd.DataFrame, alt_data: pd.DataFrame, window: int) -> pd.Series:
        """Calculate rolling correlation between BTC and an altcoin
        
        Args:
            btc_data: DataFrame with BTC price data
            alt_data: DataFrame with altcoin price data
            window: Window size for rolling correlation
            
        Returns:
            Series with correlation values
        """
        # Align the data by timestamp
        combined = pd.DataFrame({
            'btc': btc_data['close'],
            'alt': alt_data['close']
        })
        
        # Calculate rolling correlation
        correlation = combined['btc'].rolling(window=window).corr(combined['alt'])
        return correlation
    
    def analyze_all_correlations(self) -> Dict:
        """Analyze correlations for all altcoins across all timeframes and windows
        
        Returns:
            Dictionary with correlation data
        """
        results = {}
        
        for timeframe in self.timeframes:
            results[timeframe] = {}
            
            # Fetch BTC data first
            btc_data = self.fetch_historical_data('BTC/USDT', timeframe)
            if btc_data.empty:
                continue
                
            for altcoin in self.altcoins:
                alt_data = self.fetch_historical_data(f'{altcoin}/USDT', timeframe)
                if alt_data.empty:
                    continue
                    
                results[timeframe][altcoin] = {}
                
                for window in self.window_sizes:
                    correlation = self.calculate_correlation(btc_data, alt_data, window)
                    
                    # Get the latest correlation value
                    latest_corr = correlation.iloc[-1] if not correlation.empty else np.nan
                    
                    # Calculate correlation trend (increasing or decreasing)
                    corr_trend = 'neutral'
                    if len(correlation) > 5 and not correlation.empty:
                        recent_corr = correlation.iloc[-5:]
                        if recent_corr.is_monotonic_increasing:
                            corr_trend = 'increasing'
                        elif recent_corr.is_monotonic_decreasing:
                            corr_trend = 'decreasing'
                    
                    results[timeframe][altcoin][f'window_{window}'] = {
                        'current_correlation': latest_corr,
                        'correlation_trend': corr_trend,
                        'correlation_history': correlation.dropna().tolist()
                    }
            
            # Add market regime analysis
            results[timeframe]['market_regime'] = self._determine_market_regime(results[timeframe])
        
        self.correlation_data = results
        return results
    
    def _determine_market_regime(self, timeframe_data: Dict) -> str:
        """Determine the current market regime based on correlation patterns
        
        Args:
            timeframe_data: Dictionary with correlation data for a timeframe
            
        Returns:
            String describing the market regime
        """
        # Calculate average correlation across all altcoins
        avg_correlations = []
        for altcoin in self.altcoins:
            if altcoin in timeframe_data:
                for window_key in [f'window_{w}' for w in self.window_sizes]:
                    if window_key in timeframe_data[altcoin]:
                        corr_value = timeframe_data[altcoin][window_key]['current_correlation']
                        if not np.isnan(corr_value):
                            avg_correlations.append(corr_value)
        
        if not avg_correlations:
            return 'unknown'
        
        avg_corr = np.mean(avg_correlations)
        
        # Determine regime based on average correlation
        if avg_corr > self.regime_thresholds['high_correlation']:
            return 'high_correlation_regime'
        elif avg_corr > self.regime_thresholds['medium_correlation']:
            return 'medium_correlation_regime'
        elif avg_corr > self.regime_thresholds['low_correlation']:
            return 'low_correlation_regime'
        else:
            return 'uncorrelated_regime'
    
    def get_trading_signals(self) -> Dict:
        """Generate trading signals based on correlation analysis
        
        Returns:
            Dictionary with trading signals
        """
        if not self.correlation_data:
            self.analyze_all_correlations()
        
        signals = {}
        
        for timeframe in self.timeframes:
            if timeframe not in self.correlation_data:
                continue
                
            signals[timeframe] = {
                'market_regime': self.correlation_data[timeframe].get('market_regime', 'unknown'),
                'altcoin_signals': {}
            }
            
            for altcoin in self.altcoins:
                if altcoin not in self.correlation_data[timeframe]:
                    continue
                    
                # Get the correlation data for the medium window size
                medium_window = f'window_{self.window_sizes[1]}' if len(self.window_sizes) > 1 else f'window_{self.window_sizes[0]}'
                if medium_window not in self.correlation_data[timeframe][altcoin]:
                    continue
                    
                corr_data = self.correlation_data[timeframe][altcoin][medium_window]
                
                # Generate signal based on correlation and trend
                signal = 'neutral'
                corr_value = corr_data['current_correlation']
                corr_trend = corr_data['correlation_trend']
                
                if not np.isnan(corr_value):
                    if corr_value > 0.8 and corr_trend == 'increasing':
                        signal = 'strong_follow_btc'
                    elif corr_value > 0.6 and corr_trend == 'increasing':
                        signal = 'follow_btc'
                    elif corr_value < 0.2 and corr_trend == 'decreasing':
                        signal = 'independent_movement'
                    elif corr_value < 0 and corr_trend == 'decreasing':
                        signal = 'inverse_to_btc'
                
                signals[timeframe]['altcoin_signals'][altcoin] = {
                    'signal': signal,
                    'correlation': corr_value,
                    'trend': corr_trend
                }
        
        return signals
    
    def get_correlation_features(self) -> List[float]:
        """Extract correlation features for the RL agent
        
        Returns:
            List of correlation features
        """
        if not self.correlation_data:
            self.analyze_all_correlations()
        
        features = []
        
        # Use the 1h timeframe for features
        timeframe = self.timeframes[0] if self.timeframes else '1h'
        if timeframe not in self.correlation_data:
            return [0.0] * (len(self.altcoins) + 1)  # Return zeros if no data
        
        # Add market regime as a numeric feature
        regime = self.correlation_data[timeframe].get('market_regime', 'unknown')
        regime_value = {
            'high_correlation_regime': 1.0,
            'medium_correlation_regime': 0.66,
            'low_correlation_regime': 0.33,
            'uncorrelated_regime': 0.0,
            'unknown': 0.5
        }.get(regime, 0.5)
        features.append(regime_value)
        
        # Add correlation values for each altcoin
        for altcoin in self.altcoins:
            if altcoin in self.correlation_data[timeframe]:
                # Use the medium window
                medium_window = f'window_{self.window_sizes[1]}' if len(self.window_sizes) > 1 else f'window_{self.window_sizes[0]}'
                if medium_window in self.correlation_data[timeframe][altcoin]:
                    corr_value = self.correlation_data[timeframe][altcoin][medium_window]['current_correlation']
                    features.append(float(corr_value) if not np.isnan(corr_value) else 0.0)
                else:
                    features.append(0.0)
            else:
                features.append(0.0)
        
        return features

# Example usage
if __name__ == "__main__":
    analyzer = AltcoinCorrelationAnalyzer()
    correlations = analyzer.analyze_all_correlations()
    signals = analyzer.get_trading_signals()
    features = analyzer.get_correlation_features()
    
    print(f"Correlation Features for RL: {features}")
    print(f"Market Regime (1h): {correlations['1h']['market_regime']}")
    print("\nTrading Signals:")
    for altcoin, signal_data in signals['1h']['altcoin_signals'].items():
        print(f"{altcoin}: {signal_data['signal']} (Correlation: {signal_data['correlation']:.2f}, Trend: {signal_data['trend']})")