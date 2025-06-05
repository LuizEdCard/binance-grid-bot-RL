# Módulo de Gerenciamento de Risco para Bot de Grid Trading
# Suporta mercados Spot e Futuros

import time
from decimal import Decimal

import numpy as np
import pandas as pd
from binance.enums import SIDE_SELL, SIDE_BUY, FUTURE_ORDER_TYPE_STOP_MARKET

from utils.api_client import APIClient
from utils.logger import setup_logger
log = setup_logger("risk_management")

# Tentativa de importar TA-Lib
try:
    import talib

    talib_available = True
    log.info("Biblioteca TA-Lib encontrada e importada com sucesso para RiskManager.")
except ImportError:
    talib_available = False
    log.warning(
        "Biblioteca TA-Lib não encontrada para RiskManager. SL baseado em ATR e verificações de padrões estarão indisponíveis. Por favor, instale TA-Lib para funcionalidade completa (veja talib_installation_guide.md)."
    )


class RiskManager:
    """Lida com lógica de gerenciamento de risco, incluindo stop loss, proteção de lucro, 
    disjuntores e ajuste de risco dinâmico baseado no sentimento do mercado.
    Suporta tanto mercados Spot quanto Futuros.
    """

    def __init__(
        self,
        symbol: str,
        config: dict,
        grid_logic,
        api_client: APIClient,
        alerter,
        get_sentiment_score_func=None,
        market_type: str = "futures",  # "futures" ou "spot"
    ):
        self.symbol = symbol
        self.config = config
        self.market_type = market_type.lower()  # "futures" ou "spot"
        # Precisa do grid_logic para acessar informações de alavancagem/posição atuais
        self.grid_logic = grid_logic
        self.api_client = api_client
        self.alerter = alerter
        # Função para obter o último score de sentimento
        self.get_sentiment_score_func = get_sentiment_score_func

        self.risk_config = config.get("risk_management", {})
        self.grid_config = config.get("grid", {})
        self.sentiment_config = config.get("sentiment_analysis", {})
        self.risk_adjustment_config = self.sentiment_config.get("risk_adjustment", {})
        
        # Configurações específicas por mercado
        self.market_specific_config = self.risk_config.get(
            f"{self.market_type}_risk", {}
        )

        # --- Parâmetros de Risco Padrão --- #
        self.max_drawdown_perc = (
            Decimal(str(self.risk_config.get("max_drawdown_perc", "10.0"))) / 100
        )
        self.dynamic_sl_profit_lock_perc = (
            Decimal(str(self.risk_config.get("dynamic_sl_profit_lock_perc", "80.0")))
            / 100
        )
        self.tp_sl_ratio = Decimal(str(self.risk_config.get("tp_sl_ratio", "3.0")))
        self.loss_protection_trigger_perc = (
            Decimal(str(self.risk_config.get("loss_protection_trigger_perc", "15.0")))
            / 100
        )
        self.api_failure_timeout_minutes = self.risk_config.get(
            "api_failure_timeout_minutes", 5
        )
        
        # --- Parâmetros Específicos do Mercado --- #
        if self.market_type == "futures":
            self.max_leverage = self.market_specific_config.get("max_leverage", 20)
            self.liquidation_buffer_perc = Decimal(
                str(self.market_specific_config.get("liquidation_buffer_perc", "15.0"))
            ) / 100
            self.max_position_size_perc = Decimal(
                str(self.market_specific_config.get("max_position_size_perc", "50.0"))
            ) / 100
        else:  # spot
            self.max_asset_allocation_perc = Decimal(
                str(self.market_specific_config.get("max_asset_allocation_perc", "70.0"))
            ) / 100
            self.min_stable_balance_perc = Decimal(
                str(self.market_specific_config.get("min_stable_balance_perc", "30.0"))
            ) / 100

        # --- TA-Lib Specific Risk Config --- #
        self.use_atr_stop_loss = self.risk_config.get("use_atr_stop_loss", False)
        self.atr_sl_period = self.risk_config.get("atr_sl_period", 14)
        self.atr_sl_multiplier = Decimal(
            str(self.risk_config.get("atr_sl_multiplier", "2.0"))
        )
        self.check_reversal_patterns_sl = self.risk_config.get(
            "check_reversal_patterns_sl", False
        )
        self.reversal_patterns_long = self.risk_config.get(
            "reversal_patterns_long_exit",
            ["CDLENGULFING", "CDLDARKCLOUDCOVER", "CDLSHOOTINGSTAR"],
        )  # Bearish patterns to exit long
        self.reversal_patterns_short = self.risk_config.get(
            "reversal_patterns_short_exit",
            ["CDLENGULFING", "CDLPIERCING", "CDLHAMMER", "CDLINVERTEDHAMMER"],
        )  # Bullish patterns to exit short

        # --- Sentiment-Based Risk Adjustment Config --- #
        self.sentiment_risk_adj_enabled = self.risk_adjustment_config.get(
            "enabled", False
        )
        self.leverage_reduction_threshold = Decimal(
            str(self.risk_adjustment_config.get("leverage_reduction_threshold", "-0.5"))
        )
        self.leverage_reduction_factor = Decimal(
            str(self.risk_adjustment_config.get("leverage_reduction_factor", "0.5"))
        )
        # Position increase is generally risky, keep disabled by default
        # self.position_increase_threshold = Decimal(str(self.risk_adjustment_config.get('position_increase_threshold', '0.7')))
        # self.position_increase_factor = Decimal(str(self.risk_adjustment_config.get('position_increase_factor', '1.1')))

        # --- State Variables --- #
        self.highest_realized_pnl = Decimal("0")
        self.active_stop_loss_order_id = None
        self.last_api_success_time = None
        self.initial_balance = None
        self.last_atr_value = None  # Store last calculated ATR
        self.last_applied_leverage = None  # Track leverage applied by this module

        log.info(
            f"[{self.symbol}] RiskManager inicializado para mercado {self.market_type.upper()}. Max Drawdown: {self.max_drawdown_perc*100}%, Use ATR SL: {self.use_atr_stop_loss}, Check Reversal Patterns: {self.check_reversal_patterns_sl}, Sentiment Risk Adj: {self.sentiment_risk_adj_enabled}"
        )
        if (
            self.use_atr_stop_loss or self.check_reversal_patterns_sl
        ) and not talib_available:
            log.warning(
                f"[{self.symbol}] Recursos de risco dependentes do TA-Lib solicitados mas biblioteca não encontrada. Recursos desabilitados."
            )
            self.use_atr_stop_loss = False
            self.check_reversal_patterns_sl = False
        if self.sentiment_risk_adj_enabled and self.get_sentiment_score_func is None:
            log.warning(
                f"[{self.symbol}] Ajuste de risco por sentimento habilitado, mas nenhuma função de score de sentimento fornecida. Recurso desabilitado."
            )
            self.sentiment_risk_adj_enabled = False

    def check_spot_market_risks(self, account_info: dict) -> bool:
        """Verifica riscos específicos do mercado Spot."""
        if self.market_type != "spot":
            return False
            
        try:
            # Calcula alocação total em ativos não-stablecoins
            total_balance_usd = Decimal("0")
            non_stable_balance_usd = Decimal("0")
            stable_coins = ["USDT", "USDC", "BUSD", "DAI", "TUSD"]
            
            for balance in account_info.get("balances", []):
                asset = balance["asset"]
                free_amount = Decimal(balance["free"])
                locked_amount = Decimal(balance["locked"])
                total_amount = free_amount + locked_amount
                
                if total_amount > 0:
                    # Aproximação: assumir que ativos não-stable valem ~$50 cada (deve ser melhorado)
                    if asset in stable_coins:
                        balance_usd = total_amount  # Stablecoins = 1:1 USD
                    else:
                        # Para uma implementação real, deveria buscar preço atual do ativo
                        balance_usd = total_amount * Decimal("50")  # Aproximação
                    
                    total_balance_usd += balance_usd
                    if asset not in stable_coins:
                        non_stable_balance_usd += balance_usd
            
            if total_balance_usd > 0:
                non_stable_allocation = non_stable_balance_usd / total_balance_usd
                stable_allocation = (total_balance_usd - non_stable_balance_usd) / total_balance_usd
                
                # Verificar alocação máxima em ativos não-stable
                if non_stable_allocation > self.max_asset_allocation_perc:
                    log.warning(
                        f"[{self.symbol}] RISCO SPOT: Alocação em ativos não-stable ({non_stable_allocation*100:.1f}%) excede máximo ({self.max_asset_allocation_perc*100:.1f}%)"
                    )
                    self.alerter.send_message(
                        f"[{self.symbol}] Risco Spot: Muita exposição em ativos não-stable ({non_stable_allocation*100:.1f}%)",
                        level="WARNING"
                    )
                    return True
                
                # Verificar saldo mínimo em stablecoins
                if stable_allocation < self.min_stable_balance_perc:
                    log.warning(
                        f"[{self.symbol}] RISCO SPOT: Saldo em stablecoins ({stable_allocation*100:.1f}%) abaixo do mínimo ({self.min_stable_balance_perc*100:.1f}%)"
                    )
                    self.alerter.send_message(
                        f"[{self.symbol}] Risco Spot: Saldo em stablecoins muito baixo ({stable_allocation*100:.1f}%)",
                        level="WARNING"
                    )
                    return True
                    
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao verificar riscos do mercado Spot: {e}", exc_info=True)
            
        return False

    def check_futures_market_risks(self, position_info: dict) -> bool:
        """Verifica riscos específicos do mercado Futuros."""
        if self.market_type != "futures":
            return False
            
        try:
            position_amt = Decimal(position_info.get("positionAmt", "0"))
            if position_amt == 0:
                return False
                
            entry_price = Decimal(position_info.get("entryPrice", "0"))
            mark_price = Decimal(position_info.get("markPrice", "0"))
            liquidation_price = Decimal(position_info.get("liquidationPrice", "0"))
            
            if liquidation_price > 0 and mark_price > 0:
                # Calcula distância até liquidação
                if position_amt > 0:  # Long
                    liquidation_distance = (mark_price - liquidation_price) / mark_price
                else:  # Short
                    liquidation_distance = (liquidation_price - mark_price) / mark_price
                
                # Verificar buffer de liquidação
                if liquidation_distance < self.liquidation_buffer_perc:
                    log.warning(
                        f"[{self.symbol}] RISCO FUTUROS: Muito próximo da liquidação! Distância: {liquidation_distance*100:.1f}% < Buffer: {self.liquidation_buffer_perc*100:.1f}%"
                    )
                    self.alerter.send_critical_alert(
                        f"[{self.symbol}] PERIGO: Posição próxima da liquidação ({liquidation_distance*100:.1f}%)!"
                    )
                    return True
                    
        except Exception as e:
            log.error(f"[{self.symbol}] Erro ao verificar riscos do mercado Futuros: {e}", exc_info=True)
            
        return False

    def set_initial_balance(self, balance: Decimal):
        """Define saldo inicial para cálculo de drawdown."""
        if self.initial_balance is None:
            self.initial_balance = balance
            log.info(
                f"[{self.symbol}] Saldo inicial definido para cálculo de drawdown: {self.initial_balance}"
            )

    def check_circuit_breakers(self, current_balance: Decimal) -> bool:
        # ... (no changes) ...
        if self.initial_balance is not None and self.initial_balance > 0:
            current_drawdown = (
                self.initial_balance - current_balance
            ) / self.initial_balance
            if current_drawdown >= self.max_drawdown_perc:
                log.critical(
                    f"[{self.symbol}] CIRCUIT BREAKER TRIPPED: Max Drawdown exceeded! Drawdown: {current_drawdown*100:.2f}% >= {self.max_drawdown_perc*100}%"
                )
                self.alerter.send_critical_alert(
                    f"[{self.symbol}] CIRCUIT BREAKER: Max Drawdown {self.max_drawdown_perc*100}% Hit! Shutting down pair."
                )
                return True
        return False

    def _fetch_recent_data_for_risk(self, periods_needed: int):
        """Busca dados recentes para cálculos de risco baseado no tipo de mercado."""
        if not talib_available:
            return None
        try:
            limit = periods_needed + 5  # Adiciona buffer
            # Busca klines baseado no tipo de mercado
            if self.market_type == "spot":
                klines = self.api_client.get_spot_klines(
                    symbol=self.symbol, interval="1h", limit=limit
                )
            else:  # futures
                klines = self.api_client.get_futures_klines(
                    symbol=self.symbol, interval="1h", limit=limit
                )
            if not klines or len(klines) < periods_needed:
                log.warning(
                    f"[{self.symbol}] Insufficient kline data ({len(klines) if klines else 0}/{periods_needed}) for TA-Lib risk calculation."
                )
                return None

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
            df["Open"] = pd.to_numeric(df["Open"])
            df["High"] = pd.to_numeric(df["High"])
            df["Low"] = pd.to_numeric(df["Low"])
            df["Close"] = pd.to_numeric(df["Close"])
            return df
        except Exception as e:
            log.error(
                f"[{self.symbol}] Error fetching data for risk calculation: {e}",
                exc_info=True,
            )
            return None

    def _calculate_atr(self, df: pd.DataFrame) -> Decimal | None:
        # ... (no changes) ...
        if df is None or not talib_available:
            return None
        try:
            high_prices = df["High"].values
            low_prices = df["Low"].values
            close_prices = df["Close"].values

            atr_series = talib.ATR(
                high_prices, low_prices, close_prices, timeperiod=self.atr_sl_period
            )
            latest_atr = (
                atr_series[~np.isnan(atr_series)][-1]
                if not np.all(np.isnan(atr_series))
                else None
            )

            if latest_atr is not None:
                self.last_atr_value = Decimal(str(latest_atr))
                log.debug(
                    f"[{self.symbol}] Calculated ATR({self.atr_sl_period}): {self.last_atr_value}"
                )
                return self.last_atr_value
            else:
                log.warning(f"[{self.symbol}] Could not calculate valid ATR.")
                return None
        except Exception as e:
            log.error(f"[{self.symbol}] Error calculating ATR: {e}", exc_info=True)
            return None

    def _check_reversal_patterns(
        self, df: pd.DataFrame, position_is_long: bool
    ) -> str | None:
        # ... (no changes) ...
        if df is None or not talib_available or not self.check_reversal_patterns_sl:
            return None

        try:
            open_prices = df["Open"].values
            high_prices = df["High"].values
            low_prices = df["Low"].values
            close_prices = df["Close"].values

            patterns_to_check = (
                self.reversal_patterns_long
                if position_is_long
                else self.reversal_patterns_short
            )

            for pattern_func_name in patterns_to_check:
                if hasattr(talib, pattern_func_name):
                    pattern_func = getattr(talib, pattern_func_name)
                    try:
                        result = pattern_func(
                            open_prices, high_prices, low_prices, close_prices
                        )
                        if result[-1] != 0:  # Pattern detected on the last candle
                            log.warning(
                                f"[{self.symbol}] Detected potential reversal pattern: {pattern_func_name} for {'LONG' if position_is_long else 'SHORT'} position."
                            )
                            return pattern_func_name  # Return name of detected pattern
                    except Exception as e_pattern:
                        log.warning(
                            f"[{self.symbol}] Error calculating pattern {pattern_func_name}: {e_pattern}"
                        )
                else:
                    # Corrected f-string
                    log.warning(
                        f"[{self.symbol}] Candlestick pattern function '{pattern_func_name}' not found in TA-Lib."
                    )
            return None  # No relevant pattern detected
        except Exception as e:
            log.error(
                f"[{self.symbol}] Error checking reversal patterns: {e}", exc_info=True
            )
            return None

    def manage_stop_loss(self, position: dict, total_realized_pnl: Decimal):
        # ... (stop loss logic remains largely the same, but could be influenced by adjusted leverage/position size) ...
        log.debug(
            f"[{self.symbol}] Managing stop loss. Position: {position['positionAmt']}, Realized PNL: {total_realized_pnl}"
        )

        position_qty = position["positionAmt"]
        if position_qty.is_zero():
            if self.active_stop_loss_order_id:
                log.info(
                    f"[{self.symbol}] No position, cancelling active SL order {self.active_stop_loss_order_id}"
                )
                try:
                    self.api_client.cancel_futures_order(
                        symbol=self.symbol, orderId=self.active_stop_loss_order_id
                    )
                    self.active_stop_loss_order_id = None
                except Exception as e:
                    log.error(
                        f"[{self.symbol}] Failed to cancel SL order {self.active_stop_loss_order_id}: {e}"
                    )
            return

        # Fetch data if using TA-Lib features
        df = None
        periods_needed = 0
        if self.use_atr_stop_loss:
            periods_needed = max(periods_needed, self.atr_sl_period)
        if self.check_reversal_patterns_sl:
            periods_needed = max(periods_needed, 2)

        if periods_needed > 0 and talib_available:
            df = self._fetch_recent_data_for_risk(periods_needed)

        # Calculate ATR if needed
        current_atr = None
        if self.use_atr_stop_loss and df is not None:
            current_atr = self._calculate_atr(df)
        if current_atr is None:
            current_atr = self.last_atr_value

        # Check for reversal patterns if enabled
        reversal_pattern_detected = None
        if self.check_reversal_patterns_sl and df is not None:
            reversal_pattern_detected = self._check_reversal_patterns(
                df, position_qty > 0
            )

        # Calculate Stop Loss Price
        entry_price = position["entryPrice"]
        mark_price = position["markPrice"]
        stop_price = None
        is_long = position_qty > 0

        # 1. Calculate Initial/Base Stop Loss
        base_stop_price = None
        if self.use_atr_stop_loss and current_atr is not None:
            if is_long:
                base_stop_price = entry_price - (current_atr * self.atr_sl_multiplier)
            else:  # Short
                base_stop_price = entry_price + (current_atr * self.atr_sl_multiplier)
            log.debug(
                f"[{self.symbol}] Base SL using ATR({self.atr_sl_period}) * {self.atr_sl_multiplier}: {base_stop_price}"
            )
        else:
            initial_sl_percentage = (
                Decimal(str(self.risk_config.get("fallback_sl_percentage", "1.0")))
                / 100
            )  # Configurable fallback
            if is_long:
                base_stop_price = entry_price * (Decimal("1") - initial_sl_percentage)
            else:  # Short
                base_stop_price = entry_price * (Decimal("1") + initial_sl_percentage)
            log.debug(
                f"[{self.symbol}] Base SL using fallback percentage {initial_sl_percentage*100}%: {base_stop_price}"
            )

        stop_price = base_stop_price

        # 2. Apply Trailing Stop / Profit Locking (if profitable)
        unrealized_profit = position.get("unRealizedProfit", Decimal("0"))
        if (is_long and mark_price > entry_price) or (
            not is_long and mark_price < entry_price
        ):
            trailing_distance = None
            if self.use_atr_stop_loss and current_atr is not None:
                trailing_distance = current_atr * self.atr_sl_multiplier
            else:
                initial_sl_percentage = (
                    Decimal(str(self.risk_config.get("fallback_sl_percentage", "1.0")))
                    / 100
                )
                trailing_distance = mark_price * initial_sl_percentage

            if trailing_distance is not None:
                if is_long:
                    trailing_stop = mark_price - trailing_distance
                    stop_price = max(stop_price, trailing_stop)  # Trail stop upwards
                else:  # Short
                    trailing_stop = mark_price + trailing_distance
                    stop_price = min(stop_price, trailing_stop)  # Trail stop downwards
                log.debug(
                    f"[{self.symbol}] Trailing SL applied. New potential SL: {stop_price}"
                )

        # 3. Adjust SL based on Reversal Patterns (Optional)
        if reversal_pattern_detected:
            log.warning(
                f"[{self.symbol}] Adjusting SL due to detected reversal pattern: {reversal_pattern_detected}"
            )
            tighten_factor = Decimal("0.5")
            if is_long:
                current_sl_distance = mark_price - stop_price
                if current_sl_distance > 0:
                    stop_price = stop_price + current_sl_distance * tighten_factor
                    stop_price = min(
                        stop_price,
                        mark_price
                        * (Decimal("1") - self.api_client.tick_size * Decimal("2")),
                    )
            else:  # Short
                current_sl_distance = stop_price - mark_price
                if current_sl_distance > 0:
                    stop_price = stop_price - current_sl_distance * tighten_factor
                    stop_price = max(
                        stop_price,
                        mark_price
                        * (Decimal("1") + self.api_client.tick_size * Decimal("2")),
                    )
            log.warning(
                f"[{self.symbol}] SL tightened due to pattern. New SL: {stop_price}"
            )

        # 4. Place or Modify the Stop Loss Order
        if stop_price:
            formatted_stop_price = self.api_client._format_price(stop_price)
            if formatted_stop_price:
                log.info(
                    f"[{self.symbol}] Final calculated Stop Loss price: {formatted_stop_price}"
                )
                self._place_or_modify_stop_order(formatted_stop_price, position_qty)
            else:
                log.error(
                    f"[{self.symbol}] Could not format calculated stop price {stop_price}. SL not placed/modified."
                )
        else:
            log.warning(f"[{self.symbol}] Could not determine a valid stop price.")

    def _place_or_modify_stop_order(self, stop_price_str: str, position_qty: Decimal):
        # ... (no changes) ...
        if position_qty.is_zero():
            return

        side = SIDE_SELL if position_qty > 0 else SIDE_BUY
        close_qty = abs(position_qty)
        formatted_close_qty = self.api_client._format_quantity(close_qty)

        if not formatted_close_qty or Decimal(formatted_close_qty).is_zero():
            log.error(
                f"[{self.symbol}] Invalid quantity {formatted_close_qty} for SL order."
            )
            return

        needs_update = False
        if self.active_stop_loss_order_id:
            try:
                log.info(
                    f"[{self.symbol}] Cancelling existing SL order {self.active_stop_loss_order_id} to update."
                )
                self.api_client.cancel_futures_order(
                    symbol=self.symbol, orderId=self.active_stop_loss_order_id
                )
                self.active_stop_loss_order_id = None
                needs_update = True  # Cancelled, so definitely need to place new one
            except Exception as e:
                log.error(
                    f"[{self.symbol}] Failed to cancel existing SL order {self.active_stop_loss_order_id}: {e}. Assuming it needs replacement."
                )
                self.active_stop_loss_order_id = None
                needs_update = True
        else:
            needs_update = True  # No active order, need to place one

        if needs_update:
            try:
                log.info(
                    f"[{self.symbol}] Placing new STOP_MARKET order: Side={side}, Qty={formatted_close_qty}, StopPrice={stop_price_str}"
                )
                sl_order = self.api_client.place_futures_order(
                    symbol=self.symbol,
                    side=side,
                    order_type=FUTURE_ORDER_TYPE_STOP_MARKET,
                    quantity=formatted_close_qty,
                    stop_price=stop_price_str,
                    close_position=True,  # Ensure it closes the position
                )
                if sl_order and "orderId" in sl_order:
                    self.active_stop_loss_order_id = sl_order["orderId"]
                    log.info(
                        f"[{self.symbol}] Placed new SL order {self.active_stop_loss_order_id} at stop price {stop_price_str}"
                    )
                else:
                    log.error(
                        f"[{self.symbol}] Failed to place SL order. Response: {sl_order}"
                    )
            except Exception as e:
                log.error(
                    f"[{self.symbol}] Exception placing SL order: {e}", exc_info=True
                )

    def protect_realized_profit(self, position: dict, total_realized_pnl: Decimal):
        # ... (no changes) ...
        if total_realized_pnl <= 0:
            return  # No profit to protect

        self.highest_realized_pnl = max(self.highest_realized_pnl, total_realized_pnl)
        guaranteed_profit = self.highest_realized_pnl * self.dynamic_sl_profit_lock_perc
        current_unrealized_loss = abs(position.get("unRealizedProfit", Decimal("0")))

        if current_unrealized_loss > 0 and guaranteed_profit > 0:
            loss_impact_on_guaranteed = current_unrealized_loss / guaranteed_profit
            if loss_impact_on_guaranteed >= self.loss_protection_trigger_perc:
                log.warning(
                    f"[{self.symbol}] PROFIT PROTECTION TRIGGERED: Unrealized loss ({current_unrealized_loss}) is {loss_impact_on_guaranteed*100:.2f}% of guaranteed profit ({guaranteed_profit}). Closing position."
                )
                self.alerter.send_message(
                    f"[{self.symbol}] Profit Protection Triggered! Closing position to secure {guaranteed_profit:.2f} profit.",
                    level="WARNING",
                )
                try:
                    self.grid_logic.close_position_market()  # Use grid_logic method to close
                    self.highest_realized_pnl = Decimal("0")  # Reset after closing
                except Exception as e:
                    log.error(
                        f"[{self.symbol}] Error closing position due to profit protection: {e}"
                    )

    def adjust_risk_based_on_sentiment(self):
        """Adjusts leverage based on the current market sentiment score."""
        if not self.sentiment_risk_adj_enabled or self.get_sentiment_score_func is None:
            return

        try:
            current_sentiment = Decimal(
                str(self.get_sentiment_score_func(smoothed=True))
            )  # Use smoothed score
            log.debug(
                f"[{self.symbol}] Checking sentiment for risk adjustment. Score: {current_sentiment:.4f}"
            )

            # --- Leverage Reduction --- #
            if current_sentiment <= self.leverage_reduction_threshold:
                current_leverage = (
                    self.grid_logic.get_current_leverage()
                )  # Need method in GridLogic
                if current_leverage is None:
                    log.warning(
                        f"[{self.symbol}] Could not get current leverage to apply sentiment adjustment."
                    )
                    return

                target_leverage = int(
                    Decimal(current_leverage) * self.leverage_reduction_factor
                )
                # Ensure leverage is at least 1
                target_leverage = max(1, target_leverage)

                if (
                    target_leverage < current_leverage
                    and target_leverage != self.last_applied_leverage
                ):
                    log.warning(
                        f"[{self.symbol}] SENTIMENT RISK ADJUSTMENT: Sentiment ({current_sentiment:.4f}) <= threshold ({self.leverage_reduction_threshold}). Reducing leverage from {current_leverage}x to {target_leverage}x."
                    )
                    try:
                        self.api_client.change_futures_leverage(
                            symbol=self.symbol, leverage=target_leverage
                        )
                        self.alerter.send_message(
                            f"[{self.symbol}] Sentiment LOW ({current_sentiment:.2f}). Leverage reduced to {target_leverage}x.",
                            level="WARNING",
                        )
                        self.last_applied_leverage = target_leverage
                        # Important: GridLogic might need to be aware of this change
                        # if it caches leverage or uses it for calculations.
                        # self.grid_logic.update_leverage(target_leverage) #
                        # Add method to GridLogic
                    except Exception as e:
                        log.error(
                            f"[{self.symbol}] Failed to apply leverage reduction to {target_leverage}x: {e}"
                        )
                elif target_leverage == self.last_applied_leverage:
                    log.debug(
                        f"[{self.symbol}] Sentiment condition met for leverage reduction, but target leverage {target_leverage}x already applied."
                    )
                else:
                    log.debug(
                        f"[{self.symbol}] Sentiment condition met for leverage reduction, but target leverage {target_leverage}x is not lower than current {current_leverage}x."
                    )
            else:
                # If sentiment improves, consider resetting leverage? Or let manual control/RL handle it?
                # For now, only reducing leverage automatically.
                # Reset last_applied_leverage if condition no longer met,
                # allowing future reductions
                if self.last_applied_leverage is not None:
                    log.info(
                        f"[{self.symbol}] Sentiment ({current_sentiment:.4f}) above reduction threshold. Resetting last applied leverage."
                    )
                    self.last_applied_leverage = None

            # --- Position Size Increase (Example - Use Cautiously) --- #
            # if self.position_increase_threshold is not None and current_sentiment >= self.position_increase_threshold:
            #     # Logic to increase position size factor in GridLogic or here
            #     log.warning(f"[{self.symbol}] SENTIMENT RISK ADJUSTMENT: Sentiment ({current_sentiment:.4f}) >= threshold ({self.position_increase_threshold}). Consider increasing position size.")
            #     # self.grid_logic.update_position_size_factor(self.position_increase_factor)

        except Exception as e:
            log.error(
                f"[{self.symbol}] Error during sentiment risk adjustment: {e}",
                exc_info=True,
            )

    def run_checks(self):
        """Runs all risk management checks in sequence."""
        log.debug(f"[{self.symbol}] Running risk management checks...")
        try:
            # 0. Update API success time (used for API failure check)
            self.last_api_success_time = time.time()

            # 1. Check Sentiment-Based Risk Adjustment (e.g., Leverage)
            self.adjust_risk_based_on_sentiment()

            # 2. Get current position and balance info
            position_data_list = self.api_client.get_futures_position_info(symbol=self.symbol)
            current_position_info = None

            if position_data_list: # API returns a list
                # Find the position for the specific symbol
                # In normal operation with a symbol, it should be the only one, or not present
                for pos in position_data_list:
                    if pos.get('symbol') == self.symbol:
                        current_position_info = pos
                        break

            if current_position_info is None:
                log.warning(
                    f"[{self.symbol}] No position information found for symbol via get_futures_position_info. Assuming no open position. Skipping some risk checks."
                )
                # If no position, many risk checks are not applicable or need default handling
                # For example, stop loss management and profit protection might be skipped.
                # We might still want to check overall account drawdown if balance_info is available.
                # For now, let's return if key position info is missing for futures.
                if self.market_type == "futures": # Specific checks for futures might depend heavily on position
                    return


            # Convert relevant parts of current_position_info to Decimal for consistency if needed by other methods
            # For example, if manage_stop_loss expects Decimals:
            # This is a simplified conversion; ensure all necessary fields are converted as expected.
            position_for_sl = {
                "positionAmt": Decimal(current_position_info.get("positionAmt", "0") if current_position_info else "0"),
                "entryPrice": Decimal(current_position_info.get("entryPrice", "0") if current_position_info else "0"),
                "markPrice": Decimal(current_position_info.get("markPrice", "0") if current_position_info else "0"),
                "unRealizedProfit": Decimal(current_position_info.get("unRealizedProfit", "0") if current_position_info else "0"),
                "realizedPnl": Decimal(current_position_info.get("realizedPnl", "0") if current_position_info else "0") # Note: realizedPnl is usually not part of position info directly from this call
            }


            # Fetch balance info (assuming this method is okay or handled elsewhere for None)
            # For Spot, this might be more relevant than futures position for some checks
            if self.market_type == "spot":
                balance_info = self.api_client.get_spot_account_balance()
                # Process spot balance for relevant risk checks (e.g., total value, allocation)
                if self.check_spot_market_risks(balance_info if balance_info else {}):
                     self.grid_logic.trigger_shutdown(reason="Spot Market Risk Triggered")
                     return
            else: # futures
                balance_info = self.api_client.get_futures_account_balance() # This gets general balance, not just for one symbol
                # Futures-specific market risks (like liquidation distance)
                if current_position_info and self.check_futures_market_risks(current_position_info): # Pass the raw dict from API
                    self.grid_logic.trigger_shutdown(reason="Futures Market Risk Triggered (e.g. Liquidation)")
                    return


            if balance_info is None: # General check if balance fetching failed
                log.error(
                    f"[{self.symbol}] Failed to get balance info for market {self.market_type}. Skipping some risk checks."
                )
                # Depending on strictness, might return or allow continuation with limited checks
                # For now, let's allow continuation for checks that don't strictly need current balance.
                # However, drawdown check will be ineffective.

            # Determine current balance for drawdown checks
            # This needs to be adapted based on what balance_info structure is for spot vs futures
            # For futures, 'totalWalletBalance' or 'totalMarginBalance' might be more appropriate for overall account drawdown.
            # For spot, it would be the sum of all assets converted to a common currency (e.g., USDT).
            # This part requires careful thought on how "current_balance" for drawdown is defined.
            # Let's assume for now we are using a field from balance_info that represents total account value.
            # This is a placeholder and needs to be accurate based on API response.
            account_total_value_for_drawdown = Decimal("0")
            if self.market_type == "futures" and balance_info:
                 # Example: using totalWalletBalance for futures drawdown calculation
                account_total_value_for_drawdown = Decimal(balance_info[0].get("balance") if isinstance(balance_info, list) and balance_info else "0") # crude, depends on actual structure
                # A better approach for futures might be to sum 'walletBalance' for all assets in balance_info (which is a list of assets)
                # Or use 'totalMarginBalance' from futures_account call if that's more representative.
                # For now, this is a simplification.
            elif self.market_type == "spot" and balance_info:
                # For spot, sum of USDT equivalent of all assets. This is complex.
                # Simplified: assume a function `_calculate_total_spot_value_in_usdt(balance_info)`
                pass # This needs proper implementation if spot drawdown is critical path here.

            if self.initial_balance is None and account_total_value_for_drawdown > 0:
                 self.set_initial_balance(account_total_value_for_drawdown)


            # 3. Check Circuit Breakers (Max Drawdown) - Ensure current_balance is correctly sourced
            if account_total_value_for_drawdown > 0 and self.check_circuit_breakers(account_total_value_for_drawdown):
                self.grid_logic.trigger_shutdown(reason="Max Drawdown Circuit Breaker")
                return

            # For Futures: manage SL and Profit Protection using detailed position_for_sl
            if self.market_type == "futures" and current_position_info:
                # total_realized_pnl for SL might be different from position's isolated realizedPnl.
                # GridLogic's total_realized_pnl might be more appropriate if it tracks overall PNL for the grid strategy.
                # For now, using what's available in position_for_sl, but this might need refinement.
                sl_management_pnl = self.grid_logic.total_realized_pnl # Using GridLogic's tracked PNL

                self.manage_stop_loss(position_for_sl, sl_management_pnl)
                self.protect_realized_profit(position_for_sl, sl_management_pnl)
            elif self.market_type == "spot":
                # SL management for spot might be simpler or handled differently (e.g. selling all base asset)
                # Profit protection might also look at total value of base asset vs. entry costs.
                # This section would need specific implementation for Spot if features like ATR SL are desired.
                log.debug(f"[{self.symbol}] SL management and profit protection for SPOT market type needs specific implementation if advanced features are required beyond basic grid fills.")

            # (Rest of the checks like API failure timeout)

            # 6. Check for API Failure Timeout (Optional)
            # if self.last_api_success_time and (time.time() - self.last_api_success_time) > self.api_failure_timeout_minutes * 60:
            #     log.critical(f"[{self.symbol}] CIRCUIT BREAKER TRIPPED: No successful API communication for {self.api_failure_timeout_minutes} minutes.")
            #     self.alerter.send_critical_alert(f"[{self.symbol}] CIRCUIT BREAKER: API Failure Timeout! Shutting down pair.")
            #     self.grid_logic.trigger_shutdown(reason="API Failure Timeout")
            #     return

            log.debug(f"[{self.symbol}] Risk management checks completed.")

        except Exception as e:
            log.error(
                f"[{self.symbol}] Error during risk management checks: {e}",
                exc_info=True,
            )
            self.alerter.send_critical_alert(
                f"Error in {self.symbol} risk management: {e}"
            )
