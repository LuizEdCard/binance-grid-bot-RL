#!/usr/bin/env python3
from src.utils.aggressive_tp_sl import AggressiveTPSLManager
from src.utils.api_client import APIClient
import yaml
from decimal import Decimal

config_path = 'src/config/config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

try:
    # Initialize components
    api_client = APIClient(config, operation_mode='production')
    tpsl_manager = AggressiveTPSLManager(api_client, config)
    
    print("=== TESTE DO SISTEMA TP/SL ===")
    
    # Test manual position addition
    print("\n1. Testando adição manual de posição...")
    position_id = tpsl_manager.add_position(
        symbol="TRXUSDT",
        position_side="SHORT", 
        entry_price=Decimal("0.271285"),
        quantity=Decimal("38.0")
    )
    print(f"Position ID criado: {position_id}")
    
    # Check active orders in manager
    print(f"\n2. Posições ativas no TP/SL manager: {len(tpsl_manager.active_orders)}")
    for pos_id, order in tpsl_manager.active_orders.items():
        print(f"  {pos_id}: {order.symbol} {order.position_side} TP:{order.tp_price} SL:{order.sl_price}")
    
    # Test TP/SL order placement manually
    print("\n3. Testando colocação de ordem TP manualmente...")
    tp_order_id = tpsl_manager._place_limit_order("TRXUSDT", "BUY", "38.0", "0.270199")
    print(f"TP Order ID: {tp_order_id}")
    
    print("\n4. Testando colocação de ordem SL manualmente...")
    sl_order_id = tpsl_manager._place_stop_order("TRXUSDT", "BUY", "38.0", "0.272912")
    print(f"SL Order ID: {sl_order_id}")
    
except Exception as e:
    print(f'Erro: {e}')
    import traceback
    traceback.print_exc()