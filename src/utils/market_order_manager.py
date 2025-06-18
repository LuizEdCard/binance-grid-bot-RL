# Market Order Manager - Gerenciamento de ordens de mercado com controle rigoroso de slippage
import time
from decimal import Decimal, ROUND_DOWN
from typing import Dict, Optional, Tuple, List
import numpy as np

from utils.logger import setup_logger
from utils.api_client import APIClient

log = setup_logger("market_order_manager")


class SlippageMonitor:
    """Monitor de slippage para ordens de mercado."""
    
    def __init__(self, symbol: str, max_slippage_percentage: float = 0.1):
        """
        Args:
            symbol: Símbolo do ativo
            max_slippage_percentage: Slippage máximo permitido em % (0.1 = 0.1%)
        """
        self.symbol = symbol
        self.max_slippage_percentage = max_slippage_percentage
        self.slippage_history = []
        self.total_slippage_cost = Decimal("0")
        self.order_count = 0
        
    def calculate_slippage(self, expected_price: Decimal, executed_price: Decimal, 
                          quantity: Decimal) -> Dict:
        """Calcula slippage de uma ordem executada."""
        price_diff = abs(executed_price - expected_price)
        slippage_percentage = (price_diff / expected_price) * 100
        slippage_cost = price_diff * quantity
        
        slippage_data = {
            "expected_price": expected_price,
            "executed_price": executed_price,
            "slippage_percentage": float(slippage_percentage),
            "slippage_cost_usdt": float(slippage_cost),
            "quantity": quantity,
            "timestamp": time.time()
        }
        
        # Atualizar histórico
        self.slippage_history.append(slippage_data)
        self.total_slippage_cost += slippage_cost
        self.order_count += 1
        
        # Manter apenas últimas 100 ordens
        if len(self.slippage_history) > 100:
            self.slippage_history = self.slippage_history[-100:]
        
        return slippage_data
    
    def get_average_slippage(self) -> float:
        """Retorna slippage médio das últimas ordens."""
        if not self.slippage_history:
            return 0.0
        
        recent_slippages = [s["slippage_percentage"] for s in self.slippage_history[-20:]]
        return np.mean(recent_slippages)
    
    def is_slippage_acceptable(self, expected_price: Decimal, current_market_price: Decimal) -> bool:
        """Verifica se o slippage previsto está dentro do limite."""
        if expected_price == 0:
            return False
            
        predicted_slippage = abs(current_market_price - expected_price) / expected_price * 100
        return predicted_slippage <= self.max_slippage_percentage
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas de slippage."""
        if not self.slippage_history:
            return {
                "total_orders": 0,
                "avg_slippage_percentage": 0.0,
                "total_slippage_cost": 0.0,
                "max_slippage": 0.0,
                "min_slippage": 0.0
            }
        
        slippages = [s["slippage_percentage"] for s in self.slippage_history]
        
        return {
            "total_orders": len(self.slippage_history),
            "avg_slippage_percentage": np.mean(slippages),
            "total_slippage_cost": float(self.total_slippage_cost),
            "max_slippage": max(slippages),
            "min_slippage": min(slippages),
            "recent_avg_slippage": self.get_average_slippage()
        }


class MarketDepthAnalyzer:
    """Analisador de profundidade de mercado para otimizar execução."""
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        
    def analyze_market_depth(self, symbol: str, quantity: Decimal, 
                           side: str) -> Dict:
        """Analisa profundidade do mercado para uma ordem."""
        try:
            # Obter order book
            depth = self.api_client.get_order_book_depth(symbol, limit=20)
            if not depth:
                return {"error": "Could not fetch order book"}
            
            # Analisar lado apropriado
            if side.upper() == "BUY":
                orders = depth.get("asks", [])
                price_impact = self._calculate_price_impact(orders, quantity, "ask")
            else:  # SELL
                orders = depth.get("bids", [])
                price_impact = self._calculate_price_impact(orders, quantity, "bid")
            
            analysis = depth.get("analysis", {})
            analysis.update(price_impact)
            
            return analysis
            
        except Exception as e:
            log.error(f"Error analyzing market depth for {symbol}: {e}")
            return {"error": str(e)}
    
    def _calculate_price_impact(self, orders: List, quantity: Decimal, 
                              order_type: str) -> Dict:
        """Calcula impacto no preço de uma ordem."""
        if not orders:
            return {"price_impact": 0.0, "liquidity_sufficient": False}
        
        total_quantity = Decimal("0")
        weighted_price = Decimal("0")
        best_price = Decimal(str(orders[0][0]))
        
        for price_str, qty_str in orders:
            price = Decimal(str(price_str))
            qty = Decimal(str(qty_str))
            
            if total_quantity + qty >= quantity:
                # Última ordem parcial
                remaining = quantity - total_quantity
                weighted_price += price * remaining
                total_quantity = quantity
                break
            else:
                weighted_price += price * qty
                total_quantity += qty
        
        if total_quantity < quantity:
            return {
                "price_impact": 999.0,  # Liquidez insuficiente
                "liquidity_sufficient": False,
                "available_liquidity": float(total_quantity)
            }
        
        avg_execution_price = weighted_price / quantity
        price_impact = abs(avg_execution_price - best_price) / best_price * 100
        
        return {
            "price_impact": float(price_impact),
            "liquidity_sufficient": True,
            "estimated_execution_price": float(avg_execution_price),
            "best_price": float(best_price)
        }


class MarketOrderManager:
    """Gerenciador de ordens de mercado com controle rigoroso de slippage."""
    
    def __init__(self, api_client: APIClient, config: dict):
        self.api_client = api_client
        self.config = config
        
        # Configurações de slippage
        self.max_slippage = config.get("market_orders", {}).get("max_slippage_percentage", 0.15)  # 0.15%
        self.max_order_size_percentage = config.get("market_orders", {}).get("max_order_size_percentage", 0.5)  # 50% do volume
        self.enable_pre_execution_check = config.get("market_orders", {}).get("enable_pre_execution_check", True)
        
        # Monitores por símbolo
        self.slippage_monitors: Dict[str, SlippageMonitor] = {}
        self.depth_analyzer = MarketDepthAnalyzer(api_client)
        
        # Estatísticas globais
        self.total_market_orders = 0
        self.successful_orders = 0
        self.rejected_orders = 0
        
        log.info(f"MarketOrderManager inicializado - Max slippage: {self.max_slippage}%")
    
    def get_slippage_monitor(self, symbol: str) -> SlippageMonitor:
        """Obtém monitor de slippage para um símbolo."""
        if symbol not in self.slippage_monitors:
            self.slippage_monitors[symbol] = SlippageMonitor(symbol, self.max_slippage)
        return self.slippage_monitors[symbol]
    
    def place_market_order_with_slippage_control(self, symbol: str, side: str, 
                                                quantity: str, market_type: str = "futures",
                                                max_slippage_override: float = None) -> Optional[Dict]:
        """
        Coloca ordem de mercado com controle rigoroso de slippage.
        
        Args:
            symbol: Símbolo do ativo
            side: BUY ou SELL
            quantity: Quantidade da ordem
            market_type: "futures" ou "spot"
            max_slippage_override: Sobrescrever limite de slippage padrão
        
        Returns:
            Dict com resultado da ordem ou None se rejeitada
        """
        try:
            monitor = self.get_slippage_monitor(symbol)
            max_slippage = max_slippage_override or self.max_slippage
            
            log.info(f"[{symbol}] Preparando ordem de mercado: {side} {quantity}")
            
            # 1. Obter preço atual de referência
            current_price = self._get_current_price(symbol, market_type)
            if not current_price:
                log.error(f"[{symbol}] Não foi possível obter preço atual")
                self.rejected_orders += 1
                return None
            
            current_price_decimal = Decimal(str(current_price))
            quantity_decimal = Decimal(str(quantity))
            
            # 2. Análise pré-execução (se habilitada)
            if self.enable_pre_execution_check:
                depth_analysis = self.depth_analyzer.analyze_market_depth(
                    symbol, quantity_decimal, side
                )
                
                if "error" in depth_analysis:
                    log.warning(f"[{symbol}] Erro na análise de profundidade: {depth_analysis['error']}")
                
                # Verificar liquidez suficiente
                if not depth_analysis.get("liquidity_sufficient", True):
                    log.error(f"[{symbol}] Liquidez insuficiente para ordem de {quantity}")
                    self.rejected_orders += 1
                    return None
                
                # Verificar impacto no preço
                price_impact = depth_analysis.get("price_impact", 0.0)
                if price_impact > max_slippage:
                    log.error(f"[{symbol}] Impacto no preço muito alto: {price_impact:.3f}% > {max_slippage}%")
                    self.rejected_orders += 1
                    return None
                
                log.info(f"[{symbol}] Análise pré-execução OK - Impacto estimado: {price_impact:.3f}%")
            
            # 3. Executar ordem de mercado
            start_time = time.time()
            
            if market_type == "futures":
                order_result = self.api_client.place_futures_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=quantity
                )
            else:  # spot
                order_result = self.api_client.place_spot_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=quantity
                )
            
            execution_time = time.time() - start_time
            
            if not order_result or "orderId" not in order_result:
                log.error(f"[{symbol}] Falha na execução da ordem de mercado")
                self.rejected_orders += 1
                return None
            
            # 4. Analisar slippage pós-execução
            executed_price = None
            if "fills" in order_result:
                # Calcular preço médio ponderado das execuções
                total_qty = Decimal("0")
                weighted_price = Decimal("0")
                
                for fill in order_result["fills"]:
                    fill_price = Decimal(str(fill["price"]))
                    fill_qty = Decimal(str(fill["qty"]))
                    weighted_price += fill_price * fill_qty
                    total_qty += fill_qty
                
                if total_qty > 0:
                    executed_price = weighted_price / total_qty
            
            if not executed_price:
                # Fallback: usar preço da ordem
                executed_price = Decimal(str(order_result.get("price", current_price)))
            
            # Calcular e registrar slippage
            slippage_data = monitor.calculate_slippage(
                current_price_decimal, executed_price, quantity_decimal
            )
            
            # Verificar se slippage está dentro do limite
            if slippage_data["slippage_percentage"] > max_slippage:
                log.warning(f"[{symbol}] ⚠️ Slippage alto detectado: {slippage_data['slippage_percentage']:.3f}% "
                          f"(Custo: ${slippage_data['slippage_cost_usdt']:.4f})")
            else:
                log.info(f"[{symbol}] ✅ Ordem executada com slippage aceitável: {slippage_data['slippage_percentage']:.3f}%")
            
            # Atualizar estatísticas
            self.total_market_orders += 1
            self.successful_orders += 1
            
            # Adicionar dados de slippage ao resultado
            order_result.update({
                "slippage_data": slippage_data,
                "execution_time_ms": execution_time * 1000,
                "reference_price": float(current_price_decimal),
                "executed_price": float(executed_price)
            })
            
            log.info(f"[{symbol}] Ordem de mercado executada: ID {order_result['orderId']} "
                    f"({execution_time*1000:.1f}ms)")
            
            return order_result
            
        except Exception as e:
            log.error(f"[{symbol}] Erro ao executar ordem de mercado: {e}")
            self.rejected_orders += 1
            return None
    
    def _get_current_price(self, symbol: str, market_type: str) -> Optional[float]:
        """Obtém preço atual do mercado."""
        try:
            if market_type == "futures":
                ticker = self.api_client.get_futures_ticker(symbol)
                return float(ticker.get("price", 0)) if ticker else None
            else:  # spot
                ticker = self.api_client.get_spot_ticker(symbol)
                return float(ticker.get("lastPrice", 0)) if ticker else None
        except Exception as e:
            log.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def should_use_market_order(self, symbol: str, urgency_level: str = "normal") -> bool:
        """
        Determina se deve usar ordem de mercado baseado nas condições atuais.
        
        Args:
            symbol: Símbolo do ativo
            urgency_level: "low", "normal", "high", "critical"
        
        Returns:
            True se deve usar ordem de mercado
        """
        try:
            monitor = self.get_slippage_monitor(symbol)
            avg_slippage = monitor.get_average_slippage()
            
            # Limites de slippage por nível de urgência
            slippage_thresholds = {
                "low": self.max_slippage * 0.5,      # 50% do limite
                "normal": self.max_slippage * 0.75,   # 75% do limite
                "high": self.max_slippage,            # 100% do limite
                "critical": self.max_slippage * 1.5   # 150% do limite
            }
            
            threshold = slippage_thresholds.get(urgency_level, self.max_slippage)
            
            # Decisão baseada no slippage histórico
            should_use = avg_slippage <= threshold
            
            log.debug(f"[{symbol}] Market order decision: {should_use} "
                     f"(avg_slippage: {avg_slippage:.3f}%, threshold: {threshold:.3f}%)")
            
            return should_use
            
        except Exception as e:
            log.error(f"Error deciding market order usage for {symbol}: {e}")
            return False
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas globais do manager."""
        symbol_stats = {}
        total_slippage_cost = 0.0
        
        for symbol, monitor in self.slippage_monitors.items():
            stats = monitor.get_statistics()
            symbol_stats[symbol] = stats
            total_slippage_cost += stats["total_slippage_cost"]
        
        success_rate = (self.successful_orders / max(self.total_market_orders, 1)) * 100
        
        return {
            "total_orders": self.total_market_orders,
            "successful_orders": self.successful_orders,
            "rejected_orders": self.rejected_orders,
            "success_rate": success_rate,
            "total_slippage_cost": total_slippage_cost,
            "symbols_tracked": len(self.slippage_monitors),
            "symbol_statistics": symbol_stats
        }
    
    def optimize_parameters(self, symbol: str) -> Dict:
        """Otimiza parâmetros baseado no histórico de slippage."""
        try:
            monitor = self.get_slippage_monitor(symbol)
            stats = monitor.get_statistics()
            
            if stats["total_orders"] < 10:  # Dados insuficientes
                return {"optimization": "insufficient_data"}
            
            avg_slippage = stats["avg_slippage_percentage"]
            
            # Ajustar limite de slippage baseado no histórico
            if avg_slippage < self.max_slippage * 0.3:
                # Performance muito boa, pode ser mais agressivo
                recommended_limit = min(self.max_slippage * 1.2, 0.25)
                recommendation = "increase_aggressiveness"
            elif avg_slippage > self.max_slippage * 0.8:
                # Performance ruim, ser mais conservador
                recommended_limit = max(self.max_slippage * 0.7, 0.05)
                recommendation = "decrease_aggressiveness"
            else:
                # Performance adequada, manter
                recommended_limit = self.max_slippage
                recommendation = "maintain_current"
            
            return {
                "optimization": recommendation,
                "current_avg_slippage": avg_slippage,
                "recommended_max_slippage": recommended_limit,
                "total_orders_analyzed": stats["total_orders"]
            }
            
        except Exception as e:
            log.error(f"Error optimizing parameters for {symbol}: {e}")
            return {"optimization": "error", "error": str(e)}

