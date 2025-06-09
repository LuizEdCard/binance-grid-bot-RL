# test_grid_recovery.py
import os
import sys
sys.path.append('../src')
from utils.api_client import APIClient
from core.grid_logic import GridLogic
import yaml

def test_grid_recovery():
    # Carregar configuração
    with open("../src/config/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    # Inicializar cliente API
    api_client = APIClient(config["api"], operation_mode="production")

    # Criar instância do GridLogic
    grid = GridLogic(
        symbol="ADAUSDT",
        config=config,
        api_client=api_client,
        operation_mode="production",
        market_type="futures"
    )

    # Tentar recuperar grid
    print("\n🔍 Tentando recuperar grid...")
    success = grid.recover_active_grid()
    
    if success:
        print("✅ Grid recuperado com sucesso!")
        print(f"Níveis ativos: {len(grid.grid_levels)}")
        print(f"Ordens ativas: {len(grid.active_grid_orders)}")
        print(f"Mercado: {grid.market_type}")
        
        # Mostrar detalhes do grid
        for level in grid.grid_levels:
            print(f"Nível: {level['type']} @ {level['price']}")
    else:
        print("❌ Falha ao recuperar grid")

if __name__ == "__main__":
    test_grid_recovery()

