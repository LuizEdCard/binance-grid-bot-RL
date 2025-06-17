#!/usr/bin/env python3
"""
Script para fechar posições em prejuízo e liberar capital
"""

from src.utils.api_client import APIClient
import yaml

def main():
    print("=" * 60)
    print("🔄 FECHANDO POSIÇÕES EM PREJUÍZO PARA LIBERAR CAPITAL")
    print("=" * 60)
    
    # Carregar configuração
    config_path = 'src/config/config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    try:
        # Inicializar cliente API
        client = APIClient(config, operation_mode='production')
        
        # Obter posições ativas
        positions = client.get_futures_positions()
        if not positions:
            print("❌ Erro ao obter posições")
            return
        
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        if not active_positions:
            print("✅ Nenhuma posição ativa encontrada")
            return
        
        print(f"📊 Encontradas {len(active_positions)} posições ativas:")
        
        total_pnl = 0
        positions_to_close = []
        
        for pos in active_positions:
            symbol = pos['symbol']
            position_amt = float(pos['positionAmt'])
            entry_price = float(pos['entryPrice'])
            unrealized_pnl = float(pos['unRealizedProfit'])
            mark_price = float(pos.get('markPrice', 0))
            
            total_pnl += unrealized_pnl
            side = "LONG" if position_amt > 0 else "SHORT"
            status = "🔴" if unrealized_pnl < 0 else "🟢"
            
            print(f"  {status} {symbol} {side}: PnL ${unrealized_pnl:.4f}")
            
            # Adicionar posições em prejuízo > $0.01 para fechamento
            if unrealized_pnl < -0.01:
                positions_to_close.append(pos)
        
        print(f"\n💰 PnL Total: ${total_pnl:.4f}")
        print(f"🎯 Posições para fechar: {len(positions_to_close)}")
        
        if not positions_to_close:
            print("✅ Nenhuma posição significativa em prejuízo para fechar")
            return
        
        # Fechar automaticamente posições com prejuízo > $0.01
        print(f"\n🚀 Iniciando fechamento automático de posições em prejuízo...")
        print("   Objetivo: Liberar capital para novas operações")
        
        # Fechar posições
        closed_count = 0
        total_loss = 0
        
        for pos in positions_to_close:
            symbol = pos['symbol']
            position_amt = float(pos['positionAmt'])
            unrealized_pnl = float(pos['unRealizedProfit'])
            
            try:
                # Determinar lado da ordem para fechar
                if position_amt > 0:  # LONG -> SELL para fechar
                    side = "SELL"
                    quantity = abs(position_amt)
                else:  # SHORT -> BUY para fechar
                    side = "BUY"
                    quantity = abs(position_amt)
                
                print(f"\n🔄 Fechando {symbol}: {side} {quantity:.1f}...")
                
                # Fechar com ordem MARKET
                result = client.place_futures_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=str(quantity),
                    reduceOnly=True
                )
                
                if result and result.get("orderId"):
                    print(f"   ✅ {symbol} fechado com sucesso!")
                    closed_count += 1
                    total_loss += unrealized_pnl
                else:
                    print(f"   ❌ Erro ao fechar {symbol}")
                    
            except Exception as e:
                print(f"   ❌ Erro ao fechar {symbol}: {e}")
        
        print(f"\n" + "=" * 60)
        print(f"📊 RESULTADO:")
        print(f"   Posições fechadas: {closed_count}/{len(positions_to_close)}")
        print(f"   Perda realizada: ${total_loss:.4f}")
        print(f"   Status: 🔓 Capital liberado para novas operações!")
        print("=" * 60)
        
        # Verificar saldo após fechamento
        print(f"\n💰 Verificando saldo após fechamento...")
        try:
            balance = client.get_futures_account_balance()
            if isinstance(balance, list):
                for asset in balance:
                    if asset.get("asset") == "USDT":
                        available = float(asset.get("availableBalance", 0))
                        total = float(asset.get("balance", 0))
                        print(f"   Saldo disponível: ${available:.4f}")
                        print(f"   Saldo total: ${total:.4f}")
                        break
        except Exception as e:
            print(f"   Erro ao verificar saldo: {e}")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()