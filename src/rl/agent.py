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

    def __init__(self, state_size, action_size, model_path=None):
        # action_size deve ser len(market_types) * 3
        self.state_size = state_size  # Tamanho do estado (features do mercado)
        # Tamanho do espaço de ações (comprar, vender, manter)
        self.action_size = action_size
        # Memória de replay para experiências passadas
        self.memory = deque(maxlen=2000)
        self.gamma = 0.95  # Fator de desconto para recompensas futuras
        self.epsilon = 1.0  # Taxa de exploração inicial
        self.epsilon_min = 0.01  # Taxa mínima de exploração
        self.epsilon_decay = 0.995  # Taxa de decaimento da exploração
        self.learning_rate = 0.001  # Taxa de aprendizado
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
        # Saída: Q-values para cada ação
        model.add(Dense(self.action_size, activation="linear"))
        model.compile(loss="mse", optimizer=Adam(learning_rate=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        """
        Armazena experiência na memória para treinamento posterior.
        """
        self.memory.append((state, action, reward, next_state, done))

    def act(self, state, training=True):
        """
        Escolhe uma ação com base no estado atual usando política epsilon-greedy.
        Durante o treinamento, equilibra exploração e aproveitamento.
        Durante a avaliação, sempre escolhe a melhor ação.
        """
        if training and np.random.rand() <= self.epsilon:
            # Exploração: escolher ação aleatória
            return random.randrange(self.action_size)

        # Aproveitamento: prever Q-values e escolher a melhor ação
        state = np.reshape(state, [1, self.state_size, 1])
        act_values = self.model.predict(state, verbose=0)
        return np.argmax(act_values[0])  # Retorna a ação com o maior Q-value

    def replay(self, batch_size):
        """
        Treina o modelo usando experiências aleatórias da memória.
        Implementa o algoritmo de Q-learning com rede neural.
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
            # Atualiza o Q-value para a ação tomada
            target_f[0][action] = target

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
