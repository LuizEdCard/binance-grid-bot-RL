#!/usr/bin/env python3
"""
Script para verificar saldo da conta e diagnosticar problemas de margem
"""
import sys
import os
import time
from decimal import Decimal

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
from core.capital_management import CapitalManager
import yaml

log = setup_logger("check_balance")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_balances():
    """Verifica saldos completos da conta"""
    try:
        config = load_config()
        api_client = APIClient(config)
        capital_manager = CapitalManager(config, api_client)
        
        log.info("🔍 Verificando saldos da conta...")
        
        # 1. Saldo Spot
        log.info("\n📊 SALDO SPOT:")
        spot_balance = api_client.get_balance()
        total_spot_usdt = 0
        
        if spot_balance:
            for asset in spot_balance:
                if asset.get("asset") == "USDT":
                    free = float(asset.get("free", "0"))
                    locked = float(asset.get("locked", "0"))
                    total = free + locked
                    total_spot_usdt = total
                    
                    log.info(f"  USDT: Livre ${free:.2f}, Bloqueado ${locked:.2f}, Total ${total:.2f}")
                    break
        else:
            log.warning("  ❌ Não foi possível obter saldo spot")
        
        # 2. Saldo Futures
        log.info("\n💰 SALDO FUTURES:")
        futures_balance = api_client.get_futures_balance()
        total_futures_usdt = 0
        
        if futures_balance:
            for asset in futures_balance:
                if asset.get("asset") == "USDT":
                    available = float(asset.get("availableBalance", "0"))
                    wallet = float(asset.get("walletBalance", "0"))
                    unrealized_pnl = float(asset.get("unrealizedPnl", "0"))
                    total_futures_usdt = available
                    
                    log.info(f"  USDT Disponível: ${available:.2f}")
                    log.info(f"  USDT Carteira: ${wallet:.2f}")
                    log.info(f"  PnL Não Realizado: ${unrealized_pnl:.2f}")
                    break
        else:
            log.warning("  ❌ Não foi possível obter saldo futures")
        
        # 3. Informações da conta futures
        log.info("\n📈 INFORMAÇÕES DA CONTA FUTURES:")
        try:
            account_info = api_client.get_futures_account()
            if account_info:
                total_wallet_balance = float(account_info.get("totalWalletBalance", "0"))
                total_unrealized_pnl = float(account_info.get("totalUnrealizedPnl", "0"))
                total_margin_balance = float(account_info.get("totalMarginBalance", "0"))
                total_initial_margin = float(account_info.get("totalInitialMargin", "0"))
                total_maint_margin = float(account_info.get("totalMaintMargin", "0"))
                available_balance = float(account_info.get("availableBalance", "0"))
                max_withdraw_amount = float(account_info.get("maxWithdrawAmount", "0"))
                
                log.info(f"  Total Carteira: ${total_wallet_balance:.2f}")
                log.info(f"  Total Margem: ${total_margin_balance:.2f}")
                log.info(f"  Margem Inicial: ${total_initial_margin:.2f}")
                log.info(f"  Margem Manutenção: ${total_maint_margin:.2f}")
                log.info(f"  Disponível para Trade: ${available_balance:.2f}")
                log.info(f"  Máximo Saque: ${max_withdraw_amount:.2f}")
                
                # Verificar se há margem suficiente
                if available_balance < 10:
                    log.error(f"  ⚠️ MARGEM INSUFICIENTE: Apenas ${available_balance:.2f} disponível")
                    log.error(f"  💡 Necessário pelo menos $10 para trading")
                else:
                    log.info(f"  ✅ Margem suficiente para trading")
                    
        except Exception as e:
            log.error(f"Erro ao obter informações da conta futures: {e}")
        
        # 4. Posições abertas
        log.info("\n📊 POSIÇÕES ABERTAS:")
        try:
            positions = api_client.get_futures_positions()
            active_positions = []
            
            for position in positions:
                position_amt = float(position.get("positionAmt", 0))
                if position_amt != 0:
                    symbol = position.get("symbol", "")
                    entry_price = position.get("entryPrice", "0")
                    unrealized_pnl = position.get("unrealizedPnl", "0")
                    margin = position.get("initialMargin", "0")
                    
                    active_positions.append({
                        "symbol": symbol,
                        "size": position_amt,
                        "entry": entry_price,
                        "pnl": unrealized_pnl,
                        "margin": margin
                    })
                    
                    side = "LONG" if position_amt > 0 else "SHORT"
                    log.info(f"  {symbol}: {side} {abs(position_amt):.6f} @ ${entry_price} | "
                            f"PnL: ${unrealized_pnl} | Margem: ${margin}")
            
            if not active_positions:
                log.info("  📭 Nenhuma posição aberta")
            else:
                total_margin_used = sum(float(pos["margin"]) for pos in active_positions)
                log.info(f"  📊 Total posições: {len(active_positions)}")
                log.info(f"  💰 Margem total usada: ${total_margin_used:.2f}")
                
        except Exception as e:
            log.error(f"Erro ao obter posições: {e}")
        
        # 5. Usar capital manager para análise
        log.info("\n🧮 ANÁLISE DE CAPITAL MANAGER:")
        try:
            balances = capital_manager.get_available_balances()
            log.info(f"  Capital Manager - Spot: ${balances.get('spot_usdt', 0):.2f}")
            log.info(f"  Capital Manager - Futures: ${balances.get('futures_usdt', 0):.2f}")
            log.info(f"  Capital Manager - Total: ${balances.get('total_usdt', 0):.2f}")
            
            # Verificar configurações de capital
            trading_config = config.get("trading", {})
            capital_per_pair = trading_config.get("capital_per_pair_usd", 20)
            balance_threshold = trading_config.get("balance_threshold_usd", 50)
            max_pairs = trading_config.get("max_concurrent_pairs", 10)
            
            log.info(f"  Configuração - Capital por par: ${capital_per_pair}")
            log.info(f"  Configuração - Threshold mínimo: ${balance_threshold}")
            log.info(f"  Configuração - Máximo de pares: {max_pairs}")
            
            # Calcular quantos pares podemos operar
            total_available = balances.get('total_usdt', 0)
            if total_available > balance_threshold:
                max_pairs_affordable = int((total_available - balance_threshold) / capital_per_pair)
                log.info(f"  ✅ Pares que podemos operar: {min(max_pairs_affordable, max_pairs)}")
            else:
                log.error(f"  ❌ Saldo insuficiente: ${total_available:.2f} < ${balance_threshold} threshold")
                
        except Exception as e:
            log.error(f"Erro no capital manager: {e}")
        
        # 6. Recomendações
        log.info("\n💡 RECOMENDAÇÕES:")
        if total_futures_usdt < 10:
            log.error("  🚨 AÇÃO NECESSÁRIA: Transferir USDT para conta Futures")
            log.error("  📋 Comandos sugeridos:")
            log.error("     1. Na Binance Web: Carteira > Transferir > Spot para Futures")
            log.error("     2. Ou parar o bot até ter saldo suficiente")
        elif total_futures_usdt < 50:
            log.warning("  ⚠️ Saldo baixo: Considere adicionar mais USDT para trading efetivo")
        else:
            log.info("  ✅ Saldo adequado para trading")
            
        return {
            "spot_usdt": total_spot_usdt,
            "futures_usdt": total_futures_usdt,
            "total_usdt": total_spot_usdt + total_futures_usdt,
            "positions": len(active_positions) if 'active_positions' in locals() else 0,
            "sufficient_balance": total_futures_usdt >= 10
        }
        
    except Exception as e:
        log.error(f"Erro geral na verificação de saldo: {e}")
        return None

if __name__ == "__main__":
    log.info("💰 Verificação Completa de Saldo - Diagnóstico de Margem")
    log.info("=" * 60)
    
    result = check_balances()
    
    if result:
        log.info("\n" + "=" * 60)
        log.info("📋 RESUMO:")
        log.info(f"  💰 Total disponível: ${result['total_usdt']:.2f}")
        log.info(f"  📈 Futures: ${result['futures_usdt']:.2f}")
        log.info(f"  📊 Posições: {result['positions']}")
        log.info(f"  ✅ Pode operar: {'Sim' if result['sufficient_balance'] else 'Não'}")
    
    log.info("\n✅ Verificação concluída!")