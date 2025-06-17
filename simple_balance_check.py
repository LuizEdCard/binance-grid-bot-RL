#!/usr/bin/env python3
"""
Script simples para verificar saldo da conta
"""
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

log = setup_logger("balance_check")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_simple_balance():
    """Verificação simples de saldo"""
    try:
        config = load_config()
        api_client = APIClient(config)
        
        log.info("🔍 Verificando saldo FUTURES...")
        
        # Obter saldo futures
        futures_balance = api_client.get_futures_balance()
        
        if not futures_balance:
            log.error("❌ Não foi possível obter saldo futures")
            return
        
        for asset in futures_balance:
            if asset.get("asset") == "USDT":
                available = float(asset.get("availableBalance", "0"))
                wallet = float(asset.get("walletBalance", "0"))
                
                log.info(f"💰 USDT Disponível: ${available:.2f}")
                log.info(f"💰 USDT Carteira: ${wallet:.2f}")
                
                if available < 10:
                    log.error("🚨 MARGEM INSUFICIENTE! Necessário transferir USDT para conta Futures")
                    log.error("📋 Solução: Binance Web > Carteira > Transferir > Spot para Futures")
                else:
                    log.info("✅ Saldo suficiente para trading")
                
                break
        
        # Verificar posições abertas
        log.info("📊 Verificando posições abertas...")
        positions = api_client.get_futures_positions()
        
        active_positions = 0
        for position in positions:
            position_amt = float(position.get("positionAmt", 0))
            if position_amt != 0:
                active_positions += 1
                symbol = position.get("symbol", "")
                entry_price = position.get("entryPrice", "0")
                unrealized_pnl = position.get("unrealizedPnl", "0")
                
                side = "LONG" if position_amt > 0 else "SHORT"
                log.info(f"📈 {symbol}: {side} {abs(position_amt):.6f} @ ${entry_price} | PnL: ${unrealized_pnl}")
        
        if active_positions == 0:
            log.info("📭 Nenhuma posição aberta")
        else:
            log.info(f"📊 Total de posições ativas: {active_positions}")
        
    except Exception as e:
        log.error(f"Erro: {e}")

if __name__ == "__main__":
    check_simple_balance()