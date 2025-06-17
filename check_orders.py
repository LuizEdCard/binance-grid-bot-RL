#!/usr/bin/env python3
from src.utils.api_client import APIClient
import yaml

config_path = 'src/config/config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

try:
    client = APIClient(config, operation_mode='production')
    
    # Check for TRXUSDT orders (we know there's a position)
    symbol = "TRXUSDT"
    orders = client.get_open_futures_orders(symbol)
    
    print(f"Ordens abertas para {symbol}: {len(orders) if orders else 0}")
    if orders:
        for order in orders[:5]:
            print(f"  Order ID: {order['orderId']}, Side: {order['side']}, Type: {order['type']}, Price: {order['price']}, Qty: {order['origQty']}")
    
    # Check general open orders
    print("\nTodas as ordens abertas:")
    all_orders = client.get_open_futures_orders()
    if all_orders:
        print(f"Total de ordens abertas: {len(all_orders)}")
        for order in all_orders[:10]:
            print(f"  {order['symbol']}: {order['side']} {order['type']} @ {order['price']} (Qty: {order['origQty']})")
    else:
        print("Nenhuma ordem aberta encontrada")
        
except Exception as e:
    print(f'Erro: {e}')