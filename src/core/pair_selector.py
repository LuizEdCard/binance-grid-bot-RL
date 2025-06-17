# Pair Selector Module for Grid Trading Bot

import time
import asyncio
from decimal import Decimal
from typing import List, Dict, Optional

import numpy as np  # Import numpy for TA-Lib
import pandas as pd

from utils.api_client import APIClient
from utils.logger import setup_logger
log = setup_logger("pair_selector")

# Attempt to import TA-Lib
try:
    import talib

    talib_available = True
    log.info("TA-Lib library found and imported successfully for PairSelector.")
except ImportError:
    talib_available = False
    log.warning(
        "TA-Lib library not found for PairSelector. Candlestick pattern filtering will be unavailable. Please install TA-Lib for full functionality (see talib_installation_guide.md)."
    )
    # Import pandas_ta only if TA-Lib is not available
    try:
        import pandas_ta  # noqa: F401

        pandas_ta_available = True
    except ImportError:
        pandas_ta_available = False
        log.error(
            "pandas_ta library not found either! Indicator calculations might fail."
        )


class PairSelector:
    """Selects suitable trading pairs based on volume, volatility, spread, trend, sentiment, and optional candlestick patterns."""

    def __init__(
        self, config: dict, api_client: APIClient, get_sentiment_score_func=None
    ):
        self.config = config
        self.api_client = api_client
        # Function to get the latest sentiment score
        self.get_sentiment_score_func = get_sentiment_score_func
        # Market type for trading
        self.market_type = config["default_market_type"]
        self.selector_config = config["pair_selection"]
        self.sentiment_config = config["sentiment_analysis"]
        self.pair_filtering_config = self.sentiment_config["pair_filtering"]

        # --- Standard Selection Parameters --- #
        self.min_volume_usd_24h = Decimal(
            str(self.selector_config["min_volume_usd_24h"])
        )
        self.min_atr_perc_24h = (
            Decimal(str(self.selector_config["min_atr_perc_24h"])) / 100
        )
        self.max_spread_perc = (
            Decimal(str(self.selector_config["max_spread_perc"])) / 100
        )
        self.max_adx = Decimal(str(self.selector_config["max_adx"]))
        self.update_interval_hours = self.selector_config[
            "update_interval_hours"
        ]
        self.blacklist = set(self.selector_config["blacklist"])
        self.quote_asset = "USDT"  # Fixed quote asset for this trading system
        self.max_pairs = self.config["trading"]["max_concurrent_pairs"]
        
        # --- Market-specific Parameters --- #
        futures_config = self.selector_config["futures_pairs"]
        self.max_price_usdt = Decimal(str(futures_config["max_price_usdt"]))  # NOVO: Filtro de preço máximo

        # --- Optional Filters --- #
        # Candlestick filter disabled by default - not configured in yaml
        self.use_candlestick_filter = False
        # Default patterns to avoid - not configured in yaml
        self.avoid_patterns = ["CDLDOJI", "CDLENGULFING"]

        # --- Sentiment Filter Parameters --- #
        self.sentiment_filtering_enabled = self.pair_filtering_config[
            "enabled"
        ]
        self.min_sentiment_for_new_pair = Decimal(
            str(self.pair_filtering_config["min_sentiment_for_new_pair"])
        )

        # --- State --- #
        self.selected_pairs = []
        self.last_update_time = 0
        # Use absolute path to avoid working directory confusion
        import os
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Go up to project root
        self.cache_file = os.path.join(root_dir, "data", "pair_selection_cache.json")
        self._load_cache()

        log.info(
            f"PairSelector initialized. Min Vol: {self.min_volume_usd_24h} USD, Min ATR: {self.min_atr_perc_24h*100}%, Max Spread: {self.max_spread_perc*100}%, Max ADX: {self.max_adx}, Max Price: {self.max_price_usdt} USDT, Use Candlestick Filter: {self.use_candlestick_filter}, Sentiment Filter: {self.sentiment_filtering_enabled} (Min Score: {self.min_sentiment_for_new_pair})"
        )
        if not talib_available:
            log.warning("TA-Lib not available, candlestick filtering is disabled.")
            self.use_candlestick_filter = False
        if self.sentiment_filtering_enabled and self.get_sentiment_score_func is None:
            log.warning(
                f"[{self.symbol}] Sentiment pair filtering enabled, but no sentiment score function provided. Feature disabled."
            )
            self.sentiment_filtering_enabled = False

    def _load_cache(self):
        """Load cached pair selection if available."""
        try:
            import json
            import os
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Check if cache is still valid (less than update_interval_hours old)
                cache_age = time.time() - cache_data.get('timestamp', 0)
                if cache_age < (self.update_interval_hours * 3600):
                    self.selected_pairs = cache_data.get('selected_pairs', [])
                    self.last_update_time = cache_data.get('timestamp', 0)
                    log.info(f"Loaded cached pair selection: {self.selected_pairs} (age: {cache_age/3600:.1f}h)")
                    return
        except Exception as e:
            log.debug(f"Could not load cache: {e}")
        
        # If no valid cache, use preferred symbols as fallback
        preferred = self.selector_config["futures_pairs"]["preferred_symbols"]
        if preferred:
            self.selected_pairs = preferred[:self.max_pairs]
            log.info(f"Using preferred symbols as initial selection: {self.selected_pairs}")

    def _save_cache(self):
        """Save current pair selection to cache."""
        try:
            import json
            import os
            
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            
            cache_data = {
                'selected_pairs': self.selected_pairs,
                'timestamp': self.last_update_time
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
            log.debug(f"Saved pair selection cache: {len(self.selected_pairs)} pairs")
        except Exception as e:
            log.warning(f"Could not save cache: {e}")

    def _fetch_market_data(self):
        # ... (no changes) ...
        log.info("Fetching market data for pair selection...")
        try:
            tickers = self.api_client.get_futures_ticker()
            if not tickers:
                log.error("Failed to fetch tickers for pair selection.")
                return None, None

            relevant_tickers = {
                t["symbol"]: t
                for t in tickers
                if t["symbol"].endswith(self.quote_asset)
                and t["symbol"] not in self.blacklist
            }
            log.info(
                f"Found {len(relevant_tickers)} potential {self.quote_asset} pairs."
            )

            kline_data = {}
            symbols_to_fetch_klines = list(relevant_tickers.keys())
            # Load kline limits from config
            market_analysis_config = self.config['market_analysis']
            kline_limit = market_analysis_config['kline_limit']
            min_required_klines = market_analysis_config['min_required_klines']

            for symbol in symbols_to_fetch_klines:
                klines = self.api_client.get_futures_klines(
                    symbol=symbol, interval="3m", limit=kline_limit
                )
                if klines and len(klines) >= min_required_klines:
                    df = pd.DataFrame(
                        klines,
                        columns=[
                            "Open time",
                            "Open",
                            "High",
                            "Low",
                            "Close",
                            "Volume",
                            "Close time",
                            "Quote asset volume",
                            "Number of trades",
                            "Taker buy base asset volume",
                            "Taker buy quote asset volume",
                            "Ignore",
                        ],
                    )
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        df[col] = pd.to_numeric(df[col])
                    kline_data[symbol] = df
                else:
                    log.warning(
                        f"Could not fetch sufficient kline data ({len(klines) if klines else 0}/{min_required_klines}) for {symbol}. Excluding from this cycle."
                    )
                    if symbol in relevant_tickers:
                        del relevant_tickers[symbol]
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
                high_prices = df["High"].values
                low_prices = df["Low"].values
                close_prices = df["Close"].values
                open_prices = df["Open"].values

                atr = Decimal("0")
                atr_percentage = Decimal("0")
                adx = Decimal("100")
                last_pattern = "N/A"

                if talib_available:
                    try:
                        # Use configurable timeperiod from config
                        ta_timeperiod = market_analysis_config['ta_timeperiod']
                        atr_series = talib.ATR(
                            high_prices, low_prices, close_prices, timeperiod=ta_timeperiod
                        )
                        adx_series = talib.ADX(
                            high_prices, low_prices, close_prices, timeperiod=ta_timeperiod
                        )
                        latest_atr = (
                            atr_series[~np.isnan(atr_series)][-1]
                            if not np.all(np.isnan(atr_series))
                            else 0
                        )
                        latest_adx = (
                            adx_series[~np.isnan(adx_series)][-1]
                            if not np.all(np.isnan(adx_series))
                            else 100
                        )
                        atr = Decimal(str(latest_atr))
                        adx = Decimal(str(latest_adx))
                        last_close_price = Decimal(str(close_prices[-1]))
                        if last_close_price > 0:
                            atr_percentage = atr / last_close_price

                        if self.use_candlestick_filter:
                            detected_pattern_name = "None"
                            for pattern_func_name in self.avoid_patterns:
                                if hasattr(talib, pattern_func_name):
                                    pattern_func = getattr(talib, pattern_func_name)
                                    try:
                                        result = pattern_func(
                                            open_prices,
                                            high_prices,
                                            low_prices,
                                            close_prices,
                                        )
                                        if result[-1] != 0:
                                            detected_pattern_name = pattern_func_name
                                            log.debug(
                                                f"Detected pattern {pattern_func_name} for {symbol} on last candle."
                                            )
                                            break
                                    except Exception as e_pattern:
                                        log.warning(
                                            f"Error calculating pattern {pattern_func_name} for {symbol}: {e_pattern}"
                                        )
                                else:
                                    # Corrected string literal
                                    log.warning(
                                        f"Candlestick pattern function '{pattern_func_name}' not found in TA-Lib."
                                    )
                            last_pattern = detected_pattern_name
                    except Exception as e_talib:
                        log.error(
                            f"TA-Lib calculation error for {symbol}: {e_talib}. ADX/ATR might be inaccurate.",
                            exc_info=True,
                        )
                elif pandas_ta_available:
                    try:
                        df.ta.atr(length=14, append=True)
                        df.ta.adx(length=14, append=True)
                        latest_atr = df["ATRr_14"].iloc[-1]
                        latest_adx = df["ADX_14"].iloc[-1]
                        atr = (
                            Decimal(str(latest_atr))
                            if pd.notna(latest_atr)
                            else Decimal("0")
                        )
                        adx = (
                            Decimal(str(latest_adx))
                            if pd.notna(latest_adx)
                            else Decimal("100")
                        )
                        last_close_price = Decimal(
                            str(df["Close"].iloc[-1])
                        )  # Corrected df['Close']
                        if last_close_price > 0:
                            atr_percentage = atr / last_close_price
                        log.debug(
                            f"Calculated ATR/ADX for {symbol} using pandas_ta (fallback)."
                        )
                    except Exception as e_pta:
                        log.error(
                            f"pandas_ta calculation error for {symbol}: {e_pta}. ADX/ATR might be inaccurate.",
                            exc_info=True,
                        )
                else:
                    log.error(
                        f"Neither TA-Lib nor pandas_ta available for {symbol}. Cannot calculate ATR/ADX."
                    )

                spread_percentage = Decimal("0")  # Placeholder

                metrics[symbol] = {
                    "volume": volume_24h,
                    "atr_perc": atr_percentage,
                    "spread_perc": spread_percentage,
                    "adx": adx,
                    "last_pattern": last_pattern,
                    "last_price": Decimal(ticker_info.get("lastPrice", "0")),
                }
                log.debug(
                    f"{symbol}: Vol={volume_24h:.0f}, ATR%={atr_percentage*100:.2f}, ADX={adx:.2f}, Pattern={last_pattern}"
                )
            except Exception as e:
                log.error(f"Error calculating metrics for {symbol}: {e}", exc_info=True)
        return metrics

    def _get_symbol_metrics(self, symbol: str) -> Optional[Dict]:
        """Obtém métricas específicas de um símbolo."""
        try:
            # Get ticker data
            if self.market_type == "futures":
                ticker = self.api_client.get_futures_ticker(symbol=symbol)
            else:
                ticker = self.api_client.get_spot_ticker(symbol=symbol)
            
            if not ticker or not isinstance(ticker, list) or len(ticker) == 0:
                return None
                
            ticker_info = ticker[0]
            
            # Get kline data for ATR calculation
            market_analysis_config = self.config['market_analysis']
            kline_limit = market_analysis_config['kline_limit']
            
            if self.market_type == "futures":
                klines = self.api_client.get_futures_klines(symbol, "5m", kline_limit)
            else:
                klines = self.api_client.get_spot_klines(symbol, "5m", kline_limit)
            
            if not klines or len(klines) < 20:
                return None
                
            # Convert to DataFrame for analysis
            import pandas as pd
            df = pd.DataFrame(klines, columns=[
                "timestamp", "Open", "High", "Low", "Close", "Volume",
                "close_time", "quote_asset_volume", "number_of_trades",
                "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
            ])
            
            # Convert to numeric
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col])
            
            # Calculate ATR
            volume_24h = float(ticker_info.get("quoteVolume", "0"))
            atr_perc = 0.0
            
            if talib_available and len(df) >= 14:
                try:
                    ta_timeperiod = market_analysis_config['ta_timeperiod']
                    atr_series = talib.ATR(
                        df["High"].values, 
                        df["Low"].values, 
                        df["Close"].values, 
                        timeperiod=ta_timeperiod
                    )
                    
                    if len(atr_series) > 0 and not pd.isna(atr_series[-1]):
                        current_price = float(ticker_info.get("lastPrice", "0"))
                        if current_price > 0:
                            atr_perc = float(atr_series[-1]) / current_price
                            
                except Exception as e:
                    log.debug(f"Erro no cálculo ATR para {symbol}: {e}")
            
            return {
                "atr_perc": atr_perc,
                "volume_24h": volume_24h,
                "last_price": float(ticker_info.get("lastPrice", "0")),
                "price_change_24h": float(ticker_info.get("priceChangePercent", "0"))
            }
            
        except Exception as e:
            log.debug(f"Erro ao obter métricas para {symbol}: {e}")
            return None

    def _filter_and_rank_pairs(self, metrics):
        """Filters pairs based on criteria (including sentiment) and ranks them."""
        filtered_pairs = []
        current_sentiment_score = None

        # Get sentiment score once if filtering is enabled
        if self.sentiment_filtering_enabled:
            try:
                current_sentiment_score = Decimal(
                    str(self.get_sentiment_score_func(smoothed=True))
                )
                log.info(
                    f"Applying sentiment filter. Current score: {current_sentiment_score:.4f}, Minimum required: {self.min_sentiment_for_new_pair}"
                )
            except Exception as e:
                log.error(
                    f"Error getting sentiment score for pair filtering: {e}. Disabling sentiment filter for this cycle."
                )
                self.sentiment_filtering_enabled = (
                    False  # Disable for this run if error
                )

        for symbol, m in metrics.items():
            # Apply standard filters
            if m["volume"] < self.min_volume_usd_24h:
                log.debug(
                    f"Excluding {symbol}: Low volume ({m['volume']:.0f} < {self.min_volume_usd_24h})"
                )
                continue
            if m["atr_perc"] < self.min_atr_perc_24h:
                log.debug(
                    f"Excluding {symbol}: Low volatility ATR ({m['atr_perc']*100:.2f}% < {self.min_atr_perc_24h*100}%)"
                )
                continue
            if m["adx"] > self.max_adx:
                log.debug(
                    f"Excluding {symbol}: Too trendy ADX ({m['adx']:.2f} > {self.max_adx})"
                )
                continue
            
            # Apply price filter - NEW
            if m["last_price"] > self.max_price_usdt:
                log.debug(
                    f"Excluding {symbol}: Price too high ({m['last_price']:.4f} > {self.max_price_usdt})"
                )
                continue

            # Apply optional candlestick pattern filter
            if (
                self.use_candlestick_filter
                and m["last_pattern"] != "N/A"
                and m["last_pattern"] != "None"
            ):
                if m["last_pattern"] in self.avoid_patterns:
                    log.info(
                        f"Excluding {symbol}: Found undesirable pattern ({m['last_pattern']}) on last candle."
                    )
                    continue

            # --- Apply Sentiment Filter (NEW) --- #
            if self.sentiment_filtering_enabled and current_sentiment_score is not None:
                if current_sentiment_score <= self.min_sentiment_for_new_pair:
                    log.info(
                        f"Excluding {symbol}: Sentiment score ({current_sentiment_score:.4f}) is below threshold ({self.min_sentiment_for_new_pair})."
                    )
                    continue  # Skip this pair due to low sentiment
            # ------------------------------------ #

            # If all filters pass, add to list
            filtered_pairs.append(
                {
                    "symbol": symbol,
                    "volume": m["volume"],
                    "atr_perc": m["atr_perc"],
                    "adx": m["adx"],
                    "last_pattern": m["last_pattern"],
                }
            )

        log.info(
            f"Found {len(filtered_pairs)} pairs after filtering (including sentiment if enabled)."
        )

        # Rank pairs: prioritize higher ATR (more grid opportunities), then
        # lower ADX (better for grid)
        # Sort descending by ATR, then ascending by ADX
        filtered_pairs.sort(key=lambda p: (-p["atr_perc"], p["adx"]))

        ranked_symbols = [p["symbol"] for p in filtered_pairs]
        log.info(f"Ranked pairs: {ranked_symbols[:self.max_pairs]}")

        return ranked_symbols

    def get_selected_pairs(self, force_update=False):
        """Returns the list of selected pairs, updating if necessary."""
        current_time = time.time()
        needs_update = (current_time - self.last_update_time) > (
            self.update_interval_hours * 3600
        )

        if force_update or needs_update:
            log.info(
                f"Updating pair selection (Force update: {force_update}, Time elapsed: {(current_time - self.last_update_time)/3600:.2f}h)"
            )
            
            # NOVO: Verificar pares com posições abertas primeiro
            existing_position_pairs = self._get_pairs_with_open_positions()
            log.info(f"Found {len(existing_position_pairs)} pairs with open positions: {existing_position_pairs}")
            
            # Verificar se temos preferred symbols configurados
            preferred = self.selector_config["futures_pairs"]["preferred_symbols"]
            use_social_feed = self.selector_config["use_social_feed_analysis"]
            
            if preferred and len(preferred) >= 3 and not use_social_feed:
                # Se temos preferred symbols suficientes E não usar análise social, usar apenas eles (otimização)
                log.info(f"Using preferred symbols for fast selection: {preferred}")
                selected_pairs = preferred[:self.max_pairs]
            elif use_social_feed:
                # Usar análise inteligente combinando preferred + social feed
                log.info("Using intelligent pair selection with social feed analysis...")
                try:
                    # Usar método sincronizado para evitar conflitos de event loop
                    intelligent_pairs = self._get_intelligent_pair_selection_sync(preferred)
                    selected_pairs = intelligent_pairs[:self.max_pairs]
                except Exception as e:
                    log.error(f"Error in intelligent selection: {e}")
                    # Fallback para preferred symbols
                    log.warning("Falling back to preferred symbols")
                    selected_pairs = preferred[:self.max_pairs]
            else:
                # Caso contrário, fazer análise completa
                log.info("No sufficient preferred symbols, performing full market analysis...")
                tickers, kline_data = self._fetch_market_data()
                if tickers and kline_data:
                    metrics = self._calculate_metrics(tickers, kline_data)
                    ranked_symbols = self._filter_and_rank_pairs(metrics)
                    selected_pairs = ranked_symbols[:self.max_pairs]
                else:
                    log.error("Failed to update pair selection due to data fetching errors.")
                    selected_pairs = self.selected_pairs  # Keep existing
            
            # NOVO: Combinar pares selecionados com pares que têm posições abertas
            final_pairs = list(existing_position_pairs)  # Sempre incluir pares com posições
            
            # Adicionar outros pares selecionados até o limite (se houver espaço)
            for pair in selected_pairs:
                if pair not in final_pairs:
                    final_pairs.append(pair)
            
            # Log da seleção final
            log.info(f"📊 FINAL PAIR SELECTION:")
            log.info(f"  🔸 Pairs with open positions: {existing_position_pairs}")
            log.info(f"  🔸 Additional selected pairs: {[p for p in final_pairs if p not in existing_position_pairs]}")
            log.info(f"  🔸 Total pairs to trade: {len(final_pairs)} (limit was {self.max_pairs})")
            
            if len(existing_position_pairs) > self.max_pairs:
                log.warning(f"⚠️  You have {len(existing_position_pairs)} open positions but max_concurrent_pairs is {self.max_pairs}")
                log.warning(f"⚠️  Trading ALL {len(existing_position_pairs)} pairs with positions to avoid abandoning them")
            
            self.selected_pairs = final_pairs
            self.last_update_time = current_time
            self._save_cache()
            log.info(f"Pair selection completed. Selected pairs: {self.selected_pairs}")

        return self.selected_pairs
    
    def _get_intelligent_pair_selection_sync(self, preferred_symbols: List[str]) -> List[str]:
        """
        Versão sincronizada da seleção inteligente para evitar conflitos de event loop.
        
        Args:
            preferred_symbols: Lista de símbolos preferidos configurados
            
        Returns:
            Lista final de símbolos selecionados
        """
        try:
            log.info("Running simplified intelligent pair selection...")
            
            # Get configuration values instead of hardcoded ones
            trading_config = self.config["trading"]
            enable_auto_pair_addition = trading_config["enable_auto_pair_addition"]
            balance_threshold_usd = Decimal(str(trading_config["balance_threshold_usd"]))
            capital_per_pair_usd = Decimal(str(trading_config["capital_per_pair_usd"]))
            max_concurrent_pairs = trading_config["max_concurrent_pairs"]
            
            # Check if auto pair addition is enabled
            if not enable_auto_pair_addition:
                log.info("🔒 Auto pair addition is DISABLED in config. Using existing pairs only.")
                return preferred_symbols[:1] if preferred_symbols else []
            
            # Check if we have sufficient balance before selecting pairs
            total_balance = self._get_total_available_balance()
            
            if total_balance < balance_threshold_usd:
                log.warning(
                    f"❌ INSUFFICIENT BALANCE: ${total_balance:.2f} < ${balance_threshold_usd:.2f} threshold"
                )
                log.warning(
                    f"🛑 STOPPING PAIR SELECTION: Balance below threshold for new pairs"
                )
                log.info(
                    f"💡 Config: balance_threshold_usd={balance_threshold_usd}, capital_per_pair_usd={capital_per_pair_usd}"
                )
                return []
            
            # Calculate maximum pairs we can afford
            max_pairs_by_balance = min(
                int((total_balance - balance_threshold_usd + capital_per_pair_usd) / capital_per_pair_usd),
                max_concurrent_pairs
            )
            
            # Verificar se símbolos preferred são válidos
            valid_symbols = []
            for symbol in preferred_symbols[:max_pairs_by_balance]:  # Limit by balance
                if self._is_valid_trading_symbol(symbol):
                    valid_symbols.append(symbol)
            
            log.info(
                f"✅ BALANCE CHECK PASSED: ${total_balance:.2f} available (threshold: ${balance_threshold_usd})"
            )
            log.info(
                f"💰 Can afford {max_pairs_by_balance} pairs @ ${capital_per_pair_usd} each (max concurrent: {max_concurrent_pairs})"
            )
            log.info(f"📊 Validated {len(valid_symbols)} preferred symbols: {valid_symbols}")
            
            if len(valid_symbols) > 0:
                log.info(f"🚀 ADDING {len(valid_symbols)} NEW PAIRS TO TRADING")
            else:
                log.warning("⚠️  No valid symbols found despite sufficient balance")
            
            return valid_symbols
            
        except Exception as e:
            log.error(f"Error in simplified intelligent selection: {e}")
            return preferred_symbols
    
    def _get_total_available_balance(self) -> Decimal:
        """Get total available balance for trading."""
        try:
            # Get balances from API client
            spot_balance = self.api_client.get_balance()
            futures_balance = self.api_client.get_futures_balance()
            
            total_balance = Decimal("0")
            
            # Add USDT from spot
            if spot_balance:
                for asset in spot_balance:
                    if asset.get("asset") == "USDT":
                        free_balance = Decimal(str(asset.get("free", "0")))
                        total_balance += free_balance
                        break
            
            # Add USDT from futures
            if futures_balance:
                for asset in futures_balance:
                    if asset.get("asset") == "USDT":
                        available_balance = Decimal(str(asset.get("availableBalance", "0")))
                        total_balance += available_balance
                        break
            
            log.debug(f"Total available balance: ${total_balance:.2f} USDT")
            return total_balance
            
        except Exception as e:
            log.error(f"Error getting total balance: {e}")
            return Decimal("0")
    
    async def _get_intelligent_pair_selection(self, preferred_symbols: List[str]) -> List[str]:
        """
        Seleção inteligente combinando preferred symbols + análise de feeds sociais.
        
        Args:
            preferred_symbols: Lista de símbolos preferidos configurados
            
        Returns:
            Lista final de símbolos selecionados
        """
        try:
            # Importar o analisador de feeds sociais
            from utils.binance_social_feed_analyzer import BinanceSocialFeedAnalyzer
            
            # Configuração para análise social
            social_config = self.selector_config["social_feed_analysis"]
            config_with_social = {**self.config, "social_feed_analysis": social_config}
            
            # Analisar feeds sociais e notícias
            async with BinanceSocialFeedAnalyzer(config_with_social) as analyzer:
                trending_symbols = await analyzer.get_trending_symbols()
            
            # Extrair símbolos dos trending
            social_symbols = [ts.symbol for ts in trending_symbols if ts.confidence > 0.5]
            
            log.info(f"Found {len(social_symbols)} trending symbols from social analysis: {social_symbols[:10]}")
            
            # Criar sistema de scoring combinado
            symbol_scores = {}
            
            # 1. Preferred symbols tem score base alto
            for symbol in preferred_symbols:
                symbol_scores[symbol] = {
                    'score': 10.0,  # Score base alto
                    'sources': ['preferred'],
                    'reasons': ['configured_preferred']
                }
            
            # 2. Símbolos trending da análise social
            for trending_symbol in trending_symbols:
                symbol = trending_symbol.symbol
                
                # Calcular score baseado em multiple fatores
                social_score = (
                    trending_symbol.mentions * 2.0 +           # Número de menções
                    trending_symbol.sentiment_score * 3.0 +    # Sentiment
                    trending_symbol.confidence * 5.0 +         # Confiança
                    (1.0 if 'influencer' in trending_symbol.source else 0.5)  # Bonus influenciador
                )
                
                if symbol in symbol_scores:
                    # Se já existe (preferred), somar score
                    symbol_scores[symbol]['score'] += social_score
                    symbol_scores[symbol]['sources'].append('social')
                    symbol_scores[symbol]['reasons'].append(f"trending_{trending_symbol.source}")
                else:
                    # Novo símbolo apenas do social feed
                    symbol_scores[symbol] = {
                        'score': social_score,
                        'sources': ['social'],
                        'reasons': [f"trending_{trending_symbol.source}"]
                    }
            
            # 3. Filtrar símbolos que existem na Binance
            valid_symbols = {}
            for symbol, data in symbol_scores.items():
                if self._is_valid_trading_symbol(symbol):
                    valid_symbols[symbol] = data
                else:
                    log.debug(f"Symbol {symbol} not valid for trading, excluding")
            
            # 4. Ordenar por score e selecionar top símbolos
            sorted_symbols = sorted(
                valid_symbols.items(), 
                key=lambda x: x[1]['score'], 
                reverse=True
            )
            
            # 5. Criar lista final balanceada
            final_symbols = []
            
            # Garantir que pelo menos metade sejam preferred symbols
            preferred_in_final = [symbol for symbol, _ in sorted_symbols if 'preferred' in valid_symbols[symbol]['sources']]
            final_symbols.extend(preferred_in_final[:max(3, self.max_pairs // 2)])
            
            # Completar com símbolos trending
            for symbol, data in sorted_symbols:
                if symbol not in final_symbols and len(final_symbols) < self.max_pairs:
                    final_symbols.append(symbol)
            
            # Log da seleção final
            log.info("📈 INTELLIGENT PAIR SELECTION RESULTS:")
            for i, symbol in enumerate(final_symbols[:10]):
                data = valid_symbols[symbol]
                log.info(f"  {i+1}. {symbol} - Score: {data['score']:.1f} - Sources: {','.join(data['sources'])}")
            
            return final_symbols
            
        except Exception as e:
            log.error(f"Error in intelligent pair selection: {e}")
            # Fallback para preferred symbols
            log.warning("Falling back to preferred symbols only")
            return preferred_symbols
    
    def _is_valid_trading_symbol(self, symbol: str) -> bool:
        """Verifica se o símbolo é válido para trading na Binance."""
        try:
            # Verificar se termina com USDT
            if not symbol.endswith('USDT'):
                return False
            
            # Verificar se o símbolo existe na exchange
            exchange_info = self.api_client.get_exchange_info()
            if not exchange_info:
                return True  # Se não conseguir verificar, assumir válido
            
            # Procurar símbolo na lista
            for symbol_info in exchange_info.get("symbols", []):
                if symbol_info["symbol"] == symbol and symbol_info["status"] == "TRADING":
                    return True
            
            return False
            
        except Exception as e:
            log.debug(f"Error validating symbol {symbol}: {e}")
            return True  # Se erro na validação, assumir válido

    def get_market_summary(self) -> dict:
        """
        Gera resumo agregado do mercado para análise eficiente da IA.
        Evita analisar 471 pares individualmente.
        """
        try:
            log.info("Generating market summary for AI analysis...")
            
            tickers, kline_data = self._fetch_market_data()
            if not tickers or not kline_data:
                log.warning("Could not fetch market data for summary")
                return self._get_fallback_market_summary()
            
            metrics = self._calculate_metrics(tickers, kline_data)
            if not metrics:
                log.warning("No metrics calculated for market summary")
                return self._get_fallback_market_summary()
            
            # Calcular estatísticas agregadas
            volumes = [float(m["volume"]) for m in metrics.values()]
            atr_percentages = [float(m["atr_perc"]) * 100 for m in metrics.values()]
            adx_values = [float(m["adx"]) for m in metrics.values()]
            prices = [float(m["last_price"]) for m in metrics.values()]
            
            # Identificar pares de alto volume (top 10%)
            volume_threshold = sorted(volumes, reverse=True)[int(len(volumes) * 0.1)]
            high_volume_pairs = [
                symbol for symbol, m in metrics.items() 
                if float(m["volume"]) >= volume_threshold
            ][:10]  # Top 10 para evitar lista muito longa
            
            # Determinar tendência predominante do mercado
            bullish_count = 0
            bearish_count = 0
            for symbol, m in metrics.items():
                if float(m["atr_perc"]) > 0.03:  # Alta volatilidade
                    if float(m["adx"]) < 25:  # Baixo ADX = bom para grid
                        bullish_count += 1
                    else:
                        bearish_count += 1
            
            if bullish_count > bearish_count * 1.2:
                market_trend = "bullish"
            elif bearish_count > bullish_count * 1.2:
                market_trend = "bearish" 
            else:
                market_trend = "neutral"
            
            # Calcular distribuição de volatilidade
            low_vol_count = sum(1 for atr in atr_percentages if atr < 2.0)
            medium_vol_count = sum(1 for atr in atr_percentages if 2.0 <= atr <= 4.0)
            high_vol_count = sum(1 for atr in atr_percentages if atr > 4.0)
            
            summary = {
                "total_pairs": len(metrics),
                "avg_volume": sum(volumes) / len(volumes) if volumes else 0,
                "median_volume": sorted(volumes)[len(volumes)//2] if volumes else 0,
                "high_volume_pairs": high_volume_pairs,
                "market_trend": market_trend,
                "avg_volatility": sum(atr_percentages) / len(atr_percentages) if atr_percentages else 0,
                "volatility_distribution": {
                    "low": low_vol_count,
                    "medium": medium_vol_count, 
                    "high": high_vol_count
                },
                "avg_adx": sum(adx_values) / len(adx_values) if adx_values else 50,
                "price_range": {
                    "min": min(prices) if prices else 0,
                    "max": max(prices) if prices else 0,
                    "avg": sum(prices) / len(prices) if prices else 0
                },
                "market_conditions": self._assess_market_conditions(atr_percentages, adx_values),
                "timestamp": time.time()
            }
            
            log.info(f"Market summary generated: {summary['total_pairs']} pairs, "
                    f"trend: {summary['market_trend']}, "
                    f"avg_volume: {summary['avg_volume']:,.0f}")
            
            return summary
            
        except Exception as e:
            log.error(f"Error generating market summary: {e}")
            return self._get_fallback_market_summary()
    
    def _assess_market_conditions(self, atr_percentages: list, adx_values: list) -> str:
        """Avalia condições gerais do mercado baseado em volatilidade e tendência."""
        try:
            avg_atr = sum(atr_percentages) / len(atr_percentages) if atr_percentages else 0
            avg_adx = sum(adx_values) / len(adx_values) if adx_values else 50
            
            if avg_atr > 3.5 and avg_adx < 25:
                return "excellent_for_grid"  # Alta volatilidade, baixa tendência
            elif avg_atr > 2.5 and avg_adx < 30:
                return "good_for_grid"
            elif avg_atr < 1.5 or avg_adx > 40:
                return "poor_for_grid"  # Baixa volatilidade ou alta tendência
            else:
                return "moderate_for_grid"
                
        except Exception as e:
            log.warning(f"Error assessing market conditions: {e}")
            return "unknown"
    
    def monitor_atr_quality(self, active_pairs: List[str], trade_activity_data: Dict[str, Dict] = None) -> Dict[str, Dict]:
        """
        Monitora qualidade do ATR dos pares ativos e identifica pares problemáticos.
        Retorna sugestões de substituição para pares com ATR inadequado ou inativos.
        
        Args:
            active_pairs: Lista de pares atualmente ativos
            trade_activity_data: Dict com dados de atividade de trading por par
                Format: {symbol: {"last_trade_time": timestamp, "total_trades": count, "inactive_duration": seconds}}
        """
        try:
            problematic_pairs = {}
            replacement_suggestions = {}
            
            log.info("🔍 Monitorando qualidade de ATR e atividade dos pares ativos...")
            
            # Timeout de inatividade: 1 hora (3600 segundos)
            inactivity_timeout = 3600
            current_time = time.time()
            
            for symbol in active_pairs:
                try:
                    # Verificar atividade de trading primeiro (mesmo sem métricas)
                    inactive_duration = 0
                    total_trades = 0
                    last_trade_time = 0
                    
                    if trade_activity_data and symbol in trade_activity_data:
                        activity = trade_activity_data[symbol]
                        last_trade_time = activity.get("last_trade_time", 0)
                        total_trades = activity.get("total_trades", 0)
                        inactive_duration = current_time - last_trade_time if last_trade_time > 0 else 0
                        
                        inactive_hours = inactive_duration / 3600
                    
                    # Verificar critérios problemáticos baseados em atividade
                    inactive_too_long = inactive_duration > inactivity_timeout
                    consecutive_losses = activity.get("consecutive_losses", 0) if trade_activity_data and symbol in trade_activity_data else 0
                    too_many_losses = consecutive_losses >= 3  # 3 perdas consecutivas
                    
                    if inactive_too_long or too_many_losses:
                        issues = []
                        if inactive_too_long:
                            issues.append(f"Inativo há {inactive_hours:.1f}h")
                        if too_many_losses:
                            issues.append(f"{consecutive_losses} perdas consecutivas")
                            
                        log.info(f"🔄 {symbol}: Detectado como problemático - {', '.join(issues)}")
                        problematic_pairs[symbol] = {
                            "atr_percentage": 0,
                            "volume_24h": 0,
                            "inactive_duration_hours": inactive_hours,
                            "total_trades": total_trades,
                            "consecutive_losses": consecutive_losses,
                            "issues": issues
                        }
                        continue  # Pular análise de métricas se já é problemático por atividade
                    
                    # Obter métricas atuais do par
                    metrics = self._get_symbol_metrics(symbol)
                    
                    if not metrics:
                        continue
                        
                    atr_perc = float(metrics.get("atr_perc", 0)) * 100
                    volume_24h = metrics.get("volume_24h", 0)
                    
                    # Definir critérios problemáticos (atividade já foi verificada acima)
                    atr_low = atr_perc < 0.5
                    atr_zero = atr_perc == 0.0
                    volume_low = volume_24h < 1000000
                    
                    is_problematic = (atr_low or atr_zero or volume_low)
                    
                    if is_problematic:
                        problematic_pairs[symbol] = {
                            "atr_percentage": atr_perc,
                            "volume_24h": volume_24h,
                            "inactive_duration": inactive_duration,
                            "last_trade_time": last_trade_time,
                            "total_trades": total_trades,
                            "issues": []
                        }
                        
                        if atr_perc < 0.5:
                            problematic_pairs[symbol]["issues"].append(f"ATR baixo ({atr_perc:.3f}%)")
                        if atr_perc == 0.0:
                            problematic_pairs[symbol]["issues"].append("ATR zerado")
                        if volume_24h < 1000000:
                            problematic_pairs[symbol]["issues"].append(f"Volume baixo (${volume_24h:,.0f})")
                        if inactive_duration > inactivity_timeout:
                            hours_inactive = inactive_duration / 3600
                            problematic_pairs[symbol]["issues"].append(f"Inativo há {hours_inactive:.1f}h")
                        
                        log.warning(f"⚠️ Par problemático: {symbol} - {', '.join(problematic_pairs[symbol]['issues'])}")
                
                except Exception as e:
                    log.error(f"Erro ao analisar {symbol}: {e}")
            
            # Se há pares problemáticos, buscar substitutos
            if problematic_pairs:
                log.info(f"🔄 Buscando substitutos para {len(problematic_pairs)} pares problemáticos...")
                
                # Obter lista de pares alternativos com melhor ATR
                alternative_pairs = self._get_high_atr_alternatives(exclude_symbols=active_pairs)
                
                for problematic_symbol in problematic_pairs.keys():
                    if alternative_pairs:
                        best_alternative = alternative_pairs.pop(0)  # Pegar o melhor alternativo
                        replacement_suggestions[problematic_symbol] = best_alternative
                        
                        # Razão da substituição
                        issues = problematic_pairs[problematic_symbol]["issues"]
                        reason = f"Motivo: {', '.join(issues)}"
                        
                        log.info(f"💡 Sugestão: Substituir {problematic_symbol} por {best_alternative['symbol']} (ATR: {best_alternative['atr_percentage']:.2f}%) - {reason}")
            
            return {
                "problematic_pairs": problematic_pairs,
                "replacement_suggestions": replacement_suggestions,
                "total_problematic": len(problematic_pairs),
                "timestamp": current_time,
                "inactivity_timeout_hours": inactivity_timeout / 3600
            }
            
        except Exception as e:
            log.error(f"Erro no monitoramento de ATR: {e}")
            return {"problematic_pairs": {}, "replacement_suggestions": {}, "total_problematic": 0}
    
    def _get_high_atr_alternatives(self, exclude_symbols: List[str] = None, min_atr_perc: float = 1.5) -> List[Dict]:
        """
        Busca pares alternativos com ATR alto para substituição.
        """
        try:
            exclude_symbols = exclude_symbols or []
            alternatives = []
            
            # Lista de pares USDT populares para verificar
            candidate_symbols = [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT", "SOLUSDT",
                "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT", "UNIUSDT",
                "LINKUSDT", "XLMUSDT", "VETUSDT", "TRXUSDT", "EOSUSDT", "ETCUSDT",
                "FILUSDT", "AAVEUSDT", "MKRUSDT", "COMPUSDT", "YFIUSDT", "SUSHIUSDT"
            ]
            
            for symbol in candidate_symbols:
                if symbol in exclude_symbols:
                    continue
                    
                try:
                    metrics = self._get_symbol_metrics(symbol)
                    if not metrics:
                        continue
                        
                    atr_perc = float(metrics.get("atr_perc", 0)) * 100
                    volume_24h = metrics.get("volume_24h", 0)
                    
                    # Critérios para bom substituto
                    if (atr_perc >= min_atr_perc and 
                        volume_24h >= 5000000 and 
                        atr_perc <= 15.0):  # Não muito volátil também
                        
                        alternatives.append({
                            "symbol": symbol,
                            "atr_percentage": atr_perc,
                            "volume_24h": volume_24h,
                            "quality_score": atr_perc * (volume_24h / 1000000)  # Score combinado
                        })
                
                except Exception as e:
                    log.debug(f"Erro ao analisar candidato {symbol}: {e}")
            
            # Ordenar por quality_score decrescente
            alternatives.sort(key=lambda x: x["quality_score"], reverse=True)
            
            return alternatives[:10]  # Retornar top 10
            
        except Exception as e:
            log.error(f"Erro ao buscar alternativas de alta ATR: {e}")
            return []
    
    def _get_fallback_market_summary(self) -> dict:
        """Resumo de fallback quando não consegue obter dados reais."""
        return {
            "total_pairs": 471,
            "avg_volume": 5000000,
            "median_volume": 2000000,
            "high_volume_pairs": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "market_trend": "neutral",
            "avg_volatility": 2.5,
            "volatility_distribution": {"low": 150, "medium": 200, "high": 121},
            "avg_adx": 30,
            "price_range": {"min": 0.001, "max": 100000, "avg": 10},
            "market_conditions": "moderate_for_grid",
            "timestamp": time.time(),
            "fallback": True
        }
    
    def _get_pairs_with_open_positions(self) -> List[str]:
        """
        Busca todos os pares que atualmente têm posições abertas na conta futures.
        
        Returns:
            Lista de símbolos que têm posições abertas
        """
        pairs_with_positions = []
        
        try:
            # Buscar posições abertas na conta futures
            positions = self.api_client.get_futures_positions()
            
            if not positions:
                log.warning("Could not retrieve futures positions")
                return pairs_with_positions
            
            # Filtrar posições com quantidade diferente de zero
            for position in positions:
                try:
                    position_amt = float(position.get("positionAmt", 0))
                    symbol = position.get("symbol", "")
                    
                    # Se tem posição aberta (quantidade != 0)
                    if position_amt != 0 and symbol:
                        # Verificar se é um par USDT válido
                        if symbol.endswith("USDT") and symbol not in self.blacklist:
                            pairs_with_positions.append(symbol)
                            
                            # Log informações da posição
                            entry_price = position.get("entryPrice", "0")
                            unrealized_pnl = position.get("unrealizedPnl", "0")
                            side = "LONG" if position_amt > 0 else "SHORT"
                            
                            log.info(
                                f"📈 Open position found: {symbol} {side} "
                                f"Qty: {abs(position_amt):.6f} "
                                f"Entry: {entry_price} "
                                f"PnL: {unrealized_pnl} USDT"
                            )
                        
                except Exception as e:
                    log.warning(f"Error processing position data: {position} - {e}")
                    continue
            
            # Remover duplicatas e ordenar
            pairs_with_positions = list(set(pairs_with_positions))
            pairs_with_positions.sort()
            
            log.info(f"🔍 Total pairs with open positions: {len(pairs_with_positions)}")
            if pairs_with_positions:
                log.info(f"📋 Pairs: {pairs_with_positions}")
            
            return pairs_with_positions
            
        except Exception as e:
            log.error(f"Error getting pairs with open positions: {e}")
            return pairs_with_positions
