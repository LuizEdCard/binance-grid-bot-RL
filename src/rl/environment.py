import gymnasium as gym  # Use Gymnasium for modern API
import numpy as np
import pandas as pd
from gymnasium import spaces

from utils.logger import setup_logger
log = setup_logger("rl_environment")


class TradingEnvironment(gym.Env):
    """
    Ambiente de trading para Reinforcement Learning, compatível com Gymnasium.
    Agora suporta operação em Spot e Futuros, e o agente pode escolher o mercado.
    """

    metadata = {"render_modes": ["human"], "render_fps": 1}

    def __init__(
        self,
        data: pd.DataFrame,
        initial_balance: float = 10000.0,
        commission: float = 0.001,
        features_window: int = 30,
        include_sentiment: bool = False,
        market_types=("spot", "futures"),
    ):
        """
        Inicializa o ambiente de trading.

        Args:
            data: DataFrame com dados históricos de preços (deve conter colunas 'open', 'high', 'low', 'close', 'volume')
            initial_balance: Saldo inicial para trading
            commission: Taxa de comissão por transação (ex: 0.001 = 0.1%)
            features_window: Janela de features para o estado
            include_sentiment: Se True, adiciona um espaço para o score de sentimento no estado.
            market_types: Tipos de mercado disponíveis (ex: "spot" e "futures")
        """
        super().__init__()

        self.data = data
        self.initial_balance = initial_balance
        self.commission = commission
        self.features_window = features_window
        self.include_sentiment = include_sentiment
        self.market_types = market_types
        self.current_market = "spot"  # default inicial

        # Novo espaço de ação: [manter, comprar, vender] para cada mercado
        self.action_space = spaces.Discrete(len(market_types) * 3)

        # Calcular o tamanho do espaço de observação
        # Preços normalizados (window size) + Indicadores (window size * num_indicators) + Posição (3 features) + Sentimento (1 feature, se incluído)
        # Ajuste o número de indicadores conforme adicionado em
        # _calculate_indicators e _get_state
        num_price_features = self.features_window
        # rsi, macd, macd_hist, volatility (ajuste se mudar)
        num_indicators = 4
        num_indicator_features = self.features_window * num_indicators
        num_position_features = 3  # shares_held, balance, position_value
        num_sentiment_features = 1 if self.include_sentiment else 0
        num_market_features = len(market_types)  # one-hot para o mercado
        self.observation_space_size = (
            num_price_features
            + num_indicator_features
            + num_position_features
            + num_sentiment_features
            + num_market_features
        )

        # Definir limites para o espaço de observação (aproximados, podem ser refinados)
        # Usar limites amplos (-inf, inf) ou normalizar tudo entre -1 e 1 ou 0
        # e 1
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.observation_space_size,),
            dtype=np.float32,
        )

        # Estado inicial
        self.current_step = self.features_window
        self.balance = self.initial_balance
        self.shares_held = 0
        self.cost_basis = 0
        self.total_shares_bought = 0
        self.total_shares_sold = 0
        self.total_commission_paid = 0
        self.transaction_history = []

        log.info(
            f"TradingEnvironment initialized. Observation space size: {self.observation_space_size}, Include Sentiment: {self.include_sentiment}"
        )

    def _calculate_indicators(self):
        # ... (cálculo de indicadores permanece o mesmo) ...
        df = self.data.copy()
        df["sma_7"] = df["close"].rolling(window=7).mean()
        df["sma_25"] = df["close"].rolling(window=25).mean()
        df["sma_99"] = df["close"].rolling(window=99).mean()
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        df["bb_std"] = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_middle"] - 2 * df["bb_std"]
        df["volume_norm"] = df["volume"] / df["volume"].rolling(window=20).mean()
        df["volatility"] = df["close"].pct_change().rolling(window=20).std()
        df.fillna(method="bfill", inplace=True)
        df.fillna(0, inplace=True)  # Fill remaining NaNs with 0
        self.data = df

    def _get_state(self, current_sentiment_score: float = 0.0):
        """
        Constrói o estado atual para o agente RL.

        Args:
            current_sentiment_score (float): O score de sentimento atual (entre -1 e 1), usado se include_sentiment=True.

        Returns:
            state: Array numpy com features do estado atual, formatado como float32.
        """
        if self.current_step < self.features_window:
            # Handle edge case at the beginning
            log.warning(
                f"Current step {self.current_step} is less than feature window {self.features_window}. Returning zero state."
            )
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        frame = self.data.iloc[
            self.current_step - self.features_window : self.current_step
        ]
        if frame.empty or len(frame) < self.features_window:
            log.warning(
                f"Insufficient data frame length ({len(frame)}) at step {self.current_step}. Returning zero state."
            )
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        features = []

        # Preços normalizados
        close_prices = frame["close"].values
        # Avoid division by zero if the first price is 0
        first_price = close_prices[0] if close_prices[0] != 0 else 1
        normalized_prices = close_prices / first_price - 1
        features.extend(normalized_prices)

        # Indicadores técnicos normalizados
        for indicator in ["rsi", "macd", "macd_hist", "volatility"]:
            values = frame[indicator].values
            if len(values) > 0 and not np.isnan(values).all():
                min_val, max_val = np.nanmin(values), np.nanmax(values)
                if max_val > min_val:
                    normalized = (values - min_val) / (
                        max_val - min_val
                    ) * 2 - 1  # Normalize to [-1, 1]
                else:
                    normalized = np.zeros_like(values)
                features.extend(normalized)
            else:
                # Append zeros if indicator calculation failed or all NaNs
                features.extend(np.zeros(self.features_window))

        # Informações de posição atual
        current_price = (
            self.data.iloc[self.current_step]["close"]
            if self.current_step < len(self.data)
            else 0
        )
        position_value = self.shares_held * current_price
        # portfolio_value = self.balance + position_value # Unused variable

        # Normalizar informações de posição (aproximado)
        features.append(
            np.clip(
                self.shares_held
                / (
                    self.initial_balance
                    / (
                        self.data["close"].mean()
                        if self.data["close"].mean() != 0
                        else 1
                    )
                ),
                -1,
                1,
            )
        )  # Clip share count relative to potential max shares
        # Normalize balance to [-1, 1]
        features.append(np.clip((self.balance / self.initial_balance) * 2 - 1, -1, 1))
        # Normalize position value to [-1, 1]
        features.append(np.clip((position_value / self.initial_balance) * 2 - 1, -1, 1))

        # --- Adicionar Score de Sentimento (se habilitado) --- #
        if self.include_sentiment:
            features.append(np.clip(current_sentiment_score, -1.0, 1.0))
        # --- One-hot do tipo de mercado --- #
        market_one_hot = [
            1.0 if self.current_market == m else 0.0 for m in self.market_types
        ]
        features.extend(market_one_hot)

        # Garantir que o tamanho do estado corresponde ao espaço de observação
        final_state = np.array(features, dtype=np.float32)
        if len(final_state) != self.observation_space_size:
            log.error(
                f"State size mismatch! Expected {self.observation_space_size}, got {len(final_state)}. Padding/truncating."
            )
            # Pad or truncate (simple approach, might need refinement)
            if len(final_state) > self.observation_space_size:
                final_state = final_state[: self.observation_space_size]
            else:
                padding = np.zeros(
                    self.observation_space_size - len(final_state), dtype=np.float32
                )
                final_state = np.concatenate((final_state, padding))

        return final_state

    def reset(self, seed=None, options=None):
        """
        Reinicia o ambiente para um novo episódio.

        Returns:
            observation: Estado inicial do ambiente
            info: Dicionário de informações adicionais
        """
        super().reset(seed=seed)

        self.current_step = self.features_window
        self.balance = self.initial_balance
        self.shares_held = 0
        self.cost_basis = 0
        self.total_shares_bought = 0
        self.total_shares_sold = 0
        self.total_commission_paid = 0
        self.transaction_history = []

        observation = self._get_state()  # Sentiment score defaults to 0 on reset
        info = self._get_info()

        return observation, info

    def step(self, action, current_sentiment_score: float = 0.0):
        """
        Executa uma ação no ambiente e retorna o próximo estado, recompensa e flags.
        Agora o agente escolhe o mercado (spot/futuros) e a ação (manter/comprar/vender).

        Args:
            action: Índice da ação a ser executada (0: manter, 1: comprar, 2: vender)
            current_sentiment_score (float): O score de sentimento atual, usado se include_sentiment=True.

        Returns:
            observation: Próximo estado após a ação
            reward: Recompensa recebida pela ação
            terminated: Flag indicando se o episódio terminou (fim dos dados)
            truncated: Flag indicando se o episódio foi truncado (condição externa, ex: limite de tempo)
            info: Informações adicionais
        """
        terminated = False
        truncated = False
        reward = 0

        # Decodifica ação e mercado
        market_idx = action // 3
        action_type = action % 3  # 0: manter, 1: comprar, 2: vender
        self.current_market = self.market_types[market_idx]
        current_price = (
            self.data.iloc[self.current_step]["close"]
            if self.current_step < len(self.data)
            else 0
        )

        # Executar ação
        if action_type == 1:  # Comprar
            max_shares = self.balance / (current_price * (1 + self.commission))
            shares_to_buy = int(max_shares * 0.25)  # Comprar 25% do saldo
            if shares_to_buy > 0:
                cost = shares_to_buy * current_price
                commission_cost = cost * self.commission
                total_cost = cost + commission_cost
                if self.balance >= total_cost:
                    self.balance -= total_cost
                    new_total_shares = self.shares_held + shares_to_buy
                    self.cost_basis = (
                        (
                            (self.cost_basis * self.shares_held)
                            + (current_price * shares_to_buy)
                        )
                        / new_total_shares
                        if new_total_shares > 0
                        else 0
                    )
                    self.shares_held = new_total_shares
                    self.total_shares_bought += shares_to_buy
                    self.total_commission_paid += commission_cost
                    self.transaction_history.append(
                        {
                            "step": self.current_step,
                            "type": "buy",
                            "shares": shares_to_buy,
                            "price": current_price,
                            "commission": commission_cost,
                            "market": self.current_market,
                        }
                    )
                    reward = -0.01  # Pequena penalidade por transação
                else:
                    # Penalidade maior por falha (saldo insuficiente)
                    reward = -0.1
            else:
                reward = -0.05  # Penalidade por tentar comprar 0 ações

        elif action_type == 2:  # Vender
            if self.shares_held > 0:
                shares_to_sell = int(self.shares_held * 0.25)  # Vender 25% da posição
                if shares_to_sell > 0:
                    sale_value = shares_to_sell * current_price
                    commission_cost = sale_value * self.commission
                    total_value = sale_value - commission_cost
                    self.balance += total_value
                    self.shares_held -= shares_to_sell
                    self.total_shares_sold += shares_to_sell
                    self.total_commission_paid += commission_cost
                    self.transaction_history.append(
                        {
                            "step": self.current_step,
                            "type": "sell",
                            "shares": shares_to_sell,
                            "price": current_price,
                            "commission": commission_cost,
                            "market": self.current_market,
                        }
                    )
                    # Recompensa baseada no lucro/prejuízo da venda
                    profit_pct = (
                        (current_price - self.cost_basis) / self.cost_basis
                        if self.cost_basis > 0
                        else 0
                    )
                    reward = profit_pct  # Recompensa proporcional ao lucro/prejuízo percentual
                    if self.shares_held == 0:
                        self.cost_basis = 0  # Reset cost basis if position closed
                else:
                    reward = -0.05  # Penalidade por tentar vender 0 ações
            else:
                reward = -0.1  # Penalidade por tentar vender sem ter ações

        # Avançar para o próximo passo
        self.current_step += 1

        # Verificar se o episódio terminou (fim dos dados)
        if self.current_step >= len(self.data) - 1:
            terminated = True
            # Calcular valor final do portfólio para recompensa final
            final_price = self.data.iloc[-1]["close"]
            portfolio_value = self.balance + (self.shares_held * final_price)
            return_pct = (portfolio_value / self.initial_balance) - 1
            reward += (
                return_pct * 10
            )  # Adicionar recompensa final baseada no retorno total

        # Obter próximo estado e info
        observation = self._get_state(current_sentiment_score)
        info = self._get_info()

        # Adicionar recompensa baseada na mudança do valor do portfólio a cada passo
        # reward += (info["portfolio_value"] / self.initial_balance - 1) * 0.01
        # # Pequena recompensa/penalidade contínua

        return observation, reward, terminated, truncated, info

    def _get_info(self):
        """Retorna informações adicionais sobre o estado atual."""
        current_price = (
            self.data.iloc[self.current_step]["close"]
            if self.current_step < len(self.data)
            else 0
        )
        portfolio_value = self.balance + (self.shares_held * current_price)
        return {
            "step": self.current_step,
            "portfolio_value": portfolio_value,
            "balance": self.balance,
            "shares_held": self.shares_held,
            "cost_basis": self.cost_basis,
            "total_commission_paid": self.total_commission_paid,
            "current_price": current_price,
        }

    def render(self, mode="human"):
        """
        Renderiza o estado atual do ambiente.
        """
        info = self._get_info()
        profit_loss = info["portfolio_value"] - self.initial_balance

        print(f"Step: {info['step']}")
        print(f"Price: ${info['current_price']:.2f}")
        print(f"Balance: ${info['balance']:.2f}")
        print(f"Shares held: {info['shares_held']}")
        print(f"Portfolio value: ${info['portfolio_value']:.2f}")
        print(
            f"Profit/Loss: ${profit_loss:.2f} ({profit_loss/self.initial_balance*100:.2f}%)"
        )
        print("----------------------------")

    def close(self):
        """Fecha o ambiente e libera recursos."""
        pass  # Nada específico para fechar neste ambiente simples
