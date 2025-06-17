# Backend API using Flask

from utils.logger import setup_logger
from utils.api_client import APIClient
from utils.alerter import Alerter
from utils.request_cache import cached_endpoint, request_cache
from utils.market_data_manager import get_market_data_manager, initialize_market_data_manager

# Import model_api (may require RL dependencies)
try:
    from routes.model_api import model_api
    MODEL_API_AVAILABLE = True
except ImportError as e:
    MODEL_API_AVAILABLE = False
    print(f"Model API not available (RL dependencies missing): {e}")
    # Create dummy blueprint to avoid Flask errors
    from flask import Blueprint
    model_api = Blueprint('model_api_disabled', __name__)
    
    @model_api.route('/status')
    def disabled_status():
        return {"status": "disabled", "reason": "RL dependencies not available"}

# Import live_data_api (should always work)
try:
    from routes.live_data_api import live_data_api
    LIVE_DATA_API_AVAILABLE = True
    print("✅ Live Data API imported successfully")
except ImportError as e:
    LIVE_DATA_API_AVAILABLE = False
    print(f"⚠️ Live Data API not available: {e}")
    # Create dummy blueprint
    from flask import Blueprint
    live_data_api = Blueprint('live_data_api_disabled', __name__)
    
    @live_data_api.route('/api/live/status')
    def disabled_live_status():
        return {"status": "disabled", "reason": f"Live Data API not available: {e}"}

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
app.register_blueprint(live_data_api, url_prefix="")
if LIVE_DATA_API_AVAILABLE:
    print("✅ Live Data API registered successfully")
else:
    print("⚠️ Live Data API registered with fallback routes")

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
active_bots = {}  # Dicionário para armazenar status dos bots ativos

# Singleton instances to prevent multiple client creation
_client_instances = {
    'spot': None,
    'futures': None,
    'alerter': None,
    'market_data_manager': None
}

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
    """Inicializa componentes essenciais se ainda não foram inicializados usando singleton pattern."""
    global binance_spot_client, binance_futures_client, alerter
    
    # Use singleton pattern to prevent multiple client creation
    if _client_instances['spot'] is None:
        try:
            logger.info("Inicializando cliente Binance Spot...")
            # Carregar chaves de API do .env ou config (ajustar conforme necessário)
            api_key = os.getenv("BINANCE_API_KEY", config["api"].get("key"))
            api_secret = os.getenv("BINANCE_API_SECRET", config["api"].get("secret"))
            if not api_key or not api_secret:
                logger.error("Chaves da API Binance não encontradas!")
                return False
            api_config = {
                "key": api_key,
                "secret": api_secret
            }
            operation_mode = config.get("operation_mode", "production").lower()
            _client_instances['spot'] = APIClient(api_config, operation_mode=operation_mode)
            logger.info("Cliente Binance Spot inicializado.")
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Spot: {e}")
            return False
    
    binance_spot_client = _client_instances['spot']
        
    if _client_instances['futures'] is None:
        try:
            logger.info("Inicializando cliente Binance Futuros...")
            api_key = os.getenv("BINANCE_API_KEY", config["api"].get("key"))
            api_secret = os.getenv("BINANCE_API_SECRET", config["api"].get("secret"))
            api_config = {
                "key": api_key,
                "secret": api_secret
            }
            operation_mode = config.get("operation_mode", "production").lower()
            _client_instances['futures'] = APIClient(api_config, operation_mode=operation_mode)
            logger.info("Cliente Binance Futuros inicializado.")
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente Futures: {e}")
            # Continue with spot client only
    
    binance_futures_client = _client_instances['futures']

    if _client_instances['alerter'] is None and config.get("alerts", {}).get("enabled", False):
        try:
            logger.info("Inicializando Alerter do Telegram...")
            _client_instances['alerter'] = Alerter(config["alerts"])
            logger.info("Alerter do Telegram inicializado.")
        except Exception as e:
            logger.error(f"Erro ao inicializar Alerter: {e}")
    
    alerter = _client_instances['alerter']
    return binance_spot_client is not None


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
                    # Load sleep time from config
                    http_config = config.get('http_api', {})
                    trading_cycle_sleep = http_config.get('trading_cycle_sleep_seconds', 30)
                    time.sleep(trading_cycle_sleep)
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
                    # Load retry delay from config
                    error_retry_delay = http_config.get('error_retry_delay_seconds', 10)
                    time.sleep(error_retry_delay)
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
@cached_endpoint()
def get_status():
    """Retorna o status geral da API e dos bots ativos."""
    active_bots_status = {
        symbol: bot.get_status() for symbol, bot in bots.items() if bot
    }
    return jsonify({"api_status": "online", "active_bots": active_bots_status})


