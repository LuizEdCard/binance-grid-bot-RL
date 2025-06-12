#!/usr/bin/env python3
"""
Teste simples do Telegram sem asyncio complexo
"""
import os
import asyncio
from dotenv import load_dotenv

# Carregar variáveis de ambiente
env_path = os.path.join(os.path.dirname(__file__), 'secrets', '.env')
load_dotenv(dotenv_path=env_path)

bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

async def test_simple_telegram():
    """Teste simples e direto do Telegram"""
    print("🧪 Testing Simple Telegram Send")
    print("=" * 35)
    
    if not bot_token or not chat_id:
        print("❌ Missing bot token or chat ID")
        return
    
    try:
        import telegram
        
        # Criar bot
        bot = telegram.Bot(token=bot_token)
        
        # Testar informações do bot
        print("1. Getting bot info...")
        bot_info = await bot.get_me()
        print(f"   ✅ Bot: {bot_info.first_name} (@{bot_info.username})")
        
        # Enviar mensagem de teste
        print("2. Sending test message...")
        message = await bot.send_message(
            chat_id=chat_id,
            text="🤖 **Teste do Bot de Trading**\n\n"
                 "✅ Configuração funcionando!\n"
                 "💰 Sistema de alertas ativo\n"
                 "📊 Pronto para enviar notificações",
            parse_mode='Markdown'
        )
        
        print(f"   ✅ Message sent successfully!")
        print(f"   📱 Message ID: {message.message_id}")
        print(f"   ⏰ Timestamp: {message.date}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
        # Sugestões baseadas no erro
        if "chat not found" in str(e).lower():
            print("\n💡 Solução: Inicie uma conversa com o bot")
            print(f"   1. Abra o Telegram")
            print(f"   2. Procure por @{bot_info.username if 'bot_info' in locals() else 'seu_bot'}")
            print(f"   3. Clique em 'START' ou envie /start")
            print(f"   4. Tente novamente")
            
        elif "unauthorized" in str(e).lower():
            print("\n💡 Solução: Token inválido")
            print(f"   1. Verifique se o token está correto")
            print(f"   2. Crie um novo bot com @BotFather se necessário")
            
        elif "bad request" in str(e).lower():
            print("\n💡 Solução: Chat ID inválido")
            print(f"   1. Verifique o CHAT_ID no arquivo .env")
            print(f"   2. Use @userinfobot para obter seu chat ID")
            
        return False

if __name__ == "__main__":
    success = asyncio.run(test_simple_telegram())
    
    if success:
        print(f"\n🎉 Telegram está funcionando!")
        print(f"✅ Você deve ter recebido uma mensagem no Telegram")
    else:
        print(f"\n❌ Precisa corrigir a configuração do Telegram")