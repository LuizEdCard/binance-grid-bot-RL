#!/usr/bin/env python3
"""
Teste do Alerter corrigido
"""
import sys
import os
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.alerter import Alerter
from utils.logger import setup_logger

log = setup_logger("alerter_test")


def load_config():
    """Carrega configuração"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_alerter():
    """Testa o Alerter corrigido"""
    print("📢 Testing Fixed Alerter")
    print("=" * 25)
    
    config = load_config()
    
    print("1. Checking configuration:")
    alerts_enabled = config.get('alerts', {}).get('enabled', False)
    print(f"   Alerts enabled: {'✅ Yes' if alerts_enabled else '❌ No'}")
    
    if not alerts_enabled:
        print("   ⚠️  Enable alerts first: set alerts.enabled: true in config.yaml")
        return
    
    print("2. Initializing Alerter...")
    alerter = Alerter()
    
    print(f"   Alerter enabled: {'✅ Yes' if alerter.enabled else '❌ No'}")
    
    if not alerter.enabled:
        print("   ⚠️  Alerter not enabled - check bot token and chat ID")
        return
    
    print("3. Testing message sending...")
    
    # Test simple message
    success1 = alerter.send_message(
        "🧪 Teste do Alerter Corrigido\n"
        "✅ Sistema funcionando\n"
        "🚀 Pronto para alertas de trading!"
    )
    
    print(f"   Simple message: {'✅ Success' if success1 else '❌ Failed'}")
    
    # Test trading alert style message
    success2 = alerter.send_message(
        "🎯 **ALERTA DE TRADING**\n\n"
        "📊 Par: BTCUSDT\n"
        "💰 Preço: $108,000\n"
        "📈 Ação: Grid iniciado\n"
        "⏰ Horário: Agora"
    )
    
    print(f"   Trading alert: {'✅ Success' if success2 else '❌ Failed'}")
    
    # Test critical alert
    success3 = alerter.send_critical_alert("🚨 Teste de alerta crítico - Sistema funcionando!")
    
    print(f"   Critical alert: {'✅ Success' if success3 else '❌ Failed'}")
    
    if success1 or success2 or success3:
        print("\n🎉 Alerter is working!")
        print("✅ You should have received messages on Telegram")
        print("💡 The trading bot can now send notifications")
    else:
        print("\n❌ Alerter needs fixing")
        print("💡 Try running: python setup_new_telegram_bot.py")


if __name__ == "__main__":
    test_alerter()