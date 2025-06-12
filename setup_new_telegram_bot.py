#!/usr/bin/env python3
"""
Script para configurar um novo bot do Telegram
"""
import os
import asyncio
import json
from dotenv import load_dotenv

def setup_new_telegram_bot():
    """Guia para configurar um novo bot do Telegram"""
    print("🤖 Setup New Telegram Bot")
    print("=" * 30)
    
    print("📝 Step 1: Create a new bot with BotFather")
    print("   1. Open Telegram and search for: @BotFather")
    print("   2. Send: /newbot")
    print("   3. Bot name: 'Trading Alert Bot' (or any name you like)")
    print("   4. Bot username: must end with 'bot' (e.g., 'mytrading_bot')")
    print("   5. Copy the token that BotFather gives you")
    
    print(f"\n💬 Step 2: Get your Chat ID")
    print("   Method 1 - Using @userinfobot:")
    print("     • Search for @userinfobot on Telegram")
    print("     • Send any message to get your user ID")
    
    print("   Method 2 - Manual way:")
    print("     • Start a chat with your new bot")
    print("     • Send /start or any message")
    print("     • Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
    print("     • Look for 'chat':{'id': YOUR_CHAT_ID}")
    
    # Interactive token entry
    print(f"\n🔧 Step 3: Enter your new bot credentials")
    
    new_token = input("Enter your new bot token (or press Enter to skip): ").strip()
    new_chat_id = input("Enter your chat ID (or press Enter to skip): ").strip()
    
    if new_token and new_chat_id:
        print(f"\n🧪 Testing new credentials...")
        
        # Test the new credentials
        success = asyncio.run(test_new_credentials(new_token, new_chat_id))
        
        if success:
            print(f"\n✅ New bot works! Updating .env file...")
            update_env_file(new_token, new_chat_id)
            print(f"✅ Updated .env file with new credentials")
            print(f"✅ You can now use the trading bot with Telegram alerts!")
        else:
            print(f"\n❌ New credentials didn't work. Please check:")
            print(f"   • Token is correct")
            print(f"   • You started a chat with the bot (/start)")
            print(f"   • Chat ID is correct")
    else:
        print(f"\n⏭️  Skipped credential entry")
        print(f"💡 When you have the credentials, run this script again")
    
    print(f"\n📋 Final steps after getting credentials:")
    print(f"   1. Update secrets/.env file:")
    print(f"      TELEGRAM_BOT_TOKEN='your_new_token'")
    print(f"      TELEGRAM_CHAT_ID='your_chat_id'")
    print(f"   2. Make sure alerts are enabled in config.yaml:")
    print(f"      alerts.enabled: true")
    print(f"   3. Test with: python test_telegram_simple.py")


async def test_new_credentials(token, chat_id):
    """Test new Telegram credentials"""
    try:
        import telegram
        
        bot = telegram.Bot(token=token)
        
        # Test bot info
        bot_info = await bot.get_me()
        print(f"   ✅ Bot connected: {bot_info.first_name} (@{bot_info.username})")
        
        # Test sending message
        message = await bot.send_message(
            chat_id=chat_id,
            text="🎉 Novo bot configurado com sucesso!\n"
                 "✅ Trading alerts funcionando\n"
                 "🚀 Sistema pronto para uso!"
        )
        
        print(f"   ✅ Test message sent! Message ID: {message.message_id}")
        return True
        
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False


def update_env_file(new_token, new_chat_id):
    """Update .env file with new credentials"""
    env_path = os.path.join(os.path.dirname(__file__), 'secrets', '.env')
    
    # Read current .env file
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
    
    # Update or add Telegram credentials
    token_updated = False
    chat_id_updated = False
    
    for i, line in enumerate(lines):
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            lines[i] = f'TELEGRAM_BOT_TOKEN="{new_token}"\n'
            token_updated = True
        elif line.startswith('TELEGRAM_CHAT_ID='):
            lines[i] = f'TELEGRAM_CHAT_ID="{new_chat_id}"\n'
            chat_id_updated = True
    
    # Add new lines if not found
    if not token_updated:
        lines.append(f'TELEGRAM_BOT_TOKEN="{new_token}"\n')
    if not chat_id_updated:
        lines.append(f'TELEGRAM_CHAT_ID="{new_chat_id}"\n')
    
    # Write back to file
    with open(env_path, 'w') as f:
        f.writelines(lines)


if __name__ == "__main__":
    setup_new_telegram_bot()