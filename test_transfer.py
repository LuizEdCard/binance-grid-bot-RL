#!/usr/bin/env python3
"""
Teste de transferência entre mercados Spot e Futures
"""

import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.capital_management import CapitalManager
import yaml

def load_config():
    with open('src/config/config.yaml', 'r') as f:
        return yaml.safe_load(f)

def test_balance_check():
    """Verificar saldos atuais antes dos testes"""
    print("💰 VERIFICAÇÃO DE SALDOS ATUAIS")
    print("=" * 40)
    
    config = load_config()
    api = APIClient(config)
    capital_manager = CapitalManager(api, config)
    
    try:
        # Verificar saldos
        balances = capital_manager.get_available_balances()
        
        print(f"💵 Saldo Spot: ${balances['spot_usdt']:.2f}")
        print(f"🚀 Saldo Futures: ${balances['futures_usdt']:.2f}")
        print(f"💯 Total: ${balances['total_usdt']:.2f}")
        
        return balances
    except Exception as e:
        print(f"❌ Erro ao verificar saldos: {e}")
        return None

def test_spot_to_futures_transfer(amount=5.0):
    """Testar transferência de Spot para Futures"""
    print(f"\n🔄 TESTE: SPOT → FUTURES (${amount})")
    print("=" * 40)
    
    config = load_config()
    api = APIClient(config)
    
    try:
        print(f"⏳ Transferindo ${amount} USDT de Spot para Futures...")
        
        result = api.transfer_between_markets(
            asset='USDT',
            amount=amount,
            transfer_type='1'  # 1 = Spot para Futures
        )
        
        if result:
            print("✅ Transferência Spot→Futures realizada com sucesso!")
            print(f"📄 Detalhes: {result}")
            return True
        else:
            print("❌ Transferência falhou - resultado None")
            return False
            
    except Exception as e:
        print(f"❌ Erro na transferência Spot→Futures: {e}")
        return False

def test_futures_to_spot_transfer(amount=5.0):
    """Testar transferência de Futures para Spot"""
    print(f"\n🔄 TESTE: FUTURES → SPOT (${amount})")
    print("=" * 40)
    
    config = load_config()
    api = APIClient(config)
    
    try:
        print(f"⏳ Transferindo ${amount} USDT de Futures para Spot...")
        
        result = api.transfer_between_markets(
            asset='USDT',
            amount=amount,
            transfer_type='2'  # 2 = Futures para Spot
        )
        
        if result:
            print("✅ Transferência Futures→Spot realizada com sucesso!")
            print(f"📄 Detalhes: {result}")
            return True
        else:
            print("❌ Transferência falhou - resultado None")
            return False
            
    except Exception as e:
        print(f"❌ Erro na transferência Futures→Spot: {e}")
        return False

def test_capital_management_auto_transfer():
    """Testar transferência automática do Capital Management"""
    print(f"\n🤖 TESTE: TRANSFERÊNCIA AUTOMÁTICA CAPITAL MANAGEMENT")
    print("=" * 50)
    
    config = load_config()
    api = APIClient(config)
    capital_manager = CapitalManager(api, config)
    
    try:
        print("⏳ Testando transferência automática...")
        
        # Simular necessidade de capital no futures
        result = capital_manager.ensure_adequate_balance(
            market_type='futures',
            required_amount=10.0
        )
        
        if result:
            print("✅ Transferência automática funcionou!")
            print(f"📄 Resultado: {result}")
            return True
        else:
            print("⚠️  Transferência automática não necessária ou falhou")
            return False
            
    except Exception as e:
        print(f"❌ Erro na transferência automática: {e}")
        return False

def main():
    print("🚀 TESTE COMPLETO DE TRANSFERÊNCIAS")
    print("=" * 50)
    
    # 1. Verificar saldos iniciais
    initial_balances = test_balance_check()
    if not initial_balances:
        print("❌ Não foi possível verificar saldos - abortando testes")
        return
    
    # Verificar se há saldo suficiente para testes
    spot_balance = initial_balances['spot_usdt']
    futures_balance = initial_balances['futures_usdt']
    
    print(f"\n📊 Análise de viabilidade:")
    print(f"   Spot: ${spot_balance:.2f}")
    print(f"   Futures: ${futures_balance:.2f}")
    
    transfer_amount = 3.0  # Valor baixo para teste
    
    if spot_balance < transfer_amount and futures_balance < transfer_amount:
        print(f"⚠️  Saldos muito baixos para testar transferência de ${transfer_amount}")
        transfer_amount = 1.0
        print(f"🔧 Reduzindo valor de teste para ${transfer_amount}")
    
    # 2. Testar transferência Spot → Futures (se houver saldo spot)
    test1_result = False
    if spot_balance >= transfer_amount:
        test1_result = test_spot_to_futures_transfer(transfer_amount)
        time.sleep(2)  # Aguardar processamento
    else:
        print(f"\n⚠️  Pulando teste Spot→Futures - saldo insuficiente (${spot_balance:.2f} < ${transfer_amount})")
    
    # 3. Verificar saldos após primeira transferência
    print(f"\n💰 SALDOS APÓS PRIMEIRA TRANSFERÊNCIA:")
    mid_balances = test_balance_check()
    
    # 4. Testar transferência Futures → Spot (se houver saldo futures)
    test2_result = False
    if mid_balances and mid_balances['futures_usdt'] >= transfer_amount:
        test2_result = test_futures_to_spot_transfer(transfer_amount)
        time.sleep(2)  # Aguardar processamento
    else:
        print(f"\n⚠️  Pulando teste Futures→Spot - saldo insuficiente")
    
    # 5. Testar transferência automática
    test3_result = test_capital_management_auto_transfer()
    
    # 6. Verificar saldos finais
    print(f"\n💰 SALDOS FINAIS:")
    final_balances = test_balance_check()
    
    # 7. Resumo dos testes
    print("\n" + "=" * 50)
    print("📊 RESUMO DOS TESTES DE TRANSFERÊNCIA")
    print("=" * 50)
    
    print(f"✅ Teste 1 (Spot→Futures): {'PASSOU' if test1_result else 'PULADO/FALHOU'}")
    print(f"✅ Teste 2 (Futures→Spot): {'PASSOU' if test2_result else 'PULADO/FALHOU'}")
    print(f"✅ Teste 3 (Auto Transfer): {'PASSOU' if test3_result else 'FALHOU'}")
    
    if initial_balances and final_balances:
        print(f"\n💹 COMPARAÇÃO DE SALDOS:")
        print(f"   Spot: ${initial_balances['spot_usdt']:.2f} → ${final_balances['spot_usdt']:.2f}")
        print(f"   Futures: ${initial_balances['futures_usdt']:.2f} → ${final_balances['futures_usdt']:.2f}")
    
    tests_passed = sum([test1_result, test2_result, test3_result])
    tests_total = 3
    
    if tests_passed >= 2:
        print(f"\n🎉 TRANSFERÊNCIAS FUNCIONANDO! ({tests_passed}/{tests_total} testes passaram)")
    else:
        print(f"\n⚠️  PROBLEMAS DETECTADOS ({tests_passed}/{tests_total} testes passaram)")

if __name__ == "__main__":
    main()