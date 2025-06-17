#!/usr/bin/env python3
"""
Script para testar TP/SL com posições reais existentes
"""
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.global_tp_sl_manager import GlobalTPSLManager, get_global_tpsl_manager
from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

log = setup_logger("test_tpsl_positions")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def test_tp_sl_with_real_positions():
    """Testa TP/SL com posições reais"""
    try:
        log.info("🧪 Testando TP/SL com posições reais...")
        
        config = load_config()
        api_client = APIClient(config)
        
        # Primeiro verificar posições existentes
        log.info("📊 Verificando posições existentes...")
        positions = api_client.get_futures_positions()
        
        active_positions = []
        for position in positions:
            position_amt = float(position.get("positionAmt", 0))
            if position_amt != 0:
                symbol = position.get("symbol", "")
                entry_price = position.get("entryPrice", "0")
                unrealized_pnl = position.get("unrealizedPnl", "0")
                
                active_positions.append({
                    "symbol": symbol,
                    "size": position_amt,
                    "entry": entry_price,
                    "pnl": unrealized_pnl
                })
                
                side = "LONG" if position_amt > 0 else "SHORT"
                log.info(f"📈 {symbol}: {side} {abs(position_amt):.6f} @ ${entry_price} | PnL: ${unrealized_pnl}")
        
        if not active_positions:
            log.warning("⚠️ Nenhuma posição ativa encontrada - teste limitado")
            return True
        
        log.info(f"🎯 Encontradas {len(active_positions)} posições ativas")
        
        # Criar e iniciar Global TP/SL Manager
        log.info("🚀 Iniciando Global TP/SL Manager...")
        manager = get_global_tpsl_manager(api_client, config)
        
        if not manager:
            log.error("❌ Falha ao criar manager")
            return False
        
        # Iniciar monitoramento (deve detectar posições existentes)
        success = GlobalTPSLManager.start_monitoring()
        if not success:
            log.error("❌ Falha ao iniciar monitoramento")
            return False
        
        # Verificar se posições foram detectadas
        status = GlobalTPSLManager.get_status()
        log.info(f"📊 Status após detecção: {status}")
        
        if status['active_positions'] > 0:
            log.info(f"✅ {status['active_positions']} posições detectadas e adicionadas ao TP/SL")
            
            for i, pos_id in enumerate(status['positions']):
                log.info(f"  {i+1}. Posição monitorada: {pos_id}")
        else:
            log.warning("⚠️ Nenhuma posição foi detectada pelo TP/SL")
            log.info("💡 Possíveis motivos:")
            log.info("   - Posições não atendem aos critérios mínimos")
            log.info("   - Erro na detecção automática")
        
        # Aguardar alguns ciclos para ver logs de monitoramento
        log.info("⏱️ Aguardando 15 segundos para verificar monitoramento...")
        import time
        time.sleep(15)
        
        # Verificar status final
        final_status = GlobalTPSLManager.get_status()
        log.info(f"📊 Status final: {final_status}")
        
        # Parar
        GlobalTPSLManager.stop_monitoring()
        log.info("🛑 Monitoramento parado")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Erro no teste: {e}")
        return False

if __name__ == "__main__":
    log.info("🔬 Teste TP/SL com Posições Reais")
    log.info("=" * 50)
    
    success = test_tp_sl_with_real_positions()
    
    if success:
        log.info("\n✅ TESTE CONCLUÍDO!")
        log.info("💡 Agora o TP/SL deve monitorar TODAS as posições com logs visíveis")
    else:
        log.error("\n❌ TESTE FALHOU!")
    
    log.info("\n✅ Finalizado!")