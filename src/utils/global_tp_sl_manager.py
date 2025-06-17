#!/usr/bin/env python3
"""
Global TP/SL Manager Singleton
Evita múltiplas instâncias do AggressiveTPSLManager
"""

import threading
from typing import Optional, Dict
from .aggressive_tp_sl import AggressiveTPSLManager
from .logger import setup_logger

log = setup_logger("global_tp_sl")

class GlobalTPSLManager:
    """Singleton para gerenciar uma única instância do AggressiveTPSLManager."""
    
    _instance: Optional[AggressiveTPSLManager] = None
    _lock = threading.Lock()
    _initialized = False
    
    @classmethod
    def get_instance(cls, api_client=None, config: Dict = None) -> Optional[AggressiveTPSLManager]:
        """
        Retorna a instância singleton do AggressiveTPSLManager.
        
        Args:
            api_client: Cliente da API (necessário apenas na primeira chamada)
            config: Configuração (necessária apenas na primeira chamada)
            
        Returns:
            Instância do AggressiveTPSLManager ou None se não inicializado
        """
        with cls._lock:
            if cls._instance is None and api_client and config:
                try:
                    cls._instance = AggressiveTPSLManager(api_client, config)
                    cls._initialized = True
                    log.info("🎯 Global TP/SL Manager criado (singleton)")
                except Exception as e:
                    log.error(f"Erro ao criar Global TP/SL Manager: {e}")
                    return None
            
            return cls._instance
    
    @classmethod
    def start_monitoring(cls) -> bool:
        """Inicia o monitoramento TP/SL se não estiver rodando."""
        with cls._lock:
            if cls._instance and not cls._instance.running:
                try:
                    cls._instance.start_monitoring()
                    log.info("🚀 Global TP/SL Manager iniciado")
                    return True
                except Exception as e:
                    log.error(f"Erro ao iniciar Global TP/SL Manager: {e}")
                    return False
            elif cls._instance and cls._instance.running:
                log.debug("Global TP/SL Manager já está rodando")
                return True
            else:
                log.warning("Global TP/SL Manager não foi inicializado")
                return False
    
    @classmethod
    def stop_monitoring(cls) -> bool:
        """Para o monitoramento TP/SL."""
        with cls._lock:
            if cls._instance and cls._instance.running:
                try:
                    cls._instance.stop_monitoring()
                    log.info("🛑 Global TP/SL Manager parado")
                    return True
                except Exception as e:
                    log.error(f"Erro ao parar Global TP/SL Manager: {e}")
                    return False
            else:
                log.debug("Global TP/SL Manager não estava rodando")
                return True
    
    @classmethod
    def add_position(cls, symbol: str, position_side: str, entry_price, quantity) -> Optional[str]:
        """Adiciona uma posição ao monitoramento TP/SL."""
        if cls._instance:
            try:
                position_id = cls._instance.add_position(symbol, position_side, entry_price, quantity)
                log.debug(f"Posição adicionada ao Global TP/SL: {symbol} {position_side}")
                return position_id
            except Exception as e:
                log.error(f"Erro ao adicionar posição ao Global TP/SL: {e}")
        else:
            log.warning("Global TP/SL Manager não inicializado - não é possível adicionar posição")
        return None
    
    @classmethod
    def remove_position(cls, position_id: str) -> bool:
        """Remove uma posição do monitoramento TP/SL."""
        if cls._instance:
            try:
                cls._instance.remove_position(position_id)
                log.debug(f"Posição removida do Global TP/SL: {position_id}")
                return True
            except Exception as e:
                log.error(f"Erro ao remover posição do Global TP/SL: {e}")
        else:
            log.warning("Global TP/SL Manager não inicializado - não é possível remover posição")
        return False
    
    @classmethod
    def get_status(cls) -> Dict:
        """Retorna status do Global TP/SL Manager."""
        with cls._lock:
            if cls._instance:
                return {
                    "initialized": cls._initialized,
                    "running": cls._instance.running,
                    "active_positions": len(cls._instance.active_orders),
                    "positions": list(cls._instance.active_orders.keys())
                }
            else:
                return {
                    "initialized": False,
                    "running": False,
                    "active_positions": 0,
                    "positions": []
                }
    
    @classmethod
    def reset(cls):
        """Reset da instância (usado para testes ou reinicialização)."""
        with cls._lock:
            if cls._instance:
                try:
                    cls._instance.stop_monitoring()
                except:
                    pass
            cls._instance = None
            cls._initialized = False
            log.info("🔄 Global TP/SL Manager resetado")

# Convenience functions para uso fácil
def get_global_tpsl_manager(api_client=None, config=None):
    """Função de conveniência para obter a instância global."""
    return GlobalTPSLManager.get_instance(api_client, config)

def start_global_tpsl():
    """Função de conveniência para iniciar monitoramento global."""
    return GlobalTPSLManager.start_monitoring()

def stop_global_tpsl():
    """Função de conveniência para parar monitoramento global."""
    return GlobalTPSLManager.stop_monitoring()

def add_position_to_global_tpsl(symbol, position_side, entry_price, quantity):
    """Função de conveniência para adicionar posição."""
    return GlobalTPSLManager.add_position(symbol, position_side, entry_price, quantity)

def remove_position_from_global_tpsl(position_id):
    """Função de conveniência para remover posição."""
    return GlobalTPSLManager.remove_position(position_id)