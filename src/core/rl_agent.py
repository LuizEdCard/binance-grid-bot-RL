# Reinforcement Learning Agent for Grid Trading Bot

import os

import gymnasium as gym  # Use Gymnasium standard
import numpy as np
import pandas as pd
import yaml
from gymnasium import spaces

from rl.agent import RLTradingAgent
from rl.environment import TradingEnvironment
from utils.logger import setup_logger
log = setup_logger("rl_agent")

# Attempt to import TA-Lib
try:
    import talib

    talib_available = True
    log.info("TA-Lib library found and imported successfully for RLAgent.")
except ImportError:
    talib_available = False
    log.warning(
        "TA-Lib library not found for RLAgent. TA-Lib based state features will be unavailable. Please install TA-Lib for full functionality (see talib_installation_guide.md)."
    )

# Placeholder for the Trading Environment - Needs full implementation


class TradingEnvPlaceholder(gym.Env):
    """Placeholder for the trading environment the RL agent interacts with.

    This environment should simulate the grid logic, market data updates,
    and calculate rewards based on trading performance.
    Includes TA-Lib features in the observation space if available.
    """

    metadata = {"render_modes": ["human"], "render_fps": 4}

    def __init__(self, config, symbol):
        super().__init__()
        self.config = config
        self.symbol = symbol
        self.rl_config = config.get("rl_agent", {})
        self.state_features_config = self.rl_config.get(
            "state_features",
            {  # Now a dict
                # Default indicators
                "technical_indicators": ["rsi", "atr", "adx"],
                "grid_context": True,
                "position_context": True,
                "talib_indicators": [],  # e.g., ["macd", "bbands"]
                "talib_patterns": [],  # e.g., ["CDLDOJI", "CDLENGULFING"]
            },
        )

        # --- Action Space Definition --- #
        # (Assuming Discrete for now, as before)
        self.action_space = spaces.Discrete(10)
        log.info(f"[{self.symbol}] Action Space: {self.action_space}")

        # --- Observation Space Definition --- #
        state_dim = 0
        # Standard indicators
        if "rsi" in self.state_features_config.get("technical_indicators", []):
            state_dim += 1
        if "atr" in self.state_features_config.get("technical_indicators", []):
            state_dim += 1
        if "adx" in self.state_features_config.get("technical_indicators", []):
            state_dim += 1
        # Grid context
        if self.state_features_config.get("grid_context", False):
            state_dim += 3
        # Position context
        if self.state_features_config.get("position_context", False):
            state_dim += 2

        # TA-Lib Indicators
        self.talib_indicator_features = []
        if talib_available:
            for indicator in self.state_features_config.get("talib_indicators", []):
                if indicator == "macd":
                    state_dim += 1  # Using MACD hist
                elif indicator == "bbands":
                    state_dim += 1  # Using %B indicator derived from BBands
                # Add other TA-Lib indicators here
                else:
                    log.warning(f"Unsupported TA-Lib indicator in config: {indicator}")
                self.talib_indicator_features.append(indicator)
        elif self.state_features_config.get("talib_indicators", []):
            log.warning(
                f"[{self.symbol}] TA-Lib indicators configured but library not available."
            )

        # TA-Lib Patterns
        self.talib_pattern_features = []
        if talib_available:
            num_patterns = len(self.state_features_config.get("talib_patterns", []))
            if num_patterns > 0:
                # One feature per pattern (-100 -> 0, 0 -> 0.5, 100 -> 1)
                state_dim += num_patterns
                self.talib_pattern_features = self.state_features_config.get(
                    "talib_patterns", []
                )
        elif self.state_features_config.get("talib_patterns", []):
            log.warning(
                f"[{self.symbol}] TA-Lib patterns configured but library not available."
            )

        if state_dim == 0:
            log.error(
                f"[{self.symbol}] Observation space dimension is zero. Check state_features config."
            )
            raise ValueError("Observation space dimension is zero.")

        # Assuming normalized values between 0 and 1 for simplicity
        # Some features might be better normalized between -1 and 1 (like MACD hist)
        # Adjust low/high accordingly if needed.
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(state_dim,), dtype=np.float32
        )
        log.info(
            f"[{self.symbol}] Observation Space: {self.observation_space} (Includes TA-Lib features: {talib_available})"
        )
        log.info(
            f"[{self.symbol}] TA-Lib Indicators in state: {self.talib_indicator_features}"
        )
        log.info(
            f"[{self.symbol}] TA-Lib Patterns in state: {self.talib_pattern_features}"
        )

        # Placeholder for historical data needed by indicators/patterns
        self.history_df = pd.DataFrame()
        self.min_history_needed = 50  # Estimate max lookback needed

        log.info(f"[{self.symbol}] TradingEnvPlaceholder initialized.")
        log.warning(
            f"[{self.symbol}] TradingEnvPlaceholder is a placeholder and needs full implementation! Observation/Action spaces are examples."
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        log.debug(f"[{self.symbol}] TradingEnvPlaceholder reset called.")
        # Reset history
        self.history_df = pd.DataFrame()
        # Fetch initial history (in a real env)
        self._update_history()
        initial_observation = self._get_observation()
        info = self._get_info()
        return initial_observation, info

    def step(self, action):
        log.debug(
            f"[{self.symbol}] TradingEnvPlaceholder step called with action: {action}"
        )
        self._apply_action(action)

        # Simulate trading step
        # In a real env, this would involve GridLogic.run_cycle()
        # Update history with new kline data
        self._update_history()

        # Calculate reward
        reward = self._calculate_reward()

        observation = self._get_observation()
        terminated = False  # Check termination conditions
        truncated = False  # Check truncation conditions
        info = self._get_info()

        return observation, reward, terminated, truncated, info

    def _update_history(self):
        # Placeholder: In a real env, fetch latest kline(s) and append to self.history_df
        # Ensure history_df doesn't grow indefinitely
        # Example: Fetch last N candles (N >= min_history_needed)
        log.debug(f"[{self.symbol}] Updating history (Placeholder)")
        # Simulate adding a new candle
        if len(self.history_df) < self.min_history_needed:
            # Simulate fetching initial history
            num_missing = self.min_history_needed - len(self.history_df)
            # Create fake data
            fake_data = np.random.rand(num_missing, 5) * 100  # O, H, L, C, V
            fake_df = pd.DataFrame(
                fake_data, columns=["Open", "High", "Low", "Close", "Volume"]
            )
            self.history_df = pd.concat([self.history_df, fake_df], ignore_index=True)
        else:
            # Simulate adding one new candle and removing the oldest
            new_candle_data = np.random.rand(1, 5) * 100
            new_candle_df = pd.DataFrame(
                new_candle_data, columns=["Open", "High", "Low", "Close", "Volume"]
            )
            self.history_df = pd.concat(
                [self.history_df.iloc[1:], new_candle_df], ignore_index=True
            )

    def _get_observation(self):
        """Constructs the observation vector including TA-Lib features."""
        obs_list = []

        # Ensure we have enough history
        if len(self.history_df) < self.min_history_needed:
            log.warning(
                f"[{self.symbol}] Not enough history ({len(self.history_df)}/{self.min_history_needed}) for observation. Returning zeros."
            )
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        # Prepare data for TA-Lib / other indicators
        open_p = self.history_df["Open"].values.astype(float)
        high_p = self.history_df["High"].values.astype(float)
        low_p = self.history_df["Low"].values.astype(float)
        close_p = self.history_df["Close"].values.astype(float)
        # volume_p = self.history_df["Volume"].values.astype(float) # Unused variable

        # --- Calculate Standard Indicators --- #
        if "rsi" in self.state_features_config.get("technical_indicators", []):
            rsi = 0.5  # Placeholder
            if talib_available:
                try:
                    # Normalize 0-100 to 0-1
                    rsi = talib.RSI(close_p, timeperiod=14)[-1] / 100.0
                except Exception as e:
                    log.warning(f"[{self.symbol}] Error calculating RSI: {e}", exc_info=True)
                    # pass # Keep existing pass if it's intentional, or remove if error should propagate or be handled differently
            # Handle potential NaN
            obs_list.append(np.nan_to_num(rsi, nan=0.5))

        if "atr" in self.state_features_config.get("technical_indicators", []):
            atr_perc = 0.01  # Placeholder
            if talib_available:
                try:
                    atr = talib.ATR(high_p, low_p, close_p, timeperiod=14)[-1]
                    last_close = close_p[-1]
                    if last_close > 0:
                        atr_perc = atr / last_close
                    # Normalize ATR % (e.g., clip at 5% -> 1.0)
                    atr_perc = min(atr_perc / 0.05, 1.0)
                except Exception as e:
                    log.warning(f"[{self.symbol}] Error calculating ATR: {e}", exc_info=True)
                    # pass
            obs_list.append(
                np.nan_to_num(
                    atr_perc,
                    nan=0.0))  # Handle potential NaN

        if "adx" in self.state_features_config.get("technical_indicators", []):
            adx = 0.25  # Placeholder
            if talib_available:
                try:
                    # Normalize 0-100 to 0-1
                    adx = talib.ADX(high_p, low_p, close_p, timeperiod=14)[-1] / 100.0
                except Exception as e:
                    log.warning(f"[{self.symbol}] Error calculating ADX: {e}", exc_info=True)
                    # pass
            # Handle potential NaN
            obs_list.append(np.nan_to_num(adx, nan=0.25))

        # --- Calculate TA-Lib Indicators --- #
        if talib_available:
            if "macd" in self.talib_indicator_features:
                macd_hist = 0.5  # Placeholder
                try:
                    _, _, hist = talib.MACD(close_p)
                    # Normalize MACD hist (e.g., using recent range or clip)
                    # Simple normalization: scale based on recent price range
                    # (approx)
                    # Peak-to-peak over last 20 periods
                    price_range = np.ptp(close_p[-20:])
                    if price_range > 0:
                        norm_hist = hist[-1] / price_range
                        macd_hist = np.clip(
                            (norm_hist + 1.0) / 2.0, 0, 1
                        )  # Clip and scale to 0-1
                except Exception as e:
                    log.warning(f"[{self.symbol}] Error calculating MACD: {e}", exc_info=True)
                    # pass
                obs_list.append(np.nan_to_num(macd_hist, nan=0.5))

            if "bbands" in self.talib_indicator_features:
                percent_b = 0.5  # Placeholder
                try:
                    upper, middle, lower = talib.BBANDS(close_p, timeperiod=20)
                    last_close = close_p[-1]
                    band_width = upper[-1] - lower[-1]
                    if band_width > 0:
                        percent_b = (last_close - lower[-1]) / band_width
                    # %B is naturally 0-1 (or slightly outside)
                    percent_b = np.clip(percent_b, 0, 1)
                except Exception as e:
                    log.warning(f"[{self.symbol}] Error calculating BBands: {e}", exc_info=True)
                    # pass
                obs_list.append(np.nan_to_num(percent_b, nan=0.5))
            # Add other TA-Lib indicators here
        else:
            # Add placeholders if TA-Lib indicators were configured but
            # unavailable
            num_talib_inds = len(self.state_features_config.get("talib_indicators", []))
            obs_list.extend([0.5] * num_talib_inds)

        # --- Calculate TA-Lib Patterns --- #
        if talib_available:
            for pattern_name in self.talib_pattern_features:
                pattern_val = 0.5  # Placeholder (neutral)
                try:
                    pattern_func = getattr(talib, pattern_name)
                    result = pattern_func(open_p, high_p, low_p, close_p)[-1]
                    # Normalize: -100 -> 0, 0 -> 0.5, 100 -> 1
                    pattern_val = (result / 200.0) + 0.5
                except Exception as e:
                    log.warning(
                        f"[{self.symbol}] Error calculating pattern {pattern_name}: {e}",
                        exc_info=True,
                    )
                    pass  # Keep placeholder value
                obs_list.append(np.nan_to_num(pattern_val, nan=0.5))
        else:
            # Add placeholders if TA-Lib patterns were configured but
            # unavailable
            num_talib_patterns = len(
                self.state_features_config.get("talib_patterns", [])
            )
            obs_list.extend([0.5] * num_talib_patterns)

        # --- Add Grid and Position Context --- #
        if self.state_features_config.get("grid_context", False):
            # Placeholder values - fetch from actual GridLogic state
            # Normalize num_levels (e.g., current / max_possible)
            norm_levels = 0.5
            # Normalize spacing (e.g., current / max_possible)
            norm_spacing = 0.5
            direction_bias = 0.5  # -1 -> 0, 0 -> 0.5, 1 -> 1
            obs_list.extend([norm_levels, norm_spacing, direction_bias])

        if self.state_features_config.get("position_context", False):
            # Placeholder values - fetch from actual GridLogic state
            norm_pos_size = 0.5  # Normalize position size relative to max allowed
            # Normalize unrealized PNL % (e.g., clip +/- 10% -> 0-1)
            norm_upnl = 0.5
            obs_list.extend([norm_pos_size, norm_upnl])

        # --- Final Observation Vector --- #
        observation = np.array(obs_list, dtype=np.float32)

        # Verify shape
        if observation.shape != self.observation_space.shape:
            log.error(
                f"[{self.symbol}] Observation shape mismatch! Expected {self.observation_space.shape}, got {observation.shape}. Check feature calculation. Returning zeros."
            )
            return np.zeros(self.observation_space.shape, dtype=np.float32)

        return observation

    def _calculate_reward(self):
        # Placeholder: Calculate reward based on PNL change, drawdown, fills, etc.
        # Needs access to GridLogic state changes between steps.
        # reward_config = self.rl_config.get("reward_function", {})
        # ... calculate reward ...
        return np.random.rand() - 0.5  # Placeholder reward

    def _get_info(self):
        # Return auxiliary information
        return {"pnl": np.random.rand(), "trades": 0}  # Placeholder

    def _apply_action(self, action):
        # Map the action to changes in grid parameters (Placeholder)
        log.info(f"[{self.symbol}] Applying action {action} (Placeholder)")

    def render(self):
        pass

    def close(self):
        log.info(f"[{self.symbol}] TradingEnvPlaceholder closed.")


# --- RL Agent Class using RLTrading by MattsonThieme --- #


class RLAgent:
    """Manages the Reinforcement Learning model training and inference using RLTrading approach."""

    def __init__(self, config: dict, symbol: str):
        self.config = config
        self.rl_config = config.get("rl_agent", {})
        self.symbol = symbol
        self.model_path = os.path.join(
            "/home/ubuntu/grid_trading_backend/models", f"rl_agent_{symbol}"
        )
        self.agent = None
        self.env = None
        self.state_size = self.rl_config.get("state_size", 30)  # Default state size
        self.action_size = self.rl_config.get(
            "action_size", 3
        )  # Default: hold, buy, sell
        self.total_timesteps_trained = 0

        # Ensure model directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def _create_env(self, data=None):
        """Creates an instance of the trading environment."""
        log.info(f"[{self.symbol}] Creating RLTrading environment...")

        # If no data provided, fetch historical data for the symbol
        if data is None:
            # In a real implementation, fetch data from API
            # For now, create dummy data for testing
            dates = pd.date_range(start="2023-01-01", periods=500)
            data = pd.DataFrame(
                {
                    "open": np.random.normal(100, 10, 500),
                    "high": np.random.normal(105, 10, 500),
                    "low": np.random.normal(95, 10, 500),
                    "close": np.random.normal(100, 10, 500),
                    "volume": np.random.normal(1000000, 500000, 500),
                },
                index=dates,
            )
            log.warning(
                f"[{self.symbol}] Using dummy data for environment. Replace with real data in production."
            )

        # Create the trading environment
        initial_balance = self.rl_config.get("initial_balance", 10000.0)
        commission = self.rl_config.get("commission", 0.001)  # 0.1% commission
        env = TradingEnvironment(
            data, initial_balance=initial_balance, commission=commission
        )

        return env

    def setup_agent(self, training=True):
        """Sets up the RL trading agent."""
        log.info(f"[{self.symbol}] Setting up RLTrading agent...")

        # Create environment if not already created
        if self.env is None:
            self.env = self._create_env()

        if not self.env:
            log.error(
                f"[{self.symbol}] Failed to create environment. Cannot setup agent."
            )
            return False

        # Get state size from environment
        state_features = self.env._get_state()
        self.state_size = len(state_features)
        log.info(
            f"[{self.symbol}] State size determined from environment: {self.state_size}"
        )

        # Create the RLTrading agent
        model_file = f"{self.model_path}.h5"

        if os.path.exists(model_file) and not training:
            log.info(f"[{self.symbol}] Loading existing model from {model_file}")
            self.agent = RLTradingAgent(
                self.state_size, self.action_size, model_path=model_file
            )
        elif training:
            if os.path.exists(model_file):
                log.info(
                    f"[{self.symbol}] Loading existing model from {model_file} to continue training."
                )
                self.agent = RLTradingAgent(
                    self.state_size, self.action_size, model_path=model_file
                )
            else:
                log.info(f"[{self.symbol}] Creating new RLTrading agent for training.")
                self.agent = RLTradingAgent(self.state_size, self.action_size)
        else:
            log.error(
                f"[{self.symbol}] Model file {model_file} not found and not in training mode."
            )
            return False

        log.info(f"[{self.symbol}] RLTrading Agent setup complete.")
        return True

    def train_agent(self, total_timesteps=None):
        """Trains the RL agent for a given number of episodes."""
        if not self.agent:
            log.error(f"[{self.symbol}] Agent not set up. Cannot train.")
            return False

        if total_timesteps is None:
            total_timesteps = self.rl_config.get("training_timesteps", 10000)

        log.info(
            f"[{self.symbol}] Starting training for {total_timesteps} timesteps..."
        )

        try:
            # Training parameters
            batch_size = self.rl_config.get("batch_size", 32)
            episodes = self.rl_config.get("episodes", 100)
            timesteps_per_episode = max(1, total_timesteps // episodes)

            # Training loop
            for episode in range(episodes):
                state, _ = self.env.reset()
                episode_reward = 0
                done = False
                step = 0

                while not done and step < timesteps_per_episode:
                    # Choose action using epsilon-greedy policy
                    action = self.agent.act(state)

                    # Take action in environment
                    next_state, reward, done, truncated, info = self.env.step(action)
                    done = done or truncated

                    # Store experience in replay memory
                    self.agent.remember(state, action, reward, next_state, done)

                    # Update state and accumulate reward
                    state = next_state
                    episode_reward += reward
                    step += 1

                    # Train the agent by replaying experiences
                    if len(self.agent.memory) > batch_size:
                        self.agent.replay(batch_size)

                # Log episode results
                log.info(
                    f"[{self.symbol}] Episode {episode+1}/{episodes}, Reward: {episode_reward:.2f}, Steps: {step}, Epsilon: {self.agent.epsilon:.4f}"
                )

                # Save model periodically
                if (episode + 1) % 10 == 0:
                    self.save_agent()

            # Final save after training
            self.save_agent()
            self.total_timesteps_trained += total_timesteps
            log.info(
                f"[{self.symbol}] Training finished. Total timesteps trained: {self.total_timesteps_trained}"
            )
            return True

        except Exception as e:
            log.exception(f"[{self.symbol}] Error during training: {e}", exc_info=True)
            return False

    def predict_action(self, state):
        """Predicts the next action based on the current state."""
        if not self.agent:
            log.error(f"[{self.symbol}] Agent not set up. Cannot predict action.")
            return 0  # Default action (hold)

        try:
            # Ensure state has correct shape
            if len(state) != self.state_size:
                log.error(
                    f"[{self.symbol}] State size mismatch. Expected {self.state_size}, got {len(state)}. Cannot predict."
                )
                return 0

            # Get action from agent (deterministic during inference)
            action = self.agent.act(state, training=False)
            log.debug(f"[{self.symbol}] Predicted action: {action}")
            return action

        except Exception as e:
            log.error(f"[{self.symbol}] Error predicting action: {e}", exc_info=True)
            return 0  # Default action (hold)

    def save_agent(self):
        """Saves the current model state."""
        if not self.agent:
            log.error(f"[{self.symbol}] Agent not set up. Cannot save.")
            return

        model_file = f"{self.model_path}.h5"
        try:
            log.info(f"[{self.symbol}] Saving model to {model_file}...")
            self.agent.save_model(model_file)
            log.info(f"[{self.symbol}] Model saved successfully.")
        except Exception as e:
            log.error(f"[{self.symbol}] Error saving model: {e}", exc_info=True)

    def get_pair_preference_score(self, state):
        """Returns a score indicating the agent's preference for trading this pair."""
        if not self.agent:
            return 0.5  # Neutral score

        try:
            # Use the agent's model to predict Q-values for all actions
            state_reshaped = np.reshape(state, [1, self.state_size, 1])
            q_values = self.agent.model.predict(state_reshaped, verbose=0)[0]

            # Calculate preference score based on the maximum Q-value
            # Normalize to 0-1 range (higher is better)
            max_q = np.max(q_values)
            min_possible_q = -10  # Approximate minimum possible Q-value
            max_possible_q = 10  # Approximate maximum possible Q-value
            preference = (max_q - min_possible_q) / (max_possible_q - min_possible_q)
            preference = np.clip(preference, 0, 1)

            return float(preference)

        except Exception as e:
            log.error(
                f"[{self.symbol}] Error calculating pair preference: {e}", exc_info=True
            )
            return 0.5  # Neutral score on error


# --- Training Worker Function --- #


def rl_training_worker(config_path, symbol):
    """Function to run the RL training process for a specific symbol using RLTrading."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        log.error(
            f"[{symbol}] Error loading config {config_path} in training worker: {e}",
            exc_info=True,
        )
        return False

    log.info(f"[{symbol}] Starting RLTrading training worker...")
    agent = RLAgent(config, symbol)

    if agent.setup_agent(training=True):
        # Get training parameters from config
        train_steps = agent.rl_config.get("train_steps_per_trigger", 10000)
        success = agent.train_agent(total_timesteps=train_steps)

        if success:
            log.info(f"[{symbol}] RLTrading training completed successfully.")
            return True
        else:
            log.error(f"[{symbol}] RLTrading training failed.")
            return False
    else:
        log.error(f"[{symbol}] Failed to set up RLTrading agent for training.")
        return False

    log.info(f"[{symbol}] RLTrading training worker finished.")


# Example usage (for testing structure)
# if __name__ == '__main__':
#     print("RLAgent class and training worker defined.")
#     # Example: Load config
#     # config = yaml.safe_load(open('../config/config.yaml', 'r'))
#     # agent = RLAgent(config, 'BTCUSDT')
#     # if agent.setup_agent(training=True):
#     #     agent.train_agent(1000) # Train for 1000 steps
#     #     obs = agent.env.observation_space.sample()
#     #     action = agent.predict_action(obs)
#     #     print("Sample Obs:", obs)
#     #     print("Predicted Action:", action)
