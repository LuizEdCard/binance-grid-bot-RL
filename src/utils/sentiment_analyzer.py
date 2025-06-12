# sentiment_analyzer.py

import json
import os
import pathlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import onnxruntime as ort
from transformers import AutoTokenizer

from .logger import log
from .binance_news_listener import BinanceNewsListener, BinanceNewsItem

# Define base directories
BASE_DIR = pathlib.Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODELS_DIR = os.path.join(BASE_DIR, "models", "sentiment_onnx")


class SentimentAnalyzer:
    """Analyzes sentiment using a pre-trained ONNX model (llmware/slim-sentiment-onnx)."""

    def __init__(
        self, model_dir=None
    ):
        self.model_dir = model_dir if model_dir is not None else MODELS_DIR
        self.model_path = os.path.join(self.model_dir, "model.onnx")
        self.tokenizer = None
        self.session = None
        self._load_model()

    def _load_model(self):
        """Loads the ONNX model and tokenizer."""
        try:
            if not os.path.exists(self.model_path):
                log.info(
                    f"Sentiment analysis ONNX model not found at: {self.model_path}"
                )
                log.info("Attempting to download model automatically...")
                if not self._download_model():
                    raise FileNotFoundError(f"Failed to download model to: {self.model_path}")

            log.info(f"Loading sentiment analysis tokenizer from: {self.model_dir}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)

            log.info(f"Loading sentiment analysis ONNX model from: {self.model_path}")
            # Consider provider options if GPU is available and configured, default is CPU
            # providers = [("CUDAExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
            providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            log.info(
                f"Sentiment analysis model loaded successfully using {self.session.get_providers()}"
            )

        except Exception as e:
            log.error(
                f"Failed to load sentiment analysis model or tokenizer: {e}",
                exc_info=True,
            )
            self.tokenizer = None
            self.session = None
    
    def _download_model(self):
        """Downloads the ONNX sentiment model automatically."""
        try:
            from huggingface_hub import hf_hub_download
            
            log.info("Starting automatic download of ONNX sentiment model...")
            
            # Create model directory
            os.makedirs(self.model_dir, exist_ok=True)
            
            # Try different model repositories
            model_repos = [
                ("cardiffnlp/twitter-roberta-base-sentiment-latest", "onnx/model.onnx"),
                ("microsoft/DialoGPT-medium", "onnx/model.onnx"),
            ]
            
            for repo_id, model_file in model_repos:
                try:
                    log.info(f"Trying to download from {repo_id}...")
                    
                    # Download model files
                    model_files = [
                        model_file,
                        "config.json", 
                        "tokenizer.json",
                        "tokenizer_config.json",
                    ]
                    
                    success = True
                    for file_name in model_files:
                        try:
                            log.info(f"Downloading {file_name}...")
                            downloaded_path = hf_hub_download(
                                repo_id=repo_id,
                                filename=file_name,
                                local_dir=self.model_dir,
                                local_dir_use_symlinks=False
                            )
                            
                            # Rename model file if needed
                            if file_name != "model.onnx" and file_name.endswith("model.onnx"):
                                import shutil
                                shutil.move(downloaded_path, self.model_path)
                            
                            log.info(f"Downloaded {file_name} successfully")
                        except Exception as e:
                            log.warning(f"Failed to download {file_name}: {e}")
                            success = False
                            break
                    
                    if success and os.path.exists(self.model_path):
                        log.info(f"ONNX sentiment model downloaded successfully from {repo_id}!")
                        return True
                        
                except Exception as e:
                    log.warning(f"Failed to download from {repo_id}: {e}")
                    continue
            
            # Fallback: disable sentiment analysis
            log.warning("All model downloads failed. Sentiment analysis will be disabled.")
            return False
                
        except ImportError as e:
            log.error(f"Required libraries missing for model download: {e}")
            log.error("Please install: pip install huggingface_hub")
            return False
        except Exception as e:
            log.error(f"Failed to download ONNX model: {e}")
            return False

    def analyze(self, text: str) -> dict | None:
        """Analyzes the sentiment of the input text.

        Args:
            text: The text to analyze.

        Returns:
            A dictionary containing the sentiment (e.g., {"sentiment": "positive"})
            or None if analysis fails.
        """
        if not self.session or not self.tokenizer:
            log.debug(
                "Sentiment analyzer model not loaded. Trying AI fallback or rule-based analysis."
            )
            
            # Try AI analysis first if available
            ai_result = self._try_ai_analysis(text)
            if ai_result:
                return ai_result
            
            # Fallback to rule-based analysis
            return self._fallback_analysis(text)

        try:
            # Tokenize the input text
            inputs = self.tokenizer(
                text, return_tensors="np", padding=True, truncation=True, max_length=512
            )

            # Prepare inputs for ONNX Runtime
            # The input names might vary depending on the model conversion. Check the model structure if needed.
            # Common names are 'input_ids', 'attention_mask'.
            ort_inputs = {
                self.session.get_inputs()[0].name: inputs["input_ids"],
                self.session.get_inputs()[1].name: inputs["attention_mask"],
            }

            # Run inference
            ort_outputs = self.session.run(None, ort_inputs)

            # Process the output
            # The output format depends on how the model was trained/converted.
            # For slim-sentiment-onnx, it's expected to be logits or directly interpretable output.
            # We need to decode the output tokens back to text/json.
            # Assuming the output logits need decoding (this might need
            # adjustment based on model specifics)
            output_ids = ort_outputs[0]
            decoded_output = self.tokenizer.decode(
                output_ids[0], skip_special_tokens=True
            )

            # The model card says it generates a python dictionary.
            # Let's try to parse the decoded output as JSON (often models
            # output JSON strings).
            try:
                # Clean potential artifacts if needed
                cleaned_output = decoded_output.strip()
                # Find the start and end of the dictionary
                start_index = cleaned_output.find("{")
                end_index = cleaned_output.rfind("}")
                if start_index != -1 and end_index != -1:
                    dict_str = cleaned_output[start_index : end_index + 1]
                    sentiment_result = json.loads(dict_str)
                    log.debug(
                        f"Sentiment analysis result for '{text[:50]}...': {sentiment_result}"
                    )
                    return sentiment_result
                else:
                    log.warning(
                        f"Could not find valid dictionary in model output: {cleaned_output}"
                    )
                    return None
            except json.JSONDecodeError as json_err:
                log.error(
                    f"Failed to parse sentiment model output as JSON: {decoded_output}. Error: {json_err}"
                )
                return None
            except Exception as parse_err:
                log.error(
                    f"Error processing sentiment model output: {decoded_output}. Error: {parse_err}"
                )
                return None

        except Exception as e:
            log.error(
                f"Error during sentiment analysis for text '{text[:50]}...': {e}",
                exc_info=True,
            )
            return None

    def _try_ai_analysis(self, text: str) -> dict | None:
        """Try to use local AI for sentiment analysis."""
        try:
            # Import here to avoid circular imports
            import asyncio
            import aiohttp
            import json
            
            async def _ai_sentiment_request():
                try:
                    timeout = aiohttp.ClientTimeout(total=10)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        # Auto-detect model from Ollama
                        # First try to get current model
                        model_name = await self._get_current_model(session)
                        if not model_name:
                            model_name = "qwen3:1.7b"  # Fallback
                        
                        # Use Ollama API format  
                        payload = {
                            "model": model_name,
                            "prompt": f"""Analyze the sentiment of this text and respond only with a JSON object in this exact format:
{{"sentiment": "positive", "confidence": 0.8, "score": 0.7}}

Where sentiment is "positive", "negative", or "neutral", confidence is 0.0-1.0, and score is -1.0 to 1.0.

Text to analyze: {text[:300]}""",
                            "stream": False,
                            "options": {
                                "temperature": 0.3,
                                "num_predict": 100
                            }
                        }
                        
                        async with session.post(
                            "http://127.0.0.1:11434/api/generate",
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                response_text = result.get("response", "")
                                
                                # Try to parse JSON from response
                                try:
                                    # Look for JSON in the response
                                    start = response_text.find('{')
                                    end = response_text.rfind('}') + 1
                                    if start >= 0 and end > start:
                                        json_str = response_text[start:end]
                                        sentiment_data = json.loads(json_str)
                                        return sentiment_data
                                except:
                                    pass
                                    
                                return None
                            else:
                                return None
                except Exception:
                    return None
            
            # Run the async function
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If we're already in an async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _ai_sentiment_request())
                    return future.result(timeout=15)
            else:
                return loop.run_until_complete(_ai_sentiment_request())
                
        except Exception as e:
            log.debug(f"AI sentiment analysis failed: {e}")
            return None
    
    async def _get_current_model(self, session):
        """Get currently running model from Ollama."""
        try:
            # Try to get running processes
            async with session.get("http://127.0.0.1:11434/api/ps") as response:
                if response.status == 200:
                    result = await response.json()
                    models = result.get("models", [])
                    if models:
                        return models[0].get("name", "")
            
            # If no model running, get available models
            async with session.get("http://127.0.0.1:11434/api/tags") as response:
                if response.status == 200:
                    result = await response.json()
                    models = result.get("models", [])
                    if models:
                        # Prefer known good models
                        preferred = ["qwen3:1.7b", "deepseek-r1:1.5b", "qwen3:4b", "gemma3:4b"]
                        available_names = [m.get("name", "") for m in models]
                        for p in preferred:
                            if p in available_names:
                                return p
                        return available_names[0]  # Return first available
            return None
        except:
            return None

    def _fallback_analysis(self, text: str) -> dict:
        """Simple rule-based sentiment analysis fallback."""
        text_lower = text.lower()
        
        # Positive keywords
        positive_words = [
            'good', 'great', 'excellent', 'amazing', 'awesome', 'bullish', 'up', 'gain', 'profit',
            'rise', 'moon', 'pump', 'buy', 'hodl', 'green', 'positive', 'strong', 'high'
        ]
        
        # Negative keywords
        negative_words = [
            'bad', 'terrible', 'awful', 'bearish', 'down', 'loss', 'drop', 'fall', 'dump',
            'sell', 'crash', 'red', 'negative', 'weak', 'low', 'fear'
        ]
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = 0.7
        elif negative_count > positive_count:
            sentiment = "negative"
            score = -0.7
        else:
            sentiment = "neutral"
            score = 0.0
        
        return {
            "sentiment": sentiment,
            "confidence": abs(score),
            "score": score
        }
    
    async def analyze_binance_news(
        self, 
        symbols: List[str] = None, 
        hours_back: int = 24,
        min_relevance: float = 0.2
    ) -> Dict[str, Any]:
        """
        Analisa o sentimento das notícias da Binance.
        
        Args:
            symbols: Lista de símbolos crypto específicos para filtrar (ex: ['BTC', 'ETH'])
            hours_back: Buscar notícias das últimas X horas
            min_relevance: Score mínimo de relevância para incluir a notícia
            
        Returns:
            Dict com sentiment agregado e detalhes das notícias
        """
        try:
            async with BinanceNewsListener() as news_listener:
                # Testar conexão
                if not await news_listener.test_connection():
                    log.warning("Failed to connect to Binance news API")
                    return self._empty_news_sentiment()
                
                # Buscar notícias
                if symbols:
                    news_items = await news_listener.get_crypto_specific_news(symbols, hours_back)
                else:
                    news_items = await news_listener.fetch_all_recent_news(hours_back)
                
                # Filtrar por relevância
                relevant_news = [
                    news for news in news_items 
                    if news.relevance_score >= min_relevance
                ]
                
                if not relevant_news:
                    log.info("No relevant Binance news found")
                    return self._empty_news_sentiment()
                
                # Analisar sentimento de cada notícia
                analyzed_news = []
                sentiment_scores = []
                
                for news in relevant_news:
                    # Combinar título e corpo para análise
                    full_text = f"{news.title}. {news.body[:300]}"
                    
                    # Analisar sentimento
                    sentiment_result = self.analyze(full_text)
                    
                    if sentiment_result:
                        news.sentiment_score = sentiment_result.get("score", 0.0)
                        sentiment_scores.append(news.sentiment_score)
                        
                        analyzed_news.append({
                            "id": news.id,
                            "title": news.title,
                            "type": news.type,
                            "published_time": news.published_time.isoformat(),
                            "tags": news.tags,
                            "url": news.url,
                            "relevance_score": news.relevance_score,
                            "sentiment": sentiment_result.get("sentiment", "neutral"),
                            "sentiment_score": news.sentiment_score,
                            "confidence": sentiment_result.get("confidence", 0.0)
                        })
                
                # Calcular sentimento agregado
                if sentiment_scores:
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                    
                    # Pesar por relevância
                    weighted_sentiment = sum(
                        news.sentiment_score * news.relevance_score 
                        for news in relevant_news if hasattr(news, 'sentiment_score')
                    ) / sum(news.relevance_score for news in relevant_news)
                    
                    # Determinar sentimento geral
                    if weighted_sentiment > 0.2:
                        overall_sentiment = "positive"
                    elif weighted_sentiment < -0.2:
                        overall_sentiment = "negative"
                    else:
                        overall_sentiment = "neutral"
                else:
                    avg_sentiment = 0.0
                    weighted_sentiment = 0.0
                    overall_sentiment = "neutral"
                
                result = {
                    "overall_sentiment": overall_sentiment,
                    "average_score": round(avg_sentiment, 3),
                    "weighted_score": round(weighted_sentiment, 3),
                    "news_count": len(analyzed_news),
                    "time_range_hours": hours_back,
                    "analyzed_at": datetime.now().isoformat(),
                    "symbols_filter": symbols or "all",
                    "news_items": analyzed_news[:10],  # Limitar para não sobrecarregar
                    "stats": {
                        "positive_count": len([n for n in analyzed_news if n["sentiment"] == "positive"]),
                        "negative_count": len([n for n in analyzed_news if n["sentiment"] == "negative"]),
                        "neutral_count": len([n for n in analyzed_news if n["sentiment"] == "neutral"]),
                        "avg_relevance": round(sum(n["relevance_score"] for n in analyzed_news) / len(analyzed_news), 3) if analyzed_news else 0.0
                    }
                }
                
                log.info(f"Analyzed {len(analyzed_news)} Binance news items. Overall sentiment: {overall_sentiment} ({weighted_sentiment:.3f})")
                return result
                
        except Exception as e:
            log.error(f"Error analyzing Binance news sentiment: {e}")
            return self._empty_news_sentiment()
    
    def _empty_news_sentiment(self) -> Dict[str, Any]:
        """Retorna resultado vazio para sentiment de notícias."""
        return {
            "overall_sentiment": "neutral",
            "average_score": 0.0,
            "weighted_score": 0.0,
            "news_count": 0,
            "time_range_hours": 0,
            "analyzed_at": datetime.now().isoformat(),
            "symbols_filter": None,
            "news_items": [],
            "stats": {
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "avg_relevance": 0.0
            },
            "error": "No news data available"
        }
    
    async def get_symbol_sentiment_from_news(self, symbol: str, hours_back: int = 12) -> Dict[str, Any]:
        """
        Obtém sentiment específico para um símbolo baseado em notícias da Binance.
        
        Args:
            symbol: Símbolo crypto (ex: 'BTC', 'ETH')
            hours_back: Horas para buscar no passado
            
        Returns:
            Dict com sentiment específico do símbolo
        """
        news_sentiment = await self.analyze_binance_news([symbol], hours_back, min_relevance=0.1)
        
        # Adicionar informações específicas do símbolo
        symbol_info = {
            "symbol": symbol.upper(),
            "symbol_sentiment": news_sentiment["overall_sentiment"],
            "symbol_score": news_sentiment["weighted_score"],
            "mentions_count": news_sentiment["news_count"],
            "last_updated": news_sentiment["analyzed_at"],
            "timeframe_hours": hours_back
        }
        
        # Mesclar com dados das notícias
        result = {**symbol_info, "news_analysis": news_sentiment}
        
        return result
    
    async def analyze_multiple_symbols_async(self, symbols: List[str], hours_back: int = 24) -> Dict[str, Dict]:
        """
        Analisa sentiment para múltiplos símbolos de forma assíncrona.
        
        Args:
            symbols: Lista de símbolos para analisar
            hours_back: Horas para buscar no passado
            
        Returns:
            Dict com sentiment para cada símbolo
        """
        tasks = [
            self.get_symbol_sentiment_from_news(symbol, hours_back)
            for symbol in symbols
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        symbol_sentiments = {}
        for i, result in enumerate(results):
            symbol = symbols[i]
            if isinstance(result, Exception):
                log.error(f"Error analyzing {symbol}: {result}")
                symbol_sentiments[symbol] = {
                    "symbol": symbol,
                    "error": str(result),
                    "symbol_sentiment": "neutral",
                    "symbol_score": 0.0
                }
            else:
                symbol_sentiments[symbol] = result
        
        return symbol_sentiments
    
    def analyze_multiple_symbols(self, symbols: List[str], hours_back: int = 24) -> Dict[str, Dict]:
        """
        Versão síncrona para compatibilidade.
        """
        try:
            # Tentar usar loop existente
            loop = asyncio.get_running_loop()
            # Se há um loop rodando, criar uma task future
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    self.analyze_multiple_symbols_async(symbols, hours_back)
                )
                return future.result()
        except RuntimeError:
            # Não há loop rodando, criar um novo
            return asyncio.run(self.analyze_multiple_symbols_async(symbols, hours_back))


# Example Usage (for testing)
if __name__ == "__main__":
    # Ensure logger is configured for standalone testing
    import logging

    logging.basicConfig(level=logging.INFO)
    log.setLevel(logging.INFO)

    analyzer = SentimentAnalyzer()

    if analyzer.session:
        test_text_positive = "This is great news! The market is booming today."
        test_text_negative = "I am very concerned about the recent downturn."
        test_text_neutral = "The report was released this morning."

        sentiment_pos = analyzer.analyze(test_text_positive)
        print(f"Sentiment (Positive Test): {sentiment_pos}")

        sentiment_neg = analyzer.analyze(test_text_negative)
        print(f"Sentiment (Negative Test): {sentiment_neg}")

        sentiment_neu = analyzer.analyze(test_text_neutral)
        print(f"Sentiment (Neutral Test): {sentiment_neu}")
    else:
        print("Sentiment Analyzer could not be initialized.")
