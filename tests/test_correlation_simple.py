#!/usr/bin/env python3
"""
Teste simples para verificar se a correlação BTC está desabilitada
"""

import os
import sys

def check_correlation_disabled():
    """Verifica se a correlação está desabilitada no código"""
    
    grid_logic_path = os.path.join(os.path.dirname(__file__), "src", "core", "grid_logic.py")
    
    if not os.path.exists(grid_logic_path):
        print("❌ Arquivo grid_logic.py não encontrado")
        return False
    
    with open(grid_logic_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se a correlação está desabilitada
    correlation_disabled_markers = [
        "self.correlation_enabled = False",
        "# Desabilitar temporariamente",
        "Correlação BTC desabilitada para debug"
    ]
    
    print("=== VERIFICANDO STATUS DA CORRELAÇÃO ===")
    
    found_markers = []
    for marker in correlation_disabled_markers:
        if marker in content:
            found_markers.append(marker)
            print(f"✅ Encontrado: {marker}")
        else:
            print(f"❌ Não encontrado: {marker}")
    
    # Verificar se a inicialização do analisador está desabilitada
    if "if self.symbol != 'BTCUSDT' and self.correlation_enabled:" in content:
        print("✅ Inicialização do analisador está condicionada ao flag correlation_enabled")
    else:
        print("❌ Inicialização do analisador não está devidamente protegida")
    
    if len(found_markers) >= 2:
        print("\n🎉 SUCESSO: Correlação BTC está desabilitada no código!")
        return True
    else:
        print("\n❌ PROBLEMA: Correlação BTC não está devidamente desabilitada")
        return False

def check_cycle_timing():
    """Verifica se o ciclo do bot foi acelerado para 30 segundos"""
    
    main_path = os.path.join(os.path.dirname(__file__), "src", "main.py")
    
    if not os.path.exists(main_path):
        print("❌ Arquivo main.py não encontrado")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n=== VERIFICANDO TIMING DO CICLO ===")
    
    if "time.sleep(30)" in content and "# Wait 30 seconds between cycles for faster order detection" in content:
        print("✅ Ciclo do bot configurado para 30 segundos")
        return True
    else:
        print("❌ Ciclo do bot não está configurado corretamente")
        return False

def check_grid_limits():
    """Verifica se o limite de grid foi aumentado para 164"""
    
    # Buscar no frontend
    frontend_path = "/home/luiz/Área de trabalho/bot/frontend/algo-grid-pilot/src/pages/Index.tsx"
    
    if os.path.exists(frontend_path):
        with open(frontend_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("\n=== VERIFICANDO LIMITE DE GRID ===")
        
        if "max={164}" in content:
            print("✅ Limite de grid aumentado para 164 no frontend")
            return True
        else:
            print("❌ Limite de grid não foi atualizado no frontend")
            return False
    else:
        print("❌ Arquivo frontend não encontrado")
        return False

if __name__ == "__main__":
    print("Verificando melhorias implementadas...\n")
    
    correlation_ok = check_correlation_disabled()
    cycle_ok = check_cycle_timing()
    grid_limits_ok = check_grid_limits()
    
    print(f"\n=== RESUMO DOS TESTES ===")
    print(f"Correlação desabilitada: {'✅ SIM' if correlation_ok else '❌ NÃO'}")
    print(f"Ciclo acelerado (30s): {'✅ SIM' if cycle_ok else '❌ NÃO'}")
    print(f"Limite grid (164): {'✅ SIM' if grid_limits_ok else '❌ NÃO'}")
    
    if correlation_ok and cycle_ok:
        print("\n🚀 PRINCIPAL: As melhorias para resolver o problema de execução foram aplicadas!")
        print("   - Correlação BTC desabilitada para debug")
        print("   - Ciclo do bot acelerado para detectar ordens mais rapidamente")
    else:
        print("\n⚠️  ATENÇÃO: Algumas melhorias não foram encontradas.")