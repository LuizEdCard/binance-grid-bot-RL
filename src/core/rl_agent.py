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
        """Calculate reward based on trading performance and grid state."""
        try:
            # Get current market state
            current_price = self.history_df["Close"].iloc[-1]
            prev_price = self.history_df["Close"].iloc[-2]
            
            # Initialize reward components with weights
            weights = {
                'price_change': 0.3,
                'grid_profit': 0.3,
                'risk_management': 0.2,
                'trading_efficiency': 0.2
            }
            
            reward = 0.0
            
            # 1. Price change component
            price_change = (current_price - prev_price) / prev_price
            price_change_reward = np.clip(price_change * 10, -1, 1)
            reward += weights['price_change'] * price_change_reward
            
            # 2. Grid performance component
            grid_profit = 0.0
            if hasattr(self, "grid_logic") and self.grid_logic:
                status = self.grid_logic.get_status()
                grid_profit = float(status.get("total_profit_loss", 0.0))
                
                # Add trading efficiency
                total_trades = status.get("total_trades", 0)
                successful_trades = status.get("successful_trades", 0)
                if total_trades > 0:
                    efficiency = successful_trades / total_trades
                    reward += weights['trading_efficiency'] * (efficiency - 0.5)
            
            grid_profit_reward = np.clip(grid_profit * 5, -1, 1)
            reward += weights['grid_profit'] * grid_profit_reward
            
            # 3. Risk management component
            risk_penalty = 0.0
            
            # Volatility check
            volatility = np.std(self.history_df["Close"].pct_change().dropna())
            if volatility > 0.02:  # 2% volatility threshold
                risk_penalty -= 0.2
                
            # Drawdown check
            drawdown = (self.history_df["Close"].max() - current_price) / self.history_df["Close"].max()
            if drawdown > 0.1:  # 10% drawdown threshold
                risk_penalty -= 0.3
                
            # Position size check
            if hasattr(self, "grid_logic") and self.grid_logic:
                status = self.grid_logic.get_status()
                if "position_size" in status:
                    position_size = abs(float(status["position_size"]))
                    if position_size > 0.9:  # Near max position size
                        risk_penalty -= 0.2
            
            reward += weights['risk_management'] * np.clip(risk_penalty, -1, 0)
            
            # Clip final reward
            reward = np.clip(reward, -1, 1)
                
            return reward
            
        except Exception as e:
            log.error(f"[{self.symbol}] Error calculating reward: {e}", exc_info=True)
            return 0.0

    def _calculate_state_size(self):
        """Calculate the total state size based on enabled features."""
        state_dim = 0
        
        # Count standard indicators
        for indicator in ["rsi", "atr", "adx"]:
            if indicator in self.rl_config.get("state_features", {}).get("technical_indicators", []):
                state_dim += 1
        
        # Count grid context features
        if self.rl_config.get("state_features", {}).get("grid_context", False):
            state_dim += 3  # levels, spacing, direction_bias
            
        # Count position context features
        if self.rl_config.get("state_features", {}).get("position_context", False):
            state_dim += 2  # position_size, unrealized_pnl
            
        # Count TA-Lib indicators
        if talib_available:
            for indicator in self.rl_config.get("state_features", {}).get("talib_indicators", []):
                if indicator == "macd":
                    state_dim += 1
                elif indicator == "bbands":
                    state_dim += 1
                    
        # Count TA-Lib patterns
        if talib_available:
            state_dim += len(self.rl_config.get("state_features", {}).get("talib_patterns", []))
            
        return state_dim

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
    """High-level RL Agent interface that uses RLTradingAgent for implementation."""
    
    def __init__(self, config: dict, symbol: str):
        """Initialize the RL Agent."""
        self.config = config
        self.rl_config = config.get("rl_agent", {})
        self.symbol = symbol
        
        # Fix model path handling
        models_dir = config.get("models_directory", "models")
        if not os.path.isabs(models_dir):
            # Make path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_dir = os.path.join(project_root, models_dir)
            
        # Create specific directory for this symbol
        symbol_dir = os.path.join(models_dir, self.symbol.lower())
        os.makedirs(symbol_dir, exist_ok=True)
        
        # Set model paths
        self.model_path = os.path.join(symbol_dir, "model")
        
        self.agent = None
        self.env = None
        self.state_size = self.rl_config.get("state_size", 30)
        self.action_size = self.rl_config.get("action_size", 3)
        self.total_timesteps_trained = 0
        
        log.info(f"[{self.symbol}] RLAgent initialized with state_size={self.state_size}, action_size={self.action_size}")

    def setup_agent(self, training=False):
        """Set up the RL trading agent."""
        try:
            # Create environment
            if self.env is None:
                self.env = TradingEnvironment(
                    data=None,  # Will be set when actual data is available
                    initial_balance=self.rl_config.get("initial_balance", 10000.0),
                    commission=self.rl_config.get("commission", 0.001),
                    features_window=self.rl_config.get("features_window", 30),
                    include_sentiment=self.rl_config.get("use_sentiment", False)
                )

            # Create or load agent
            if training or not os.path.exists(f"{self.model_path}.h5"):
                log.info(f"[{self.symbol}] Creating new RLTrading agent")
                self.agent = RLTradingAgent(self.state_size, self.action_size)
            else:
                log.info(f"[{self.symbol}] Loading existing model from {self.model_path}.h5")
                self.agent = RLTradingAgent(self.state_size, self.action_size)
                self.agent.load_model(f"{self.model_path}.h5")

            return True
        except Exception as e:
            log.error(f"[{self.symbol}] Error setting up agent: {e}", exc_info=True)
            return False

    def predict_action(self, state, sentiment_score=None):
        """Predict action based on current state and optional sentiment score."""
        if not self.agent:
            log.error(f"[{self.symbol}] Agent not set up. Cannot predict action.")
            return 0  # Default to HOLD

        try:
            # Validate state
            if not isinstance(state, np.ndarray):
                state = np.array(state)

            # Handle sentiment score
            if sentiment_score is not None:
                if len(state) != self.state_size - 1:  # -1 because we'll add sentiment
                    log.error(f"[{self.symbol}] Invalid state size for sentiment inclusion. Expected {self.state_size-1}, got {len(state)}")
                    return 0
                state = np.append(state, sentiment_score)
            else:
                if len(state) != self.state_size:
                    log.error(f"[{self.symbol}] Invalid state size. Expected {self.state_size}, got {len(state)}")
                    return 0

            # Reshape and predict
            state = state.reshape(1, -1)
            action = self.agent.act(state, training=False)
            log.debug(f"[{self.symbol}] Predicted action: {action}")
            return action

        except Exception as e:
            log.error(f"[{self.symbol}] Error predicting action: {e}", exc_info=True)
            return 0  # Default to HOLD

    def train_agent(self, total_timesteps=None):
        """Train the RL agent."""
        if not self.agent:
            log.error(f"[{self.symbol}] Agent not set up. Cannot train.")
            return False

        try:
            if total_timesteps is None:
                total_timesteps = self.rl_config.get("training_timesteps", 10000)

            log.info(f"[{self.symbol}] Starting training for {total_timesteps} timesteps...")
            
            # Training parameters
            batch_size = self.rl_config.get("batch_size", 32)
            episodes = self.rl_config.get("episodes", 100)
            timesteps_per_episode = max(1, total_timesteps // episodes)

            # Training loop
            for episode in range(episodes):
                state, info = self.env.reset()
                total_reward = 0
                
                for step in range(timesteps_per_episode):
                    action = self.agent.act(state, training=True)
                    next_state, reward, terminated, truncated, info = self.env.step(action)
                    done = terminated or truncated
                    
                    self.agent.remember(state, action, reward, next_state, done)
                    state = next_state
                    total_reward += reward

                    if len(self.agent.memory) > batch_size:
                        self.agent.replay(batch_size)

                    if done:
                        break

                log.info(f"[{self.symbol}] Episode {episode+1}/{episodes}, Reward: {total_reward:.2f}")
                
                # Save periodically
                if (episode + 1) % 10 == 0:
                    self.save_agent()

            self.save_agent()
            self.total_timesteps_trained += total_timesteps
            return True

        except Exception as e:
            log.error(f"[{self.symbol}] Error during training: {e}", exc_info=True)
            return False

    def save_agent(self):
        """Save the agent's model."""
        if self.agent:
            try:
                self.agent.save_model(f"{self.model_path}.h5")
                log.info(f"[{self.symbol}] Model saved to {self.model_path}.h5")
                return True
            except Exception as e:
                log.error(f"[{self.symbol}] Error saving model: {e}", exc_info=True)
        return False
        
    def calculate_pair_preference(self, market_data, sentiment_score=None):
        """Calculate preference score for this trading pair.
        
        Returns a score between 0.0 and 1.0 indicating preference for this pair.
        """
        try:
            # Implementation of pair preference calculation
            return 0.75  # Placeholder - higher means preferred
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
