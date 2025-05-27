# Core logic for Grid Trading

import time
import math
import random
import numpy as np # Import numpy for TA-Lib
import pandas as pd # Import pandas for data manipulation
from decimal import Decimal, ROUND_DOWN, ROUND_UP

from ..utils.logger import log
from ..utils.api_client import APIClient
from binance.enums import *

# Attempt to import TA-Lib
try:
    import talib
    talib_available = True
    log.info("TA-Lib library found and imported successfully for GridLogic.")
except ImportError:
    talib_available = False
    log.warning("TA-Lib library not found for GridLogic. Some advanced features (dynamic spacing based on ATR, pattern checks) will be unavailable. Please install TA-Lib for full functionality (see talib_installation_guide.md).")
    # No direct fallback needed here unless specific indicators are calculated within GridLogic itself

class GridLogic:
    """Encapsulates the core logic for grid trading strategy.

    Can be controlled by an RL agent for dynamic adjustments.
    Supports Production (real trading) and Shadow (real data, simulated orders) modes.
    Optionally uses TA-Lib for dynamic adjustments.
    """

    def __init__(self, symbol: str, config: dict, api_client: APIClient, operation_mode: str = "shadow"):
        self.symbol = symbol
        self.config = config
        self.api_client = api_client
        self.operation_mode = operation_mode.lower()
        self.grid_config = config.get("grid", {})
        self.risk_config = config.get("risk_management", {})
        self.exchange_info = None
        self.symbol_info = None
        self.tick_size = None
        self.step_size = None
        self.min_notional = None
        self.quantity_precision = None
        self.price_precision = None

        # Grid parameters
        self.num_levels = self.grid_config.get("initial_levels", 10)
        self.base_spacing_percentage = Decimal(self.grid_config.get("initial_spacing_perc", "0.005")) # Base spacing
        self.use_dynamic_spacing = self.grid_config.get("use_dynamic_spacing_atr", False) # New config
        self.dynamic_spacing_atr_period = self.grid_config.get("dynamic_spacing_atr_period", 14)
        self.dynamic_spacing_multiplier = Decimal(str(self.grid_config.get("dynamic_spacing_atr_multiplier", "0.5"))) # Multiplier for ATR
        self.current_spacing_percentage = self.base_spacing_percentage # Actual spacing used
        self.grid_direction = "neutral"

        self.grid_levels = []
        self.active_grid_orders = {} # Stores {level_price: order_id}
        self.open_orders = {} # Stores {order_id: order_details}

        # --- Shadow Mode State --- #
        self.simulated_open_orders = {} # {order_id: {symbol, side, type, price, quantity, status, ...}}
        self.simulated_position = {
            "positionAmt": Decimal("0"),
            "entryPrice": Decimal("0"),
            "markPrice": Decimal("0"), # Updated from real ticker
            "unRealizedProfit": Decimal("0"),
            "liquidationPrice": Decimal("0") # Hard to simulate accurately
        }
        # ------------------------- #

        # Use simulated state in shadow mode, real state otherwise
        self.position = self.simulated_position if self.operation_mode == "shadow" else {
            "positionAmt": Decimal("0"),
            "entryPrice": Decimal("0"),
            "markPrice": Decimal("0"),
            "unRealizedProfit": Decimal("0"),
            "liquidationPrice": Decimal("0")
        }

        self.trade_history = []
        self.total_realized_pnl = Decimal("0")
        self.fees_paid = Decimal("0")
        self.total_trades = 0 # Counter for RL retraining

        log.info(f"[{self.symbol}] GridLogic initialized in {self.operation_mode.upper()} mode. Dynamic Spacing (ATR): {self.use_dynamic_spacing}")
        if self.use_dynamic_spacing and not talib_available:
            log.warning(f"[{self.symbol}] Dynamic spacing requested but TA-Lib not found. Falling back to fixed spacing.")
            self.use_dynamic_spacing = False

        if not self._initialize_symbol_info():
             raise ValueError(f"[{self.symbol}] Failed to initialize symbol info. Cannot start GridLogic.")

    def _initialize_symbol_info(self) -> bool:
        # ... (no changes) ...
        log.info(f"[{self.symbol}] Initializing exchange information...")
        self.exchange_info = self.api_client.get_exchange_info()
        if not self.exchange_info:
            log.error(f"[{self.symbol}] Failed to fetch exchange info.")
            return False
        for item in self.exchange_info.get("symbols", []):
            if item["symbol"] == self.symbol:
                self.symbol_info = item
                break
        if not self.symbol_info:
            log.error(f"[{self.symbol}] Symbol information not found in exchange info.")
            return False

        self.quantity_precision = self.symbol_info.get("quantityPrecision")
        self.price_precision = self.symbol_info.get("pricePrecision")
        price_filter = next((f for f in self.symbol_info["filters"] if f["filterType"] == "PRICE_FILTER"), None)
        lot_size_filter = next((f for f in self.symbol_info["filters"] if f["filterType"] == "LOT_SIZE"), None)
        min_notional_filter = next((f for f in self.symbol_info["filters"] if f["filterType"] == "MIN_NOTIONAL"), None)

        if price_filter: self.tick_size = Decimal(price_filter["tickSize"])
        else: log.error(f"[{self.symbol}] Price filter not found."); return False
        if lot_size_filter: self.step_size = Decimal(lot_size_filter["stepSize"])
        else: log.error(f"[{self.symbol}] Lot size filter not found."); return False
        if min_notional_filter: self.min_notional = Decimal(min_notional_filter.get("notional", "5")) # Default 5 if key missing
        else:
            market_lot_filter = next((f for f in self.symbol_info["filters"] if f["filterType"] == "MARKET_LOT_SIZE"), None)
            if market_lot_filter:
                 self.min_notional = Decimal("5") # Default to 5 USDT
                 log.warning(f"[{self.symbol}] MIN_NOTIONAL filter missing, using default: {self.min_notional} USDT")
            else:
                log.error(f"[{self.symbol}] Min Notional filter (and fallback) not found.")
                return False

        log.info(f"[{self.symbol}] Tick: {self.tick_size}, Step: {self.step_size}, MinNotional: {self.min_notional}, PricePrec: {self.price_precision}, QtyPrec: {self.quantity_precision}")
        if not all([self.tick_size, self.step_size, self.min_notional, self.quantity_precision is not None, self.price_precision is not None]):
             log.error(f"[{self.symbol}] Failed to initialize all necessary symbol filters/precision.")
             return False
        return True

    def _format_price(self, price):
        # ... (no changes) ...
        if self.tick_size is None or self.price_precision is None: return None
        try:
            adjusted_price = (Decimal(str(price)) / self.tick_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * self.tick_size
            return f"{adjusted_price:.{self.price_precision}f}"
        except Exception as e: log.error(f"[{self.symbol}] Error formatting price {price}: {e}"); return None

    def _format_quantity(self, quantity):
        # ... (no changes) ...
        if self.step_size is None or self.quantity_precision is None: return None
        try:
            adjusted_quantity = (Decimal(str(quantity)) / self.step_size).quantize(Decimal("1"), rounding=ROUND_DOWN) * self.step_size
            if adjusted_quantity == Decimal("0") and Decimal(str(quantity)) > Decimal("0"): adjusted_quantity = self.step_size
            return f"{adjusted_quantity:.{self.quantity_precision}f}"
        except Exception as e: log.error(f"[{self.symbol}] Error formatting quantity {quantity}: {e}"); return None

    def _check_min_notional(self, price, quantity):
        # ... (no changes) ...
        if not self.min_notional: return False
        try:
            notional_value = Decimal(str(price)) * Decimal(str(quantity))
            meets = notional_value >= self.min_notional
            if not meets: log.warning(f"[{self.symbol}] Order notional {notional_value:.4f} < min_notional {self.min_notional} (Price: {price}, Qty: {quantity})")
            return meets
        except Exception as e: log.error(f"[{self.symbol}] Error checking min notional: {e}"); return False

    def update_grid_parameters(self, num_levels=None, spacing_percentage=None, direction=None):
        # ... (no changes, RL agent still controls base parameters) ...
        updated = False
        if num_levels is not None and num_levels != self.num_levels:
            self.num_levels = num_levels if num_levels % 2 == 0 else num_levels + 1
            log.info(f"[{self.symbol}] RL Agent updated num_levels to: {self.num_levels}")
            updated = True
        if spacing_percentage is not None and spacing_percentage != self.base_spacing_percentage:
            self.base_spacing_percentage = Decimal(str(spacing_percentage))
            log.info(f"[{self.symbol}] RL Agent updated base_spacing_percentage to: {self.base_spacing_percentage}")
            # Recalculate current spacing if dynamic is off
            if not self.use_dynamic_spacing:
                self.current_spacing_percentage = self.base_spacing_percentage
            updated = True
        if direction is not None and direction in ["long", "short", "neutral"] and direction != self.grid_direction:
            self.grid_direction = direction
            log.info(f"[{self.symbol}] RL Agent updated grid_direction to: {self.grid_direction}")
            updated = True
        if updated:
            # Redefine grid on next cycle if parameters changed
            self.grid_levels = []
            self.cancel_active_grid_orders()
            log.info(f"[{self.symbol}] Grid parameters updated by RL agent. Grid will be redefined.")

    def _update_dynamic_spacing(self):
        """Updates current_spacing_percentage based on ATR if dynamic spacing is enabled."""
        if not self.use_dynamic_spacing or not talib_available:
            self.current_spacing_percentage = self.base_spacing_percentage
            return

        try:
            # Fetch recent klines (e.g., 1h, enough for ATR calculation)
            # Need at least atr_period + 1 candles
            limit = self.dynamic_spacing_atr_period + 5 # Add buffer
            klines = self.api_client.get_futures_klines(symbol=self.symbol, interval='1h', limit=limit)
            if not klines or len(klines) < self.dynamic_spacing_atr_period:
                log.warning(f"[{self.symbol}] Insufficient kline data ({len(klines) if klines else 0}) for dynamic ATR spacing. Using base spacing.")
                self.current_spacing_percentage = self.base_spacing_percentage
                return

            # Prepare data for TA-Lib
            df = pd.DataFrame(klines, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
            high_prices = pd.to_numeric(df['High']).values
            low_prices = pd.to_numeric(df['Low']).values
            close_prices = pd.to_numeric(df['Close']).values

            # Calculate ATR
            atr_series = talib.ATR(high_prices, low_prices, close_prices, timeperiod=self.dynamic_spacing_atr_period)
            latest_atr = atr_series[~np.isnan(atr_series)][-1] if not np.all(np.isnan(atr_series)) else None
            last_close_price = close_prices[-1]

            if latest_atr is not None and last_close_price > 0:
                atr_percentage = (Decimal(str(latest_atr)) / Decimal(str(last_close_price)))
                # Combine base spacing with ATR component
                # Example: spacing = base + atr_perc * multiplier
                dynamic_spacing = self.base_spacing_percentage + (atr_percentage * self.dynamic_spacing_multiplier)
                # Add bounds to prevent extreme spacing
                min_spacing = self.base_spacing_percentage / Decimal("2")
                max_spacing = self.base_spacing_percentage * Decimal("3")
                self.current_spacing_percentage = max(min_spacing, min(max_spacing, dynamic_spacing))
                log.info(f"[{self.symbol}] Dynamic spacing updated: ATR={latest_atr:.4f}, ATR%={atr_percentage*100:.3f}%, New Spacing%={self.current_spacing_percentage*100:.3f}%")
            else:
                log.warning(f"[{self.symbol}] Could not calculate valid ATR or price for dynamic spacing. Using base spacing.")
                self.current_spacing_percentage = self.base_spacing_percentage

        except Exception as e:
            log.error(f"[{self.symbol}] Error updating dynamic spacing: {e}", exc_info=True)
            self.current_spacing_percentage = self.base_spacing_percentage

    def define_grid_levels(self, current_price: float):
        # Update dynamic spacing first if enabled
        if self.use_dynamic_spacing:
            self._update_dynamic_spacing()
        else:
            self.current_spacing_percentage = self.base_spacing_percentage

        log.info(f"[{self.symbol}] Defining grid levels around price: {current_price} (Levels: {self.num_levels}, Spacing: {self.current_spacing_percentage*100:.3f}%, Direction: {self.grid_direction})" + (" (Dynamic)" if self.use_dynamic_spacing else " (Fixed)"))
        if self.num_levels <= 0: log.error(f"[{self.symbol}] Num levels <= 0. Cannot define grid."); self.grid_levels = []; return
        self.grid_levels = []
        center_price_str = self._format_price(current_price)
        if not center_price_str: log.error(f"[{self.symbol}] Could not format center price {current_price}."); return
        center_price = Decimal(center_price_str)

        levels_above = self.num_levels // 2
        levels_below = self.num_levels // 2
        if self.grid_direction == "long": levels_above, levels_below = self.num_levels // 3, self.num_levels - (self.num_levels // 3)
        elif self.grid_direction == "short": levels_below, levels_above = self.num_levels // 3, self.num_levels - (self.num_levels // 3)

        # Use current_spacing_percentage which might be dynamic
        spacing = self.current_spacing_percentage

        last_price = center_price
        for i in range(levels_below):
            # Use geometric spacing: Price_n = Price_n-1 * (1 - spacing)
            level_price_raw = last_price * (Decimal("1") - spacing)
            level_price_str = self._format_price(level_price_raw)
            if level_price_str:
                level_price = Decimal(level_price_str)
                self.grid_levels.append({"price": level_price, "type": "buy"})
                last_price = level_price # Update last price for next calculation
            else:
                log.warning(f"[{self.symbol}] Could not format lower grid level near {level_price_raw}. Stopping lower grid definition."); break

        last_price = center_price
        for i in range(levels_above):
            # Use geometric spacing: Price_n = Price_n-1 * (1 + spacing)
            level_price_raw = last_price * (Decimal("1") + spacing)
            level_price_str = self._format_price(level_price_raw)
            if level_price_str:
                level_price = Decimal(level_price_str)
                self.grid_levels.append({"price": level_price, "type": "sell"})
                last_price = level_price # Update last price for next calculation
            else:
                log.warning(f"[{self.symbol}] Could not format upper grid level near {level_price_raw}. Stopping upper grid definition."); break

        self.grid_levels.sort(key=lambda x: x["price"])
        log.info(f"[{self.symbol}] Defined {len(self.grid_levels)} grid levels.")

    def _calculate_quantity_per_order(self, current_price: Decimal) -> Decimal:
        # ... (no changes) ...
        total_capital_usd = Decimal(self.config.get("trading", {}).get("capital_per_pair_usd", "100"))
        leverage = Decimal(self.grid_config.get("leverage", "1"))
        num_grids = len(self.grid_levels) if self.grid_levels else self.num_levels
        if num_grids <= 0: log.error(f"[{self.symbol}] Num grids is zero."); return Decimal("0")
        capital_per_grid = total_capital_usd / Decimal(str(num_grids))
        exposure_per_grid = capital_per_grid * leverage
        quantity = exposure_per_grid / current_price
        formatted_qty_str = self._format_quantity(quantity)
        if not formatted_qty_str: log.error(f"[{self.symbol}] Failed to format quantity {quantity}."); return Decimal("0")
        log.info(f"[{self.symbol}] Calculated quantity per order: {formatted_qty_str}")
        return Decimal(formatted_qty_str)

    def _place_order(self, side, price_str, qty_str):
        # ... (no changes) ...
        log.info(f"[{self.symbol} - {self.operation_mode.upper()}] Placing {side} LIMIT order at {price_str}, Qty: {qty_str}")
        try:
            # APIClient handles simulation in shadow mode
            order = self.api_client.place_futures_order(
                symbol=self.symbol,
                side=side,
                order_type=ORDER_TYPE_LIMIT,
                quantity=qty_str,
                price=price_str,
                timeInForce=TIME_IN_FORCE_GTC
            )
            if order and "orderId" in order:
                order_id = order["orderId"]
                log.info(f"[{self.symbol}] Successfully placed {side} order {order_id} at {price_str}")
                # Store order details (real or simulated)
                self.open_orders[order_id] = order
                if self.operation_mode == "shadow":
                    # Store simulated order state
                    self.simulated_open_orders[order_id] = {
                        "orderId": order_id,
                        "symbol": self.symbol,
                        "side": side,
                        "type": ORDER_TYPE_LIMIT,
                        "price": Decimal(price_str),
                        "origQty": Decimal(qty_str),
                        "executedQty": Decimal("0"),
                        "status": ORDER_STATUS_NEW,
                        "time": order.get("time", int(time.time() * 1000))
                    }
                return order_id
            else:
                log.error(f"[{self.symbol}] Failed to place {side} order at {price_str}. Response: {order}")
                return None
        except Exception as e:
            log.error(f"[{self.symbol}] Exception placing {side} order at {price_str}: {e}")
            return None

    def place_initial_grid_orders(self):
        # ... (no changes) ...
        log.info(f"[{self.symbol}] Placing initial grid orders...\")
        if not self.grid_levels: log.warning(f\"[{self.symbol}] No grid levels defined."); return
        if self.active_grid_orders: log.warning(f\"[{self.symbol}] Initial grid orders seem active. Skipping."); return

        ticker = self.api_client.get_futures_ticker(symbol=self.symbol)
        if not ticker or \"lastPrice\" not in ticker: log.error(f\"[{self.symbol}] Could not get current price.\"); return
        current_price = Decimal(ticker[\"lastPrice\"])
        quantity_per_order = self._calculate_quantity_per_order(current_price)
        if quantity_per_order <= Decimal(\"0\"): log.error(f\"[{self.symbol}] Quantity is zero.\"); return

        placed_count = 0
        for level in self.grid_levels:
            level_price = level[\"price\"]
            order_type = level[\"type\"]
            if level_price in self.active_grid_orders: continue

            formatted_price_str = self._format_price(level_price)
            formatted_qty_str = self._format_quantity(quantity_per_order)
            if not formatted_price_str or not formatted_qty_str: continue
            if not self._check_min_notional(formatted_price_str, formatted_qty_str): continue

            side = SIDE_BUY if order_type == \"buy\" else SIDE_SELL
            order_id = self._place_order(side, formatted_price_str, formatted_qty_str)
            if order_id:
                self.active_grid_orders[level_price] = order_id
                placed_count += 1
            time.sleep(0.1)
        log.info(f\"[{self.symbol}] Placed {placed_count} initial grid orders.\")

    def check_and_handle_fills(self, current_kline=None):
        # ... (rest of the file remains unchanged for now) ...
        # Add TA-Lib pattern checks here later if needed
        if self.operation_mode == "production":
            self._check_fills_production()
        elif self.operation_mode == "shadow":
            self._check_fills_shadow(current_kline)

    def _check_fills_production(self):
        if not self.open_orders: return
        log.info(f"[{self.symbol}] Checking status of {len(self.open_orders)} open orders via API...")
        order_ids_to_check = list(self.open_orders.keys())
        filled_orders_data = []
        still_open_orders = {}

        for order_id in order_ids_to_check:
            try:
                status = self.api_client.get_futures_order_status(symbol=self.symbol, orderId=order_id)
                time.sleep(0.05) # Small delay
                if status:
                    if status['status'] == ORDER_STATUS_FILLED:
                        log.info(f"[{self.symbol}] Order {order_id} FILLED.")
                        filled_orders_data.append(status)
                        # Remove from open orders immediately
                        if order_id in self.open_orders: del self.open_orders[order_id]
                        # Find which grid level this corresponds to
                        filled_level_price = None
                        for price, oid in list(self.active_grid_orders.items()):
                            if oid == order_id:
                                filled_level_price = price
                                del self.active_grid_orders[price]
                                break
                        if filled_level_price:
                            self._handle_filled_order(status, filled_level_price)
                        else:
                            log.warning(f"[{self.symbol}] Filled order {order_id} not found in active grid levels.")
                    elif status['status'] in [ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED, ORDER_STATUS_REJECTED]:
                        log.warning(f"[{self.symbol}] Order {order_id} has status {status['status']}. Removing from tracking.")
                        if order_id in self.open_orders: del self.open_orders[order_id]
                        for price, oid in list(self.active_grid_orders.items()):
                            if oid == order_id:
                                del self.active_grid_orders[price]
                                break
                    else: # Still open (NEW, PARTIALLY_FILLED)
                        still_open_orders[order_id] = status
                else:
                    log.warning(f"[{self.symbol}] Could not get status for order {order_id}. Assuming still open.")
                    still_open_orders[order_id] = self.open_orders[order_id] # Keep old data
            except Exception as e:
                log.error(f"[{self.symbol}] Error checking status for order {order_id}: {e}")
                still_open_orders[order_id] = self.open_orders[order_id] # Keep old data on error

        self.open_orders = still_open_orders # Update open orders list
        log.info(f"[{self.symbol}] Finished checking orders. {len(filled_orders_data)} filled, {len(self.open_orders)} still open.")

    def _check_fills_shadow(self, current_kline):
        if not self.simulated_open_orders or current_kline is None:
            return

        kline_open = Decimal(current_kline['Open'])
        kline_high = Decimal(current_kline['High'])
        kline_low = Decimal(current_kline['Low'])
        kline_close = Decimal(current_kline['Close'])
        log.debug(f"[{self.symbol} - SHADOW] Checking fills against Kline O:{kline_open} H:{kline_high} L:{kline_low} C:{kline_close}")

        filled_orders_simulated = []
        remaining_sim_orders = {}

        for order_id, order in list(self.simulated_open_orders.items()):
            order_price = order['price']
            order_side = order['side']
            filled = False

            # Check if kline range crossed the order price
            if order_side == SIDE_BUY and kline_low <= order_price <= kline_high:
                filled = True
                fill_price = min(kline_open, order_price) # Simulate fill at order price or open if gapped down
            elif order_side == SIDE_SELL and kline_low <= order_price <= kline_high:
                filled = True
                fill_price = max(kline_open, order_price) # Simulate fill at order price or open if gapped up

            if filled:
                log.info(f"[{self.symbol} - SHADOW] Simulating FILL for {order_side} order {order_id} at price {order_price} (Kline range [{kline_low}-{kline_high}])")
                simulated_fill_data = order.copy()
                simulated_fill_data['status'] = ORDER_STATUS_FILLED
                simulated_fill_data['executedQty'] = order['origQty']
                simulated_fill_data['cummulativeQuoteQty'] = str(order['origQty'] * fill_price) # Approximate
                simulated_fill_data['avgPrice'] = str(fill_price)
                simulated_fill_data['updateTime'] = int(time.time() * 1000)

                filled_orders_simulated.append(simulated_fill_data)

                # Find corresponding grid level price
                filled_level_price = None
                for price, oid in list(self.active_grid_orders.items()):
                    if oid == order_id:
                        filled_level_price = price
                        del self.active_grid_orders[price]
                        break

                if filled_level_price:
                    self._handle_filled_order(simulated_fill_data, filled_level_price)
                else:
                    log.warning(f"[{self.symbol} - SHADOW] Filled simulated order {order_id} not found in active grid levels.")

                # Remove from open orders (both real placeholder and simulated)
                if order_id in self.open_orders: del self.open_orders[order_id]
                # Do not add to remaining_sim_orders
            else:
                remaining_sim_orders[order_id] = order # Keep if not filled

        self.simulated_open_orders = remaining_sim_orders
        log.debug(f"[{self.symbol} - SHADOW] Finished checking simulated fills. {len(filled_orders_simulated)} filled, {len(self.simulated_open_orders)} still open.")

    def _handle_filled_order(self, fill_data, filled_level_price):
        """Handles logic after an order is filled: update position, place TP order, record trade."""
        side = fill_data['side']
        filled_qty = Decimal(fill_data['executedQty'])
        avg_price = Decimal(fill_data['avgPrice'])
        commission = Decimal(fill_data.get('commission', '0')) # Need to fetch this properly if possible
        commission_asset = fill_data.get('commissionAsset', self.quote_asset)

        log.info(f"[{self.symbol}] Handling filled {side} order {fill_data['orderId']} at {avg_price}, Qty: {filled_qty}")

        # --- Update Position (Simplified) ---
        # This needs a more robust position tracking mechanism, especially for futures
        current_pos_amt = self.position['positionAmt']
        current_entry_price = self.position['entryPrice']

        if side == SIDE_BUY:
            new_pos_amt = current_pos_amt + filled_qty
            if current_pos_amt >= 0: # Adding to long or opening long
                new_entry_price = ((current_entry_price * current_pos_amt) + (avg_price * filled_qty)) / new_pos_amt if new_pos_amt != 0 else Decimal("0")
            else: # Reducing short position
                # Entry price doesn't change when reducing short
                new_entry_price = current_entry_price
        else: # SIDE_SELL
            new_pos_amt = current_pos_amt - filled_qty
            if current_pos_amt <= 0: # Adding to short or opening short
                # Use absolute values for calculation, entry price is positive
                new_entry_price = ((current_entry_price * abs(current_pos_amt)) + (avg_price * filled_qty)) / abs(new_pos_amt) if new_pos_amt != 0 else Decimal("0")
            else: # Reducing long position
                # Entry price doesn't change when reducing long
                new_entry_price = current_entry_price

        self.position['positionAmt'] = new_pos_amt
        self.position['entryPrice'] = new_entry_price
        log.info(f"[{self.symbol}] Updated Position: Amt={self.position['positionAmt']}, Entry={self.position['entryPrice']:.{self.price_precision}f}")
        # -------------------------------------

        # --- Calculate PnL for this fill (if closing part of a position) ---
        realized_pnl = Decimal("0")
        if (side == SIDE_SELL and current_pos_amt > 0) or (side == SIDE_BUY and current_pos_amt < 0):
            qty_closed = min(abs(current_pos_amt), filled_qty)
            if side == SIDE_SELL: # Closed long
                realized_pnl = (avg_price - current_entry_price) * qty_closed
            else: # Closed short
                realized_pnl = (current_entry_price - avg_price) * qty_closed
            # Adjust PnL for fees (assuming commission is in quote asset)
            # This is simplified, real fee calculation depends on taker/maker, asset etc.
            fee_estimate = avg_price * filled_qty * Decimal("0.0004") # Rough estimate (0.04%)
            realized_pnl -= fee_estimate
            self.total_realized_pnl += realized_pnl
            self.fees_paid += fee_estimate
            log.info(f"[{self.symbol}] Realized PnL from this fill: {realized_pnl:.4f} {self.quote_asset}")

        # --- Place Corresponding Take Profit Order --- #
        tp_price = None
        tp_side = None
        tp_qty = filled_qty # TP order matches the filled quantity

        # Find the next grid level in the opposite direction
        self.grid_levels.sort(key=lambda x: x["price"]) # Ensure sorted
        try:
            current_level_index = next(i for i, level in enumerate(self.grid_levels) if level["price"] == filled_level_price)

            if side == SIDE_BUY:
                # Find next sell level above
                if current_level_index + 1 < len(self.grid_levels):
                    tp_level = self.grid_levels[current_level_index + 1]
                    if tp_level["type"] == "sell":
                        tp_price = tp_level["price"]
                        tp_side = SIDE_SELL
            else: # Filled Sell
                # Find next buy level below
                if current_level_index - 1 >= 0:
                    tp_level = self.grid_levels[current_level_index - 1]
                    if tp_level["type"] == "buy":
                        tp_price = tp_level["price"]
                        tp_side = SIDE_BUY

        except StopIteration:
            log.warning(f"[{self.symbol}] Could not find filled level price {filled_level_price} in current grid definition.")
        except Exception as e:
            log.error(f"[{self.symbol}] Error finding TP level: {e}")

        if tp_price and tp_side:
            formatted_tp_price_str = self._format_price(tp_price)
            formatted_tp_qty_str = self._format_quantity(tp_qty)
            if formatted_tp_price_str and formatted_tp_qty_str and self._check_min_notional(formatted_tp_price_str, formatted_tp_qty_str):
                log.info(f"[{self.symbol}] Placing corresponding TP ({tp_side}) order at {formatted_tp_price_str}, Qty: {formatted_tp_qty_str}")
                tp_order_id = self._place_order(tp_side, formatted_tp_price_str, formatted_tp_qty_str)
                if tp_order_id:
                    # Add this TP order to the grid tracking
                    self.active_grid_orders[tp_price] = tp_order_id
            else:
                log.warning(f"[{self.symbol}] Could not place TP order for fill {fill_data['orderId']}. Price/Qty/Notional issue.")
        else:
            log.warning(f"[{self.symbol}] Could not determine TP level for filled order {fill_data['orderId']} at level {filled_level_price}. Maybe edge of grid?")

        # --- Record Trade --- #
        self.trade_history.append({
            'timestamp': fill_data.get('updateTime', int(time.time() * 1000)),
            'orderId': fill_data['orderId'],
            'side': side,
            'price': avg_price,
            'quantity': filled_qty,
            'realizedPnl': realized_pnl,
            'commission': commission,
            'commissionAsset': commission_asset,
            'positionAmtAfter': self.position['positionAmt']
        })
        self.total_trades += 1
        log.info(f"[{self.symbol}] Trade recorded. Total trades: {self.total_trades}")

        # --- Check for RL Retraining Trigger --- #
        retrain_threshold = self.config.get("rl", {}).get("retrain_after_trades", 0)
        if retrain_threshold > 0 and self.total_trades % retrain_threshold == 0:
            log.info(f"[{self.symbol}] Reached {self.total_trades} trades. Triggering RL retraining signal (implementation needed in main loop)." )
            # The main loop should check a flag or queue to start the training process
            # self.trigger_rl_retraining_flag = True # Example flag

    def cancel_active_grid_orders(self):
        # ... (no changes) ...
        log.warning(f"[{self.symbol}] Cancelling all active grid orders ({len(self.active_grid_orders)})...\")
        orders_to_cancel = list(self.active_grid_orders.values())
        cancelled_count = 0
        failed_count = 0
        for order_id in orders_to_cancel:
            try:
                # APIClient handles simulation
                success = self.api_client.cancel_futures_order(symbol=self.symbol, orderId=order_id)
                time.sleep(0.1)
                if success:
                    log.info(f\"[{self.symbol}] Cancelled order {order_id}.\")
                    cancelled_count += 1
                    # Remove from tracking
                    if order_id in self.open_orders: del self.open_orders[order_id]
                    if self.operation_mode == \"shadow\" and order_id in self.simulated_open_orders:
                        del self.simulated_open_orders[order_id]
                    # Remove from active_grid_orders by value
                    for price, oid in list(self.active_grid_orders.items()):
                        if oid == order_id:
                            del self.active_grid_orders[price]
                            break
                else:
                    log.error(f\"[{self.symbol}] Failed to cancel order {order_id}.\")
                    failed_count += 1
            except Exception as e:
                log.error(f\"[{self.symbol}] Exception cancelling order {order_id}: {e}\")
                failed_count += 1
        log.warning(f\"[{self.symbol}] Order cancellation finished. Cancelled: {cancelled_count}, Failed: {failed_count}. Remaining active: {len(self.active_grid_orders)}\")
        # Clear remaining just in case, though ideally they should be removed above
        self.active_grid_orders.clear()
        self.open_orders.clear()
        if self.operation_mode == \"shadow\": self.simulated_open_orders.clear()

    def get_state(self):
        """Returns the current state of the grid for the RL agent or monitoring."""
        # Update position info before returning state
        self._update_position_info()

        return {
            "symbol": self.symbol,
            "operation_mode": self.operation_mode,
            "num_levels": self.num_levels,
            "base_spacing_percentage": float(self.base_spacing_percentage),
            "current_spacing_percentage": float(self.current_spacing_percentage),
            "use_dynamic_spacing": self.use_dynamic_spacing,
            "grid_direction": self.grid_direction,
            "grid_levels_count": len(self.grid_levels),
            "active_grid_orders_count": len(self.active_grid_orders),
            "open_orders_count": len(self.open_orders),
            "position_amount": float(self.position.get("positionAmt", 0)),
            "entry_price": float(self.position.get("entryPrice", 0)),
            "mark_price": float(self.position.get("markPrice", 0)),
            "unrealized_pnl": float(self.position.get("unRealizedProfit", 0)),
            "total_realized_pnl": float(self.total_realized_pnl),
            "total_trades": self.total_trades,
            "talib_available": talib_available # Expose TA-Lib status
        }

    def _update_position_info(self):
        """Updates the position details (mark price, PnL) from the API or ticker."""
        try:
            if self.operation_mode == "production":
                pos_data = self.api_client.get_futures_position_info(symbol=self.symbol)
                if pos_data:
                    # Binance API returns a list, find the specific symbol
                    symbol_pos = next((p for p in pos_data if p.get('symbol') == self.symbol), None)
                    if symbol_pos:
                        self.position['positionAmt'] = Decimal(symbol_pos.get('positionAmt', '0'))
                        self.position['entryPrice'] = Decimal(symbol_pos.get('entryPrice', '0'))
                        self.position['markPrice'] = Decimal(symbol_pos.get('markPrice', '0'))
                        self.position['unRealizedProfit'] = Decimal(symbol_pos.get('unRealizedProfit', '0'))
                        self.position['liquidationPrice'] = Decimal(symbol_pos.get('liquidationPrice', '0'))
                    else:
                        # No position exists, reset
                        self.position = {'positionAmt': Decimal('0'), 'entryPrice': Decimal('0'), 'markPrice': Decimal('0'), 'unRealizedProfit': Decimal('0'), 'liquidationPrice': Decimal('0')}
                else:
                    log.warning(f"[{self.symbol}] Could not fetch production position info.")
                    # Fetch ticker as fallback for mark price
                    ticker = self.api_client.get_futures_ticker(symbol=self.symbol)
                    if ticker and 'lastPrice' in ticker:
                        self.position['markPrice'] = Decimal(ticker['lastPrice'])

            elif self.operation_mode == "shadow":
                # Update mark price from ticker
                ticker = self.api_client.get_futures_ticker(symbol=self.symbol)
                if ticker and 'lastPrice' in ticker:
                    mark_price = Decimal(ticker['lastPrice'])
                    self.position['markPrice'] = mark_price
                    # Update simulated unrealized PnL
                    pos_amt = self.position['positionAmt']
                    entry_price = self.position['entryPrice']
                    if pos_amt != 0 and entry_price != 0:
                        if pos_amt > 0: # Long
                            self.position['unRealizedProfit'] = (mark_price - entry_price) * pos_amt
                        else: # Short
                            self.position['unRealizedProfit'] = (entry_price - mark_price) * abs(pos_amt)
                    else:
                        self.position['unRealizedProfit'] = Decimal('0')
                else:
                    log.warning(f"[{self.symbol} - SHADOW] Could not fetch ticker to update mark price.")

        except Exception as e:
            log.error(f"[{self.symbol}] Error updating position info: {e}", exc_info=True)

    def get_market_state(self):
        """Gets the current market state for RL agent.
        
        Returns:
            numpy.ndarray: State vector containing market and grid features
        """
        # Ensure we have latest market data
        self._update_market_data()
        
        # Create state vector
        state_features = []
        
        # 1. Price features
        current_price = self.current_price
        if hasattr(self, 'price_history') and len(self.price_history) > 0:
            # Normalized price changes
            price_changes = []
            for i in range(1, min(10, len(self.price_history))):
                if self.price_history[0] > 0:
                    change = (self.price_history[i-1] / self.price_history[0]) - 1.0
                    price_changes.append(change)
            
            # Add recent price changes to state
            state_features.extend(price_changes)
            
            # Add volatility estimate
            if len(self.price_history) >= 20:
                volatility = np.std(self.price_history[:20]) / np.mean(self.price_history[:20])
                state_features.append(volatility)
            else:
                state_features.append(0.01)  # Default volatility
        else:
            # If no price history, add placeholders
            state_features.extend([0.0] * 10)  # Price changes
            state_features.append(0.01)  # Volatility
        
        # 2. Grid features
        # Normalized grid parameters
        state_features.append(self.num_levels / 20.0)  # Normalize by max levels
        state_features.append(float(self.current_spacing_percentage) / 0.02)  # Normalize by max spacing
        
        # Grid position relative to current price
        if hasattr(self, 'grid_levels') and len(self.grid_levels) > 0:
            buy_levels_below = sum(1 for level in self.grid_levels if level < current_price)
            sell_levels_above = sum(1 for level in self.grid_levels if level > current_price)
            grid_balance = (buy_levels_below - sell_levels_above) / max(1, len(self.grid_levels))
            state_features.append(grid_balance)
        else:
            state_features.append(0.0)  # Balanced grid
        
        # 3. Position features
        # Current position size
        position_size = self.current_position_size if hasattr(self, 'current_position_size') else 0.0
        max_position = self.risk_config.get("max_position_size", 1.0)
        state_features.append(position_size / max_position)  # Normalized position size
        
        # Unrealized PnL
        unrealized_pnl = self.unrealized_pnl if hasattr(self, 'unrealized_pnl') else 0.0
        state_features.append(min(1.0, max(-1.0, unrealized_pnl / 0.1)))  # Clip to [-1, 1]
        
        # 4. Technical indicators (if TA-Lib available)
        if talib_available and hasattr(self, 'price_history') and len(self.price_history) >= 30:
            prices = np.array(self.price_history[:30])
            
            # RSI
            try:
                rsi = talib.RSI(prices, timeperiod=14)[-1] / 100.0  # Normalize to [0, 1]
                state_features.append(rsi)
            except:
                state_features.append(0.5)  # Neutral RSI
            
            # MACD
            try:
                macd, signal, hist = talib.MACD(prices)
                # Normalize histogram
                norm_hist = np.clip((hist[-1] / (prices.mean() * 0.01)) / 2.0 + 0.5, 0, 1)
                state_features.append(norm_hist)
            except:
                state_features.append(0.5)  # Neutral MACD
        else:
            # Add placeholders if TA-Lib not available
            state_features.extend([0.5, 0.5])  # Neutral RSI and MACD
        
        # 5. Market activity features
        # Recent trades count/volume
        if hasattr(self, 'recent_trades_count'):
            state_features.append(min(1.0, self.recent_trades_count / 1000.0))  # Normalize trades count
        else:
            state_features.append(0.5)  # Average activity
        
        # Convert to numpy array and ensure all values are valid
        state_array = np.array(state_features, dtype=np.float32)
        state_array = np.nan_to_num(state_array, nan=0.5)  # Replace NaN with neutral value
        
        return state_array
    
    def _apply_discrete_rl_action(self, action):
        """Applies a discrete action from the RL agent to modify grid parameters.
        
        Args:
            action (int): Discrete action index from the RL agent
                0: No change (maintain current parameters)
                1: Increase number of levels
                2: Decrease number of levels
                3: Increase spacing percentage
                4: Decrease spacing percentage
                5: Shift grid direction bullish (long)
                6: Shift grid direction bearish (short)
                7: Reset to balanced grid (neutral)
                8: Aggressive bullish setup (more levels, tighter spacing, long direction)
                9: Aggressive bearish setup (more levels, tighter spacing, short direction)
        """
        log.info(f"[{self.symbol}] Applying RL discrete action: {action}")
        
        # Current parameters
        current_levels = self.num_levels
        current_spacing = self.base_spacing_percentage
        current_direction = self.grid_direction if hasattr(self, 'grid_direction') else "neutral"
        
        # Parameter change amounts
        level_change = max(2, int(current_levels * 0.2))  # 20% change, ensure even number
        if level_change % 2 != 0:
            level_change += 1  # Make it even
        
        spacing_change = Decimal(str(float(current_spacing) * 0.2))  # 20% change
        
        # Apply action
        if action == 0:  # No change
            log.info(f"[{self.symbol}] RL action: No change to grid parameters")
            return
            
        elif action == 1:  # Increase levels
            new_levels = current_levels + level_change
            self.update_grid_parameters(num_levels=new_levels)
            log.info(f"[{self.symbol}] RL action: Increased levels from {current_levels} to {new_levels}")
            
        elif action == 2:  # Decrease levels
            new_levels = max(4, current_levels - level_change)  # Minimum 4 levels
            if new_levels % 2 != 0:
                new_levels += 1  # Ensure even number
            self.update_grid_parameters(num_levels=new_levels)
            log.info(f"[{self.symbol}] RL action: Decreased levels from {current_levels} to {new_levels}")
            
        elif action == 3:  # Increase spacing
            new_spacing = current_spacing + spacing_change
            self.update_grid_parameters(spacing_percentage=float(new_spacing))
            log.info(f"[{self.symbol}] RL action: Increased spacing from {current_spacing} to {new_spacing}")
            
        elif action == 4:  # Decrease spacing
            new_spacing = max(Decimal('0.001'), current_spacing - spacing_change)
            self.update_grid_parameters(spacing_percentage=float(new_spacing))
            log.info(f"[{self.symbol}] RL action: Decreased spacing from {current_spacing} to {new_spacing}")
            
        elif action == 5:  # More bullish
            self.update_grid_parameters(direction="long")
            log.info(f"[{self.symbol}] RL action: Shifted direction bullish from {current_direction} to long")
            
        elif action == 6:  # More bearish
            self.update_grid_parameters(direction="short")
            log.info(f"[{self.symbol}] RL action: Shifted direction bearish from {current_direction} to short")
            
        elif action == 7:  # Reset to balanced
            self.update_grid_parameters(direction="neutral")
            log.info(f"[{self.symbol}] RL action: Reset to balanced grid (direction=neutral)")
            
        elif action == 8:  # Aggressive bullish
            new_levels = min(20, current_levels + level_change)
            new_spacing = max(Decimal('0.001'), current_spacing - spacing_change)
            self.update_grid_parameters(
                num_levels=new_levels,
                spacing_percentage=float(new_spacing),
                direction="long"
            )
            log.info(f"[{self.symbol}] RL action: Aggressive bullish setup (levels={new_levels}, spacing={new_spacing}, direction=long)")
            
        elif action == 9:  # Aggressive bearish
            new_levels = min(20, current_levels + level_change)
            new_spacing = max(Decimal('0.001'), current_spacing - spacing_change)
            self.update_grid_parameters(
                num_levels=new_levels,
                spacing_percentage=float(new_spacing),
                direction="short"
            )
            log.info(f"[{self.symbol}] RL action: Aggressive bearish setup (levels={new_levels}, spacing={new_spacing}, direction=short)")
            
        else:
            log.warning(f"[{self.symbol}] Unknown RL action: {action}")
    
    def run_cycle(self, rl_action=None):
        """Main execution cycle for the grid logic."""
        log.info(f"[{self.symbol}] Running grid cycle...")

        # 0. Update position info first
        self._update_position_info()
        
        # Apply RL agent actions if provided
        if rl_action is not None:
            # Process RL action based on the action type
            if isinstance(rl_action, (int, np.integer)):
                # Discrete action space (0: no change, 1: increase levels, 2: decrease levels, etc.)
                self._apply_discrete_rl_action(rl_action)
            elif isinstance(rl_action, dict):
                # Dictionary with explicit parameters
                self.update_grid_parameters(
                    num_levels=rl_action.get('num_levels'),
                    spacing_percentage=rl_action.get('spacing_percentage'),
                    direction=rl_action.get('direction')
                )
            else:
                log.warning(f"[{self.symbol}] Unsupported RL action type: {type(rl_action)}")

        # 1. Check if grid needs (re)definition
        if not self.grid_levels:
            ticker = self.api_client.get_futures_ticker(symbol=self.symbol)
            if not ticker or 'lastPrice' not in ticker:
                log.error(f"[{self.symbol}] Cannot define grid, failed to get current price.")
                return # Wait for next cycle
            current_price = float(ticker['lastPrice'])
            self.define_grid_levels(current_price)
            if self.grid_levels:
                self.place_initial_grid_orders()
            else:
                log.error(f"[{self.symbol}] Failed to define grid levels.")
                return

        # 2. Check for filled orders
        # In shadow mode, need kline data for simulation
        current_kline = None
        if self.operation_mode == "shadow":
            # Fetch the last completed kline (e.g., 1 minute)
            klines = self.api_client.get_futures_klines(symbol=self.symbol, interval='1m', limit=2)
            if klines and len(klines) >= 2:
                # Use the second to last kline (the last fully closed one)
                last_closed_kline_data = klines[-2]
                current_kline = {
                    'Open': last_closed_kline_data[1],
                    'High': last_closed_kline_data[2],
                    'Low': last_closed_kline_data[3],
                    'Close': last_closed_kline_data[4]
                }
            else:
                log.warning(f"[{self.symbol} - SHADOW] Could not fetch sufficient kline data for fill simulation.")

        self.check_and_handle_fills(current_kline=current_kline)

        # 3. (Optional) Add other checks like risk management triggers (handled externally for now)

        log.info(f"[{self.symbol}] Grid cycle finished.")

# Example usage (for testing structure)
# if __name__ == '__main__':
#     # Requires mocking APIClient and config
#     print("GridLogic class defined.")

