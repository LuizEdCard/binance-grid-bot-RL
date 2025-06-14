#!/usr/bin/env python3
"""
Valida se a correção está funcionando no código atual
"""

import os
import sys

def validate_multi_agent_fix():
    """Valida se o multi_agent_bot.py tem a correção aplicada"""
    
    file_path = "/home/luiz/PycharmProjects/binance-grid-bot-RL/src/multi_agent_bot.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Verificar se a correção está presente
    recovery_checks = [
        "has_existing_position = False",
        "data/grid_states/{symbol}_state.json",
        "Found existing grid state - allowing recovery",
        "Only enforce capital requirements for new positions",
        "if not has_existing_position and not capital_manager.can_trade_symbol"
    ]
    
    print("🔍 Validando correções no multi_agent_bot.py...")
    
    all_present = True
    for check in recovery_checks:
        if check in content:
            print(f"✅ {check}")
        else:
            print(f"❌ {check}")
            all_present = False
    
    # Verificar se não há import os duplo
    import_os_count = content.count("import os")
    print(f"\n📊 Importações de 'os': {import_os_count}")
    
    if "import os" in content and import_os_count == 1:
        print("✅ Import de 'os' está correto (único)")
    else:
        print("⚠️ Possível problema com import de 'os'")
    
    # Verificar se não há conflitos na função _trading_worker_main
    worker_function_start = content.find("def _trading_worker_main(")
    if worker_function_start != -1:
        # Pegar só a função
        next_function = content.find("\n    def ", worker_function_start + 1)
        if next_function == -1:
            worker_function = content[worker_function_start:]
        else:
            worker_function = content[worker_function_start:next_function]
        
        # Verificar se há import os dentro da função
        local_import_os = "import os" in worker_function
        if local_import_os:
            print("❌ Import local de 'os' encontrado na função (pode causar conflito)")
        else:
            print("✅ Nenhum import local de 'os' na função")
    
    print(f"\n📋 Resultado da validação: {'✅ PASSOU' if all_present else '❌ FALHOU'}")
    return all_present

if __name__ == "__main__":
    validate_multi_agent_fix()