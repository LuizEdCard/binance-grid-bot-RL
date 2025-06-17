# Módulo de Gerenciamento de Risco para Bot de Grid Trading
# Suporta mercados Spot e Futuros

import time
from decimal import Decimal
from typing import Dict, Optional

import numpy as np
import pandas as pd
from binance.enums import SIDE_SELL, SIDE_BUY, FUTURE_ORDER_TYPE_STOP_MARKET

from utils.api_client import APIClient
from utils.logger import setup_logger
from utils.trailing_stop import TrailingStopManager, TrailingStopConfig, PositionSide
from utils.conditional_orders import ConditionalOrderManager, ConditionalOrderConfig, OrderType, ConditionType
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
        
        # Get kline interval from config
        self.kline_interval = config.get("http_api", {}).get("default_kline_interval", "3m")
        
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
        
        # --- Trailing Stop Manager --- #
        self.trailing_stop_manager = TrailingStopManager(api_client, alerter)
        self.trailing_stop_enabled = self.risk_config.get("trailing_stop", {}).get("enabled", True)
        self.trailing_stop_config = self._create_trailing_stop_config()
        
        # --- Conditional Orders Manager --- #
        self.conditional_order_manager = ConditionalOrderManager(api_client, alerter)
        self.conditional_orders_enabled = self.risk_config.get("conditional_orders", {}).get("enabled", True)
        
        # Iniciar monitoramento de ordens condicionais
        if self.conditional_orders_enabled:
            self.conditional_order_manager.start_monitoring()

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

    def _create_trailing_stop_config(self) -> TrailingStopConfig:
        """Cria configuração do trailing stop baseada no config do sistema"""
        trailing_config = self.risk_config.get("trailing_stop", {})
        
        return TrailingStopConfig(
            trail_amount=trailing_config.get("trail_amount", 1.0),  # 1% padrão
            trail_type=trailing_config.get("trail_type", "percentage"),
            activation_threshold=trailing_config.get("activation_threshold", 0.5),  # 0.5% para ativar
            min_trail_distance=trailing_config.get("min_trail_distance", 0.001),
            max_trail_distance=trailing_config.get("max_trail_distance", 0.05),
            update_frequency=trailing_config.get("update_frequency", 5)
        )

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
                    symbol=self.symbol, interval=getattr(self, 'kline_interval', '3m'), limit=limit
                )
            else:  # futures
                klines = self.api_client.get_futures_klines(
                    symbol=self.symbol, interval=getattr(self, 'kline_interval', '3m'), limit=limit
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

    def start_trailing_stop(self, position_side: str, entry_price: float, initial_stop_price: float) -> bool:
        """Inicia trailing stop para uma posição"""
        if not self.trailing_stop_enabled:
            return False
            
        try:
            # Converter para o enum apropriado
            if position_side.upper() in ["LONG", "BUY"]:
                side = PositionSide.LONG
            elif position_side.upper() in ["SHORT", "SELL"]:
                side = PositionSide.SHORT
            else:
                log.warning(f"[{self.symbol}] Invalid position side for trailing stop: {position_side}")
                return False
            
            success = self.trailing_stop_manager.add_trailing_stop(
                symbol=self.symbol,
                config=self.trailing_stop_config,
                position_side=side,
                entry_price=entry_price,
                initial_stop_price=initial_stop_price
            )
            
            if success:
                log.info(f"[{self.symbol}] Trailing stop started for {side.value} position")
            
            return success
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error starting trailing stop: {e}")
            return False

    def update_trailing_stop(self, current_price: float) -> Optional[float]:
        """Atualiza trailing stop com preço atual"""
        if not self.trailing_stop_enabled:
            return None
            
        try:
            new_stop_price = self.trailing_stop_manager.update_trailing_stop(self.symbol, current_price)
            
            # Se o trailing stop foi acionado, verificar se deve fechar posição
            if self.trailing_stop_manager.check_stop_triggered(self.symbol, current_price):
                log.warning(f"[{self.symbol}] Trailing stop triggered at price {current_price}")
                try:
                    self.grid_logic.close_position_market()
                    self.remove_trailing_stop()
                    self.alerter.send_message(f"[{self.symbol}] Position closed by trailing stop")
                except Exception as e:
                    log.error(f"[{self.symbol}] Error closing position on trailing stop: {e}")
            
            return new_stop_price
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error updating trailing stop: {e}")
            return None

    def remove_trailing_stop(self) -> bool:
        """Remove trailing stop da posição"""
        try:
            success = self.trailing_stop_manager.remove_trailing_stop(self.symbol)
            if success:
                log.info(f"[{self.symbol}] Trailing stop removed")
            return success
        except Exception as e:
            log.error(f"[{self.symbol}] Error removing trailing stop: {e}")
            return False

    def get_trailing_stop_info(self) -> Optional[Dict]:
        """Retorna informações do trailing stop ativo"""
        try:
            return self.trailing_stop_manager.get_trailing_stop_info(self.symbol)
        except Exception as e:
            log.error(f"[{self.symbol}] Error getting trailing stop info: {e}")
            return None

    def place_stop_limit_order(self, side: str, quantity: str, stop_price: str, 
                              limit_price: str, reduce_only: bool = True) -> Optional[Dict]:
        """Coloca ordem STOP_LIMIT para melhor controle de slippage"""
        try:
            if not self.conditional_orders_enabled:
                log.warning(f"[{self.symbol}] Conditional orders disabled, using STOP_MARKET fallback")
                return self._place_or_modify_stop_order(stop_price, Decimal(quantity))
            
            result = self.api_client.place_stop_limit_order(
                symbol=self.symbol,
                side=side,
                quantity=quantity,
                stop_price=stop_price,
                price=limit_price,
                reduceOnly="true" if reduce_only else "false"
            )
            
            if result:
                log.info(f"[{self.symbol}] STOP_LIMIT order placed: {result.get('orderId')}")
                self.alerter.send_message(
                    f"[{self.symbol}] 🛡️ STOP_LIMIT order placed\\n"
                    f"Side: {side}, Qty: {quantity}\\n"
                    f"Stop: {stop_price}, Limit: {limit_price}"
                )
            
            return result
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error placing STOP_LIMIT order: {e}")
            return None

    def add_conditional_order(self, side: str, quantity: str, condition_type: ConditionType,
                             condition_value: float, order_type: OrderType = OrderType.MARKET,
                             price: str = None, stop_price: str = None,
                             condition_params: Dict = None, expiry_minutes: int = 60) -> bool:
        """Adiciona ordem condicional baseada em indicadores técnicos"""
        try:
            if not self.conditional_orders_enabled:
                log.warning(f"[{self.symbol}] Conditional orders disabled")
                return False
            
            order_id = f"{self.symbol}_{side}_{condition_type.value}_{int(time.time())}"
            
            config = ConditionalOrderConfig(
                order_id=order_id,
                symbol=self.symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                condition_type=condition_type,
                condition_value=condition_value,
                condition_params=condition_params or {},
                expiry_time=time.time() + (expiry_minutes * 60),
                check_interval=10  # Verificar a cada 10 segundos
            )
            
            success = self.conditional_order_manager.add_conditional_order(config)
            
            if success:
                log.info(f"[{self.symbol}] Conditional order added: {order_id}")
                self.alerter.send_message(
                    f"[{self.symbol}] 📋 Conditional Order Created\\n"
                    f"Condition: {condition_type.value}\\n"
                    f"Trigger: {condition_value}\\n"
                    f"Action: {side} {quantity} ({order_type.value})"
                )
            
            return success
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error adding conditional order: {e}")
            return False

    def add_rsi_based_order(self, side: str, quantity: str, rsi_threshold: float = 30,
                           order_type: OrderType = OrderType.MARKET, price: str = None) -> bool:
        """Adiciona ordem baseada em RSI (oversold/overbought)"""
        condition_type = ConditionType.RSI_OVERSOLD if rsi_threshold < 50 else ConditionType.RSI_OVERBOUGHT
        condition_params = {"rsi_threshold": rsi_threshold}
        
        return self.add_conditional_order(
            side=side,
            quantity=quantity,
            condition_type=condition_type,
            condition_value=rsi_threshold,
            order_type=order_type,
            price=price,
            condition_params=condition_params
        )

    def add_price_breakout_order(self, side: str, quantity: str, breakout_price: float,
                                order_type: OrderType = OrderType.LIMIT, limit_price: str = None) -> bool:
        """Adiciona ordem de breakout de preço"""
        condition_type = ConditionType.PRICE_ABOVE if side == "BUY" else ConditionType.PRICE_BELOW
        
        return self.add_conditional_order(
            side=side,
            quantity=quantity,
            condition_type=condition_type,
            condition_value=breakout_price,
            order_type=order_type,
            price=limit_price or str(breakout_price)
        )

    def add_volume_spike_order(self, side: str, quantity: str, volume_multiplier: float = 2.0,
                              order_type: OrderType = OrderType.MARKET) -> bool:
        """Adiciona ordem baseada em spike de volume"""
        condition_params = {"volume_multiplier": volume_multiplier}
        
        return self.add_conditional_order(
            side=side,
            quantity=quantity,
            condition_type=ConditionType.VOLUME_SPIKE,
            condition_value=volume_multiplier,
            order_type=order_type,
            condition_params=condition_params
        )

    def get_conditional_orders_info(self) -> Dict:
        """Retorna informações das ordens condicionais ativas"""
        try:
            if not self.conditional_orders_enabled:
                return {"enabled": False}
            
            active_orders = self.conditional_order_manager.get_active_orders()
            statistics = self.conditional_order_manager.get_statistics()
            
            return {
                "enabled": True,
                "active_orders": active_orders,
                "statistics": statistics
            }
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error getting conditional orders info: {e}")
            return {"enabled": False, "error": str(e)}

    def remove_conditional_order(self, order_id: str) -> bool:
        """Remove ordem condicional específica"""
        try:
            if not self.conditional_orders_enabled:
                return False
            
            success = self.conditional_order_manager.remove_conditional_order(order_id)
            
            if success:
                log.info(f"[{self.symbol}] Conditional order removed: {order_id}")
                self.alerter.send_message(f"[{self.symbol}] ❌ Conditional order removed: {order_id}")
            
            return success
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error removing conditional order: {e}")
            return False

    def cleanup_conditional_orders(self):
        """Limpa ordens condicionais ao finalizar"""
        try:
            if self.conditional_orders_enabled:
                self.conditional_order_manager.stop_monitoring()
                log.info(f"[{self.symbol}] Conditional orders cleanup completed")
        except Exception as e:
            log.error(f"[{self.symbol}] Error during conditional orders cleanup: {e}")

    def run_checks(self):
        """Runs all risk management checks in sequence."""
        log.debug(f"[{self.symbol}] Running risk management checks...")
        try:
            # 0. Update API success time (used for API failure check)
            self.last_api_success_time = time.time()

            # 1. Check Sentiment-Based Risk Adjustment (e.g., Leverage)
            self.adjust_risk_based_on_sentiment()

            # 2. Get current position and balance info
            position = self.api_client.get_futures_position(self.symbol)
            balance_info = self.api_client.get_futures_balance()
            # TODO: Handle potential errors from API calls here

            if position is None or balance_info is None:
                log.error(
                    f"[{self.symbol}] Failed to get position or balance info. Skipping risk checks."
                )
                return

            current_balance = balance_info.get(
                "availableBalance", Decimal("0")
            )  # Or total wallet balance?
            if self.initial_balance is None:
                self.set_initial_balance(balance_info.get("balance", Decimal("0")))

            # 3. Check Circuit Breakers (Max Drawdown)
            if self.check_circuit_breakers(current_balance):
                # Signal GridLogic or main process to stop trading this pair
                self.grid_logic.trigger_shutdown(reason="Max Drawdown Circuit Breaker")
                return  # Stop further checks if breaker tripped

            # 4. Update Trailing Stop if enabled and position exists
            if self.trailing_stop_enabled and position and Decimal(position.get("positionAmt", "0")) != 0:
                current_price = float(position.get("markPrice", "0"))
                if current_price > 0:
                    self.update_trailing_stop(current_price)

            # 5. Manage Stop Loss
            total_realized_pnl = position.get(
                "realizedPnl", Decimal("0")
            )  # Get PNL from position info
            self.manage_stop_loss(position, total_realized_pnl)

            # 6. Protect Realized Profit
            self.protect_realized_profit(position, total_realized_pnl)

            # 7. Check for API Failure Timeout (Optional)
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
