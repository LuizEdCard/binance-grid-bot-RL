"""
Capital Management - Gestão inteligente de capital baseada em saldo disponível
"""
import math
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from utils.logger import setup_logger
from utils.api_client import APIClient

log = setup_logger("capital_management")


@dataclass
class CapitalAllocation:
    """Representação da alocação de capital."""
    symbol: str
    allocated_amount: float
    max_position_size: float
    grid_levels: int
    spacing_percentage: float
    market_type: str  # 'spot' ou 'futures'
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "allocated_amount": self.allocated_amount,
            "max_position_size": self.max_position_size,
            "grid_levels": self.grid_levels,
            "spacing_percentage": self.spacing_percentage,
            "market_type": self.market_type
        }


class CapitalManager:
    """
    Gerencia a alocação de capital baseada no saldo disponível.
    Adapta automaticamente o grid ao capital disponível.
    """
    
    def __init__(self, api_client: APIClient, config: dict):
        self.api_client = api_client
        self.config = config
        
        # Configurações de trading
        self.trading_config = config.get("trading", {})
        self.max_concurrent_pairs = self.trading_config.get("max_concurrent_pairs", 3)
        self.market_allocation = self.trading_config.get("market_allocation", {
            "spot_percentage": 40,
            "futures_percentage": 60
        })
        
        # Configurações de risco
        self.risk_config = config.get("risk_management", {})
        self.max_capital_per_pair_percentage = 30.0  # Máximo 30% do capital por par
        self.min_capital_per_pair_usd = 5.0  # Mínimo $5 por par
        self.safety_buffer_percentage = 10.0  # 10% de buffer de segurança
        
        # Cache
        self.last_balance_check = 0
        self.cached_balances = {}
        self.current_allocations = {}
        
        # Estatísticas
        self.stats = {
            "balance_checks": 0,
            "allocation_updates": 0,
            "insufficient_capital_events": 0,
            "last_total_balance": 0.0
        }
        
    def get_available_balances(self) -> Dict[str, float]:
        """Obtém saldos disponíveis para spot e futures."""
        try:
            balances = {
                "spot_usdt": 0.0,
                "futures_usdt": 0.0,
                "total_usdt": 0.0
            }
            
            # Saldo Spot
            try:
                spot_balance = self.api_client.get_account_balance()
                if isinstance(spot_balance, list):
                    for asset in spot_balance:
                        if asset.get("asset") == "USDT":
                            balances["spot_usdt"] = float(asset.get("free", "0"))
                            break
                elif isinstance(spot_balance, dict):
                    usdt_balance = spot_balance.get("USDT", {})
                    balances["spot_usdt"] = float(usdt_balance.get("free", "0"))
            except Exception as e:
                log.warning(f"Failed to get spot balance: {e}")
            
            # Saldo Futures
            try:
                futures_balance = self.api_client.get_futures_account_balance()
                if isinstance(futures_balance, list):
                    for asset in futures_balance:
                        if asset.get("asset") == "USDT":
                            balances["futures_usdt"] = float(asset.get("availableBalance", "0"))
                            break
                elif isinstance(futures_balance, dict):
                    balances["futures_usdt"] = float(futures_balance.get("availableBalance", "0"))
            except Exception as e:
                log.warning(f"Failed to get futures balance: {e}")
            
            # Total
            balances["total_usdt"] = balances["spot_usdt"] + balances["futures_usdt"]
            
            # Cache e estatísticas
            self.cached_balances = balances
            self.last_balance_check = time.time()
            self.stats["balance_checks"] += 1
            self.stats["last_total_balance"] = balances["total_usdt"]
            
            log.info(f"Available balances - Spot: ${balances['spot_usdt']:.2f}, Futures: ${balances['futures_usdt']:.2f}, Total: ${balances['total_usdt']:.2f}")
            return balances
            
        except Exception as e:
            log.error(f"Error getting available balances: {e}")
            return {"spot_usdt": 0.0, "futures_usdt": 0.0, "total_usdt": 0.0}
    
    def detect_and_convert_brl_balance(self) -> bool:
        """
        Detecta saldo em BRL e converte para USDT quando disponível.
        
        Returns:
            bool: True se conversão foi realizada ou não necessária, False se houve erro
        """
        try:
            log.info("Checking for BRL balance to convert to USDT...")
            
            # Verificar saldo spot completo para encontrar BRL
            spot_balances = self.api_client.get_account_balance()
            brl_balance = 0.0
            
            if isinstance(spot_balances, list):
                for asset in spot_balances:
                    if asset.get("asset") == "BRL":
                        brl_balance = float(asset.get("free", "0"))
                        break
            elif isinstance(spot_balances, dict):
                brl_data = spot_balances.get("BRL", {})
                brl_balance = float(brl_data.get("free", "0"))
            
            # Mínimo de R$ 50 para converter (evitar conversões muito pequenas)
            min_brl_to_convert = 50.0
            
            if brl_balance < min_brl_to_convert:
                if brl_balance > 0:
                    log.info(f"BRL balance too small to convert: R$ {brl_balance:.2f} (minimum: R$ {min_brl_to_convert:.2f})")
                return True
            
            log.info(f"Found BRL balance: R$ {brl_balance:.2f}. Attempting conversion to USDT...")
            
            # Obter cotação BRL/USDT
            try:
                ticker = self.api_client.get_spot_ticker("BRLUSDT")
                if not ticker or "price" not in ticker:
                    log.error("Could not get BRL/USDT price. Cannot convert.")
                    return False
                
                brl_usdt_price = float(ticker["price"])
                estimated_usdt = brl_balance * brl_usdt_price
                
                log.info(f"BRL/USDT price: {brl_usdt_price:.6f} - Estimated USDT: ${estimated_usdt:.2f}")
                
                # Verificar se vale a pena converter (mínimo de $10 USDT)
                if estimated_usdt < 10.0:
                    log.info(f"Conversion would yield too little USDT: ${estimated_usdt:.2f} < $10.00")
                    return True
                
            except Exception as e:
                log.error(f"Error getting BRL/USDT price: {e}")
                return False
            
            # Executar conversão via order de mercado
            success = self._execute_brl_to_usdt_conversion(brl_balance, brl_usdt_price)
            
            if success:
                log.info(f"✅ Successfully converted R$ {brl_balance:.2f} to USDT")
                return True
            else:
                log.error(f"❌ Failed to convert R$ {brl_balance:.2f} to USDT")
                return False
                
        except Exception as e:
            log.error(f"Error in BRL detection/conversion: {e}")
            return False
    
    def _execute_brl_to_usdt_conversion(self, brl_amount: float, brl_usdt_price: float) -> bool:
        """
        Executa a conversão BRL -> USDT via order de mercado.
        
        Args:
            brl_amount: Quantidade de BRL disponível
            brl_usdt_price: Preço atual BRL/USDT
            
        Returns:
            bool: True se conversão foi bem-sucedida
        """
        try:
            # Calcular quantidade para vender (descontar small fee)
            quantity_to_sell = brl_amount * 0.999  # 0.1% buffer para fees
            
            log.info(f"Placing BRL/USDT market sell order: {quantity_to_sell:.6f} BRL")
            
            # Executar order de mercado
            if self.api_client.operation_mode == "shadow":
                # Em modo shadow, simular a conversão
                log.info(f"[SHADOW MODE] Simulated BRL->USDT conversion: {quantity_to_sell:.2f} BRL -> ${quantity_to_sell * brl_usdt_price:.2f} USDT")
                return True
            else:
                # Modo production - order real
                order_result = self.api_client.place_spot_order(
                    symbol="BRLUSDT",
                    side="SELL",
                    order_type="MARKET",
                    quantity=quantity_to_sell
                )
                
                if order_result and order_result.get("status") in ["FILLED", "NEW"]:
                    log.info(f"BRL conversion order successful: {order_result.get('orderId')}")
                    return True
                else:
                    log.error(f"BRL conversion order failed: {order_result}")
                    return False
                    
        except Exception as e:
            log.error(f"Error executing BRL conversion: {e}")
            return False
    
    def calculate_optimal_allocations(self, 
                                    symbols: List[str], 
                                    market_types: Dict[str, str] = None,
                                    use_proportional_allocation: bool = True) -> List[CapitalAllocation]:
        """
        Calcula alocações ótimas de capital baseadas no saldo disponível.
        
        Args:
            symbols: Lista de símbolos para trading
            market_types: Dict mapeando símbolo para tipo de mercado (spot/futures)
        """
        # Primeiro, verificar e converter saldo BRL se disponível
        try:
            self.detect_and_convert_brl_balance()
        except Exception as e:
            log.warning(f"BRL conversion check failed: {e}")
        
        balances = self.get_available_balances()
        total_capital = balances["total_usdt"]
        
        if total_capital < self.min_capital_per_pair_usd:
            log.warning(f"Insufficient capital: ${total_capital:.2f} < ${self.min_capital_per_pair_usd:.2f} minimum")
            self.stats["insufficient_capital_events"] += 1
            return []
        
        # Aplicar buffer de segurança
        available_capital = total_capital * (1 - self.safety_buffer_percentage / 100)
        
        # Determinar número máximo de pares baseado no capital
        max_pairs_by_capital = int(available_capital / self.min_capital_per_pair_usd)
        effective_max_pairs = min(self.max_concurrent_pairs, max_pairs_by_capital, len(symbols))
        
        if effective_max_pairs == 0:
            log.warning(f"Cannot trade any pairs with available capital: ${available_capital:.2f}")
            return []
        
        # Selecionar símbolos prioritários (primeiros da lista)
        selected_symbols = symbols[:effective_max_pairs]
        
        # Calcular alocação por par
        capital_per_pair = available_capital / effective_max_pairs
        
        # Limitar alocação máxima por par
        max_capital_per_pair = total_capital * (self.max_capital_per_pair_percentage / 100)
        capital_per_pair = min(capital_per_pair, max_capital_per_pair)
        
        # Calcular alocação proporcional entre mercados se solicitado
        target_spot_capital = 0
        target_futures_capital = 0
        
        if use_proportional_allocation and balances["spot_usdt"] > 0 and balances["futures_usdt"] > 0:
            # Ambos mercados têm saldo - aplicar proporção configurada
            total_to_allocate = capital_per_pair * effective_max_pairs
            spot_percentage = self.market_allocation.get("spot_percentage", 40) / 100
            futures_percentage = self.market_allocation.get("futures_percentage", 60) / 100
            
            target_spot_capital = min(total_to_allocate * spot_percentage, balances["spot_usdt"])
            target_futures_capital = min(total_to_allocate * futures_percentage, balances["futures_usdt"])
            
            log.info(f"Proportional allocation target - Spot: ${target_spot_capital:.2f}, Futures: ${target_futures_capital:.2f}")
        
        allocations = []
        spot_allocated = 0
        futures_allocated = 0
        
        for i, symbol in enumerate(selected_symbols):
            # Determinar tipo de mercado
            if market_types and symbol in market_types:
                # Usuário especificou mercado manualmente
                market_type = market_types[symbol]
            else:
                # Decisão automática baseada em análise de mercado
                market_type = self.decide_optimal_market_for_symbol(symbol)
            
            # Se usando alocação proporcional, considerar targets
            if use_proportional_allocation and target_spot_capital > 0 and target_futures_capital > 0:
                # Verificar se devemos ajustar para cumprir proporção
                if market_type == "spot" and spot_allocated >= target_spot_capital:
                    if futures_allocated < target_futures_capital:
                        market_type = "futures"  # Mudar para futures para balancear
                elif market_type == "futures" and futures_allocated >= target_futures_capital:
                    if spot_allocated < target_spot_capital:
                        market_type = "spot"  # Mudar para spot para balancear
            
            # Verificar se há capital suficiente para este mercado
            original_market_type = market_type
            transfer_attempted = False
            
            if market_type == "spot" and balances["spot_usdt"] < capital_per_pair:
                # Tentar transferir de Futures para Spot
                if balances["futures_usdt"] >= capital_per_pair:
                    log.info(f"[{symbol}] Attempting transfer from Futures to Spot for optimal allocation")
                    if self.transfer_capital_for_optimal_allocation(capital_per_pair, 0):
                        # Atualizar saldos após transferência
                        balances = self.get_available_balances()
                        transfer_attempted = True
                    else:
                        market_type = "futures"  # Fallback para futures
                        log.info(f"[{symbol}] Transfer failed, using futures instead")
                else:
                    log.warning(f"Insufficient balance for {symbol} in both markets")
                    continue
                    
            elif market_type == "futures" and balances["futures_usdt"] < capital_per_pair:
                # Tentar transferir de Spot para Futures
                if balances["spot_usdt"] >= capital_per_pair:
                    log.info(f"[{symbol}] Attempting transfer from Spot to Futures for optimal allocation")
                    if self.transfer_capital_for_optimal_allocation(0, capital_per_pair):
                        # Atualizar saldos após transferência
                        balances = self.get_available_balances()
                        transfer_attempted = True
                    else:
                        market_type = "spot"  # Fallback para spot
                        log.info(f"[{symbol}] Transfer failed, using spot instead")
                else:
                    log.warning(f"Insufficient balance for {symbol} in both markets")
                    continue
            
            # Verificação final após possível transferência
            if market_type == "spot" and balances["spot_usdt"] < capital_per_pair:
                log.warning(f"[{symbol}] Still insufficient spot balance after transfer attempt")
                continue
            elif market_type == "futures" and balances["futures_usdt"] < capital_per_pair:
                log.warning(f"[{symbol}] Still insufficient futures balance after transfer attempt")
                continue
            
            if transfer_attempted:
                log.info(f"[{symbol}] Successfully allocated to {market_type} after transfer")
            
            # Adaptar parâmetros do grid baseado no capital
            grid_params = self._calculate_grid_parameters(capital_per_pair)
            
            allocation = CapitalAllocation(
                symbol=symbol,
                allocated_amount=capital_per_pair,
                max_position_size=grid_params["max_position_size"],
                grid_levels=grid_params["grid_levels"],
                spacing_percentage=grid_params["spacing_percentage"],
                market_type=market_type
            )
            
            allocations.append(allocation)
            
            # Atualizar saldos disponíveis e contadores
            if market_type == "spot":
                balances["spot_usdt"] -= capital_per_pair
                spot_allocated += capital_per_pair
            else:
                balances["futures_usdt"] -= capital_per_pair
                futures_allocated += capital_per_pair
        
        # Atualizar cache e estatísticas
        self.current_allocations = {alloc.symbol: alloc for alloc in allocations}
        self.stats["allocation_updates"] += 1
        
        log.info(f"Calculated {len(allocations)} capital allocations from {len(symbols)} requested symbols")
        log.info(f"Capital per pair: ${capital_per_pair:.2f}, Total allocated: ${sum(a.allocated_amount for a in allocations):.2f}")
        
        # Log distribuição entre mercados
        if allocations:
            spot_pairs = [a for a in allocations if a.market_type == "spot"]
            futures_pairs = [a for a in allocations if a.market_type == "futures"]
            
            log.info(f"Market distribution: {len(spot_pairs)} Spot pairs (${spot_allocated:.2f}), {len(futures_pairs)} Futures pairs (${futures_allocated:.2f})")
            
            if spot_allocated + futures_allocated > 0:
                spot_percentage = (spot_allocated / (spot_allocated + futures_allocated)) * 100
                futures_percentage = (futures_allocated / (spot_allocated + futures_allocated)) * 100
                log.info(f"Allocation percentage: Spot {spot_percentage:.1f}% | Futures {futures_percentage:.1f}%")
        
        return allocations
    
    def _calculate_grid_parameters(self, allocated_capital: float) -> Dict:
        """Calcula parâmetros do grid baseados no capital alocado."""
        
        # Configurações base do grid
        base_grid_levels = self.config.get("grid", {}).get("initial_levels", 10)
        base_spacing = float(self.config.get("grid", {}).get("initial_spacing_perc", "0.005"))
        
        # Adaptar número de níveis baseado no capital
        if allocated_capital < 10:
            # Capital baixo: grid mais simples
            grid_levels = max(5, base_grid_levels // 2)
            spacing_percentage = base_spacing * 1.5  # Spacing maior para menos níveis
            max_position_size = allocated_capital * 0.8  # 80% do capital
        elif allocated_capital < 50:
            # Capital médio: grid padrão
            grid_levels = base_grid_levels
            spacing_percentage = base_spacing
            max_position_size = allocated_capital * 0.7  # 70% do capital
        else:
            # Capital alto: grid mais denso
            grid_levels = min(20, base_grid_levels + 5)
            spacing_percentage = base_spacing * 0.8  # Spacing menor para mais níveis
            max_position_size = allocated_capital * 0.6  # 60% do capital
        
        return {
            "grid_levels": grid_levels,
            "spacing_percentage": spacing_percentage,
            "max_position_size": max_position_size
        }
    
    def get_allocation_for_symbol(self, symbol: str) -> Optional[CapitalAllocation]:
        """Obtém alocação de capital para um símbolo específico."""
        return self.current_allocations.get(symbol)
    
    def symbol_exists_on_market(self, symbol: str, market_type: str = "spot") -> bool:
        """Verifica se o símbolo existe no mercado (Spot ou Futures) na Binance."""
        try:
            if market_type == "spot":
                exchange_info = self.api_client.get_spot_exchange_info()
            else:
                exchange_info = self.api_client.get_exchange_info()
            if not exchange_info:
                log.error(f"Não foi possível obter exchange_info para {market_type}.")
                return False
            for item in exchange_info.get("symbols", []):
                if item["symbol"] == symbol:
                    return True
            log.warning(f"Símbolo {symbol} não encontrado no mercado {market_type}.")
            return False
        except Exception as e:
            log.error(f"Erro ao checar existência do símbolo {symbol} no mercado {market_type}: {e}")
            return False

    def can_trade_symbol(self, symbol: str, required_capital: float = None, market_type: str = "spot") -> bool:
        """Verifica se há capital suficiente e se o símbolo existe para operar."""
        if not self.symbol_exists_on_market(symbol, market_type):
            log.warning(f"Não é possível operar {symbol}: símbolo não existe no mercado {market_type}.")
            return False
        if required_capital is None:
            required_capital = self.min_capital_per_pair_usd
            
        balances = self.get_available_balances()
        total_available = balances["total_usdt"]
        
        # Considerar buffer de segurança
        available_with_buffer = total_available * (1 - self.safety_buffer_percentage / 100)
        
        return available_with_buffer >= required_capital
    
    def update_allocation_usage(self, symbol: str, used_capital: float) -> None:
        """Atualiza o uso de capital para um símbolo."""
        if symbol in self.current_allocations:
            allocation = self.current_allocations[symbol]
            remaining = allocation.allocated_amount - used_capital
            log.debug(f"[{symbol}] Capital usage: ${used_capital:.2f} / ${allocation.allocated_amount:.2f} (${remaining:.2f} remaining)")
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas do gerenciador de capital."""
        balances = self.cached_balances
        total_allocated = sum(alloc.allocated_amount for alloc in self.current_allocations.values())
        
        return {
            **self.stats,
            "current_balances": balances,
            "total_allocated_capital": total_allocated,
            "number_of_active_allocations": len(self.current_allocations),
            "capital_utilization_percentage": (total_allocated / balances.get("total_usdt", 1)) * 100 if balances.get("total_usdt", 0) > 0 else 0,
            "effective_max_pairs": min(self.max_concurrent_pairs, int(balances.get("total_usdt", 0) / self.min_capital_per_pair_usd))
        }
    
    def log_capital_status(self) -> None:
        """Log do status atual do capital."""
        stats = self.get_statistics()
        
        log.info(f"=== Capital Management Status ===")
        log.info(f"Total Balance: ${stats['current_balances'].get('total_usdt', 0):.2f}")
        log.info(f"Allocated Capital: ${stats['total_allocated_capital']:.2f}")
        log.info(f"Utilization: {stats['capital_utilization_percentage']:.1f}%")
        log.info(f"Active Pairs: {stats['number_of_active_allocations']} / {stats['effective_max_pairs']} max")
        
        if self.current_allocations:
            log.info(f"Current Allocations:")
            for symbol, alloc in self.current_allocations.items():
                log.info(f"  {symbol}: ${alloc.allocated_amount:.2f} ({alloc.market_type}, {alloc.grid_levels} levels)")
    
    def transfer_capital_for_optimal_allocation(self, required_spot: float, required_futures: float) -> bool:
        """
        Transfere capital entre mercados para otimizar alocação.
        
        Args:
            required_spot: Capital necessário em Spot
            required_futures: Capital necessário em Futures
            
        Returns:
            bool: True se transferências foram bem-sucedidas
        """
        # Primeiro, verificar e converter saldo BRL se disponível
        try:
            self.detect_and_convert_brl_balance()
        except Exception as e:
            log.warning(f"BRL conversion check failed during transfer: {e}")
        
        balances = self.get_available_balances()
        
        # Verificar se transferências são necessárias
        spot_deficit = max(0, required_spot - balances["spot_usdt"])
        futures_deficit = max(0, required_futures - balances["futures_usdt"])
        
        if spot_deficit == 0 and futures_deficit == 0:
            log.info("No transfers needed - sufficient balance in both markets")
            return True
        
        # Realizar transferências necessárias
        transfers_successful = True
        
        # Verificar se vale a pena fazer transferências (saldo mínimo para transferir)
        min_transfer_amount = 5.0  # Mínimo de $5 para transferências
        total_balance = balances["spot_usdt"] + balances["futures_usdt"]
        
        # Se o saldo total é muito baixo, evitar transferências
        if total_balance < 100.0:
            log.info(f"Total balance too low (${total_balance:.2f}) to justify transfers. Minimum required: $100. Skipping rebalancing.")
            transfers_successful = True  # Considerar como "sucesso" para não bloquear
        elif spot_deficit > min_transfer_amount and balances["futures_usdt"] >= (spot_deficit + 10):
            # Transferir de Futures para Spot (deixar pelo menos $10 em Futures)
            log.info(f"Transferring ${spot_deficit:.2f} from Futures to Spot")
            result = self.api_client.transfer_between_markets("USDT", spot_deficit, "2")  # 2 = Futures->Spot
            
            if result and result.get("status") == "CONFIRMED":
                log.info(f"✅ Transfer Futures->Spot successful: ${spot_deficit:.2f}")
            else:
                log.error(f"❌ Transfer Futures->Spot failed")
                transfers_successful = False
        
        elif futures_deficit > min_transfer_amount and balances["spot_usdt"] >= (futures_deficit + 10):
            # Transferir de Spot para Futures (deixar pelo menos $10 em Spot)
            log.info(f"Transferring ${futures_deficit:.2f} from Spot to Futures")
            result = self.api_client.transfer_between_markets("USDT", futures_deficit, "1")  # 1 = Spot->Futures
            
            if result and result.get("status") == "CONFIRMED":
                log.info(f"✅ Transfer Spot->Futures successful: ${futures_deficit:.2f}")
            else:
                log.error(f"❌ Transfer Spot->Futures failed")
                transfers_successful = False
        else:
            log.info(f"Transfer amounts too small or insufficient buffer. Spot deficit: ${spot_deficit:.2f}, Futures deficit: ${futures_deficit:.2f}")
            transfers_successful = True  # Não é um erro, apenas não necessário
        
        return transfers_successful
    
    def decide_optimal_market_for_symbol(self, symbol: str, current_market_conditions: dict = None) -> str:
        """
        Decide automaticamente qual mercado é melhor para um símbolo.
        
        Args:
            symbol: Símbolo a analisar
            current_market_conditions: Condições atuais do mercado (opcional)
            
        Returns:
            str: 'spot' ou 'futures'
        """
        try:
            # Fatores para decisão automática
            decision_factors = {
                "volatility": 0,
                "volume": 0,
                "spread": 0,
                "liquidity": 0,
                "fees": 0
            }
            
            # Analisar dados de mercado
            try:
                # Obter dados de Futures
                futures_ticker = self.api_client.get_futures_ticker(symbol)
                futures_volume = float(futures_ticker.get("volume", "0")) if futures_ticker else 0
                
                # Obter dados de Spot
                spot_ticker = self.api_client.get_spot_ticker(symbol)
                spot_volume = float(spot_ticker.get("volume", "0")) if spot_ticker else 0
                
                # Fator 1: Volume (maior volume = melhor liquidez)
                if futures_volume > spot_volume * 1.2:  # 20% maior
                    decision_factors["volume"] = 1  # Favorece futures
                elif spot_volume > futures_volume * 1.2:
                    decision_factors["volume"] = -1  # Favorece spot
                
                # Fator 2: Spread (será implementado se necessário)
                decision_factors["spread"] = 0
                
                # Fator 3: Volatilidade - Futures geralmente melhor para alta volatilidade
                # Para símbolos como BTC, ETH que são muito voláteis
                high_volatility_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
                if symbol in high_volatility_symbols:
                    decision_factors["volatility"] = 1  # Favorece futures
                
                # Fator 4: Liquidez - Futures geralmente têm mais liquidez para pares principais
                major_pairs = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "SOLUSDT"]
                if symbol in major_pairs:
                    decision_factors["liquidity"] = 1  # Favorece futures
                
                # Fator 5: Taxas - Futures podem ter taxas menores para trading frequente
                decision_factors["fees"] = 0.5  # Leve preferência por futures
                
            except Exception as e:
                log.warning(f"Error analyzing market data for {symbol}: {e}")
            
            # Calcular score total
            total_score = sum(decision_factors.values())
            
            # Decisão baseada no score
            if total_score > 0.5:
                decision = "futures"
                reason = "Higher volume/liquidity in futures market"
            elif total_score < -0.5:
                decision = "spot"
                reason = "Better conditions in spot market"
            else:
                # Fallback: usar mercado com mais capital disponível
                balances = self.get_available_balances()
                if balances["futures_usdt"] > balances["spot_usdt"]:
                    decision = "futures"
                    reason = "More capital available in futures"
                else:
                    decision = "spot"
                    reason = "More capital available in spot"
            
            log.info(f"Market decision for {symbol}: {decision} ({reason})")
            return decision
            
        except Exception as e:
            log.error(f"Error deciding market for {symbol}: {e}")
            # Fallback seguro
            balances = self.get_available_balances()
            return "futures" if balances["futures_usdt"] > balances["spot_usdt"] else "spot"


# Utility functions para integração fácil
def get_capital_manager(api_client: APIClient, config: dict) -> CapitalManager:
    """Factory function para criar CapitalManager."""
    return CapitalManager(api_client, config)


def adapt_grid_to_capital(grid_config: dict, allocated_capital: float) -> dict:
    """Adapta configuração do grid ao capital alocado."""
    manager = CapitalManager(None, {"grid": grid_config})
    params = manager._calculate_grid_parameters(allocated_capital)
    
    # Retornar configuração adaptada
    return {
        **grid_config,
        "initial_levels": params["grid_levels"],
        "initial_spacing_perc": str(params["spacing_percentage"]),
        "max_position_size_usd": params["max_position_size"]
    }


class DynamicOrderSizer:
    """
    Ajusta dinamicamente tamanhos de ordem baseado no saldo atual e limites da Binance.
    Evita erros de notional insuficiente e otimiza uso do capital.
    """
    
    def __init__(self, api_client: APIClient, config: dict):
        self.api_client = api_client
        self.config = config
        
        # Limites mínimos por mercado (valores conservadores)
        self.min_notional_limits = {
            "spot": 10.0,      # $10 USD mínimo para spot
            "futures": 5.0     # $5 USD mínimo para futures
        }
        
        # Cache de informações de símbolos para evitar múltiplas consultas
        self._symbol_info_cache = {}
        self._cache_expiry = 300  # 5 minutos
        self._last_cache_update = 0
    
    def get_optimized_order_size(self, symbol: str, market_type: str, 
                                available_balance: float, price: float,
                                target_percentage: float = 0.1) -> dict:
        """
        Calcula tamanho otimizado de ordem baseado no saldo e limites.
        
        Args:
            symbol: Par de trading (ex: BTCUSDT)
            market_type: 'spot' ou 'futures'
            available_balance: Saldo disponível em USDT
            price: Preço atual do ativo
            target_percentage: % do saldo a usar (padrão 10%)
        
        Returns:
            dict com quantidade, valor notional e se é válida
        """
        try:
            # Obter informações do símbolo
            symbol_info = self._get_symbol_info(symbol, market_type)
            if not symbol_info:
                return self._create_error_result("Symbol info not available")
            
            # Calcular tamanho base da ordem
            target_value = available_balance * target_percentage
            base_quantity = target_value / price
            
            # Aplicar limites do símbolo
            min_qty = float(symbol_info.get("minQty", 0))
            max_qty = float(symbol_info.get("maxQty", float('inf')))
            step_size = float(symbol_info.get("stepSize", 0.00001))
            min_notional = float(symbol_info.get("minNotional", 
                                               self.min_notional_limits[market_type]))
            
            # Ajustar quantidade para step size
            if step_size > 0:
                quantity = math.floor(base_quantity / step_size) * step_size
            else:
                quantity = base_quantity
            
            # Verificar limites
            quantity = max(min_qty, min(quantity, max_qty))
            notional_value = quantity * price
            
            # Verificar notional mínimo
            if notional_value < min_notional:
                # Ajustar para atingir notional mínimo
                required_qty = min_notional / price
                quantity = math.ceil(required_qty / step_size) * step_size
                notional_value = quantity * price
                
                # Verificar se ainda está dentro dos limites
                if quantity > max_qty or notional_value > available_balance:
                    return self._create_error_result(
                        f"Cannot meet min notional {min_notional} with available balance"
                    )
            
            # Verificar se o valor não excede saldo disponível
            if notional_value > available_balance:
                # Reduzir quantidade para caber no saldo
                max_affordable_qty = available_balance / price
                quantity = math.floor(max_affordable_qty / step_size) * step_size
                notional_value = quantity * price
            
            # Validação final
            is_valid = (
                quantity >= min_qty and 
                quantity <= max_qty and
                notional_value >= min_notional and
                notional_value <= available_balance
            )
            
            result = {
                "quantity": quantity,
                "notional_value": notional_value,
                "is_valid": is_valid,
                "price_used": price,
                "symbol": symbol,
                "market_type": market_type,
                "limits": {
                    "min_qty": min_qty,
                    "max_qty": max_qty,
                    "step_size": step_size,
                    "min_notional": min_notional
                }
            }
            
            if not is_valid:
                result["error"] = "Order size validation failed"
            
            log.debug(f"[{symbol}] Order size calculation: {result}")
            return result
            
        except Exception as e:
            log.error(f"Error calculating order size for {symbol}: {e}")
            return self._create_error_result(str(e))
    
    def _get_symbol_info(self, symbol: str, market_type: str) -> dict:
        """Obtém informações do símbolo com cache."""
        cache_key = f"{symbol}_{market_type}"
        current_time = time.time()
        
        # Verificar cache
        if (cache_key in self._symbol_info_cache and 
            current_time - self._last_cache_update < self._cache_expiry):
            return self._symbol_info_cache[cache_key]
        
        try:
            if market_type == "futures":
                exchange_info = self.api_client.futures_exchange_info()
            else:
                exchange_info = self.api_client.spot_exchange_info()
            
            if not exchange_info or "symbols" not in exchange_info:
                return None
            
            # Encontrar informações do símbolo
            symbol_data = None
            for sym_info in exchange_info["symbols"]:
                if sym_info["symbol"] == symbol:
                    symbol_data = sym_info
                    break
            
            if not symbol_data:
                return None
            
            # Extrair filtros relevantes
            filters = {}
            for filter_info in symbol_data.get("filters", []):
                if filter_info["filterType"] == "LOT_SIZE":
                    filters.update({
                        "minQty": filter_info["minQty"],
                        "maxQty": filter_info["maxQty"],
                        "stepSize": filter_info["stepSize"]
                    })
                elif filter_info["filterType"] == "MIN_NOTIONAL":
                    filters["minNotional"] = filter_info["minNotional"]
                elif filter_info["filterType"] == "NOTIONAL":
                    filters["minNotional"] = filter_info.get("minNotional", 
                                                           filters.get("minNotional"))
            
            # Cache resultado
            self._symbol_info_cache[cache_key] = filters
            self._last_cache_update = current_time
            
            return filters
            
        except Exception as e:
            log.error(f"Error fetching symbol info for {symbol}: {e}")
            return None
    
    def _create_error_result(self, error_msg: str) -> dict:
        """Cria resultado de erro padronizado."""
        return {
            "quantity": 0,
            "notional_value": 0,
            "is_valid": False,
            "error": error_msg
        }
    
    def adjust_grid_quantities_to_balance(self, symbol: str, market_type: str,
                                        grid_levels: int, total_allocation: float,
                                        current_price: float) -> List[dict]:
        """
        Ajusta quantidades do grid para se adequar ao saldo disponível.
        
        Returns:
            Lista de ordens com quantidades ajustadas
        """
        try:
            # Dividir alocação total entre níveis do grid
            allocation_per_level = total_allocation / grid_levels
            
            orders = []
            for i in range(grid_levels):
                # Calcular preço do nível (simplificado)
                level_price = current_price * (1 + (i - grid_levels/2) * 0.005)
                
                # Calcular tamanho otimizado para este nível
                order_info = self.get_optimized_order_size(
                    symbol, market_type, allocation_per_level, level_price
                )
                
                if order_info["is_valid"]:
                    orders.append({
                        "level": i,
                        "price": level_price,
                        "quantity": order_info["quantity"],
                        "side": "buy" if i < grid_levels/2 else "sell",
                        "notional": order_info["notional_value"]
                    })
                else:
                    log.warning(f"[{symbol}] Invalid order for level {i}: {order_info.get('error')}")
            
            return orders
            
        except Exception as e:
            log.error(f"Error adjusting grid quantities for {symbol}: {e}")
            return []