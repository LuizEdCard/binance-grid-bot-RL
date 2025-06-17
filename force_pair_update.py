#\!/usr/bin/env python3
import os
import sys
import yaml
from dotenv import load_dotenv

SRC_DIR = os.path.join(os.path.dirname(__file__), 'src')
sys.path.append(SRC_DIR)

from core.pair_selector import PairSelector
from utils.api_client import APIClient
from utils.logger import setup_logger

log = setup_logger("force_pair_update")

def main():
    ROOT_DIR = os.path.dirname(__file__)
    ENV_PATH = os.path.join(ROOT_DIR, "secrets", ".env")
    CONFIG_PATH = os.path.join(SRC_DIR, "config", "config.yaml")
    
    load_dotenv(dotenv_path=ENV_PATH)
    
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)
    
    api_client = APIClient(config)
    pair_selector = PairSelector(config, api_client)
    
    cache_file = os.path.join(ROOT_DIR, "data", "pair_selection_cache.json")
    if os.path.exists(cache_file):
        os.remove(cache_file)
        log.info(f"Cache removido: {cache_file}")
    
    log.info("Forçando atualização da seleção de pares...")
    
    try:
        from core.capital_management import CapitalManager
        capital_manager = CapitalManager(api_client, config)
        balances = capital_manager.get_available_balances()
        log.info(f"Saldo disponível: ${balances['total_usdt']:.2f} USDT")
        
    except Exception as e:
        log.error(f"Erro verificando saldo: {e}")
    
    try:
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        log.info(f"Novos pares selecionados: {selected_pairs}")
        
        preferred = config["pair_selection"]["futures_pairs"]["preferred_symbols"]
        log.info(f"Pares preferidos configurados: {preferred}")
        
        new_pairs = [p for p in selected_pairs if p not in preferred]
        if new_pairs:
            log.info(f"Novos pares descobertos: {new_pairs}")
        else:
            log.info("Nenhum par novo encontrado - usando preferidos")
            
    except Exception as e:
        log.error(f"Erro na seleção de pares: {e}")
        return False
    
    log.info("Atualização de pares concluída!")
    return True

if __name__ == "__main__":
    main()
