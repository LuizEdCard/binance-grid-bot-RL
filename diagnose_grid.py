#!/usr/bin/env python3
"""
Temporary diagnostic script to check the state of ADAUSDT grid orders
"""

import os
import sys
from utils.api_client import APIClient
from utils.logger import setup_logger
import yaml

def run_grid_diagnosis():
    """Função temporária para diagnosticar o estado do grid ADAUSDT."""
    try:
        # Carregar configuração
        config_path = os.path.join("src", "config", "config.yaml")
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Inicializar cliente API
        print("🔑 Initializing API client")
        api_client = APIClient(config["api"], operation_mode="production")
        
        # Verificar ordens spot
        print("\n🔍 Checking SPOT orders for ADAUSDT")
        try:
            spot_orders = api_client._make_request(api_client.client.get_open_orders, symbol='ADAUSDT')
            print(f"✅ SPOT orders found: {len(spot_orders) if spot_orders else 0}")
            if spot_orders:
                for order in spot_orders:
                    print(f"  - SPOT: {order['side']} @ {order['price']}, Amount: {order['origQty']}")
                    print(f"    OrderId: {order['orderId']}, Status: {order['status']}")
        except Exception as e:
            print(f"❌ Error checking SPOT orders: {e}")

        # Verificar ordens futures
        print("\n🔍 Checking FUTURES orders for ADAUSDT")
        try:
            futures_orders = api_client._make_request(api_client.client.futures_get_open_orders, symbol='ADAUSDT')
            print(f"✅ FUTURES orders found: {len(futures_orders) if futures_orders else 0}")
            if futures_orders:
                # Analisar espaçamentos entre ordens
                futures_orders.sort(key=lambda x: float(x['price']))
                for i in range(len(futures_orders)):
                    order = futures_orders[i]
                    print(f"  - FUTURES: {order['side']} @ {order['price']}, Amount: {order['origQty']}")
                    print(f"    OrderId: {order['orderId']}, Status: {order['status']}")
                    
                    # Calcular espaçamento com a próxima ordem
                    if i < len(futures_orders) - 1:
                        price1 = float(order['price'])
                        price2 = float(futures_orders[i+1]['price'])
                        spacing = abs((price2 - price1) / price1) * 100
                        print(f"    Spacing to next order: {spacing:.2f}%")
        except Exception as e:
            print(f"❌ Error checking FUTURES orders: {e}")
            
        # Check account balances
        print("\n💰 Checking account balances")
        try:
            # Spot balances
            account = api_client._make_request(api_client.client.get_account)
            if account and 'balances' in account:
                ada_balance = next((float(b['free']) for b in account['balances'] if b['asset'] == 'ADA'), 0)
                ada_locked = next((float(b['locked']) for b in account['balances'] if b['asset'] == 'ADA'), 0)
                usdt_balance = next((float(b['free']) for b in account['balances'] if b['asset'] == 'USDT'), 0)
                usdt_locked = next((float(b['locked']) for b in account['balances'] if b['asset'] == 'USDT'), 0)
                print(f"  SPOT balances:")
                print(f"    ADA: {ada_balance} (free) + {ada_locked} (locked)")
                print(f"    USDT: {usdt_balance} (free) + {usdt_locked} (locked)")
            
            # Futures balance
            futures_account = api_client._make_request(api_client.client.futures_account_balance)
            if futures_account:
                futures_usdt = next((float(b['balance']) for b in futures_account if b['asset'] == 'USDT'), 0)
                print(f"  FUTURES balance: USDT: {futures_usdt}")
            
            # Check ADA position in futures
            positions = api_client._make_request(api_client.client.futures_position_information, symbol='ADAUSDT')
            if positions:
                position = positions[0]
                amt = float(position['positionAmt'])
                if amt != 0:
                    entry_price = float(position['entryPrice'])
                    unrealized_pnl = float(position['unRealizedProfit'])
                    mark_price = float(position['markPrice'])
                    print(f"  FUTURES position:")
                    print(f"    Amount: {amt}")
                    print(f"    Entry price: {entry_price}")
                    print(f"    Mark price: {mark_price}")
                    print(f"    Unrealized PnL: {unrealized_pnl}")
                else:
                    print("  No active FUTURES position for ADAUSDT")
            
        except Exception as e:
            print(f"❌ Error checking balances: {e}")

    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")

if __name__ == "__main__":
    print("🔧 Starting ADAUSDT grid diagnosis")
    run_grid_diagnosis()
    print("\n✅ Diagnosis complete")
