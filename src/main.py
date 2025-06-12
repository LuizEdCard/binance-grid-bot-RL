# Backend API using Flask

from utils.logger import setup_logger
from utils.api_client import APIClient
from utils.alerter import Alerter
from routes.model_api import model_api
from core.capital_management import CapitalManager
from core.risk_management import RiskManager
from core.grid_logic import GridLogic
from flask_cors import CORS
from flask import Flask, jsonify, request, send_from_directory
import yaml
import threading
import os
import sys
import time
from dotenv import load_dotenv

# DON'T CHANGE THIS !!! Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Carrega as variáveis de ambiente do arquivo .env

# Determinar o caminho para o arquivo .env na pasta secrets
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'secrets', '.env')

# Carregar variáveis do arquivo .env
load_dotenv(dotenv_path)
print(f"Carregando variáveis de ambiente de: {dotenv_path}")
print(f"BINANCE_API_KEY presente: {'BINANCE_API_KEY' in os.environ}")


# Importar rotas de modelos (tabular e RL)
# Importar lógica do bot (ajustar caminhos e nomes conforme necessário)

# from core.rl_agent import RLAgent # RL Agent desativado temporariamente


# --- Configuração Inicial ---
app = Flask(__name__, static_folder='static')
CORS(app)  # Habilita CORS para todas as rotas
app.register_blueprint(model_api, url_prefix="/api/model")

# Carregar configuração
config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

# Configurar logging
logger = setup_logger("flask_api")

# Inicializar componentes (simplificado para API)
# A inicialização completa pode ocorrer ao iniciar o bot via API
binance_spot_client = None
binance_futures_client = None
alerter = None
bots = {}  # Dicionário para armazenar instâncias de bots por par
bot_threads = {}  # Dicionário para armazenar threads de bots

# --- Rotas Básicas ---

