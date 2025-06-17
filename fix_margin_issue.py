#!/usr/bin/env python3
"""
Script para diagnosticar e sugerir soluções para problema de margem insuficiente
"""
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

log = setup_logger("margin_fix")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def analyze_and_suggest_fixes():
    """Analisa a situação e sugere soluções"""
    try:
        config = load_config()
        api_client = APIClient(config)
        
        log.info("🔍 Analisando situação da conta...")
        
        # 1. Verificar saldos
        spot_balance = api_client.get_spot_account_balance()
        futures_balance = api_client.get_futures_account_balance()
        
        spot_usdt = 0
        futures_usdt = 0
        
        # Spot USDT
        if spot_balance:
            for asset in spot_balance:
                if asset.get("asset") == "USDT":
                    spot_usdt = float(asset.get("free", "0"))
                    break
        
        # Futures USDT
        if futures_balance:
            for asset in futures_balance:
                if asset.get("asset") == "USDT":
                    futures_usdt = float(asset.get("availableBalance", "0"))
                    break
        
        log.info(f"💰 Saldo Spot USDT: ${spot_usdt:.2f}")
        log.info(f"💰 Saldo Futures USDT: ${futures_usdt:.2f}")
        
        # 2. Verificar posições abertas
        positions = api_client.get_futures_positions()
        active_positions = []
        total_unrealized_pnl = 0
        
        for position in positions:
            position_amt = float(position.get("positionAmt", 0))
            if position_amt != 0:
                symbol = position.get("symbol", "")
                entry_price = float(position.get("entryPrice", "0"))
                unrealized_pnl = float(position.get("unrealizedPnl", "0"))
                total_unrealized_pnl += unrealized_pnl
                
                active_positions.append({
                    "symbol": symbol,
                    "size": position_amt,
                    "entry": entry_price,
                    "pnl": unrealized_pnl
                })
        
        log.info(f"📊 Posições ativas: {len(active_positions)}")
        log.info(f"💹 PnL total não realizado: ${total_unrealized_pnl:.2f}")
        
        # 3. Análise e sugestões
        log.info("\n" + "="*60)
        log.info("📋 ANÁLISE E SOLUÇÕES SUGERIDAS:")
        log.info("="*60)
        
        if futures_usdt < 1.0:
            log.error("🚨 PROBLEMA: Margem insuficiente na conta Futures")
            
            if spot_usdt > 10:
                log.info("✅ SOLUÇÃO 1 (RECOMENDADA): Transferir USDT do Spot para Futures")
                log.info(f"   💰 Você tem ${spot_usdt:.2f} em Spot")
                log.info("   📋 Passos:")
                log.info("   1. Acesse Binance Web/App")
                log.info("   2. Vá em Carteira > Transferir")
                log.info("   3. Spot → Futures")
                log.info(f"   4. Transfira pelo menos $20 USDT")
                log.info("   5. Aguarde alguns minutos e reinicie o bot")
                
            if len(active_positions) > 5:
                log.info("✅ SOLUÇÃO 2: Fechar algumas posições para liberar margem")
                log.info("   📋 Posições que podem ser fechadas:")
                
                # Sugerir posições com menor PnL para fechar
                sorted_positions = sorted(active_positions, key=lambda x: x["pnl"])
                for i, pos in enumerate(sorted_positions[:3]):
                    side = "LONG" if pos["size"] > 0 else "SHORT"
                    close_side = "SELL" if pos["size"] > 0 else "BUY"
                    
                    log.info(f"   {i+1}. {pos['symbol']}: {side} (PnL: ${pos['pnl']:.2f})")
                    log.info(f"      Comando: Ordem MARKET {close_side} para fechar posição")
            
            if spot_usdt < 10 and len(active_positions) < 3:
                log.error("❌ SOLUÇÃO 3: Adicionar mais USDT à conta")
                log.error("   💳 Você precisa depositar mais USDT")
                log.error("   📋 Opções:")
                log.error("   1. Depósito via PIX (Brasil)")
                log.error("   2. Transferência bancária")
                log.error("   3. Compra com cartão de crédito")
                log.error("   4. P2P Trading")
        
        else:
            log.info("✅ Margem adequada para continuar trading")
        
        # 4. Verificar configuração do bot
        log.info("\n📋 CONFIGURAÇÃO DO BOT:")
        trading_config = config.get("trading", {})
        capital_per_pair = trading_config.get("capital_per_pair_usd", 20)
        balance_threshold = trading_config.get("balance_threshold_usd", 50)
        max_pairs = trading_config.get("max_concurrent_pairs", 10)
        
        log.info(f"   💰 Capital por par: ${capital_per_pair}")
        log.info(f"   📊 Threshold mínimo: ${balance_threshold}")
        log.info(f"   🔢 Máximo de pares: {max_pairs}")
        
        total_needed = (len(active_positions) * capital_per_pair) + balance_threshold
        log.info(f"   🎯 Capital necessário total: ${total_needed:.2f}")
        
        if futures_usdt + spot_usdt < total_needed:
            deficit = total_needed - (futures_usdt + spot_usdt)
            log.warning(f"   ⚠️ Déficit: ${deficit:.2f} USDT")
        
        # 5. Próximos passos
        log.info("\n🎯 PRÓXIMOS PASSOS RECOMENDADOS:")
        if futures_usdt < 5:
            log.info("1. 🔄 Transferir USDT para Futures (URGENTE)")
            log.info("2. 🔄 Executar: python simple_balance_check.py")
            log.info("3. 🔄 Reiniciar o sistema: ./start_multi_agent_bot.sh")
        else:
            log.info("1. ✅ Sistema pode continuar operando")
            log.info("2. 📊 Monitorar saldo regularmente")
        
        return {
            "spot_usdt": spot_usdt,
            "futures_usdt": futures_usdt,
            "positions": len(active_positions),
            "total_pnl": total_unrealized_pnl,
            "action_needed": futures_usdt < 5
        }
        
    except Exception as e:
        log.error(f"Erro na análise: {e}")
        return None

if __name__ == "__main__":
    log.info("🩺 Diagnóstico de Margem - Análise e Soluções")
    log.info("=" * 60)
    
    result = analyze_and_suggest_fixes()
    
    if result and result["action_needed"]:
        log.info("\n🚨 AÇÃO IMEDIATA NECESSÁRIA!")
        log.info("💡 Execute as soluções sugeridas acima")
    elif result:
        log.info("\n✅ Sistema operacional!")
    
    log.info("\n✅ Diagnóstico concluído!")