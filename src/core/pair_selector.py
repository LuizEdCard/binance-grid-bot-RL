# Pair Selector Module for Grid Trading Bot

import time
import pandas as pd
import numpy as np # Import numpy for TA-Lib
from decimal import Decimal

from ..utils.logger import log
from ..utils.api_client import APIClient

# Attempt to import TA-Lib
try:
    import talib
    talib_available = True
    log.info("TA-Lib library found and imported successfully for PairSelector.")
except ImportError:
    talib_available = False
    log.warning("TA-Lib library not found for PairSelector. Candlestick pattern filtering will be unavailable. Please install TA-Lib for full functionality (see talib_installation_guide.md).")
    # Import pandas_ta only if TA-Lib is not available
    try:
        import pandas_ta as ta
        pandas_ta_available = True
    except ImportError:
        pandas_ta_available = False
        log.error("pandas_ta library not found either! Indicator calculations might fail.")

class PairSelector:
    """Selects suitable trading pairs based on volume, volatility, spread, trend, sentiment, and optional candlestick patterns."""

    def __init__(self, config: dict, api_client: APIClient, get_sentiment_score_func=None):
        self.config = config
        self.api_client = api_client
        self.get_sentiment_score_func = get_sentiment_score_func # Function to get the latest sentiment score
        self.selector_config = config.get("pair_selection", {})
        self.sentiment_config = config.get("sentiment_analysis", {})
        self.pair_filtering_config = self.sentiment_config.get("pair_filtering", {})

        # --- Standard Selection Parameters --- #
        self.min_volume_usd_24h = Decimal(str(self.selector_config.get("min_volume_usd_24h", "10000000")))
        self.min_atr_perc_24h = Decimal(str(self.selector_config.get("min_atr_perc_24h", "2.0"))) / 100
        self.max_spread_perc = Decimal(str(self.selector_config.get("max_spread_perc", "0.1"))) / 100
        self.max_adx = Decimal(str(self.selector_config.get("max_adx", "25")))
        self.update_interval_hours = self.selector_config.get("update_interval_hours", 6)
        self.blacklist = set(self.selector_config.get("blacklist", []))
        self.quote_asset = self.config.get("trading", {}).get("quote_asset", "USDT") # e.g., USDT
        self.max_pairs = self.config.get("trading", {}).get("max_concurrent_pairs", 5)

        # --- Optional Filters --- #
        self.use_candlestick_filter = self.selector_config.get("use_candlestick_filter", False)
        self.avoid_patterns = self.selector_config.get("avoid_candlestick_patterns", ["CDLDOJI", "CDLENGULFING"])

        # --- Sentiment Filter Parameters --- #
        self.sentiment_filtering_enabled = self.pair_filtering_config.get("enabled", False)
        self.min_sentiment_for_new_pair = Decimal(str(self.pair_filtering_config.get("min_sentiment_for_new_pair", "-0.3")))

        # --- State --- #
        self.selected_pairs = []
        self.last_update_time = 0

        log.info(f"PairSelector initialized. Min Vol: {self.min_volume_usd_24h} USD, Min ATR: {self.min_atr_perc_24h*100}%, Max Spread: {self.max_spread_perc*100}%, Max ADX: {self.max_adx}, Use Candlestick Filter: {self.use_candlestick_filter}, Sentiment Filter: {self.sentiment_filtering_enabled} (Min Score: {self.min_sentiment_for_new_pair})")
        if not talib_available:
            log.warning("TA-Lib not available, candlestick filtering is disabled.")
            self.use_candlestick_filter = False
        if self.sentiment_filtering_enabled and self.get_sentiment_score_func is None:
            log.warning(f"[{self.symbol}] Sentiment pair filtering enabled, but no sentiment score function provided. Feature disabled.")
            self.sentiment_filtering_enabled = False

    def _fetch_market_data(self):
        # ... (no changes) ...
        log.info("Fetching market data for pair selection...")
        try:
            tickers = self.api_client.get_futures_ticker()
            if not tickers:
                log.error("Failed to fetch tickers for pair selection.")
                return None, None

            relevant_tickers = {
                t["symbol"]: t for t in tickers
                if t["symbol"].endswith(self.quote_asset) and t["symbol"] not in self.blacklist
            }
            log.info(f"Found {len(relevant_tickers)} potential {self.quote_asset} pairs.")

            kline_data = {}
            symbols_to_fetch_klines = list(relevant_tickers.keys())
            kline_limit = 50
            min_required_klines = 30

            for symbol in symbols_to_fetch_klines:
                klines = self.api_client.get_futures_klines(symbol=symbol, interval=\'1h\', limit=kline_limit)
                if klines and len(klines) >= min_required_klines:
                    df = pd.DataFrame(klines, columns=[
                        \'Open time\', \'Open\', \'High\', \'Low\', \'Close\', \'Volume\',
                        \'Close time\', \'Quote asset volume\', \'Number of trades\',
                        \'Taker buy base asset volume\', \'Taker buy quote asset volume\', \'Ignore\'
                    ])
                    for col in [\'Open\', \'High\', \'Low\', \'Close\', \'Volume\']:
                        df[col] = pd.to_numeric(df[col])
                    kline_data[symbol] = df
                else:
                    log.warning(f"Could not fetch sufficient kline data ({len(klines) if klines else 0}/{min_required_klines}) for {symbol}. Excluding from this cycle.")
                    if symbol in relevant_tickers: del relevant_tickers[symbol]
                time.sleep(0.1)

            log.info(f"Fetched kline data for {len(kline_data)} pairs.")
            return relevant_tickers, kline_data

        except Exception as e:
            log.error(f"Error fetching market data: {e}", exc_info=True)
            return None, None

    def _calculate_metrics(self, tickers, kline_data):
        # ... (no changes) ...
        metrics = {}
        for symbol, df in kline_data.items():
            if symbol not in tickers:
                continue

            ticker_info = tickers[symbol]
            try:
                volume_24h = Decimal(ticker_info.get("quoteVolume", "0"))
                high_prices = df[\'High\'].values
                low_prices = df[\'Low\'].values
                close_prices = df[\'Close\'].values
                open_prices = df[\'Open\'].values

                atr = Decimal("0")
                atr_percentage = Decimal("0")
                adx = Decimal("100")
                last_pattern = "N/A"

                if talib_available:
                    try:
                        atr_series = talib.ATR(high_prices, low_prices, close_prices, timeperiod=14)
                        adx_series = talib.ADX(high_prices, low_prices, close_prices, timeperiod=14)
                        latest_atr = atr_series[~np.isnan(atr_series)][-1] if not np.all(np.isnan(atr_series)) else 0
                        latest_adx = adx_series[~np.isnan(adx_series)][-1] if not np.all(np.isnan(adx_series)) else 100
                        atr = Decimal(str(latest_atr))
                        adx = Decimal(str(latest_adx))
                        last_close_price = Decimal(str(close_prices[-1]))
                        if last_close_price > 0: atr_percentage = (atr / last_close_price)

                        if self.use_candlestick_filter:
                            detected_pattern_name = "None"
                            for pattern_func_name in self.avoid_patterns:
                                if hasattr(talib, pattern_func_name):
                                    pattern_func = getattr(talib, pattern_func_name)
                                    try:
                                        result = pattern_func(open_prices, high_prices, low_prices, close_prices)
                                        if result[-1] != 0:
                                            detected_pattern_name = pattern_func_name
                                            log.debug(f"Detected pattern {pattern_func_name} for {symbol} on last candle.")
                                            break
                                    except Exception as e_pattern:
                                        log.warning(f"Error calculating pattern {pattern_func_name} for {symbol}: {e_pattern}")
                                else:
                                    log.warning(f"Candlestick pattern function 	{pattern_func_name}\' not found in TA-Lib.")
                            last_pattern = detected_pattern_name
                    except Exception as e_talib:
                        log.error(f"TA-Lib calculation error for {symbol}: {e_talib}. ADX/ATR might be inaccurate.", exc_info=True)
                elif pandas_ta_available:
                    try:
                        df.ta.atr(length=14, append=True)
                        df.ta.adx(length=14, append=True)
                        latest_atr = df["ATRr_14"].iloc[-1]
                        latest_adx = df["ADX_14"].iloc[-1]
                        atr = Decimal(str(latest_atr)) if pd.notna(latest_atr) else Decimal("0")
                        adx = Decimal(str(latest_adx)) if pd.notna(latest_adx) else Decimal("100")
                        last_close_price = Decimal(str(df["Close"].iloc[-1]))
                        if last_close_price > 0: atr_percentage = (atr / last_close_price)
                        log.debug(f"Calculated ATR/ADX for {symbol} using pandas_ta (fallback).")
                    except Exception as e_pta:
                        log.error(f"pandas_ta calculation error for {symbol}: {e_pta}. ADX/ATR might be inaccurate.", exc_info=True)
                else:
                    log.error(f"Neither TA-Lib nor pandas_ta available for {symbol}. Cannot calculate ATR/ADX.")

                spread_percentage = Decimal("0") # Placeholder

                metrics[symbol] = {
                    "volume": volume_24h,
                    "atr_perc": atr_percentage,
                    "spread_perc": spread_percentage,
                    "adx": adx,
                    "last_pattern": last_pattern,
                    "last_price": Decimal(ticker_info.get("lastPrice", "0"))
                }
                log.debug(f"{symbol}: Vol={volume_24h:.0f}, ATR%={atr_percentage*100:.2f}, ADX={adx:.2f}, Pattern={last_pattern}")
            except Exception as e:
                log.error(f"Error calculating metrics for {symbol}: {e}", exc_info=True)
        return metrics

    def _filter_and_rank_pairs(self, metrics):
        """Filters pairs based on criteria (including sentiment) and ranks them."""
        filtered_pairs = []
        current_sentiment_score = None

        # Get sentiment score once if filtering is enabled
        if self.sentiment_filtering_enabled:
            try:
                current_sentiment_score = Decimal(str(self.get_sentiment_score_func(smoothed=True)))
                log.info(f"Applying sentiment filter. Current score: {current_sentiment_score:.4f}, Minimum required: {self.min_sentiment_for_new_pair}")
            except Exception as e:
                log.error(f"Error getting sentiment score for pair filtering: {e}. Disabling sentiment filter for this cycle.")
                self.sentiment_filtering_enabled = False # Disable for this run if error

        for symbol, m in metrics.items():
            # Apply standard filters
            if m["volume"] < self.min_volume_usd_24h:
                log.debug(f"Excluding {symbol}: Low volume ({m["volume"]:.0f} < {self.min_volume_usd_24h})")
                continue
            if m["atr_perc"] < self.min_atr_perc_24h:
                log.debug(f"Excluding {symbol}: Low volatility ATR ({m["atr_perc"]*100:.2f}% < {self.min_atr_perc_24h*100}%)")
                continue
            if m["adx"] > self.max_adx:
                log.debug(f"Excluding {symbol}: Too trendy ADX ({m["adx"]:.2f} > {self.max_adx})")
                continue

            # Apply optional candlestick pattern filter
            if self.use_candlestick_filter and m["last_pattern"] != "N/A" and m["last_pattern"] != "None":
                if m["last_pattern"] in self.avoid_patterns:
                    log.info(f"Excluding {symbol}: Found undesirable pattern ({m["last_pattern"]}) on last candle.")
                    continue

            # --- Apply Sentiment Filter (NEW) --- #
            if self.sentiment_filtering_enabled and current_sentiment_score is not None:
                if current_sentiment_score <= self.min_sentiment_for_new_pair:
                    log.info(f"Excluding {symbol}: Sentiment score ({current_sentiment_score:.4f}) is below threshold ({self.min_sentiment_for_new_pair}).")
                    continue # Skip this pair due to low sentiment
            # ------------------------------------ #

            # If all filters pass, add to list
            filtered_pairs.append({
                "symbol": symbol,
                "volume": m["volume"],
                "atr_perc": m["atr_perc"],
                "adx": m["adx"],
                "last_pattern": m["last_pattern"]
            })

        log.info(f"Found {len(filtered_pairs)} pairs after filtering (including sentiment if enabled).")

        # Rank pairs: prioritize higher ATR (more grid opportunities), then lower ADX (better for grid)
        filtered_pairs.sort(key=lambda p: (-p["atr_perc"], p["adx"])) # Sort descending by ATR, then ascending by ADX

        ranked_symbols = [p["symbol"] for p in filtered_pairs]
        log.info(f"Ranked pairs: {ranked_symbols[:self.max_pairs]}")

        return ranked_symbols

    def get_selected_pairs(self, force_update=False):
        """Returns the list of selected pairs, updating if necessary."""
        current_time = time.time()
        needs_update = (current_time - self.last_update_time) > (self.update_interval_hours * 3600)

        if force_update or needs_update:
            log.info(f"Updating pair selection (Force update: {force_update}, Time elapsed: {(current_time - self.last_update_time)/3600:.2f}h)")
            tickers, kline_data = self._fetch_market_data()
            if tickers and kline_data:
                metrics = self._calculate_metrics(tickers, kline_data)
                ranked_symbols = self._filter_and_rank_pairs(metrics)
                self.selected_pairs = ranked_symbols[:self.max_pairs]
                self.last_update_time = current_time
                log.info(f"Pair selection updated. Selected pairs: {self.selected_pairs}")
            else:
                log.error("Failed to update pair selection due to data fetching errors.")
                log.warning(f"Keeping previously selected pairs: {self.selected_pairs}")

        return self.selected_pairs

