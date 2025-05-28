# Backend API using Flask

from utils.logger import setup_logger
from utils.api_client import APIClient
from utils.alerter import Alerter
from routes.model_api import model_api
from core.risk_management import RiskManager
from core.grid_logic import GridLogic
from flask_cors import CORS
from flask import Flask, jsonify, request
import yaml
import threading
import os
import sys

# DON'T CHANGE THIS !!! Ensure the src directory is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Carrega as variáveis de ambiente do arquivo .env
from dotenv import load_dotenv

# Determinar o caminho para o arquivo .env na raiz do projeto
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')

# Carregar variáveis do arquivo .env
load_dotenv(dotenv_path)
print(f"Carregando variáveis de ambiente de: {dotenv_path}")
print(f"BINANCE_API_KEY presente: {'BINANCE_API_KEY' in os.environ}")


# Importar rotas de modelos (tabular e RL)
# Importar lógica do bot (ajustar caminhos e nomes conforme necessário)

# from core.rl_agent import RLAgent # RL Agent desativado temporariamente


# --- Configuração Inicial ---
app = Flask(__name__)
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

# --- Funções Auxiliares (Exemplo) ---


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
        operation_mode = config.get("operation_mode", "shadow").lower()
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
        operation_mode = config.get("operation_mode", "shadow").lower()
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

        # Create bot first without risk manager
        bot = GridLogic(
            symbol=symbol,
            client=client,
            grid_config=grid_config,
            risk_manager=None,  # Will set it later after creating risk_manager
            # rl_agent=rl_agent, # RL desativado
            alerter=alerter,

        # Then create risk manager with all required parameters
        risk_manager = RiskManager(
            symbol=symbol,
            config=config,
            grid_logic=bot,
            api_client=client,
            alerter=alerter,
            market_type=market_type
        )
        
        # Update bot with the risk manager
        bot.risk_manager = risk_manager,
            logger=logger,
            trading_mode=config.get("trading_mode", "shadow"),
        )
        bots[symbol] = bot
        bot.run()
    except Exception as e:
        logger.error(f"Erro na thread do bot para {symbol}: {e}", exc_info=True)
    finally:
        logger.info(f"Thread do bot para {symbol} finalizada.")
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
        logger.info("Tentando obter tickers do mercado spot...")
        # Exemplo: buscar tickers 24h
        tickers = binance_spot_client.get_spot_ticker()  # Este método retorna todos os tickers quando chamado sem argumentos
        logger.info(f"Tickers obtidos: {tickers[:2] if isinstance(tickers, list) else tickers}")  # Mostra apenas os 2 primeiros tickers se for lista
        # Filtrar/formatar conforme necessidade do frontend
        if isinstance(tickers, list):
            formatted_tickers = [
                {"symbol": t["symbol"], "price": t["price"], "volume": t.get("volume", "0")}
                for t in tickers
                if "USDT" in t["symbol"]
            ]
        else:
            # Se for um único ticker
            formatted_tickers = [{"symbol": tickers["symbol"], "price": tickers["price"], "volume": tickers.get("volume", "0")}]
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

    # Aqui você pode validar a configuração, salvar, etc.
    # Por enquanto, apenas logamos
    logger.info(f"Configuração recebida para {symbol}: {grid_config}")

    # Poderia retornar a configuração validada ou sugestões do RL (se ativo)
    return jsonify(
        {
            "message": f"Configuração para {symbol} recebida.",
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

    # Certifique-se de que o frontend envie 'market_type' em grid_config, ou
    # defina padrão
    if "market_type" not in grid_config:
        grid_config["market_type"] = "spot"  # padrão

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


@app.route("/api/grid/status/<symbol>", methods=["GET"])
def get_grid_status(symbol):
    """Retorna o status específico de um bot de grid."""
    if symbol in bots and bots[symbol]:
        return jsonify(bots[symbol].get_status())
    else:
        return jsonify(
            {"status": "inactive", "message": f"Bot para {symbol} não está ativo."}
        )


# --- Inicialização do Servidor --- #
if __name__ == "__main__":
    logger.info("Iniciando servidor Flask API...")
    # Usar host 0.0.0.0 para ser acessível externamente
    # Usar uma porta diferente da padrão do React (ex: 5000)
    # Debug=True para desenvolvimento
    app.run(host="0.0.0.0", port=5000, debug=True)  # Mudando para porta 5000
