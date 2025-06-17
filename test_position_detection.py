#!/usr/bin/env python3
"""
Teste para verificar detecção de posições abertas
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.pair_selector import PairSelector
from utils.logger import setup_logger
import yaml

def load_config():
    """Carrega configuração do bot."""
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_position_detection():
    """Testa detecção de posições abertas."""
    log = setup_logger("test_positions")
    
    try:
        # Carregar configuração
        config = load_config()
        
        # Inicializar API client
        api_client = APIClient(config)
        
        # Inicializar pair selector
        pair_selector = PairSelector(config, api_client)
        
        print("🔍 Testing position detection...")
        print("=" * 50)
        
        # Testar detecção direta de posições
        print("\n1. Testing direct position detection:")
        positions = api_client.get_futures_positions()
        
        if positions:
            open_positions = []
            for pos in positions:
                position_amt = float(pos.get("positionAmt", 0))
                if position_amt != 0:
                    symbol = pos.get("symbol", "")
                    entry_price = pos.get("entryPrice", "0")
                    unrealized_pnl = pos.get("unrealizedPnl", "0")
                    side = "LONG" if position_amt > 0 else "SHORT"
                    
                    open_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "amount": abs(position_amt),
                        "entry_price": entry_price,
                        "pnl": unrealized_pnl
                    })
                    
                    print(f"   📈 {symbol} {side} | Qty: {abs(position_amt):.6f} | Entry: {entry_price} | PnL: {unrealized_pnl} USDT")
            
            print(f"\n   Total open positions found: {len(open_positions)}")
            
            # Extrair símbolos únicos
            unique_symbols = list(set([pos["symbol"] for pos in open_positions]))
            print(f"   Unique symbols with positions: {len(unique_symbols)}")
            print(f"   Symbols: {unique_symbols}")
        else:
            print("   ❌ Could not retrieve positions from API")
        
        print("\n2. Testing PairSelector detection:")
        # Testar método do PairSelector
        pairs_with_positions = pair_selector._get_pairs_with_open_positions()
        print(f"   PairSelector found {len(pairs_with_positions)} pairs: {pairs_with_positions}")
        
        print("\n3. Testing complete pair selection:")
        # Testar seleção completa de pares
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        print(f"   Final selected pairs: {len(selected_pairs)} pairs")
        print(f"   Pairs: {selected_pairs}")
        
        print("\n" + "=" * 50)
        print("✅ Position detection test completed!")
        
        # Verificar se todos os pares com posições estão sendo incluídos
        if pairs_with_positions and selected_pairs:
            missing_pairs = [pair for pair in pairs_with_positions if pair not in selected_pairs]
            if missing_pairs:
                print(f"⚠️  WARNING: These pairs have positions but are NOT in selected pairs: {missing_pairs}")
            else:
                print("✅ SUCCESS: All pairs with open positions are included in selection!")
        
        return True
        
    except Exception as e:
        log.error(f"Error in position detection test: {e}")
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_position_detection()