#!/usr/bin/env python3
"""
Script para testar o novo Global TP/SL Manager
"""
import sys
import os
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.global_tp_sl_manager import GlobalTPSLManager, get_global_tpsl_manager
from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

log = setup_logger("test_global_tpsl")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def test_global_tp_sl():
    """Testa o Global TP/SL Manager"""
    try:
        log.info("🧪 Testando Global TP/SL Manager...")
        
        config = load_config()
        api_client = APIClient(config)
        
        # Test 1: Criar instância singleton
        log.info("Test 1: Criando primeira instância...")
        manager1 = get_global_tpsl_manager(api_client, config)
        
        # Test 2: Tentar criar segunda instância (deve retornar a mesma)
        log.info("Test 2: Criando segunda instância (deve ser a mesma)...")
        manager2 = get_global_tpsl_manager()
        
        if manager1 is manager2:
            log.info("✅ Singleton funcionando - mesma instância retornada")
        else:
            log.error("❌ Singleton falhou - instâncias diferentes")
            return False
        
        # Test 3: Verificar status inicial
        log.info("Test 3: Verificando status inicial...")
        status = GlobalTPSLManager.get_status()
        log.info(f"Status: {status}")
        
        # Test 4: Iniciar monitoramento
        log.info("Test 4: Iniciando monitoramento...")
        success = GlobalTPSLManager.start_monitoring()
        if success:
            log.info("✅ Monitoramento iniciado com sucesso")
        else:
            log.error("❌ Falha ao iniciar monitoramento")
            return False
        
        # Test 5: Verificar status após iniciar
        log.info("Test 5: Verificando status após iniciar...")
        status = GlobalTPSLManager.get_status()
        log.info(f"Status: {status}")
        
        # Test 6: Verificar posições existentes detectadas
        if status['active_positions'] > 0:
            log.info(f"✅ Detectadas {status['active_positions']} posições existentes")
            for pos_id in status['positions']:
                log.info(f"  📈 Posição monitorada: {pos_id}")
        else:
            log.info("ℹ️ Nenhuma posição existente detectada (normal se conta vazia)")
        
        # Test 7: Aguardar alguns ciclos de monitoramento
        log.info("Test 7: Aguardando 10 segundos para verificar logs de monitoramento...")
        time.sleep(10)
        
        # Test 8: Verificar status final
        log.info("Test 8: Status final...")
        final_status = GlobalTPSLManager.get_status()
        log.info(f"Status final: {final_status}")
        
        # Test 9: Parar monitoramento
        log.info("Test 9: Parando monitoramento...")
        stop_success = GlobalTPSLManager.stop_monitoring()
        if stop_success:
            log.info("✅ Monitoramento parado com sucesso")
        else:
            log.error("❌ Falha ao parar monitoramento")
        
        log.info("🎉 Todos os testes concluídos com sucesso!")
        return True
        
    except Exception as e:
        log.error(f"❌ Erro no teste: {e}")
        return False

if __name__ == "__main__":
    log.info("🔬 Teste do Global TP/SL Manager")
    log.info("=" * 50)
    
    success = test_global_tp_sl()
    
    if success:
        log.info("\n✅ TODOS OS TESTES PASSARAM!")
        log.info("💡 O Global TP/SL Manager está funcionando corretamente")
        log.info("🚀 Agora todas as posições serão monitoradas por uma única instância")
    else:
        log.error("\n❌ ALGUNS TESTES FALHARAM!")
        log.error("🔧 Verifique os logs acima para identificar problemas")
    
    log.info("\n✅ Teste concluído!")