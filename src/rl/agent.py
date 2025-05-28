import os
import random
from collections import deque

import numpy as np
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.optimizers import Adam


class RLTradingAgent:
    """
    Agente de Reinforcement Learning para trading baseado na abordagem de MattsonThieme.
    Agora suporta decisão entre Spot e Futuros.
    """

    def __init__(self, state_size, action_size, model_path=None, market_types=["futures", "spot"]):
        self.state_size = state_size  # Tamanho do estado (features do mercado)
        self.action_size = action_size  # Tamanho total do espaço de ações
        self.market_types = market_types  # Tipos de mercado disponíveis
        
        # Definir espaço de ações estruturado:
        # Primeiro: escolha do mercado (0=futures, 1=spot)
        # Segundo: ação do grid (0-9 como definido anteriormente)
        self.market_choice_actions = len(market_types)  # 2 opções: futures ou spot
        self.grid_actions = 10  # Ações de grid (0-9)
        
        # Memória de replay para experiências passadas
        self.memory = deque(maxlen=2000)
        self.gamma = 0.95  # Fator de desconto para recompensas futuras
        self.epsilon = 1.0  # Taxa de exploração inicial
        self.epsilon_min = 0.01  # Taxa mínima de exploração
        self.epsilon_decay = 0.995  # Taxa de decaimento da exploração
        self.learning_rate = 0.001  # Taxa de aprendizado
        
        # Histórico de desempenho por mercado
        self.market_performance = {
            "futures": {"trades": 0, "total_pnl": 0.0, "success_rate": 0.0},
            "spot": {"trades": 0, "total_pnl": 0.0, "success_rate": 0.0}
        }
        
        self.model = self._build_model()  # Modelo de rede neural

        # Carregar modelo existente se fornecido
        if model_path and os.path.exists(model_path):
            self.model.load_weights(model_path)
            self.epsilon = (
                self.epsilon_min
            )  # Reduzir exploração se já temos um modelo treinado

    def _build_model(self):
        """
        Constrói a arquitetura da rede neural para o agente DQN.
        Utiliza uma combinação de camadas LSTM e Dense para capturar padrões temporais.
        Agora com saídas separadas para escolha de mercado e ações de grid.
        """
        model = Sequential()
        # Camada LSTM para capturar padrões temporais nos dados de mercado
        model.add(
            LSTM(units=64, input_shape=(self.state_size, 1), return_sequences=True)
        )
        model.add(Dropout(0.2))
        model.add(LSTM(units=64, return_sequences=False))
        model.add(Dropout(0.2))
        model.add(Dense(32, activation="relu"))
        
        # Saída: Q-values para escolha de mercado + ações de grid
        # Total: market_choice_actions + grid_actions
        total_actions = self.market_choice_actions + self.grid_actions
        model.add(Dense(total_actions, activation="linear"))
        model.compile(loss="mse", optimizer=Adam(learning_rate=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        """
        Armazena experiência na memória para treinamento posterior.
        """
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state, training=True, current_market_type="futures"):
        """
        Escolhe uma ação com base no estado atual usando política epsilon-greedy.
        Retorna tanto a escolha do mercado quanto a ação do grid.
        Durante o treinamento, equilibra exploração e aproveitamento.
        Durante a avaliação, sempre escolhe a melhor ação.
        """
        if training and np.random.rand() <= self.epsilon:
            # Exploração: escolher ação aleatória
            market_action = random.randrange(self.market_choice_actions)
            grid_action = random.randrange(self.grid_actions)
        else:
            # Aproveitamento: prever Q-values e escolher as melhores ações
            state = np.reshape(state, [1, self.state_size, 1])
            act_values = self.model.predict(state, verbose=0)
            
            # Separar Q-values para mercado e grid
            market_q_values = act_values[0][:self.market_choice_actions]
            grid_q_values = act_values[0][self.market_choice_actions:]
            
            market_action = np.argmax(market_q_values)
            grid_action = np.argmax(grid_q_values)
        
        # Converter ação do mercado para string
        chosen_market = self.market_types[market_action]
        
        # Adicionar lógica de persistência: evitar trocar de mercado muito frequentemente
        if hasattr(self, 'last_market_choice') and self.last_market_choice != chosen_market:
            # Verificar se realmente vale a pena trocar de mercado
            market_switch_threshold = 0.1  # Diferença mínima nos Q-values para trocar
            current_market_idx = self.market_types.index(current_market_type)
            
            if abs(market_q_values[market_action] - market_q_values[current_market_idx]) < market_switch_threshold:
                chosen_market = current_market_type
                market_action = current_market_idx
        
        self.last_market_choice = chosen_market
        
        return {
            "market_type": chosen_market,
            "market_action": market_action,
            "grid_action": grid_action,
            "combined_action": market_action * self.grid_actions + grid_action  # Para compatibilidade
        }

    def update_market_performance(self, market_type, pnl, is_successful):
        """
        Atualiza o histórico de desempenho para um mercado específico.
        """
        if market_type in self.market_performance:
            self.market_performance[market_type]["trades"] += 1
            self.market_performance[market_type]["total_pnl"] += pnl
            
            # Calcular taxa de sucesso
            total_trades = self.market_performance[market_type]["trades"]
            if total_trades > 0:
                current_successes = self.market_performance[market_type]["success_rate"] * (total_trades - 1)
                new_successes = current_successes + (1 if is_successful else 0)
                self.market_performance[market_type]["success_rate"] = new_successes / total_trades

    def get_market_performance_features(self):
        """
        Retorna features de desempenho dos mercados para inclusão no estado.
        """
        features = []
        for market_type in self.market_types:
            perf = self.market_performance[market_type]
            features.extend([
                perf["trades"] / 1000.0,  # Normalizado
                min(1.0, max(-1.0, perf["total_pnl"] / 1000.0)),  # Normalizado e limitado
                perf["success_rate"]
            ])
        return features

    def replay(self, batch_size):
        """
        Treina o modelo usando experiências aleatórias da memória.
        Implementa o algoritmo de Q-learning com rede neural.
        Agora considera ações separadas para mercado e grid.
        """
        if len(self.memory) < batch_size:
            return

        # Amostra aleatória de experiências da memória
        minibatch = random.sample(self.memory, batch_size)

        for state, action, reward, next_state, done in minibatch:
            state = np.reshape(state, [1, self.state_size, 1])
            next_state = np.reshape(next_state, [1, self.state_size, 1])

            # Cálculo do Q-value alvo
            target = reward
            if not done:
                # Q(s',a') para o próximo estado
                target = reward + self.gamma * np.amax(
                    self.model.predict(next_state, verbose=0)[0]
                )

            # Q(s,a) atual
            target_f = self.model.predict(state, verbose=0)
            
            # Se action é um dicionário (novo formato), usar combined_action
            if isinstance(action, dict):
                action_idx = action["combined_action"]
            else:
                action_idx = action
            
            # Atualiza o Q-value para a ação tomada
            target_f[0][action_idx] = target

            # Treina o modelo para aproximar o Q-value alvo
            self.model.fit(state, target_f, epochs=1, verbose=0)

        # Decai a taxa de exploração
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def save_model(self, path):
        """
        Salva os pesos do modelo em um arquivo.
        """
        self.model.save_weights(path)

    def load_model(self, path):
        """
        Carrega os pesos do modelo de um arquivo.
        """
        self.model.load_weights(path)
        self.epsilon = (
            self.epsilon_min
        )  # Reduz exploração após carregar modelo treinado
