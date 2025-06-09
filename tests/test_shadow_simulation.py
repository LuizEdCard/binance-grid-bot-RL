#!/usr/bin/env python3
"""
Script para testar o sistema Shadow simulando dados localmente, 
sem precisar de conexão com API Binance.
"""

import sys
import os
import numpy as np
import time

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.data_storage import shadow_storage
from core.grid_logic import GridLogic
from utils.api_client import APIClient

class MockAPIClient:
    """Mock do APIClient para testes sem API real."""
    
    def __init__(self, operation_mode="shadow"):
        self.operation_mode = operation_mode
        
    def get_spot_exchange_info(self):
        """Retorna informações fake de exchange."""
        return {
            "symbols": [{
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "baseAssetPrecision": 8,
                "quoteAssetPrecision": 8,
                "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01000000", "minPrice": "0.01000000", "maxPrice": "1000000.00000000"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.00001000", "minQty": "0.00001000", "maxQty": "1000.00000000"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"}
                ]
            }]
        }
        
    def get_spot_ticker(self, symbol=None):
        """Retorna ticker fake."""
        return {"symbol": "BTCUSDT", "price": "45000.00"}
        
    def get_spot_klines(self, symbol, interval, limit=100):
        """Retorna klines fake."""
        # Gerar dados fake de preços
        base_price = 45000
        klines = []
        for i in range(limit):
            price = base_price + np.random.uniform(-1000, 1000)
            kline = [
                int(time.time() * 1000) - (limit - i) * 60000,  # Open time
                f"{price:.2f}",  # Open
                f"{price + 100:.2f}",  # High  
                f"{price - 100:.2f}",  # Low
                f"{price + np.random.uniform(-50, 50):.2f}",  # Close
                "100.0",  # Volume
                int(time.time() * 1000) - (limit - i) * 60000 + 59999,  # Close time
                "4500000.0",  # Quote asset volume
                50,  # Number of trades
                "50.0",  # Taker buy base asset volume
                "2250000.0",  # Taker buy quote asset volume
                "0"  # Ignore
            ]
            klines.append(kline)
        return klines
        
    def place_spot_order(self, **kwargs):
        """Simula colocação de ordem."""
        return {
            "orderId": int(time.time() * 1000),
            "symbol": kwargs.get("symbol"),
            "status": "NEW",
            "type": kwargs.get("type"),
            "side": kwargs.get("side"),
            "price": kwargs.get("price"),
            "origQty": kwargs.get("quantity"),
            "time": int(time.time() * 1000)
        }

def test_shadow_data_simulation():
    """Testa coleta de dados simulando operação local."""
    print("🧪 TESTE DE SIMULAÇÃO DE DADOS SHADOW")
    print("=" * 50)
    
    # Limpar dados anteriores
    print("🧹 Limpando dados anteriores...")
    for file in ["shadow_trades.jsonl", "market_states.jsonl", "rl_actions.jsonl"]:
        filepath = os.path.join("data", file)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"   Removido: {file}")
    
    # Criar mock API client
    print("🔧 Criando cliente API simulado...")
    mock_client = MockAPIClient(operation_mode="shadow")
    
    # Configurar grid
    grid_config = {
        "initial_levels": 6,
        "spacing_perc": 1.0,
        "market_type": "spot",
        "base_spacing_percentage": 0.01,
        "num_levels": 6
    }
    
    print("🤖 Inicializando GridLogic em modo Shadow...")
    try:
        # Criar GridLogic com dados simulados
        grid = GridLogic(
            symbol="BTCUSDT",
            config=grid_config,
            api_client=mock_client,
            operation_mode="shadow",
            market_type="spot"
        )
        
        # Simular inicialização manual dos atributos necessários
        grid.current_price = 45000.0
        grid.price_history = [45000.0 + np.random.uniform(-100, 100) for _ in range(50)]
        grid.num_levels = 6
        grid.base_spacing_percentage = 0.01
        grid.current_spacing_percentage = 0.01
        grid.grid_levels = [44000, 44500, 45000, 45500, 46000, 46500]
        grid.current_position_size = 0.0
        grid.unrealized_pnl = 0.0
        grid.recent_trades_count = 100
        
        print("✅ GridLogic inicializado com sucesso!")
        
        # Teste 1: Capturar estado de mercado
        print("\n1️⃣ Testando captura de estado de mercado...")
        state = grid.get_market_state()
        print(f"   Estado capturado: {len(state)} features")
        print(f"   Primeiras features: {state[:5]}")
        
        # Teste 2: Simular colocação de ordens
        print("\n2️⃣ Testando colocação de ordens simuladas...")
        for i in range(3):
            side = "BUY" if i % 2 == 0 else "SELL"
            price = f"{45000 + i * 100:.2f}"
            qty = "0.001"
            
            order_id = grid._place_order_unified(side, price, qty)
            if order_id:
                print(f"   Ordem {i+1}: {side} {qty} @ {price} = Order ID {order_id}")
            else:
                print(f"   Ordem {i+1}: FALHOU")
        
        # Teste 3: Aplicar ações RL
        print("\n3️⃣ Testando aplicação de ações RL...")
        for action in [0, 1, 3, 7]:  # Diferentes ações
            print(f"   Aplicando ação RL: {action}")
            grid._apply_discrete_rl_action(action)
            time.sleep(0.1)
        
        print("✅ Simulação concluída!")
        
        # Verificar dados salvos
        print("\n📊 Verificando dados coletados...")
        stats = shadow_storage.get_data_stats()
        
        total_collected = 0
        for data_type, count in stats.items():
            print(f"   📄 {data_type}: {count} entradas")
            total_collected += count
        
        if total_collected > 0:
            print(f"\n🎉 SUCESSO! {total_collected} entradas coletadas")
            
            # Mostrar exemplos de dados
            print("\n📋 EXEMPLOS DE DADOS COLETADOS:")
            
            # Exemplo de trade
            trades_df = shadow_storage.load_trades_df()
            if not trades_df.empty:
                trade = trades_df.iloc[0]
                print(f"   💰 Trade: {trade['side']} {trade['quantity']} {trade['symbol']} @ {trade['price']}")
            
            # Exemplo de dados RL
            rl_data = shadow_storage.load_training_data(limit=1)
            if rl_data['states']:
                print(f"   🧠 RL State: {len(rl_data['states'][0])} features")
                print(f"   🎯 RL Action: {rl_data['actions'][0]}")
                print(f"   🏆 RL Reward: {rl_data['rewards'][0]:.4f}")
            
            return True
        else:
            print(f"\n❌ FALHA: Nenhum dado coletado")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante simulação: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_shadow_data_simulation()
    
    if success:
        print(f"\n🎯 CONCLUSÃO: Sistema Shadow está funcionando!")
        print(f"📚 Os dados podem ser usados para treinar o agente RL")
        print(f"🔧 Para usar com API real, adicione as chaves no .env")
    else:
        print(f"\n⚠️ CONCLUSÃO: Sistema precisa de ajustes")