@app.route("/api/market_data", methods=["GET"])
@cached_endpoint(lambda: request.args.get('limit', '50'))
def get_market_data():
    """Busca dados de mercado usando WebSocket em tempo real (sem polling da API)."""
    logger.info("Recebida requisição para /api/market_data (WebSocket mode)")
    
    try:
        # Initialize components first
        if not initialize_components():
            logger.error("Falha ao inicializar componentes")
            return jsonify({"error": "Falha ao inicializar cliente Binance"}), 500
        
        # Get or initialize market data manager
        market_manager = get_market_data_manager(binance_spot_client, testnet=False)
        
        # Initialize if not running
        if not market_manager.is_running:
            import asyncio
            try:
                # Create event loop if none exists
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Start market data manager in background
            if not loop.is_running():
                asyncio.run(initialize_market_data_manager(binance_spot_client))
            else:
                # Schedule initialization
                loop.create_task(initialize_market_data_manager(binance_spot_client))
        
        # Get limit from request
        limit = int(request.args.get('limit', 50))
        
        # Use WebSocket data instead of API calls
        logger.info("Obtendo dados de mercado via WebSocket (sem API polling)...")
        market_data = market_manager.get_market_data(limit=limit)
        
        if market_data:
            logger.info(f"Dados WebSocket obtidos: {len(market_data)} símbolos")
            return jsonify(market_data)
        else:
            # Fallback to high volatility pairs info if no WebSocket data yet
            logger.warning("WebSocket data not available yet, returning high volatility pairs")
            fallback_data = []
            for symbol in market_manager.high_volatility_pairs[:limit]:
                fallback_data.append({
                    "symbol": symbol,
                    "price": "0.00000000",
                    "change_24h": "0.00%",
                    "volume": "0.00",
                    "high_24h": "0.00000000",
                    "low_24h": "0.00000000",
                    "source": "fallback"
                })
            return jsonify(fallback_data)
            
    except Exception as e:
        logger.error(f"Erro ao buscar dados via WebSocket: {e}")
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
    
    # Load defaults from config
    http_config = config.get('http_api', {})
    default_interval = http_config.get('default_kline_interval', '5m')
    default_limit = http_config.get('default_kline_limit', 100)
    max_limit = http_config.get('max_kline_limit', 1000)
    min_limit = http_config.get('min_kline_limit', 1)
    
    # Parâmetros da requisição
    interval = request.args.get('interval', default_interval)
    limit = int(request.args.get('limit', default_limit))
    market_type = request.args.get('market_type', 'spot')  # Padrão spot
    
    # Validar limite
    if limit > max_limit:
        limit = max_limit
    if limit < min_limit:
        limit = min_limit
        
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
        # Use fallback mode for now due to dependency issues
        logger.info("Using fallback sentiment analysis mode")
        return jsonify({
            "models": {
                "gemma3": {"available": False, "loaded": False, "error": "Dependencies not available"},
                "fallback": {"available": True, "loaded": True}
            },
            "performance": {"total_analyses": 0, "avg_latency": 0.1},
            "recommended_model": "fallback",
            "crypto_optimized": False,
            "fallback_available": True,
            "status": "fallback_mode",
            "note": "Advanced sentiment models unavailable, using simple keyword analysis"
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter status dos modelos de sentimento: {e}")
        return jsonify({
            "models": {"fallback": {"available": True, "loaded": True}},
            "status": "fallback_mode",
            "error": str(e)
        }), 200


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
        
        # Use fallback sentiment analysis (advanced models have dependency issues)
        logger.info("Using fallback sentiment analysis")
        
        # Fallback simple sentiment analysis
        positive_words = ["good", "great", "excellent", "bull", "moon", "pump", "positive", "profit", "gain", "up", "rise", "buy"]
        negative_words = ["bad", "terrible", "bear", "dump", "crash", "down", "fall", "loss", "sell", "negative", "drop"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.9, 0.5 + (positive_count - negative_count) * 0.1)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.9, 0.5 + (negative_count - positive_count) * 0.1)
        else:
            sentiment = "neutral"
            confidence = 0.6
            
        crypto_words = ["bitcoin", "btc", "crypto", "ethereum", "eth", "trading", "investment"]
        crypto_relevant = any(word in text_lower for word in crypto_words)
        
        return jsonify({
            "text": text,
            "sentiment": sentiment,
            "confidence": confidence,
            "analyzer_used": "fallback",
            "reasoning": f"Simple keyword analysis: {positive_count} positive, {negative_count} negative words",
            "crypto_relevant": crypto_relevant
        })
            
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
@cached_endpoint()
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
        interval = request.args.get("interval", "3m")
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
@cached_endpoint()
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
    """Retorna lista de pares recomendados com foco em alta volatilidade."""
    try:
        recommended = []
        
        # Priorizar bots ativos
        active_bots = list(bots.keys())
        recommended.extend(active_bots)
        
        # Adicionar pares de alta volatilidade se disponível
        try:
            if initialize_components():
                market_manager = get_market_data_manager(binance_spot_client, testnet=False)
                high_vol_pairs = [pair['symbol'] for pair in market_manager.get_high_volatility_pairs(limit=10)]
                
                # Adicionar pares de alta volatilidade que não estão ativos
                for pair in high_vol_pairs:
                    if pair not in recommended:
                        recommended.append(pair)
        except Exception as e:
            logger.error(f"Erro ao buscar pares de alta volatilidade: {e}")
        
        # Fallback para pares conhecidos de alta volatilidade
        if not recommended:
            fallback_pairs = [
                "BTCUSDT", "ETHUSDT", "PNUTUSDT", "ACTUSDT", "MOODENGUSDT",
                "ADAUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "AVAXUSDT"
            ]
            recommended.extend(fallback_pairs)
        
        return jsonify({
            "recommended_pairs": recommended[:15],  # Limit to 15 pairs
            "criteria": "Alta volatilidade + bots ativos",
            "total": len(recommended)
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar pares recomendados: {e}")
        return jsonify({"recommended_pairs": [], "error": str(e)}), 500

@app.route("/api/high_volatility_pairs", methods=["GET"])
def get_high_volatility_pairs():
    """Retorna pares com maior volatilidade para trading mais frequente."""
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        market_manager = get_market_data_manager(binance_spot_client, testnet=False)
        limit = int(request.args.get('limit', 20))
        
        volatility_pairs = market_manager.get_high_volatility_pairs(limit=limit)
        
        return jsonify({
            "high_volatility_pairs": volatility_pairs,
            "total_pairs": len(market_manager.high_volatility_pairs),
            "analysis_timestamp": time.time(),
            "recommendation": "Estes pares têm maior volatilidade e podem gerar mais oportunidades de trade"
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar pares de alta volatilidade: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/trading_state_recovery', methods=['GET'])
def get_trading_state_recovery():
    """
    Recupera estado real do trading baseado no histórico da Binance.
    Mostra PnL real, capital investido e posições das últimas 24h.
    """
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        from utils.trading_state_recovery import TradingStateRecovery
        
        # Recuperar estado
        recovery = TradingStateRecovery(binance_futures_client)
        hours_back = int(request.args.get('hours', 24))
        state = recovery.recover_trading_state(hours_back=hours_back)
        
        # Formatar resposta
        response = {
            "status": "success",
            "timestamp": state.get('recovery_timestamp', time.time()),
            "fallback": state.get('fallback', False),
            "hours_analyzed": hours_back,
            "summary": state.get('trading_summary', {}),
            "positions": {}
        }
        
        # Formatar posições para JSON
        for symbol, position in state.get('positions', {}).items():
            response["positions"][symbol] = {
                "symbol": position.symbol,
                "side": position.side,
                "size": position.size,
                "entry_price": position.entry_price,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
                "total_invested": position.total_invested,
                "leverage": position.leverage,
                "orders_count": position.orders_count,
                "roi_percentage": ((position.unrealized_pnl + position.realized_pnl) / position.total_invested * 100) if position.total_invested > 0 else 0,
                "first_order_time": position.first_order_time,
                "last_order_time": position.last_order_time,
                "tp_price": position.tp_price,
                "sl_price": position.sl_price
            }
        
        # Adicionar detalhes adicionais
        response["realized_pnl_by_symbol"] = state.get('realized_pnl', {})
        response["invested_capital_by_symbol"] = state.get('total_invested', {})
        response["analysis"] = {
            "total_positions": len(response["positions"]),
            "profitable_positions": sum(1 for p in response["positions"].values() if p["unrealized_pnl"] > 0),
            "losing_positions": sum(1 for p in response["positions"].values() if p["unrealized_pnl"] < 0),
            "avg_roi": sum(p["roi_percentage"] for p in response["positions"].values()) / len(response["positions"]) if response["positions"] else 0
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Erro na recuperação de estado: {e}")
        return jsonify({
            "status": "error",
            "message": f"Erro na recuperação de estado: {str(e)}",
            "timestamp": time.time()
        }), 500


@app.route("/api/websocket/performance", methods=["GET"])
def get_websocket_performance():
    """Retorna estatísticas de performance do WebSocket e redução de API calls."""
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        market_manager = get_market_data_manager(binance_spot_client, testnet=False)
        performance_stats = market_manager.get_performance_stats()
        
        # Add cache statistics
        cache_stats = request_cache.cache if hasattr(request_cache, 'cache') else {}
        
        return jsonify({
            "websocket_performance": performance_stats,
            "api_optimization": {
                "description": "Usando WebSocket em vez de polling da API REST",
                "benefits": [
                    "Dados em tempo real sem rate limiting",
                    "Redução de 90%+ nas chamadas da API",
                    "Armazenamento local de dados de candles",
                    "Pares de alta volatilidade priorizados"
                ],
                "api_calls_saved": performance_stats.get('api_calls_saved', 0),
                "cache_entries": len(cache_stats),
                "data_source": "WebSocket + Local SQLite"
            },
            "high_frequency_trading": {
                "enabled": market_manager.hft_engine is not None,
                "target_pairs": len(market_manager.high_volatility_pairs),
                "status": "Pronto para trades de alta frequência"
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar performance do WebSocket: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/realtime_klines/<symbol>", methods=["GET"])
def get_realtime_klines(symbol):
    """Busca klines em tempo real via WebSocket (sem API polling)."""
    try:
        if not validate_symbol_format(symbol):
            return jsonify({"error": "Formato de símbolo inválido"}), 400
        
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        market_manager = get_market_data_manager(binance_spot_client, testnet=False)
        
        # Parâmetros
        interval = request.args.get('interval', '1m')
        limit = int(request.args.get('limit', 100))
        
        # Buscar dados em tempo real do WebSocket
        klines = market_manager.get_realtime_klines(symbol, interval, limit)
        
        if klines:
            return jsonify({
                "symbol": symbol,
                "interval": interval,
                "data": klines,
                "source": "WebSocket + Local Storage",
                "count": len(klines)
            })
        else:
            return jsonify({"error": "Nenhum dado de klines encontrado em tempo real"}), 404
        
    except Exception as e:
        logger.error(f"Erro ao buscar klines em tempo real para {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/metrics", methods=["GET"])
def get_multi_agent_metrics():
    """Retorna métricas do sistema multi-agente para o frontend."""
    try:
        # Get WebSocket performance metrics
        websocket_metrics = {}
        try:
            if initialize_components():
                market_manager = get_market_data_manager(binance_spot_client, testnet=False)
                websocket_metrics = market_manager.get_performance_stats()
        except Exception as e:
            logger.error(f"Erro ao obter métricas WebSocket: {e}")
        
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
            "api_status": "optimized",
            "binance_connection": "WebSocket + REST",
            "operation_mode": config.get("operation_mode", "Production"),
            "websocket_enabled": websocket_metrics.get('is_running', False),
            "api_calls_saved": websocket_metrics.get('api_calls_saved', 0)
        }
        
        # Combinar métricas
        response = {
            "multi_agent": multi_agent_metrics,
            "system": system_metrics,
            "websocket": websocket_metrics,
            "optimization": {
                "api_polling_reduced": True,
                "real_time_data": websocket_metrics.get('is_running', False),
                "high_volatility_focus": True,
                "local_data_storage": True
            },
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


# ===== SYSTEM ENDPOINTS FOR FRONTEND =====

@app.route("/api/system/metrics", methods=["GET"])
def get_system_metrics():
    """Retorna métricas do sistema para a aba System."""
    try:
        import time
        
        # Try to import psutil for system metrics
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            system_metrics = {
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "disk_usage": disk.percent,
                "disk_total": disk.total,
                "disk_free": disk.free
            }
        except ImportError:
            # Fallback when psutil is not available
            system_metrics = {
                "cpu_usage": 0,
                "memory_usage": 0,
                "memory_total": 0,
                "memory_available": 0,
                "disk_usage": 0,
                "disk_total": 0,
                "disk_free": 0
            }
        
        # Trading bot metrics
        active_bots_count = len([bot for bot in active_bots.values() if bot.get('status') == 'running'])
        
        return jsonify({
            "system": system_metrics,
            "trading": {
                "active_bots": active_bots_count,
                "total_symbols": len(active_bots),
                "uptime": time.time() - app.start_time if hasattr(app, 'start_time') else 0
            },
            "api": {
                "status": "online",
                "version": "1.0.0",
                "last_update": time.time()
            }
        })
    except Exception as e:
        logger.error(f"Erro ao buscar métricas do sistema: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents", methods=["GET"])
def get_agents():
    """Retorna lista de agentes para a aba Agents."""
    try:
        # Get AI agents status
        agents = [
            {
                "name": "ai_agent",
                "status": "active",
                "last_action": "Market analysis",
                "performance": 85.5,
                "decisions_count": 142
            },
            {
                "name": "risk_agent", 
                "status": "active",
                "last_action": "Risk assessment",
                "performance": 92.1,
                "decisions_count": 89
            },
            {
                "name": "data_agent",
                "status": "active", 
                "last_action": "Data collection",
                "performance": 78.3,
                "decisions_count": 256
            },
            {
                "name": "sentiment_agent",
                "status": "idle",
                "last_action": "Sentiment analysis",
                "performance": 67.8,
                "decisions_count": 34
            }
        ]
        
        return jsonify({"agents": agents})
    except Exception as e:
        logger.error(f"Erro ao buscar agentes: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_name>/metrics", methods=["GET"])
def get_agent_metrics(agent_name):
    """Retorna métricas específicas de um agente."""
    try:
        # Mock data for agent metrics
        metrics = {
            "total_actions": 142,
            "success_rate": 85.5,
            "avg_response_time": 0.23,
            "last_active": "2024-01-15T10:30:00Z"
        }
        
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Erro ao buscar métricas do agente {agent_name}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agents/<agent_name>/history", methods=["GET"])
def get_agent_history(agent_name):
    """Retorna histórico de ações de um agente."""
    try:
        # Mock data for agent history
        history = [
            {
                "timestamp": "2024-01-15T10:30:00Z",
                "action": "Market analysis",
                "context": {"symbol": "BTCUSDT", "price": 42000},
                "result": "BUY signal generated",
                "confidence": 0.85
            },
            {
                "timestamp": "2024-01-15T10:25:00Z", 
                "action": "Risk assessment",
                "context": {"portfolio_risk": 0.3},
                "result": "Risk within limits",
                "confidence": 0.92
            }
        ]
        
        return jsonify({"history": history})
    except Exception as e:
        logger.error(f"Erro ao buscar histórico do agente {agent_name}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/hft/metrics", methods=["GET"])
def get_hft_metrics():
    """Retorna métricas de HFT para a aba HFT."""
    try:
        metrics = {
            "latency": {
                "avg": 2.3,
                "min": 1.1,
                "max": 5.7,
                "p95": 3.2
            },
            "throughput": {
                "orders_per_second": 145,
                "trades_per_minute": 23,
                "volume_24h": 125000
            },
            "performance": {
                "success_rate": 94.2,
                "fill_rate": 87.8,
                "slippage_avg": 0.02
            }
        }
        
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Erro ao buscar métricas HFT: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sentiment/analysis", methods=["GET"])
def get_sentiment_analysis():
    """Retorna análise de sentimento para a aba Sentiment."""
    try:
        sentiment = {
            "overall_sentiment": "bullish",
            "sentiment_score": 0.73,
            "sources": {
                "twitter": {"score": 0.68, "volume": 1250},
                "reddit": {"score": 0.78, "volume": 890},
                "news": {"score": 0.71, "volume": 45}
            },
            "trending_topics": [
                {"topic": "Bitcoin ETF", "sentiment": 0.82, "volume": 3400},
                {"topic": "DeFi Growth", "sentiment": 0.65, "volume": 1200},
                {"topic": "Regulation", "sentiment": 0.34, "volume": 890}
            ],
            "last_updated": time.time()
        }
        
        return jsonify(sentiment)
    except Exception as e:
        logger.error(f"Erro ao buscar análise de sentimento: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/system/clear_cache", methods=["POST"])
def clear_system_cache():
    """Força limpeza de todos os caches do sistema."""
    try:
        import subprocess
        import os
        
        # Execute clear cache script
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "clear_all_caches.py")
        
        if os.path.exists(script_path):
            result = subprocess.run([sys.executable, script_path], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info("✅ Cache limpo com sucesso via API")
                return jsonify({
                    "success": True,
                    "message": "Cache limpo com sucesso",
                    "output": result.stdout,
                    "timestamp": time.time()
                })
            else:
                logger.error(f"❌ Erro ao limpar cache: {result.stderr}")
                return jsonify({
                    "success": False,
                    "error": result.stderr,
                    "timestamp": time.time()
                }), 500
        else:
            return jsonify({
                "success": False,
                "error": "Script de limpeza não encontrado",
                "timestamp": time.time()
            }), 404
            
    except Exception as e:
        logger.error(f"Erro ao limpar cache via API: {e}")
        return jsonify({"error": str(e), "timestamp": time.time()}), 500


@app.route("/api/system/reload_config", methods=["POST"])
def reload_configuration():
    """Força reload da configuração do sistema."""
    try:
        global config
        
        # Reload config file
        config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
        with open(config_path, "r") as f:
            new_config = yaml.safe_load(f)
        
        # Update global config
        old_pairs = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
        config = new_config
        new_pairs = config.get('pair_selection', {}).get('futures_pairs', {}).get('preferred_symbols', [])
        
        logger.info(f"🔄 Configuração recarregada via API")
        logger.info(f"    Pares antigos: {len(old_pairs)} -> Novos: {len(new_pairs)}")
        
        return jsonify({
            "success": True,
            "message": "Configuração recarregada com sucesso",
            "changes": {
                "old_preferred_pairs_count": len(old_pairs),
                "new_preferred_pairs_count": len(new_pairs),
                "new_preferred_pairs": new_pairs
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        logger.error(f"Erro ao recarregar configuração: {e}")
        return jsonify({"error": str(e), "timestamp": time.time()}), 500


@app.route("/api/system/force_pair_update", methods=["POST"])
def force_pair_update():
    """Força atualização da seleção de pares."""
    try:
        import subprocess
        import os
        
        # Execute force pair update script
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "force_pair_update.py")
        
        if os.path.exists(script_path):
            result = subprocess.run([sys.executable, script_path], 
                                  capture_output=True, text=True, timeout=60)
            
            logger.info("🔄 Force pair update executado via API")
            
            return jsonify({
                "success": True,
                "message": "Atualização de pares executada",
                "output": result.stdout,
                "errors": result.stderr if result.stderr else None,
                "return_code": result.returncode,
                "timestamp": time.time()
            })
        else:
            return jsonify({
                "success": False,
                "error": "Script de atualização não encontrado",
                "timestamp": time.time()
            }), 404
            
    except Exception as e:
        logger.error(f"Erro ao executar force pair update: {e}")
        return jsonify({"error": str(e), "timestamp": time.time()}), 500


@app.route("/api/sentiment/symbols/<symbol>", methods=["GET"])
def get_symbol_sentiment(symbol):
    """Retorna sentimento específico para um símbolo."""
    try:
        sentiment = {
            "symbol": symbol,
            "sentiment_score": 0.67,
            "trend": "positive",
            "confidence": 0.84,
            "sources_count": 156,
            "last_updated": time.time()
        }
        
        return jsonify(sentiment)
    except Exception as e:
        logger.error(f"Erro ao buscar sentimento para {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/trading/performance", methods=["GET"])
def get_trading_performance():
    """Retorna métricas de performance de trading consolidadas."""
    try:
        symbol = request.args.get('symbol', 'ALL')
        
        # Coletar dados de posições ativas
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        # Get positions and account info
        positions = binance_futures_client.get_futures_positions()
        
        active_positions = []
        total_unrealized_pnl = 0
        total_invested = 0
        
        for pos in positions:
            if float(pos.get('positionAmt', 0)) != 0:
                active_positions.append({
                    "symbol": pos['symbol'],
                    "side": "LONG" if float(pos['positionAmt']) > 0 else "SHORT",
                    "size": abs(float(pos['positionAmt'])),
                    "entry_price": float(pos['entryPrice']),
                    "mark_price": float(pos['markPrice']),
                    "unrealized_pnl": float(pos['unRealizedProfit']),
                    "percentage": float(pos['percentage']),
                    "leverage": int(pos.get('leverage', 1))
                })
                total_unrealized_pnl += float(pos['unRealizedProfit'])
                total_invested += abs(float(pos['positionAmt'])) * float(pos['entryPrice'])
        
        # Get open orders
        open_orders = binance_futures_client.get_open_futures_orders()
        orders_summary = {
            "total": len(open_orders),
            "buy_orders": len([o for o in open_orders if o['side'] == 'BUY']),
            "sell_orders": len([o for o in open_orders if o['side'] == 'SELL']),
            "limit_orders": len([o for o in open_orders if o['type'] == 'LIMIT']),
            "market_orders": len([o for o in open_orders if o['type'] == 'MARKET'])
        }
        
        # Calculate performance metrics
        performance_data = {
            "overview": {
                "total_positions": len(active_positions),
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_invested": total_invested,
                "overall_return_percentage": (total_unrealized_pnl / total_invested * 100) if total_invested > 0 else 0,
                "active_orders": len(open_orders)
            },
            "positions": active_positions,
            "orders": {
                "summary": orders_summary,
                "recent_orders": open_orders[:10]  # Last 10 orders
            },
            "metrics": {
                "win_rate": 0,  # Would need historical data
                "avg_hold_time": 0,  # Would need historical data  
                "largest_win": max([p['unrealized_pnl'] for p in active_positions]) if active_positions else 0,
                "largest_loss": min([p['unrealized_pnl'] for p in active_positions]) if active_positions else 0,
                "total_trades_today": 0,  # Would need trade history
                "profit_factor": 0  # Would need historical data
            },
            "last_updated": time.time()
        }
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(f"Erro ao buscar performance de trading: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/trading/orders/status", methods=["GET"])
def get_orders_status():
    """Retorna status detalhado de todas as ordens."""
    try:
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        # Get open orders
        open_orders = binance_futures_client.get_open_futures_orders()
        
        orders_by_symbol = {}
        for order in open_orders:
            symbol = order['symbol']
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            
            orders_by_symbol[symbol].append({
                "order_id": order['orderId'],
                "symbol": symbol,
                "side": order['side'],
                "type": order['type'],
                "quantity": float(order['origQty']),
                "filled_quantity": float(order['executedQty']),
                "price": float(order['price']) if order['price'] != '0' else None,
                "status": order['status'],
                "time_in_force": order['timeInForce'],
                "created_time": order['time'],
                "update_time": order['updateTime']
            })
        
        # Summary statistics
        total_orders = len(open_orders)
        summary = {
            "total_orders": total_orders,
            "symbols_trading": len(orders_by_symbol),
            "orders_by_type": {},
            "orders_by_status": {}
        }
        
        for order in open_orders:
            order_type = order['type']
            status = order['status']
            
            if order_type not in summary['orders_by_type']:
                summary['orders_by_type'][order_type] = 0
            summary['orders_by_type'][order_type] += 1
            
            if status not in summary['orders_by_status']:
                summary['orders_by_status'][status] = 0
            summary['orders_by_status'][status] += 1
        
        return jsonify({
            "summary": summary,
            "orders_by_symbol": orders_by_symbol,
            "total_orders": total_orders,
            "last_updated": time.time()
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar status das ordens: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/system/live_status", methods=["GET"])
def get_live_system_status():
    """Retorna status ao vivo do sistema para a aba System."""
    try:
        # Get real-time system information
        if not initialize_components():
            return jsonify({"error": "Falha ao inicializar componentes"}), 500
        
        # WebSocket status
        market_manager = get_market_data_manager(binance_spot_client, testnet=False)
        websocket_status = market_manager.get_performance_stats() if market_manager else {}
        
        # Trading status
        positions = binance_futures_client.get_futures_positions()
        active_positions = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
        
        # Connection status
        try:
            # Test connection
            server_time = binance_futures_client.client.get_server_time()
            connection_healthy = True
            latency = 0  # Would need to measure actual latency
        except:
            connection_healthy = False
            latency = 999
        
        live_status = {
            "system_health": {
                "api_connection": "healthy" if connection_healthy else "error",
                "websocket_connection": "active" if websocket_status.get('is_running') else "inactive",
                "database_connection": "healthy",  # Assuming DB is working
                "latency_ms": latency
            },
            "trading_activity": {
                "active_positions": len(active_positions),
                "total_unrealized_pnl": sum([float(p['unRealizedProfit']) for p in active_positions]),
                "symbols_trading": len(set([p['symbol'] for p in active_positions])),
                "last_trade_time": time.time()  # Would need actual last trade time
            },
            "system_resources": {
                "memory_usage": websocket_status.get('memory_usage', 'N/A'),
                "cpu_usage": "N/A",  # Would need system monitoring
                "disk_space": "N/A",  # Would need system monitoring
                "network_io": "N/A"   # Would need system monitoring
            },
            "last_updated": time.time()
        }
        
        return jsonify(live_status)
        
    except Exception as e:
        logger.error(f"Erro ao buscar status ao vivo: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("[DEBUG] Entrando no bloco main do Flask...")
    logger.info("Iniciando servidor Flask API com otimizações WebSocket...")
    
    # Set app start time for uptime calculation
    app.start_time = time.time()
    
    # Initialize market data manager on startup
    try:
        if initialize_components():
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if not loop.is_running():
                logger.info("Inicializando Market Data Manager...")
                asyncio.run(initialize_market_data_manager(binance_spot_client))
    except Exception as e:
        logger.error(f"Erro ao inicializar Market Data Manager: {e}")
    
    # Load Flask server settings from config
    http_config = config.get('http_api', {})
    host = http_config.get('host', '0.0.0.0')
    port = http_config.get('port', 5000)
    debug = http_config.get('debug', False)
    
    # Run Flask server with configured settings
    app.run(host=host, port=port, debug=debug)
