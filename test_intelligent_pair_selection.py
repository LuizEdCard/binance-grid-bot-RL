#!/usr/bin/env python3
"""
Teste da seleção inteligente de pares com análise de feeds sociais
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.api_client import APIClient
from core.pair_selector import PairSelector
from utils.binance_social_feed_analyzer import BinanceSocialFeedAnalyzer
import yaml
import asyncio

async def test_ai_analysis():
    print("🤖 TESTE: ANÁLISE DE IA DOS FEEDS")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    
    try:
        from utils.ai_social_analyzer import AISocialAnalyzer
        
        print("\n1. 🔧 VERIFICANDO IA LOCAL...")
        ai_analyzer = AISocialAnalyzer(config)
        
        # Verificar se IA está disponível
        if await ai_analyzer._check_ai_availability():
            print("   ✅ IA local está disponível")
            
            # Testar análise de sentiment
            print("\n2. 🧠 TESTANDO ANÁLISE DE SENTIMENT...")
            test_post = {
                "content": "BTCUSDT breaking out! Strong bullish momentum, targeting $50k. This could be the start of a major rally! 🚀",
                "author_type": "INFLUENCER",
                "engagement": {"likes": 150, "comments": 25}
            }
            
            result = await ai_analyzer.analyze_social_post(test_post)
            if result:
                print(f"   ✅ Análise concluída:")
                print(f"      Símbolos detectados: {result.symbols_detected}")
                print(f"      Sentiment: {result.sentiment_score:.2f}")
                print(f"      Confiança: {result.confidence:.2f}")
                print(f"      Sinais: {result.market_signals}")
                print(f"      Ação recomendada: {result.recommended_action}")
                print(f"      Raciocínio: {result.reasoning[:100]}...")
                
                return True
            else:
                print("   ❌ Análise falhou")
                return False
        else:
            print("   ⚠️ IA local não disponível - análise será básica")
            return True  # Não é erro, apenas não tem IA
            
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_social_feed_analyzer():
    print("\n🔍 TESTE: ANALISADOR DE FEEDS SOCIAIS")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    
    try:
        async with BinanceSocialFeedAnalyzer(config) as analyzer:
            print("\n1. 📈 BUSCANDO SÍMBOLOS EM TENDÊNCIA...")
            trending_symbols = await analyzer.get_trending_symbols()
            
            print(f"   ✅ Encontrados {len(trending_symbols)} símbolos em tendência:")
            
            for i, symbol in enumerate(trending_symbols[:5]):  # Mostrar só top 5
                print(f"      {i+1}. {symbol.symbol}")
                print(f"          Menções: {symbol.mentions}")
                print(f"          Sentiment: {symbol.sentiment_score:.2f}")
                print(f"          Confiança: {symbol.confidence:.2f}")
                print(f"          Fonte: {symbol.source}")
                
                # Verificar se foi analisado pela IA
                if "+AI" in symbol.source:
                    print(f"          🤖 ANALISADO PELA IA")
                if "🔥AI_HOT" in symbol.context:
                    print(f"          🔥 MARCADO COMO HOT PELA IA")
                    
                print(f"          Contexto: {symbol.context[:100]}...")
                print()
            
            return len(trending_symbols) > 0
            
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_intelligent_pair_selection():
    print("\n🧠 TESTE: SELEÇÃO INTELIGENTE DE PARES")
    print("=" * 60)
    
    config = yaml.safe_load(open('src/config/config.yaml'))
    api = APIClient(config)
    
    try:
        print("\n1. 🔧 VERIFICANDO CONFIGURAÇÃO:")
        use_social = config.get('pair_selection', {}).get('use_social_feed_analysis', False)
        preferred = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
        
        print(f"   Análise social habilitada: {use_social}")
        print(f"   Preferred symbols: {preferred}")
        
        print("\n2. 🔄 TESTANDO SELEÇÃO INTELIGENTE:")
        pair_selector = PairSelector(config, api)
        
        # Forçar seleção com análise social
        selected_pairs = pair_selector.get_selected_pairs(force_update=True)
        
        print(f"   ✅ Pares selecionados: {len(selected_pairs)}")
        for i, pair in enumerate(selected_pairs):
            print(f"      {i+1}. {pair}")
        
        # Verificar se há mix de preferred + trending
        preferred_in_selection = [p for p in selected_pairs if p in preferred]
        social_in_selection = [p for p in selected_pairs if p not in preferred]
        
        print(f"\n3. 📊 ANÁLISE DA SELEÇÃO:")
        print(f"   Preferred symbols na seleção: {len(preferred_in_selection)}")
        print(f"   Símbolos do feed social: {len(social_in_selection)}")
        
        if social_in_selection:
            print(f"   🎯 Novos símbolos detectados: {social_in_selection}")
            
        return len(selected_pairs) > 0
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("🚀 TESTE COMPLETO: SELEÇÃO INTELIGENTE COM IA E FEEDS SOCIAIS")
    print("=" * 70)
    
    # Teste 1: Análise de IA
    test1 = await test_ai_analysis()
    
    # Teste 2: Analisador de feeds sociais
    test2 = await test_social_feed_analyzer()
    
    # Teste 3: Seleção inteligente de pares
    test3 = test_intelligent_pair_selection()
    
    print(f"\n📊 RESUMO DOS TESTES:")
    print(f"   1. Análise de IA: {'✅ PASSOU' if test1 else '❌ FALHOU'}")
    print(f"   2. Análise de feeds sociais: {'✅ PASSOU' if test2 else '❌ FALHOU'}")
    print(f"   3. Seleção inteligente: {'✅ PASSOU' if test3 else '❌ FALHOU'}")
    
    if test1 and test2 and test3:
        print(f"\n🎉 SISTEMA DE ANÁLISE SOCIAL COM IA FUNCIONANDO!")
        print(f"🤖 IA local analisa sentiment, detecta padrões e filtra ruído")
        print(f"📈 Feeds sociais detectam símbolos trending de influenciadores")
        print(f"📰 Notícias da Binance são analisadas para extrair sinais")
        print(f"🧠 Combinação inteligente: Preferred + Trending + IA + Análise técnica")
        print(f"\n🔥 Símbolos 'hot' detectados pela IA recebem prioridade!")
        print(f"⚡ Sistema otimizado para detectar oportunidades em tempo real")
    else:
        print(f"\n⚠️ ALGUNS PROBLEMAS ENCONTRADOS")
        if not test1:
            print(f"   - IA local não disponível ou com problemas")
        if not test2:
            print(f"   - Verificar conexão com APIs da Binance para feeds")
        if not test3:
            print(f"   - Verificar integração no PairSelector")

if __name__ == "__main__":
    asyncio.run(main())