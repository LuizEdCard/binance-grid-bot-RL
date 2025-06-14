#!/usr/bin/env python3
"""
Debug balance and margin requirements
"""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
import yaml

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def main():
    print("🔍 Balance and Margin Debug")
    print("=" * 30)
    
    config = load_config()
    api = APIClient(config)
    
    # Check futures account balance
    print("📊 Futures Account Balance:")
    futures_balance = api.get_futures_account_balance()
    
    if isinstance(futures_balance, list):
        for asset in futures_balance:
            if asset.get("asset") == "USDT":
                print(f"  USDT:")
                print(f"    Wallet Balance: ${float(asset.get('walletBalance', 0)):.4f}")
                print(f"    Available Balance: ${float(asset.get('availableBalance', 0)):.4f}")
                print(f"    Cross Wallet Balance: ${float(asset.get('crossWalletBalance', 0)):.4f}")
                print(f"    Cross Unrealized PnL: ${float(asset.get('crossUnPnl', 0)):.4f}")
                break
    
    # Check positions
    print("\n📈 Current Positions:")
    positions = api.get_futures_positions()
    active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
    
    if active_positions:
        for pos in active_positions:
            symbol = pos.get('symbol')
            amount = pos.get('positionAmt')
            entry_price = pos.get('entryPrice')
            mark_price = pos.get('markPrice')
            pnl = pos.get('unRealizedProfit')
            print(f"  {symbol}: {amount} @ ${entry_price} (Mark: ${mark_price}, PnL: ${pnl})")
    else:
        print("  No active positions")
    
    # Test minimum order
    print("\n🧪 Testing Minimum Order Requirements:")
    test_symbol = "ADAUSDT"
    ticker = api.get_futures_ticker(test_symbol)
    current_price = float(ticker.get('price', 0))
    
    # Calculate minimum quantity
    exchange_info = api.get_exchange_info()
    symbol_info = None
    for s in exchange_info.get('symbols', []):
        if s.get('symbol') == test_symbol:
            symbol_info = s
            break
    
    if symbol_info:
        filters = symbol_info.get('filters', [])
        min_notional = None
        min_qty = None
        
        for f in filters:
            if f.get('filterType') == 'MIN_NOTIONAL':
                min_notional = float(f.get('notional', 0))
            elif f.get('filterType') == 'LOT_SIZE':
                min_qty = float(f.get('minQty', 0))
        
        print(f"  {test_symbol}:")
        print(f"    Current Price: ${current_price:.6f}")
        print(f"    Min Notional: ${min_notional}")
        print(f"    Min Quantity: {min_qty}")
        
        if min_notional and current_price:
            required_qty = min_notional / current_price
            print(f"    Required Qty for Min Notional: {required_qty:.0f}")
            print(f"    Required Capital: ${required_qty * current_price:.2f}")

if __name__ == "__main__":
    main()