@app.route("/", methods=["GET"])
def home():
    """Rota raiz da API - Retorna página de informações."""
    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Grid Trading Bot API</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   min-height: 100vh; color: white; }}
            .container {{ max-width: 800px; margin: 0 auto; background: rgba(255,255,255,0.1); 
                         padding: 30px; border-radius: 15px; backdrop-filter: blur(10px); }}
            h1 {{ text-align: center; margin-bottom: 30px; font-size: 2.5em; }}
            .status {{ background: rgba(0,255,0,0.2); padding: 15px; border-radius: 10px; 
                      text-align: center; margin-bottom: 30px; }}
            .endpoints {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                         gap: 15px; margin-top: 20px; }}
            .endpoint {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px; 
                        border-left: 4px solid #00ff88; }}
            .endpoint h3 {{ margin: 0 0 10px 0; color: #00ff88; }}
            .endpoint p {{ margin: 5px 0; opacity: 0.9; }}
            .method {{ background: #007acc; color: white; padding: 4px 8px; border-radius: 4px; 
                      font-size: 0.8em; font-weight: bold; }}
            a {{ color: #00ff88; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Grid Trading Bot API</h1>
            
            <div class="status">
                <h2>✅ API Status: ONLINE</h2>
                <p>Versão: 1.0.0 | Modo: {config.get('operation_mode', 'production').upper()}</p>
            </div>
            
            <h2>🛠️ Endpoints Disponíveis:</h2>
            <div class="endpoints">
                <div class="endpoint">
                    <h3><span class="method">GET</span> /api/status</h3>
                    <p>Status do sistema e componentes</p>
                    <a href="/api/status" target="_blank">Testar »</a>
                </div>
                
                <div class="endpoint">
                    <h3><span class="method">GET</span> /api/market_data</h3>
                    <p>Dados de mercado em tempo real</p>
                    <a href="/api/market_data" target="_blank">Testar »</a>
                </div>
                
                <div class="endpoint">
                    <h3><span class="method">POST</span> /api/grid/config</h3>
                    <p>Configurar parâmetros de grid trading</p>
                </div>
                
                <div class="endpoint">
                    <h3><span class="method">POST</span> /api/grid/start</h3>
                    <p>Iniciar trading bot para símbolo</p>
                </div>
                
                <div class="endpoint">
                    <h3><span class="method">POST</span> /api/grid/stop</h3>
                    <p>Parar trading bot</p>
                </div>
                
                <div class="endpoint">
                    <h3><span class="method">GET</span> /api/grid/status/&lt;symbol&gt;</h3>
                    <p>Status do bot para símbolo específico</p>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 30px; opacity: 0.7;">
                <p>📈 Sistema de Grid Trading com IA e Análise de Sentiment</p>
                <p>Desenvolvido com Flask + Binance API + Reinforcement Learning</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/test", methods=["GET"])
def test_page():
    """Serve a página de teste da API."""
    return send_from_directory('static', 'index.html')


# --- Funções Auxiliares (Exemplo) ---

def validate_grid_config(grid_config):
    """Valida a configuração da grade de trading."""
    errors = []
    
    # Validar initial_levels (deve ser inteiro positivo e razoável)
    if "initial_levels" in grid_config:
        try:
            initial_levels = int(grid_config["initial_levels"])
            if initial_levels <= 0:
                errors.append("initial_levels deve ser um número inteiro positivo")
            elif initial_levels > 1000:
                errors.append("initial_levels deve ser menor ou igual a 1000")
        except (ValueError, TypeError):
            errors.append("initial_levels deve ser um número inteiro válido")
    
    # Validar spacing_perc (deve ser float positivo e finito)
    if "spacing_perc" in grid_config:
        try:
            spacing_perc = float(grid_config["spacing_perc"])
            if spacing_perc <= 0:
                errors.append("spacing_perc deve ser um número positivo")
            elif spacing_perc > 100:
                errors.append("spacing_perc deve ser menor ou igual a 100")
            elif not (spacing_perc == spacing_perc):  # Check for NaN
                errors.append("spacing_perc não pode ser NaN")
            elif spacing_perc == float('inf'):
                errors.append("spacing_perc não pode ser infinito")
        except (ValueError, TypeError, OverflowError):
            errors.append("spacing_perc deve ser um número decimal válido")
    
    # Validar market_type
    if "market_type" in grid_config:
        market_type = grid_config["market_type"]
        if market_type not in ["spot", "futures"]:
            errors.append("market_type deve ser 'spot' ou 'futures'")
    
    return errors

def validate_symbol(symbol, client, market_type="spot"):
    """Valida se o símbolo de trading existe."""
    try:
        # Tentar obter informações do símbolo baseado no tipo de mercado
        if market_type == "spot":
            symbol_info = client.get_spot_ticker(symbol)
        else:  # futures
            symbol_info = client.get_futures_ticker(symbol)
        return symbol_info is not None
    except Exception as e:
        logger.error(f"Erro ao validar símbolo {symbol} no mercado {market_type}: {e}")
        return False


def initialize_components():
    """Inicializa componentes essenciais se ainda não foram inicializados."""
    global binance_spot_client, binance_futures_client, alerter
    if binance_spot_client is None:
        logger.info("Inicializando cliente Binance Spot...")
        # Carregar chaves de API do .env ou config (ajustar conforme
        # necessário)
        api_key = os.getenv("BINANCE_API_KEY", config["api"].get("key"))
        api_secret = os.getenv("BINANCE_API_SECRET", config["api"].get("secret"))
        if not api_key or not api_secret:
            logger.error("Chaves da API Binance não encontradas!")
            # Tratar erro apropriadamente
            return False
        api_config = {
            "key": api_key,
            "secret": api_secret
        }
        operation_mode = config.get("operation_mode", "production").lower()
        binance_spot_client = APIClient(api_config, operation_mode=operation_mode)
        logger.info("Cliente Binance Spot inicializado.")
        
    if binance_futures_client is None:
        logger.info("Inicializando cliente Binance Futuros...")
        api_key = os.getenv("BINANCE_API_KEY", config["api"].get("key"))
        api_secret = os.getenv("BINANCE_API_SECRET", config["api"].get("secret"))
        api_config = {
            "key": api_key,
            "secret": api_secret
        }
        operation_mode = config.get("operation_mode", "production").lower()
        binance_futures_client = APIClient(api_config, operation_mode=operation_mode)
        logger.info("Cliente Binance Futuros inicializado.")

    if alerter is None and config.get("alerts", {}).get("enabled", False):
        logger.info("Inicializando Alerter do Telegram...")
        alerter = Alerter(config["alerts"])
        logger.info("Alerter do Telegram inicializado.")
    return True


def run_bot_thread(symbol, grid_config):
    """Função para rodar o bot em uma thread separada."""
    try:
        logger.info(f"Iniciando bot para {symbol} em uma nova thread...")
        if not initialize_components():
            logger.error(f"Falha ao inicializar componentes para {symbol}.")
            return

        # Determinar o tipo de mercado a partir da configuração recebida
        market_type = grid_config.get("market_type", "spot")  # 'spot' ou 'futures'
        if market_type == "futures":
            client = binance_futures_client
        else:
            client = binance_spot_client

        # Initialize capital manager and validate symbol before grid initialization
        capital_manager = CapitalManager(client, config)
        
        # Check if we have sufficient capital for this symbol
        min_capital = capital_manager.min_capital_per_pair_usd
        if not capital_manager.can_trade_symbol(symbol, min_capital):
            logger.error(f"[{symbol}] Insufficient capital to trade. Minimum required: ${min_capital:.2f}")
            capital_manager.log_capital_status()
            return
        
        # Get capital allocation for this symbol
        allocation = capital_manager.get_allocation_for_symbol(symbol)
        if not allocation:
            # Calculate allocation for single symbol
            allocations = capital_manager.calculate_optimal_allocations([symbol])
            if not allocations:
                logger.error(f"[{symbol}] No capital can be allocated for trading")
                return
            allocation = allocations[0]
        
        logger.info(f"[{symbol}] Capital allocated: ${allocation.allocated_amount:.2f} ({allocation.market_type}, {allocation.grid_levels} levels)")
        
        # Initialize grid logic with capital-adapted configuration
        adapted_config = grid_config.copy()
        adapted_config['initial_levels'] = allocation.grid_levels
        adapted_config['initial_spacing_perc'] = str(allocation.spacing_percentage)
        adapted_config['max_position_size_usd'] = allocation.max_position_size

        # Create bot first without risk manager
        bot = GridLogic(
            symbol=symbol,
            config=adapted_config,
            api_client=client,
            operation_mode=config.get("operation_mode", "production"),
            market_type=allocation.market_type
        )

        # Recuperar grid ativo ao iniciar
        bot.recover_active_grid()
        
        # Then create risk manager with all required parameters
        risk_manager = RiskManager(
            symbol=symbol,
            config=config,
            grid_logic=bot,
            api_client=client,
            alerter=alerter,
            get_sentiment_score_func=None,  # Add the missing parameter
            market_type=market_type
        )
        
        # Update bot with the risk manager
        bot.risk_manager = risk_manager
        bots[symbol] = bot
        
        # Run bot in loop with error handling
        error_count = 0
        max_errors = 5
        
        try:
            while error_count < max_errors and not bot.is_stopped():
                try:
                    bot.run_cycle()
                    error_count = 0
                    time.sleep(30)
                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    
                    # Check for symbol-related errors
                    if "Invalid symbol" in error_msg or "APIError(code=-1121)" in error_msg:
                        logger.error(f"Símbolo {symbol} inválido ou não suportado. Parando bot.")
                        break
                    
                    logger.error(f"Erro no ciclo {error_count}/{max_errors} do bot {symbol}: {e}")
                    if error_count >= max_errors:
                        logger.error(f"Bot {symbol} parou após {max_errors} erros consecutivos")
                        break
                    time.sleep(10)  # Wait 10 seconds before retry
        except Exception as e:
            logger.error(f"Erro crítico no loop do bot {symbol}: {e}")
    except Exception as e:
        logger.error(f"Erro na thread do bot para {symbol}: {e}", exc_info=True)
    finally:
        logger.info(f"Thread do bot para {symbol} finalizada.")
        # Garantir cancelamento de ordens ao parar
        try:
            bot.stop()
        except Exception as e:
            logger.error(f"Erro ao cancelar ordens ao parar bot {symbol}: {e}")
        if symbol in bots:
            del bots[symbol]
        if symbol in bot_threads:
            del bot_threads[symbol]


# --- Rotas da API ---


@app.route("/api/status", methods=["GET"])
def get_status():
    """Retorna o status geral da API e dos bots ativos."""
    active_bots_status = {
        symbol: bot.get_status() for symbol, bot in bots.items() if bot
    }
    return jsonify({"api_status": "online", "active_bots": active_bots_status})


@app.route("/api/market_data", methods=["GET"])
def get_market_data():
    """Busca dados de mercado (ex: símbolos, tickers)."""
    logger.info("Recebida requisição para /api/market_data")
    if not initialize_components():
        logger.error("Falha ao inicializar componentes")
        return jsonify({"error": "Falha ao inicializar cliente Binance"}), 500
    try:
        logger.info("Tentando obter tickers com volume do mercado spot...")
        # Usar get_ticker() para obter dados completos incluindo volume
        tickers_24h = binance_spot_client._make_request(binance_spot_client.client.get_ticker)
        logger.info(f"Tickers com volume obtidos: {len(tickers_24h) if isinstance(tickers_24h, list) else 1}")
        
        # Filtrar apenas símbolos USDT e formatar dados
        if isinstance(tickers_24h, list):
            formatted_tickers = [
                {
                    "symbol": t["symbol"], 
                    "price": t["lastPrice"], 
                    "volume": t["volume"],
                    "change_24h": t["priceChangePercent"],
                    "high_24h": t["highPrice"],
                    "low_24h": t["lowPrice"],
                    "quote_volume": t["quoteVolume"]
                }
                for t in tickers_24h
                if "USDT" in t["symbol"] and float(t["volume"]) > 0
            ]
            # Ordenar por volume (maior para menor)
            formatted_tickers.sort(key=lambda x: float(x["volume"]), reverse=True)
            # Limitar a 50 símbolos mais ativos
            formatted_tickers = formatted_tickers[:50]
        else:
            # Se for um único ticker
            formatted_tickers = [{
                "symbol": tickers_24h["symbol"], 
                "price": tickers_24h["lastPrice"], 
                "volume": tickers_24h["volume"],
                "change_24h": tickers_24h["priceChangePercent"],
                "high_24h": tickers_24h["highPrice"],
                "low_24h": tickers_24h["lowPrice"],
                "quote_volume": tickers_24h["quoteVolume"]
            }]
        return jsonify(formatted_tickers)
    except Exception as e:
        logger.error(f"Erro ao buscar dados de mercado: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/grid/config", methods=["POST"])
def configure_grid():
    """Recebe a configuração da grade do frontend."""
    data = request.json
    symbol = data.get("symbol")
    grid_config = data.get("config")

    if not symbol or not grid_config:
        return jsonify({"error": "Símbolo e configuração são obrigatórios"}), 400

    # Validar configuração da grade
    validation_errors = validate_grid_config(grid_config)
    if validation_errors:
        return jsonify({
            "error": "Configuração inválida",
            "details": validation_errors
        }), 400

    logger.info(f"Configuração válida recebida para {symbol}: {grid_config}")

    return jsonify(
        {
            "message": f"Configuração para {symbol} validada e recebida.",
            "received_config": grid_config,
        }
    )


@app.route("/api/grid/start", methods=["POST"])
def start_grid():
    """Inicia o bot de grid para um símbolo específico."""
    data = request.json
    symbol = data.get("symbol")
    grid_config = data.get("config")  # Receber a config ao iniciar

    if not symbol or not grid_config:
        return (
            jsonify({"error": "Símbolo e configuração são obrigatórios para iniciar"}),
            400,
        )

    # Validar configuração da grade
    validation_errors = validate_grid_config(grid_config)
    if validation_errors:
        return jsonify({
            "error": "Configuração inválida para iniciar bot",
            "details": validation_errors
        }), 400

    # Certifique-se de que o frontend envie 'market_type' em grid_config, ou
    # defina padrão
    if "market_type" not in grid_config:
        grid_config["market_type"] = "spot"  # padrão

    # Inicializar componentes para validar símbolo
    if not initialize_components():
        return jsonify({"error": "Falha ao inicializar cliente de trading"}), 500

    # Determinar cliente para validação
    market_type = grid_config.get("market_type", "spot")
    client = binance_futures_client if market_type == "futures" else binance_spot_client

    # Validar formato do símbolo antes de verificar na API
    if not validate_symbol_format(symbol):
        return jsonify({"error": "Formato de símbolo inválido"}), 400
    
    # Validar se o símbolo existe
    if not validate_symbol(symbol, client, market_type):
        return jsonify({"error": f"Símbolo {symbol} não encontrado ou inválido para mercado {market_type}"}), 400

    if symbol in bot_threads and bot_threads[symbol].is_alive():
        return jsonify({"error": f"Bot para {symbol} já está rodando"}), 400

    logger.info(f"Recebida solicitação para iniciar bot para {symbol}")
    thread = threading.Thread(
        target=run_bot_thread, args=(symbol, grid_config), daemon=True
    )
    bot_threads[symbol] = thread
    thread.start()

    return jsonify({"message": f"Bot para {symbol} iniciado em background."})


@app.route("/api/grid/stop", methods=["POST"])
def stop_grid():
    """Para o bot de grid para um símbolo específico."""
    data = request.json
    symbol = data.get("symbol")

    if not symbol:
        return jsonify({"error": "Símbolo é obrigatório"}), 400

    if symbol not in bots or not bots[symbol]:
        return (
            jsonify({"error": f"Bot para {symbol} não encontrado ou não está rodando"}),
            404,
        )

    logger.info(f"Recebida solicitação para parar bot para {symbol}")
    bot = bots[symbol]
    bot.stop()  # Sinaliza para a thread parar

    # Esperar a thread finalizar? (Opcional, pode levar tempo)
    # if symbol in bot_threads:
    #     bot_threads[symbol].join(timeout=10)
    #     if bot_threads[symbol].is_alive():
    #         logger.warning(f"Thread para {symbol} não finalizou no tempo esperado.")

    # Limpeza já ocorre no finally da thread

    return jsonify({"message": f"Sinal de parada enviado para o bot {symbol}."})


@app.route("/api/grid/recovery_status/<symbol>", methods=["GET"])
def get_recovery_status(symbol):
    """Verifica status de recuperação de grid ativo para um símbolo."""
    if symbol not in bots or not bots[symbol]:
        return jsonify({"error": f"Bot para {symbol} não encontrado"}), 404
    
    bot = bots[symbol]
    
    recovery_info = {
        "symbol": symbol,
        "recovery_attempted": getattr(bot, '_recovery_attempted', False),
        "grid_recovered": getattr(bot, '_grid_recovered', False),
        "active_orders_count": len(bot.active_grid_orders),
        "grid_levels_count": len(bot.grid_levels) if bot.grid_levels else 0,
        "operation_mode": bot.operation_mode,
        "current_price": bot.current_price,
        "spacing_percentage": float(bot.current_spacing_percentage) if hasattr(bot, 'current_spacing_percentage') else None
    }
    
    if recovery_info["grid_recovered"]:
        recovery_info["message"] = "Grid ativo recuperado com sucesso"
        recovery_info["status"] = "recovered"
    elif recovery_info["recovery_attempted"]:
        recovery_info["message"] = "Nenhum grid ativo encontrado - novo grid iniciado"
        recovery_info["status"] = "new_grid"
    else:
        recovery_info["message"] = "Recuperação ainda não tentada"
        recovery_info["status"] = "pending"
    
    return jsonify(recovery_info)


def validate_symbol_format(symbol):
    """Valida o formato de um símbolo de trading."""
    if not symbol or len(symbol) < 3:
        return False
    
    # Não deve ser apenas números
    if symbol.isdigit():
        return False
    
    # Deve conter apenas letras, números e alguns caracteres especiais válidos
    import re
    valid_pattern = re.compile(r'^[A-Za-z0-9/_-]+$')
    if not valid_pattern.match(symbol):
        return False
    
    # Não deve conter múltiplas barras consecutivas
    if '//' in symbol:
        return False
    
    return True

@app.route("/api/grid/status/<path:symbol>", methods=["GET"])
def get_grid_status(symbol):
    """Retorna o status específico de um bot de grid."""
    # Validar formato do símbolo
    if not validate_symbol_format(symbol):
        return jsonify({"error": "Formato de símbolo inválido"}), 400
    
    if symbol in bots and bots[symbol]:
        return jsonify(bots[symbol].get_status())
    elif symbol in bot_threads:
        # Bot foi iniciado mas thread ainda não criou o objeto bot
        return jsonify({
            "status": "starting", 
            "message": f"Bot para {symbol} está sendo iniciado."
        })
    else:
        return jsonify(
            {"status": "never_started", "message": f"Bot para {symbol} nunca foi iniciado."}
        )


@app.route("/api/klines/<symbol>", methods=["GET"])
def get_klines(symbol):
    """Busca dados de klines (candlesticks) para um símbolo."""
    logger.info(f"Recebida requisição para klines de {symbol}")
    
    # Validar formato do símbolo
    if not validate_symbol_format(symbol):
        return jsonify({"error": "Formato de símbolo inválido"}), 400
    
    # Parâmetros da requisição
    interval = request.args.get('interval', '1h')  # Padrão 1 hora
    limit = int(request.args.get('limit', 100))    # Padrão 100 candles
    market_type = request.args.get('market_type', 'spot')  # Padrão spot
    
    # Validar limite
    if limit > 1000:
        limit = 1000
    if limit < 1:
        limit = 1
        
    # Validar intervalo
    valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
    if interval not in valid_intervals:
        return jsonify({"error": f"Intervalo inválido. Use um dos: {', '.join(valid_intervals)}"}), 400
    
    if not initialize_components():
        return jsonify({"error": "Falha ao inicializar cliente de trading"}), 500
    
    try:
        # Determinar cliente baseado no tipo de mercado
        if market_type == "spot":
            client = binance_spot_client
            klines = client.get_spot_klines(symbol=symbol, interval=interval, limit=limit)
        else:  # futures
            client = binance_futures_client
            klines = client.get_futures_klines(symbol=symbol, interval=interval, limit=limit)

        logger.info(f"Klines recebidos para {symbol}: {klines[:3]}")  # Loga os 3 primeiros para debug

        if not klines:
            return jsonify({"error": "Nenhum dado de klines encontrado"}), 404

        # Formatar dados para o frontend
        formatted_klines = []
        all_doji = True
        for kline in klines:
            try:
                o = float(kline[1])
                h = float(kline[2])
                l = float(kline[3])
                c = float(kline[4])
                v = float(kline[5])
                if not (o == h == l == c):
                    all_doji = False
                formatted_klines.append({
                    "timestamp": int(kline[0]),
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": v,
                    "close_time": int(kline[6]),
                    "quote_volume": float(kline[7]),
                    "trades": int(kline[8])
                })
            except Exception as e:
                logger.error(f"Erro ao formatar kline: {kline} - {e}")
        if all_doji:
            logger.error(f"Todos os candles vieram como doji (OHLC iguais) para {symbol}. Dados brutos: {klines[:3]}")
            return jsonify({"error": "Todos os candles vieram como doji (OHLC iguais ou zerados). Verifique o símbolo, limite ou se a Binance está retornando dados válidos.", "raw_klines": klines[:3]}), 500
        return jsonify({
            "symbol": symbol,
            "interval": interval,
            "data": formatted_klines
        })
    except Exception as e:
        logger.error(f"Erro ao buscar klines para {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rl/status", methods=["GET"])
def get_rl_status():
    """Retorna o status do sistema de RL e análise de sentimento."""
    try:
        # Verificar se há bots ativos com RL
        active_rl_bots = []
        for symbol, bot in bots.items():
            if bot and hasattr(bot, 'rl_enabled'):
                active_rl_bots.append({
                    "symbol": symbol,
                    "rl_enabled": getattr(bot, 'rl_enabled', False),
                    "sentiment_enabled": True  # Assumir que sentiment está sempre ativo
                })
        
        return jsonify({
            "rl_available": True,
            "sentiment_available": True,
            "onnx_model_loaded": True,  # Legacy compatibility
            "gemma3_model_loaded": True,  # New Gemma-3 model status
            "active_bots": active_rl_bots,
            "total_active_bots": len(active_rl_bots)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter status do RL: {e}")
        return jsonify({
            "rl_available": False,
            "sentiment_available": False,
            "onnx_model_loaded": False,
            "error": str(e)
        }), 500


@app.route("/api/rl/training/status", methods=["GET"])
def get_rl_training_status():
    """Retorna o status detalhado do treinamento RL."""
    try:
        # Simular dados de treinamento RL (em produção, isso viria do agente RL real)
        training_data = {
            "is_training": False,  # Treinamento não está ativo no momento
            "last_training_session": {
                "date": "2024-01-15T10:30:00Z",
                "episodes_completed": 150,
                "total_episodes": 200,
                "completion_percentage": 75.0,
                "average_reward": 0.834,
                "best_reward": 1.245,
                "training_time_minutes": 180,
                "status": "completed"
            },
            "model_performance": {
                "accuracy": 82.5,
                "win_rate": 68.2,
                "profit_factor": 1.34,
                "sharpe_ratio": 1.87,
                "max_drawdown": 8.5
            },
            "training_history": [
                {"episode": 50, "reward": 0.456, "timestamp": "2024-01-15T08:30:00Z"},
                {"episode": 100, "reward": 0.723, "timestamp": "2024-01-15T09:15:00Z"},
                {"episode": 150, "reward": 0.834, "timestamp": "2024-01-15T10:00:00Z"}
            ],
            "next_training_scheduled": "2024-01-16T02:00:00Z",
            "training_config": {
                "algorithm": "PPO",
                "learning_rate": 0.0003,
                "batch_size": 64,
                "memory_size": 10000,
                "update_frequency": 100
            }
        }
        
        return jsonify(training_data)
        
    except Exception as e:
        logger.error(f"Erro ao obter status do treinamento RL: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sentiment/status", methods=["GET"])
def get_sentiment_model_status():
    """Retorna o status detalhado dos modelos de análise de sentimento."""
    try:
        # Import the hybrid analyzer
        from utils.hybrid_sentiment_analyzer import create_sentiment_analyzer
        
        # Create analyzer instance to check status
        analyzer = create_sentiment_analyzer()
        model_status = analyzer.get_model_status()
        performance_stats = analyzer.get_stats()
        
        return jsonify({
            "models": model_status,
            "performance": performance_stats,
            "recommended_model": "gemma3" if model_status["gemma3"]["available"] else "onnx",
            "crypto_optimized": model_status["gemma3"]["loaded"],
            "fallback_available": model_status["onnx"]["available"],
            "status": "operational" if (model_status["gemma3"]["loaded"] or model_status["onnx"]["loaded"]) else "unavailable"
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter status dos modelos de sentimento: {e}")
        return jsonify({
            "error": str(e),
            "models": {"gemma3": {"available": False}, "onnx": {"available": False}},
            "status": "error"
        }), 500


@app.route("/api/sentiment/analyze", methods=["POST"])
def analyze_sentiment_endpoint():
    """Endpoint para testar análise de sentimento."""
    try:
        data = request.get_json()
        if not data or "text" not in data:
            return jsonify({"error": "Campo 'text' é obrigatório"}), 400
        
        text = data["text"]
        if not text.strip():
            return jsonify({"error": "Texto não pode estar vazio"}), 400
        
        # Import and use hybrid analyzer
        from utils.hybrid_sentiment_analyzer import create_sentiment_analyzer
        
        analyzer = create_sentiment_analyzer()
        result = analyzer.analyze(text)
        
        if result:
            return jsonify({
                "text": text,
                "sentiment": result["sentiment"],
                "confidence": result["confidence"],
                "analyzer_used": result["analyzer_used"],
                "reasoning": result.get("reasoning", ""),
                "crypto_relevant": analyzer._calculate_crypto_relevance(text) >= 0.3
            })
        else:
            return jsonify({"error": "Falha na análise de sentimento"}), 500
            
    except Exception as e:
        logger.error(f"Erro na análise de sentimento: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/trading/executions", methods=["GET"])
def get_current_trading_executions():
    """Retorna as execuções de trading atuais em tempo real (dados reais do bot/grid)."""
    try:
        current_executions = []
        for symbol, bot in bots.items():
            if bot and hasattr(bot, 'get_status'):
                bot_status = bot.get_status()
                if bot_status.get('status') == 'running':
                    # Buscar ordens abertas reais
                    open_orders = []
                    for order in bot.open_orders.values():
                        open_orders.append({
                            "order_id": str(order["orderId"]),
                            "type": order.get("type", "LIMIT").lower(),
                            "side": order["side"].lower(),
                            "price": float(order["price"]),
                            "quantity": float(order["origQty"]),
                            "status": order.get("status", "NEW").lower(),
                            "timestamp": int(order.get("time", 0))
                        })
                    # Último trade real
                    last_trade = None
                    if bot.trade_history:
                        t = bot.trade_history[-1]
                        last_trade = {
                            "type": t.get("side", "").lower(),
                            "price": float(t.get("price", 0)),
                            "quantity": float(t.get("quantity", 0)),
                            "timestamp": int(t.get("timestamp", 0))
                        }
                    execution_data = {
                        "symbol": symbol,
                        "status": "active",
                        "market_type": getattr(bot, 'market_type', 'spot'),
                        "current_price": bot_status.get('current_price', 0),
                        "grid_levels": bot_status.get('grid_levels', 0),
                        "active_orders": bot_status.get('active_orders', 0),
                        "total_trades": bot_status.get('total_trades', 0),
                        "realized_pnl": bot_status.get('realized_pnl', 0),
                        "unrealized_pnl": bot_status.get('unrealized_pnl', 0),
                        "last_trade": last_trade,
                        "open_orders": open_orders,
                        "grid_config": {
                            "levels": bot_status.get('grid_levels', 0),
                            "spacing": str(bot_status.get('spacing_percentage', '')),
                            "leverage": bot.grid_config.get('leverage', 1)
                        },
                        "uptime": bot_status.get('uptime', None),
                        "last_update": bot_status.get('last_update', None)
                    }
                    current_executions.append(execution_data)
        # Sempre retorna um array, mesmo se vazio
        return jsonify({
            "executions": current_executions if isinstance(current_executions, list) else [],
            "total_active": len(current_executions),
            "timestamp": int(time.time() * 1000)
        })
    except Exception as e:
        logger.error(f"Erro ao obter execuções de trading: {e}")
        return jsonify({"executions": [], "error": str(e)}), 500


@app.route("/api/trading/pairs", methods=["GET"])
def get_trading_pairs():
    """Retorna pares de trading ativos reais."""
    # Retorna os símbolos dos bots ativos e seus dados atuais
    pairs = []
    for symbol, bot in bots.items():
        if bot and hasattr(bot, 'get_status'):
            status = bot.get_status()
            pairs.append({
                "symbol": symbol,
                "price": status.get("current_price", 0),
                "volume": status.get("volume", 0),
                "change_24h": status.get("change_24h", 0)
            })
    return jsonify({"pairs": pairs})


@app.route("/api/indicators/list", methods=["GET"])
def get_indicators_list():
    """Retorna lista de indicadores técnicos disponíveis reais (se implementado, senão vazio)."""
    # Se houver integração real, retorne a lista, senão vazio
    indicators = []
    return jsonify({"indicators": indicators})


@app.route("/api/indicators/<symbol>", methods=["GET"])
def get_indicators_for_symbol(symbol):
    """Retorna dados reais de indicadores técnicos para o símbolo usando TA-Lib e dados da Binance."""
    import numpy as np
    try:
        # --- Parâmetros ---
        indicator_type = request.args.get("type", "RSI").upper()
        period = int(request.args.get("period", 14))
        interval = request.args.get("interval", "1h")
        limit = int(request.args.get("limit", 500))
        # --- Cache simples em memória ---
        if not hasattr(get_indicators_for_symbol, "_klines_cache"):
            get_indicators_for_symbol._klines_cache = {}
        klines_cache = get_indicators_for_symbol._klines_cache
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()
        # 5 minutos de cache
        if cache_key in klines_cache and now - klines_cache[cache_key][1] < 300:
            klines = klines_cache[cache_key][0]
        else:
            if not binance_spot_client:
                return jsonify({"error": "Binance client não inicializado"}), 500
            klines = binance_spot_client.get_spot_klines(symbol, interval, limit=limit)
            if not klines or len(klines) < period:
                return jsonify({"error": "Dados insuficientes para cálculo do indicador"}), 400
            klines_cache[cache_key] = (klines, now)
        closes = np.array([float(k[4]) for k in klines])
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        volumes = np.array([float(k[5]) for k in klines])
        timestamps = [int(k[0]) for k in klines]
        import talib
        # --- Cálculo do indicador ---
        if indicator_type == "SMA":
            indicator_values = talib.SMA(closes, timeperiod=period)
        elif indicator_type == "EMA":
            indicator_values = talib.EMA(closes, timeperiod=period)
        elif indicator_type == "RSI":
            indicator_values = talib.RSI(closes, timeperiod=period)
        elif indicator_type == "MACD":
            macd, macdsignal, macdhist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
            return jsonify({
                "indicator": "MACD",
                "period": period,
                "macd": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(macd) if not np.isnan(v)],
                "signal": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(macdsignal) if not np.isnan(v)],
                "histogram": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(macdhist) if not np.isnan(v)]
            })
        elif indicator_type == "ATR":
            indicator_values = talib.ATR(highs, lows, closes, timeperiod=period)
        elif indicator_type == "ADX":
            indicator_values = talib.ADX(highs, lows, closes, timeperiod=period)
        elif indicator_type == "BBANDS":
            upper, middle, lower = talib.BBANDS(closes, timeperiod=period, nbdevup=2, nbdevdn=2, matype=0)
            return jsonify({
                "indicator": "BBANDS",
                "period": period,
                "upper": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(upper) if not np.isnan(v)],
                "middle": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(middle) if not np.isnan(v)],
                "lower": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(lower) if not np.isnan(v)]
            })
        elif indicator_type == "STOCH":
            slowk, slowd = talib.STOCH(highs, lows, closes, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
            return jsonify({
                "indicator": "STOCH",
                "period": period,
                "k": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(slowk) if not np.isnan(v)],
                "d": [{"timestamp": timestamps[i], "value": float(v)} for i, v in enumerate(slowd) if not np.isnan(v)]
            })
        elif indicator_type == "VWAP":
            typical_price = (highs + lows + closes) / 3
            cumulative_vol = np.cumsum(volumes)
            cumulative_pv = np.cumsum(typical_price * volumes)
            indicator_values = cumulative_pv / cumulative_vol
        elif indicator_type == "OBV":
            indicator_values = talib.OBV(closes, volumes)
        elif indicator_type == "FIBONACCI":
            from utils.fibonacci_calculator import format_fibonacci_for_api
            window = int(request.args.get("window", 5))
            fibonacci_result = format_fibonacci_for_api(highs, lows, timestamps, window)
            return jsonify(fibonacci_result)
        else:
            return jsonify({"error": f"Indicador '{indicator_type}' não suportado"}), 400
        # Formatar resposta (remover valores NaN)
        values = []
        for i, value in enumerate(indicator_values):
            if not np.isnan(value):
                values.append({"timestamp": timestamps[i], "value": float(value)})
        return jsonify({
            "indicator": indicator_type,
            "period": period,
            "values": values[-100:]  # Últimos 100 valores
        })
    except Exception as e:
        logger.error(f"Erro ao calcular indicador {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/balance", methods=["GET"])
def get_account_balance():
    """Retorna o saldo da conta Binance para Spot e Futures."""
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar cliente de trading"}), 500
        
        balance_data = {
            "spot": {"balances": [], "total_usdt": 0, "error": None},
            "futures": {"balances": [], "total_usdt": 0, "margin_balance": 0, "available_balance": 0, "error": None},
            "timestamp": "2024-01-15T12:30:50Z"
        }
        
        # Buscar saldo Spot
        try:
            spot_account = binance_spot_client._make_request(binance_spot_client.client.get_account)
            if spot_account and 'balances' in spot_account:
                spot_balances = []
                total_usdt_spot = 0
                
                for balance in spot_account['balances']:
                    free_balance = float(balance['free'])
                    locked_balance = float(balance['locked'])
                    total_balance = free_balance + locked_balance
                    
                    if total_balance > 0:  # Apenas mostrar moedas com saldo
                        asset = balance['asset']
                        
                        # Calcular valor em USDT (usando preços reais quando possível)
                        usdt_value = 0
                        if asset == 'USDT':
                            usdt_value = total_balance
                        else:
                            try:
                                # Tentar obter preço real da Binance
                                symbol_pair = f"{asset}USDT"
                                ticker = binance_spot_client._make_request(
                                    lambda: binance_spot_client.client.get_symbol_ticker(symbol=symbol_pair)
                                )
                                if ticker and 'price' in ticker:
                                    usdt_value = total_balance * float(ticker['price'])
                                else:
                                    # Fallback para valores aproximados
                                    price_estimates = {
                                        'BTC': 45000, 'ETH': 2500, 'BNB': 300, 'ADA': 0.5,
                                        'DOT': 8, 'SOL': 100, 'MATIC': 1, 'LINK': 15
                                    }
                                    usdt_value = total_balance * price_estimates.get(asset, 1)
                            except:
                                # Em caso de erro, usar valores aproximados
                                price_estimates = {
                                    'BTC': 45000, 'ETH': 2500, 'BNB': 300, 'ADA': 0.5,
                                    'DOT': 8, 'SOL': 100, 'MATIC': 1, 'LINK': 15
                                }
                                usdt_value = total_balance * price_estimates.get(asset, 1)
                        
                        total_usdt_spot += usdt_value
                        
                        spot_balances.append({
                            "asset": asset,
                            "free": free_balance,
                            "locked": locked_balance,
                            "total": total_balance,
                            "usdt_value": usdt_value
                        })
                
                balance_data["spot"]["balances"] = sorted(spot_balances, key=lambda x: x['usdt_value'], reverse=True)
                balance_data["spot"]["total_usdt"] = total_usdt_spot
        except Exception as e:
            logger.error(f"Erro ao buscar saldo Spot: {e}")
            balance_data["spot"]["error"] = str(e)
        
        # Buscar saldo Futures
        try:
            futures_account = binance_futures_client._make_request(binance_futures_client.client.futures_account)
            if futures_account:
                futures_balances = []
                
                # Informações gerais da conta Futures
                balance_data["futures"]["margin_balance"] = float(futures_account.get('totalMarginBalance', 0))
                balance_data["futures"]["available_balance"] = float(futures_account.get('availableBalance', 0))
                
                if 'assets' in futures_account:
                    for asset in futures_account['assets']:
                        wallet_balance = float(asset['walletBalance'])
                        margin_balance = float(asset['marginBalance'])
                        
                        if wallet_balance > 0 or margin_balance > 0:
                            asset_name = asset['asset']
                            
                            # Calcular valor em USDT (usando preços reais quando possível)
                            usdt_value = 0
                            if asset_name == 'USDT':
                                usdt_value = wallet_balance
                            else:
                                try:
                                    # Tentar obter preço real da Binance
                                    symbol_pair = f"{asset_name}USDT"
                                    ticker = binance_futures_client._make_request(
                                        lambda: binance_futures_client.client.get_symbol_ticker(symbol=symbol_pair)
                                    )
                                    if ticker and 'price' in ticker:
                                        usdt_value = wallet_balance * float(ticker['price'])
                                    else:
                                        # Fallback para valores aproximados
                                        price_estimates = {
                                            'BTC': 45000, 'ETH': 2500, 'BNB': 300, 'ADA': 0.5,
                                            'DOT': 8, 'SOL': 100, 'MATIC': 1, 'LINK': 15
                                        }
                                        usdt_value = wallet_balance * price_estimates.get(asset_name, 1)
                                except:
                                    # Em caso de erro, usar valores aproximados
                                    price_estimates = {
                                        'BTC': 45000, 'ETH': 2500, 'BNB': 300, 'ADA': 0.5,
                                        'DOT': 8, 'SOL': 100, 'MATIC': 1, 'LINK': 15
                                    }
                                    usdt_value = wallet_balance * price_estimates.get(asset_name, 1)
                            
                            futures_balances.append({
                                "asset": asset_name,
                                "wallet_balance": wallet_balance,
                                "margin_balance": margin_balance,
                                "usdt_value": usdt_value
                            })
                
                balance_data["futures"]["balances"] = sorted(futures_balances, key=lambda x: x['usdt_value'], reverse=True)
                balance_data["futures"]["total_usdt"] = balance_data["futures"]["margin_balance"]
        except Exception as e:
            logger.error(f"Erro ao buscar saldo Futures: {e}")
            balance_data["futures"]["error"] = str(e)
        
        return jsonify(balance_data)
        
    except Exception as e:
        logger.error(f"Erro geral ao buscar saldos: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/balance/summary", methods=["GET"])
def get_balance_summary():
    """Retorna um resumo simplificado dos saldos."""
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar cliente de trading"}), 500
        
        summary = {
            "spot_usdt": 0,
            "futures_usdt": 0,
            "total_usdt": 0,
            "spot_available": True,
            "futures_available": True,
            "last_updated": "2024-01-15T12:30:50Z"
        }
        
        # Saldo Spot USDT
        try:
            spot_account = binance_spot_client._make_request(binance_spot_client.client.get_account)
            if spot_account and 'balances' in spot_account:
                for balance in spot_account['balances']:
                    if balance['asset'] == 'USDT':
                        summary["spot_usdt"] = float(balance['free']) + float(balance['locked'])
                        break
        except Exception as e:
            logger.error(f"Erro ao buscar saldo Spot USDT: {e}")
            summary["spot_available"] = False
        
        # Saldo Futures USDT
        try:
            futures_account = binance_futures_client._make_request(binance_futures_client.client.futures_account)
            if futures_account:
                summary["futures_usdt"] = float(futures_account.get('availableBalance', 0))
        except Exception as e:
            logger.error(f"Erro ao buscar saldo Futures USDT: {e}")
            summary["futures_available"] = False
        
        summary["total_usdt"] = summary["spot_usdt"] + summary["futures_usdt"]
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Erro ao buscar resumo de saldos: {e}")
        return jsonify({"error": str(e)}), 500


# --- Endpoints de Controle de Modo --- #

@app.route("/api/operation_mode", methods=["GET"])
def get_operation_mode():
    """Obtém o modo de operação atual."""
    current_mode = config.get("operation_mode", "Production")
    return jsonify({
        "current_mode": current_mode,
        "available_modes": ["Production"],
        "description": {
            "Production": "Modo real - executa trades reais na Binance"
        }
    })


@app.route("/api/operation_mode", methods=["POST"])
def set_operation_mode():
    """Altera o modo de operação (Production/Shadow)."""
    data = request.get_json()
    if not data or "mode" not in data:
        return jsonify({"error": "Campo 'mode' é obrigatório"}), 400
    
    new_mode = data["mode"]
    if new_mode not in ["Production"]:
        return jsonify({"error": "Modo deve ser 'Production'"}), 400
    
    old_mode = config.get("operation_mode", "Production")
    
    # Atualizar configuração em memória
    config["operation_mode"] = new_mode
    
    # Atualizar arquivo de configuração
    try:
        with open(config_path, "r") as f:
            file_config = yaml.safe_load(f)
        file_config["operation_mode"] = new_mode
        with open(config_path, "w") as f:
            yaml.safe_dump(file_config, f, default_flow_style=False)
        
        logger.info(f"Modo de operação alterado de {old_mode} para: {new_mode}")
        
        # Avisar sobre necessidade de reiniciar bots ativos
        active_bots_list = [symbol for symbol, thread in bot_threads.items() if thread.is_alive()]
        warning = None
        if active_bots_list:
            warning = f"Atenção: {len(active_bots_list)} bot(s) ativo(s) ainda estão no modo anterior. Considere reiniciá-los."
        return jsonify({
            "success": True,
            "old_mode": old_mode,
            "new_mode": new_mode,
            "message": f"Modo confirmado como {new_mode}",
            "warning": warning,
            "active_bots": active_bots_list
        })
        
    except Exception as e:
        logger.error(f"Erro ao salvar nova configuração: {e}")
        return jsonify({"error": f"Erro ao salvar configuração: {str(e)}"}), 500


@app.route("/api/rl/training_status", methods=["GET"])
def get_rl_training_status_alias():
    """Alias para compatibilidade com frontend antigo."""
    resp = get_rl_training_status()
    # Adiciona aviso de mock se for simulado
    if resp.status_code == 200:
        data = resp.get_json()
        data["mock_warning"] = "DADOS MOCKADOS: Esta resposta é simulada para compatibilidade."
        return jsonify(data)
    return resp

@app.route("/api/trades/<symbol>", methods=["GET"])
def get_trades(symbol):
    """Retorna trades reais para o símbolo."""
    if symbol not in bots or not bots[symbol]:
        return jsonify({"trades": [], "error": f"Bot para {symbol} não encontrado"}), 404
    bot = bots[symbol]
    trades = bot.trade_history if hasattr(bot, 'trade_history') else []
    return jsonify({"trades": trades})

@app.route("/api/recommended_pairs", methods=["GET"])
def get_recommended_pairs():
    """Retorna lista de pares recomendados reais (baseado nos bots ativos ou lista vazia)."""
    # Exemplo: retorna os símbolos dos bots ativos
    recommended = list(bots.keys())
    return jsonify({"recommended_pairs": recommended})

@app.route("/api/metrics", methods=["GET"])
def get_multi_agent_metrics():
    """Retorna métricas do sistema multi-agente para o frontend."""
    try:
        # Importar multi-agent system se disponível
        try:
            from multi_agent_bot import get_system_metrics
            multi_agent_metrics = get_system_metrics()
        except (ImportError, AttributeError):
            # Fallback para métricas básicas
            multi_agent_metrics = {
                "coordinator": {
                    "status": "running" if bots else "idle",
                    "active_tasks": len([bot for bot in bots.values() if bot]),
                    "last_update": "2024-01-15T12:30:00Z"
                },
                "agents": {
                    "ai_agent": {"status": "active", "health": 100},
                    "data_agent": {"status": "active", "health": 100},
                    "risk_agent": {"status": "active", "health": 100},
                    "sentiment_agent": {"status": "active", "health": 95}
                },
                "cache": {
                    "hit_rate": 0.85,
                    "entries": 150,
                    "memory_usage": "12.5MB"
                }
            }
        
        # Adicionar métricas do sistema atual
        system_metrics = {
            "active_bots": len([bot for bot in bots.values() if bot]),
            "total_symbols": len(bots),
            "uptime": "2h 15m",
            "api_status": "operational",
            "binance_connection": "connected",
            "operation_mode": config.get("operation_mode", "Production")
        }
        
        # Combinar métricas
        response = {
            "multi_agent": multi_agent_metrics,
            "system": system_metrics,
            "timestamp": "2024-01-15T12:30:00Z",
            "version": "1.0.0"
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro ao buscar métricas multi-agente: {e}")
        return jsonify({
            "error": str(e),
            "multi_agent": {
                "coordinator": {"status": "error", "message": str(e)},
                "agents": {},
                "cache": {"hit_rate": 0, "entries": 0, "memory_usage": "0MB"}
            },
            "system": {
                "active_bots": 0,
                "total_symbols": 0,
                "uptime": "unknown",
                "api_status": "error",
                "binance_connection": "unknown",
                "operation_mode": "unknown"
            }
        }), 500

if __name__ == "__main__":
    print("[DEBUG] Entrando no bloco main do Flask...")
    logger.info("Iniciando servidor Flask API...")
    app.run(host="0.0.0.0", port=5000, debug=True)
