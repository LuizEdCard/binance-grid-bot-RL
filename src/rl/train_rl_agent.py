import pandas as pd
import numpy as np
from rl.agent import RLTradingAgent
from rl.environment import TradingEnvironment

# Exemplo de uso: treinamento RL

def train_rl_agent(data_path, episodes=10, model_save_path=None):
    df = pd.read_csv(data_path)
    env = TradingEnvironment(df)
    state_size = len(env._get_state())
    action_size = 3  # manter, comprar, vender
    agent = RLTradingAgent(state_size, action_size, model_path=model_save_path)

    for ep in range(episodes):
        state = env.reset()
        state = np.reshape(state, (state_size, 1))
        total_reward = 0
        done = False
        while not done:
            action = agent.act(state)
            next_state, reward, done, info = env.step(action)
            next_state = np.reshape(next_state, (state_size, 1))
            agent.remember(state, action, reward, next_state, done)
            state = next_state
            total_reward += reward
            if done:
                print(f"Episódio {ep+1}/{episodes} - Recompensa total: {total_reward:.2f}")
                break
            agent.replay(batch_size=32)
        if model_save_path:
            agent.model.save_weights(model_save_path)

if __name__ == "__main__":
    # Exemplo de chamada
    train_rl_agent("/caminho/para/dados.csv", episodes=20, model_save_path="/caminho/para/modelo_rl.h5")
