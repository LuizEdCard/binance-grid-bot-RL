#!/usr/bin/env python3
"""
Script para forçar rotação de pares inativos e testar a nova lógica
"""
import sys
import os
import time
import json
from datetime import datetime
from decimal import Decimal

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from utils.logger import setup_logger
from utils.trade_activity_tracker import TradeActivityTracker
from core.pair_selector import PairSelector
import yaml

log = setup_logger("force_pair_rotation")

def load_config():
    """Load configuration from config.yaml"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_current_active_pairs(api_client):
    """Identifica pares atualmente ativos baseado em posições abertas"""
    try:
        positions = api_client.get_futures_positions()
        active_pairs = []
        
        for position in positions:
            position_amt = float(position.get("positionAmt", 0))
            symbol = position.get("symbol", "")
            
            if position_amt != 0 and symbol.endswith("USDT"):
                active_pairs.append(symbol)
                log.info(f"📈 Posição ativa: {symbol} ({position_amt:.6f})")
        
        return active_pairs
    except Exception as e:
        log.error(f"Erro ao obter pares ativos: {e}")
        return []

def force_pair_rotation():
    """Força rotação de pares inativos usando o sistema existente"""
    try:
        log.info("🔄 Iniciando rotação forçada de pares...")
        
        config = load_config()
        api_client = APIClient(config)
        
        # Inicializar componentes
        tracker = TradeActivityTracker(config=config)
        pair_selector = PairSelector(config, api_client)
        
        # Obter pares atualmente ativos
        active_pairs = get_current_active_pairs(api_client)
        
        if not active_pairs:
            log.warning("❌ Nenhum par ativo encontrado")
            return
        
        log.info(f"📊 Pares ativos encontrados: {active_pairs}")
        
        # Obter dados de atividade
        activity_data = tracker.get_activity_data(active_pairs)
        
        log.info("📈 Análise de atividade dos pares:")
        current_time = time.time()
        
        for symbol in active_pairs:
            if symbol in activity_data:
                data = activity_data[symbol]
                last_trade = data['last_trade_time']
                inactive_hours = (current_time - last_trade) / 3600 if last_trade > 0 else float('inf')
                total_trades = data['total_trades']
                
                log.info(f"  {symbol}: {total_trades} trades, inativo há {inactive_hours:.1f}h")
            else:
                log.info(f"  {symbol}: Sem dados de atividade")
        
        # Executar análise de qualidade ATR
        log.info("🔍 Executando análise de qualidade ATR...")
        atr_analysis = pair_selector.monitor_atr_quality(active_pairs, activity_data)
        
        problematic_pairs = atr_analysis.get("problematic_pairs", {})
        replacement_suggestions = atr_analysis.get("replacement_suggestions", {})
        
        if not problematic_pairs:
            log.info("✅ Nenhum par problemático encontrado")
            return
        
        log.info(f"🚨 Pares problemáticos identificados: {len(problematic_pairs)}")
        
        for symbol, issues in problematic_pairs.items():
            issues_list = issues.get("issues", [])
            log.warning(f"  ❌ {symbol}: {', '.join(issues_list)}")
        
        if replacement_suggestions:
            log.info(f"💡 Sugestões de substituição: {len(replacement_suggestions)}")
            
            for old_pair, new_pair_info in replacement_suggestions.items():
                new_symbol = new_pair_info["symbol"]
                atr_perc = new_pair_info["atr_percentage"]
                
                log.info(f"  🔄 {old_pair} → {new_symbol} (ATR: {atr_perc:.2f}%)")
                
                # Aqui você poderia implementar a troca automática
                # Por agora, apenas logamos as sugestões
        
        # Gerar relatório JSON para análise
        report = {
            "timestamp": current_time,
            "active_pairs": active_pairs,
            "problematic_pairs": problematic_pairs,
            "replacement_suggestions": replacement_suggestions,
            "total_problematic": len(problematic_pairs),
            "inactivity_timeout_hours": atr_analysis.get("inactivity_timeout_hours", 1)
        }
        
        report_file = "data/pair_rotation_report.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        log.info(f"📄 Relatório salvo em: {report_file}")
        
        # Sugestões para o usuário
        if problematic_pairs:
            log.info("🎯 RECOMENDAÇÕES:")
            log.info("1. Cancele ordens antigas com: python check_old_orders.py")
            log.info("2. Reinicie o sistema multi-agent para aplicar rotações")
            log.info("3. Monitore logs para verificar se novos pares são selecionados")
        else:
            log.info("✅ Sistema está funcionando corretamente!")
        
    except Exception as e:
        log.error(f"Erro na rotação forçada: {e}")

def test_pair_selection_update():
    """Testa atualização forçada da seleção de pares"""
    try:
        log.info("🧪 Testando atualização forçada de seleção de pares...")
        
        config = load_config()
        api_client = APIClient(config)
        pair_selector = PairSelector(config, api_client)
        
        # Forçar atualização
        log.info("⚡ Forçando atualização de seleção...")
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        
        log.info(f"📊 Pares selecionados: {selected_pairs}")
        
        # Verificar se há pares com posições abertas
        positions_pairs = pair_selector._get_pairs_with_open_positions()
        log.info(f"🏦 Pares com posições: {positions_pairs}")
        
        # Verificar se todos os pares com posições estão na seleção
        missing_pairs = set(positions_pairs) - set(selected_pairs)
        if missing_pairs:
            log.warning(f"⚠️ Pares com posições não selecionados: {missing_pairs}")
        else:
            log.info("✅ Todos os pares com posições estão selecionados")
        
    except Exception as e:
        log.error(f"Erro no teste de seleção: {e}")

if __name__ == "__main__":
    print("🔄 Rotação Inteligente de Pares - Análise e Teste")
    print("=" * 50)
    
    # Executar análise de rotação
    force_pair_rotation()
    
    print("\n" + "=" * 50)
    
    # Testar seleção de pares
    test_pair_selection_update()
    
    print("\n✅ Análise concluída!")