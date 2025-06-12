#!/usr/bin/env python3
"""
Teste e diagnóstico do bot do Telegram
"""
import sys
import os
import asyncio
import yaml
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.alerter import Alerter
from utils.logger import setup_logger

log = setup_logger("telegram_test")


def load_config():
    """Carrega configuração"""
    config_path = os.path.join(os.path.dirname(__file__), 'src', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def test_telegram_credentials():
    """Testa credenciais e conectividade do Telegram"""
    print("🤖 Testing Telegram Bot Configuration")
    print("=" * 45)
    
    # Carregar variáveis de ambiente
    env_path = os.path.join(os.path.dirname(__file__), 'secrets', '.env')
    load_dotenv(dotenv_path=env_path)
    
    # Verificar se as variáveis existem
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    print("1. Checking environment variables:")
    print(f"   TELEGRAM_BOT_TOKEN: {'✅ Found' if bot_token else '❌ Missing'}")
    if bot_token:
        print(f"     Token: {bot_token[:20]}...{bot_token[-10:] if len(bot_token) > 30 else bot_token}")
    
    print(f"   TELEGRAM_CHAT_ID: {'✅ Found' if chat_id else '❌ Missing'}")
    if chat_id:
        print(f"     Chat ID: {chat_id}")
    
    if not bot_token or not chat_id:
        print("\n❌ Missing Telegram credentials!")
        print("📝 To create a new Telegram bot:")
        print("   1. Message @BotFather on Telegram")
        print("   2. Send: /newbot")
        print("   3. Choose a name and username")
        print("   4. Copy the token to .env file")
        print("   5. Start a chat with your bot and get your chat ID")
        return False
    
    # Teste direto com a biblioteca telegram
    print(f"\n2. Testing direct Telegram API connection:")
    
    try:
        import telegram
        
        # Criar bot
        bot = telegram.Bot(token=bot_token)
        
        # Teste básico - obter informações do bot
        print("   Testing bot info...")
        import asyncio
        
        async def test_bot_info():
            try:
                bot_info = await bot.get_me()
                print(f"   ✅ Bot connected successfully!")
                print(f"     Bot name: {bot_info.first_name}")
                print(f"     Bot username: @{bot_info.username}")
                print(f"     Bot ID: {bot_info.id}")
                return True
            except Exception as e:
                print(f"   ❌ Bot connection failed: {e}")
                return False
        
        bot_works = asyncio.run(test_bot_info())
        
        if bot_works:
            # Teste de envio de mensagem
            print(f"\n3. Testing message sending:")
            
            async def test_send_message():
                try:
                    message = await bot.send_message(
                        chat_id=chat_id,
                        text="🧪 Teste de conexão do bot de trading!\n✅ Bot configurado corretamente!"
                    )
                    print(f"   ✅ Message sent successfully!")
                    print(f"     Message ID: {message.message_id}")
                    return True
                except Exception as e:
                    print(f"   ❌ Failed to send message: {e}")
                    if "chat not found" in str(e).lower():
                        print("   💡 Tip: Make sure you've started a chat with the bot first")
                        print("      Send /start to your bot on Telegram")
                    elif "unauthorized" in str(e).lower():
                        print("   💡 Tip: Bot token may be invalid")
                    return False
            
            message_works = asyncio.run(test_send_message())
        else:
            message_works = False
            
    except ImportError:
        print("   ❌ Telegram library not installed")
        print("   Run: pip install python-telegram-bot")
        return False
    except Exception as e:
        print(f"   ❌ Error testing Telegram: {e}")
        return False
    
    # Teste com Alerter
    print(f"\n4. Testing Alerter class:")
    
    try:
        config = load_config()
        
        # Verificar se alerts estão habilitados
        alerts_enabled = config.get('alerts', {}).get('enabled', False)
        print(f"   Alerts enabled in config: {'✅ Yes' if alerts_enabled else '❌ No'}")
        
        if not alerts_enabled:
            print("   ⚠️  Alerts are disabled in config.yaml")
            print("   To enable: set alerts.enabled: true")
        
        # Tentar criar Alerter
        alerter = Alerter(config)
        
        # Teste de envio
        if alerts_enabled:
            print("   Testing Alerter.send_message...")
            success = alerter.send_message("🧪 Teste via Alerter class!")
            print(f"   Alerter test: {'✅ Success' if success else '❌ Failed'}")
        else:
            print("   Skipping Alerter test (alerts disabled)")
            
    except Exception as e:
        print(f"   ❌ Error testing Alerter: {e}")
    
    # Instruções para criar novo bot se necessário
    print(f"\n5. Instructions for creating a new Telegram bot:")
    print("   Step 1: Create bot with BotFather")
    print("     • Open Telegram and search for @BotFather")
    print("     • Send: /newbot")
    print("     • Choose name: 'Trading Bot' (or any name)")
    print("     • Choose username: 'your_trading_bot' (must be unique)")
    print("     • Copy the token BotFather gives you")
    
    print("   Step 2: Get your Chat ID")
    print("     • Start a chat with your new bot")
    print("     • Send any message to the bot")
    print("     • Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
    print("     • Look for 'chat':{'id': YOUR_CHAT_ID}")
    
    print("   Step 3: Update .env file")
    print("     • TELEGRAM_BOT_TOKEN='your_new_token'")
    print("     • TELEGRAM_CHAT_ID='your_chat_id'")
    
    print("   Step 4: Enable alerts in config.yaml")
    print("     • alerts.enabled: true")
    
    return bot_works and message_works


if __name__ == "__main__":
    success = test_telegram_credentials()
    
    if success:
        print(f"\n🎉 Telegram bot is working correctly!")
    else:
        print(f"\n❌ Telegram bot needs configuration.")
        print(f"💡 Follow the instructions above to fix it.")