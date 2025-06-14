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
        self.selector_config = config.get("pair_selection", {})
        self.sentiment_config = config.get("sentiment_analysis", {})
        self.pair_filtering_config = self.sentiment_config.get("pair_filtering", {})

        # --- Standard Selection Parameters --- #
        self.min_volume_usd_24h = Decimal(
            str(self.selector_config.get("min_volume_usd_24h", "10000000"))
        )
        self.min_atr_perc_24h = (
            Decimal(str(self.selector_config.get("min_atr_perc_24h", "2.0"))) / 100
        )
        self.max_spread_perc = (
            Decimal(str(self.selector_config.get("max_spread_perc", "0.1"))) / 100
        )
        self.max_adx = Decimal(str(self.selector_config.get("max_adx", "25")))
        self.update_interval_hours = self.selector_config.get(
            "update_interval_hours", 6
        )
        self.blacklist = set(self.selector_config.get("blacklist", []))
        self.quote_asset = self.config.get("trading", {}).get(
            "quote_asset", "USDT"
        )  # e.g., USDT
        self.max_pairs = self.config.get("trading", {}).get("max_concurrent_pairs", 5)
        
        # --- Market-specific Parameters --- #
        futures_config = self.selector_config.get("futures_pairs", {})
        self.max_price_usdt = Decimal(str(futures_config.get("max_price_usdt", "999999")))  # NOVO: Filtro de preço máximo

        # --- Optional Filters --- #
        self.use_candlestick_filter = self.selector_config.get(
            "use_candlestick_filter", False
        )
        self.avoid_patterns = self.selector_config.get(
            "avoid_candlestick_patterns", ["CDLDOJI", "CDLENGULFING"]
        )

        # --- Sentiment Filter Parameters --- #
        self.sentiment_filtering_enabled = self.pair_filtering_config.get(
            "enabled", False
        )
        self.min_sentiment_for_new_pair = Decimal(
            str(self.pair_filtering_config.get("min_sentiment_for_new_pair", "-0.3"))
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
        preferred = self.selector_config.get("futures_pairs", {}).get("preferred_symbols", [])
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
            kline_limit = 50
            min_required_klines = 30

            for symbol in symbols_to_fetch_klines:
                klines = self.api_client.get_futures_klines(
                    symbol=symbol, interval="1h", limit=kline_limit
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
                        atr_series = talib.ATR(
                            high_prices, low_prices, close_prices, timeperiod=14
                        )
                        adx_series = talib.ADX(
                            high_prices, low_prices, close_prices, timeperiod=14
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
            
            # Verificar se temos preferred symbols configurados
            preferred = self.selector_config.get("futures_pairs", {}).get("preferred_symbols", [])
            use_social_feed = self.selector_config.get("use_social_feed_analysis", True)
            
            if preferred and len(preferred) >= 3 and not use_social_feed:
                # Se temos preferred symbols suficientes E não usar análise social, usar apenas eles (otimização)
                log.info(f"Using preferred symbols for fast selection: {preferred}")
                self.selected_pairs = preferred[:self.max_pairs]
                self.last_update_time = current_time
                self._save_cache()
                log.info(f"Fast pair selection completed. Selected pairs: {self.selected_pairs}")
            elif use_social_feed:
                # Usar análise inteligente combinando preferred + social feed
                log.info("Using intelligent pair selection with social feed analysis...")
                try:
                    # Usar método sincronizado para evitar conflitos de event loop
                    intelligent_pairs = self._get_intelligent_pair_selection_sync(preferred)
                    
                    self.selected_pairs = intelligent_pairs[:self.max_pairs]
                    self.last_update_time = current_time
                    self._save_cache()
                    log.info(f"Intelligent pair selection completed. Selected pairs: {self.selected_pairs}")
                except Exception as e:
                    log.error(f"Error in intelligent selection: {e}")
                    # Fallback para preferred symbols
                    log.warning("Falling back to preferred symbols")
                    self.selected_pairs = preferred[:self.max_pairs]
                    self.last_update_time = current_time
                    self._save_cache()
            else:
                # Caso contrário, fazer análise completa
                log.info("No sufficient preferred symbols, performing full market analysis...")
                tickers, kline_data = self._fetch_market_data()
                if tickers and kline_data:
                    metrics = self._calculate_metrics(tickers, kline_data)
                    ranked_symbols = self._filter_and_rank_pairs(metrics)
                    self.selected_pairs = ranked_symbols[: self.max_pairs]
                    self.last_update_time = current_time
                    self._save_cache()
                    log.info(
                        f"Full pair selection updated. Selected pairs: {self.selected_pairs}"
                    )
                else:
                    log.error(
                        "Failed to update pair selection due to data fetching errors."
                    )
                log.warning(f"Keeping previously selected pairs: {self.selected_pairs}")

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
            
            # Por enquanto, retornar preferred symbols com análise básica
            # TODO: Implementar versão simplificada da análise social sem async
            
            # Verificar se símbolos preferred são válidos
            valid_symbols = []
            for symbol in preferred_symbols:
                if self._is_valid_trading_symbol(symbol):
                    valid_symbols.append(symbol)
            
            log.info(f"Validated {len(valid_symbols)} preferred symbols: {valid_symbols}")
            
            # Por enquanto, retornar apenas preferred symbols válidos
            # Em futuras iterações, podemos adicionar análise social básica sem async
            return valid_symbols
            
        except Exception as e:
            log.error(f"Error in simplified intelligent selection: {e}")
            return preferred_symbols
    
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
            social_config = self.selector_config.get("social_feed_analysis", {})
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
