# Main entry point for the Grid Trading RL Bot

from utils.social_listener import SocialListener
from utils.hybrid_sentiment_analyzer import HybridSentimentAnalyzer
from utils.logger import log, setup_logger
from utils.api_client import APIClient
from utils.alerter import Alerter
from core.capital_management import CapitalManager
from core.rl_agent import RLAgent
from core.risk_management import RiskManager
from core.pair_selector import PairSelector
from core.grid_logic import GridLogic
import praw  # Added import for praw
import multiprocessing
import os
import signal
import sys
import threading
import time
from collections import deque  # For storing recent sentiment scores

import numpy as np  # For calculating moving average
import yaml
from dotenv import load_dotenv

# Add src directory to Python path
SRC_DIR = os.path.dirname(__file__)
sys.path.append(SRC_DIR)


# --- Shared State (Consider a more robust state management if needed) --- #
latest_sentiment_score = 0.0
sentiment_score_lock = threading.Lock()
sentiment_history = deque(maxlen=10)  # Store last 10 scores for smoothing
last_positive_alert_time = 0
last_negative_alert_time = 0


def get_latest_sentiment_score(smoothed=True):
    """Safely gets the latest calculated sentiment score.

    Args:
        smoothed (bool): If True, returns the moving average. Otherwise, the raw latest score.

    Returns:
        float: The sentiment score.
    """
    with sentiment_score_lock:
        if smoothed and len(sentiment_history) > 0:
            return np.mean(list(sentiment_history))
        return latest_sentiment_score


def update_sentiment_score(new_score):
    """Safely updates the latest sentiment score and history."""
    global latest_sentiment_score
    with sentiment_score_lock:
        latest_sentiment_score = new_score
        # Ensure history uses the specified maxlen from config if available, else default
        # This requires config access here or passing maxlen during init
        sentiment_history.append(new_score)
        # Log the raw score and the smoothed score for clarity
        log.info(
            f"[Sentiment] Updated sentiment score: {new_score:.4f} (Smoothed: {get_latest_sentiment_score(smoothed=True):.4f}) History size: {len(sentiment_history)}"
        )


def check_and_send_sentiment_alerts(current_score, config, alerter):
    """Checks sentiment score against thresholds and sends alerts if needed, respecting cooldown."""
    global last_positive_alert_time, last_negative_alert_time

    sentiment_config = config.get("sentiment_analysis", {})
    alert_config = sentiment_config.get("alerts", {})

    if not alert_config.get("enabled", False):
        return

    positive_threshold = alert_config.get("positive_threshold", 0.7)
    negative_threshold = alert_config.get("negative_threshold", -0.5)
    cooldown_seconds = alert_config.get("alert_cooldown_minutes", 120) * 60
    current_time = time.time()

    try:
        # Check for Positive Alert
        if current_score >= positive_threshold:
            if current_time - last_positive_alert_time > cooldown_seconds:
                log.info(
                    f"[Sentiment] Positive threshold ({positive_threshold}) reached. Sending alert."
                )
                alerter.send_message(
                    f"\U0001f7e2 Market Sentiment HIGH: {current_score:.2f} (Threshold: {positive_threshold})",
                    level="WARNING",
                )  # Corrected f-string to simple string
                last_positive_alert_time = current_time
            else:
                log.debug(
                    f"[Sentiment] Positive threshold reached, but alert is on cooldown."
                )

        # Check for Negative Alert
        elif current_score <= negative_threshold:
            if current_time - last_negative_alert_time > cooldown_seconds:
                log.info(
                    f"[Sentiment] Negative threshold ({negative_threshold}) reached. Sending alert."
                )
                alerter.send_message(
                    f"\U0001f534 Market Sentiment LOW: {current_score:.2f} (Threshold: {negative_threshold})",
                    level="WARNING",
                )  # Corrected f-string to simple string
                last_negative_alert_time = current_time
            else:
                log.debug(
                    f"[Sentiment] Negative threshold reached, but alert is on cooldown."
                )

    except Exception as e:
        log.error(f"[Sentiment] Error sending sentiment alert: {e}", exc_info=True)


# --- Configuration Loading --- #


ROOT_DIR = os.path.dirname(SRC_DIR)
ENV_PATH = os.path.join(ROOT_DIR, "secrets", ".env")
CONFIG_PATH = os.path.join(ROOT_DIR, "config", "config.yaml")

load_dotenv(dotenv_path=ENV_PATH)


def load_config():
    """Loads the YAML configuration file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = yaml.safe_load(f)
            if config_data is None:
                log.warning(f"Config file {CONFIG_PATH} is empty or invalid.")
                return {}
            log.info(f"Configuration loaded successfully from {CONFIG_PATH}")
            # Update sentiment history maxlen based on config
            global sentiment_history
            smoothing_window = config_data.get("sentiment_analysis", {}).get(
                "smoothing_window", 10
            )
            if smoothing_window > 0 and sentiment_history.maxlen != smoothing_window:
                log.info(
                    f"[Sentiment] Setting history window to {smoothing_window} based on config."
                )
                sentiment_history = deque(
                    list(sentiment_history), maxlen=smoothing_window
                )
            elif smoothing_window <= 0 and sentiment_history.maxlen != 1:
                log.info(
                    "[Sentiment] Disabling sentiment score smoothing based on config (window <= 0)."
                )
                sentiment_history = deque(
                    list(sentiment_history), maxlen=1
                )  # Store only the last score

            return config_data
    except FileNotFoundError:
        log.error(f"Configuration file not found at {CONFIG_PATH}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Error loading configuration: {e}")
        sys.exit(1)


# --- Worker Process Function --- #


def trading_pair_worker(
    symbol: str,
    config: dict,
    stop_event: multiprocessing.Event,
    global_trade_counter: multiprocessing.Value,
):
    """Function executed by each process to manage a single trading pair."""
    worker_log = setup_logger(f"{symbol}_worker")
    log.info(f"[{symbol}] Worker process started (PID: {os.getpid()}).")

    operation_mode = config.get("operation_mode", "Shadow").lower()
    log.info(f"[{symbol}] Operating in {operation_mode.upper()} mode.")

    try:
        api_client = APIClient(config, operation_mode=operation_mode)
        alerter = Alerter(api_client)
        
        # Initialize capital manager and validate symbol before grid initialization
        capital_manager = CapitalManager(api_client, config)
        
        # Check if we have sufficient capital for this symbol
        min_capital = capital_manager.min_capital_per_pair_usd
        if not capital_manager.can_trade_symbol(symbol, min_capital):
            log.error(f"[{symbol}] Insufficient capital to trade. Minimum required: ${min_capital:.2f}")
            capital_manager.log_capital_status()
            return
        
        # Get capital allocation for this symbol
        allocation = capital_manager.get_allocation_for_symbol(symbol)
        if not allocation:
            # Calculate allocation for single symbol
            allocations = capital_manager.calculate_optimal_allocations([symbol])
            if not allocations:
                log.error(f"[{symbol}] No capital can be allocated for trading")
                return
            allocation = allocations[0]
        
        log.info(f"[{symbol}] Capital allocated: ${allocation.allocated_amount:.2f} ({allocation.market_type}, {allocation.grid_levels} levels)")
        
        # Initialize grid logic with capital-adapted configuration
        adapted_config = config.copy()
        adapted_config['initial_levels'] = allocation.grid_levels
        adapted_config['initial_spacing_perc'] = str(allocation.spacing_percentage)
        adapted_config['max_position_size_usd'] = allocation.max_position_size
        
        grid_logic = GridLogic(
            symbol, adapted_config, api_client, 
            operation_mode=operation_mode, 
            market_type=allocation.market_type
        )
        # Pass the getter function for sentiment score
        risk_manager = RiskManager(
            symbol,
            config,
            grid_logic,
            api_client,
            alerter,
            get_sentiment_score_func=get_latest_sentiment_score,
        )
        rl_agent = RLAgent(config, symbol)

        if not rl_agent.setup_agent(training=False):
            log.error(f"[{symbol}] Failed to setup RL agent. Exiting worker.")
            return

        cycle_interval_seconds = config.get("trading", {}).get(
            "cycle_interval_seconds", 60
        )
        local_trade_count = grid_logic.total_trades  # Initialize local counter

        while not stop_event.is_set():
            start_time = time.time()
            # Get latest SMOOTHED score for decisions/logging
            current_sentiment = get_latest_sentiment_score(smoothed=True)
            log.info(
                f"[{symbol}] Starting trading cycle... (Current Sentiment: {current_sentiment:.4f})"
                + (
                    " (Sentiment Analysis Active)"
                    if config.get("sentiment_analysis", {}).get("enabled")
                    else ""
                )
            )

            try:
                # 1. Get RL Action
                # Get and validate RL action with better error handling
                rl_action = None
                if rl_agent:
                    try:
                        market_state = grid_logic.get_market_state()
                        if market_state is None:
                            log.error(f"[{symbol}] Failed to get market state for RL agent")
                        else:
                            # Validate market state format
                            if not isinstance(market_state, (list, np.ndarray)):
                                log.error(f"[{symbol}] Invalid market state format: {type(market_state)}")
                            else:
                                try:
                                    market_state = np.array(market_state, dtype=np.float32)
                                except (ValueError, TypeError) as e:
                                    log.error(f"[{symbol}] Error converting market state to numpy array: {e}")
                                else:
                                    # Get sentiment if enabled
                                    use_sentiment = config.get("sentiment_analysis", {}).get("rl_feature", {}).get("enabled", False)
                                    if use_sentiment:
                                        try:
                                            current_sentiment = get_latest_sentiment_score(smoothed=True)
                                            if current_sentiment is None:
                                                log.warning(f"[{symbol}] No sentiment score available. Using RL without sentiment.")
                                                rl_action = rl_agent.predict_action(market_state)
                                            else:
                                                rl_action = rl_agent.predict_action(market_state, sentiment_score=current_sentiment)
                                                log.info(f"[{symbol}] RL agent action with sentiment {current_sentiment:.4f}: {rl_action}")
                                        except Exception as e:
                                            log.error(f"[{symbol}] Error getting RL action with sentiment: {e}", exc_info=True)
                                            try:
                                                rl_action = rl_agent.predict_action(market_state)
                                                log.info(f"[{symbol}] RL agent action (fallback without sentiment): {rl_action}")
                                            except Exception as e:
                                                log.error(f"[{symbol}] Error getting fallback RL action: {e}", exc_info=True)
                                    else:
                                        try:
                                            rl_action = rl_agent.predict_action(market_state)
                                            log.info(f"[{symbol}] RL agent action: {rl_action}")
                                        except Exception as e:
                                            log.error(f"[{symbol}] Error getting RL action: {e}", exc_info=True)
                    except Exception as e:
                        log.error(f"[{symbol}] Error in RL agent processing: {e}", exc_info=True)
                        rl_action = None

                # 2. Validate RL action before using
                if rl_action is not None:
                    try:
                        rl_action = float(rl_action)
                        if not (-1 <= rl_action <= 1):
                            log.warning(f"[{symbol}] Invalid RL action value: {rl_action}. Using default action.")
                            rl_action = 0
                    except (ValueError, TypeError) as e:
                        log.error(f"[{symbol}] Error processing RL action: {e}")
                        rl_action = 0

                # 3. Pass validated RL action to grid_logic with error handling
                try:
                    grid_logic.run_cycle(rl_action=rl_action)
                except Exception as e:
                    log.error(f"[{symbol}] Error in grid_logic cycle with RL action {rl_action}: {e}", exc_info=True)
                    if "fatal" in str(e).lower():
                        return  # Exit on fatal errors

                # 3. Run Risk Management Checks (Now potentially uses
                # sentiment)
                risk_manager.run_checks()

                # 4. Update Global Trade Counter if local count increased
                new_local_trade_count = grid_logic.total_trades
                if new_local_trade_count > local_trade_count:
                    trades_made = new_local_trade_count - local_trade_count
                    with global_trade_counter.get_lock():
                        global_trade_counter.value += trades_made
                        log.info(
                            f"[{symbol}] Reported {trades_made} new trades. Global count: {global_trade_counter.value}"
                        )
                    local_trade_count = new_local_trade_count

                log.info(f"[{symbol}] Trading cycle finished.")

            except Exception as cycle_error:
                log.exception(f"[{symbol}] Error during trading cycle: {cycle_error}")
                alerter.send_critical_alert(
                    f"Error in {symbol} trading cycle: {cycle_error}"
                )

            elapsed_time = time.time() - start_time
            wait_time = max(0, cycle_interval_seconds - elapsed_time)
            log.debug(
                f"[{symbol}] Cycle took {elapsed_time:.2f}s. Waiting {wait_time:.2f}s for next cycle."
            )
            if wait_time > 0:
                stop_event.wait(wait_time)

    except Exception as worker_error:
        log.exception(f"[{symbol}] Unhandled error in worker process: {worker_error}")
        try:
            Alerter().send_critical_alert(
                f"CRITICAL ERROR in {symbol} worker process: {worker_error}. Process terminating."
            )
        except Exception as alert_err:
            log.error(f"[{symbol}] Failed to send critical error alert: {alert_err}")
    finally:
        log.warning(f"[{symbol}] Worker process stopping (PID: {os.getpid()}).")
        try:
            if "grid_logic" in locals() and grid_logic:
                log.info(
                    f"[{symbol}] Attempting to cancel all orders on exit (if in Production mode)..."
                )
                if grid_logic.operation_mode == "production":
                    grid_logic.cancel_all_orders()
                else:
                    log.info(
                        f"[{symbol}] In Shadow mode, skipping real order cancellation."
                    )
        except Exception as cleanup_error:
            log.error(f"[{symbol}] Error during worker cleanup: {cleanup_error}")


# --- RL Training Process Function --- #


def rl_training_worker(config: dict, stop_event: multiprocessing.Event):
    """Function executed by a separate process to train the RL agent."""
    # ... (RL training logic remains the same) ...
    setup_logger("rl_trainer")
    log.info(f"[RL Trainer] Training process started (PID: {os.getpid()}).")
    alerter = Alerter()  # For sending training status updates

    try:
        # Initialize RL agent specifically for training
        # Use a generic symbol or handle multiple models
        try:
            rl_agent = RLAgent(config, symbol="GLOBAL")
            if not rl_agent.setup_agent(training=True):
                log.error("[RL Trainer] Failed to setup RL agent for training. Exiting.")
                alerter.send_critical_alert(
                    "RL Training process failed to initialize agent."
                )
                return
        except Exception as e:
            log.error(f"[RL Trainer] Error initializing RL agent: {e}", exc_info=True)
            alerter.send_critical_alert(
                f"RL Training process failed to initialize agent: {e}"
            )
            return

        log.info("[RL Trainer] Starting RL training cycle...")
        alerter.send_message("\U0001f9ee Starting RL Model Retraining... \U0001f9ee")

        # --- Training Logic --- #
        success = (
            rl_agent.train_agent()
        )  # Assuming train_agent handles the training loop
        # -------------------- #

        if success:
            log.info("[RL Trainer] RL training completed successfully.")
            alerter.send_message(
                "\U00002705 RL Model Retraining Completed Successfully. New model deployed."
            )
        else:
            log.error("[RL Trainer] RL training failed.")
            alerter.send_critical_alert("RL Model Retraining Failed! Check logs.")

    except Exception as training_error:
        log.exception(f"[RL Trainer] Unhandled error during training: {training_error}")
        alerter.send_critical_alert(
            f"CRITICAL ERROR in RL Training process: {training_error}"
        )
    finally:
        log.warning(f"[RL Trainer] Training process stopping (PID: {os.getpid()}).")


# --- Sentiment Analysis Thread Function --- #


def sentiment_analysis_worker(config: dict, stop_event: threading.Event):
    """Function executed by a separate thread to fetch and analyze sentiment."""
    setup_logger("sentiment_analyzer")
    log.info("[Sentiment] Analysis thread started.")

    sentiment_config = config.get("sentiment_analysis", {})
    if not sentiment_config.get("enabled", False):
        log.info("[Sentiment] Analysis disabled in config. Thread exiting.")
        return

    fetch_interval_seconds = sentiment_config.get("fetch_interval_minutes", 60) * 60
    reddit_config = sentiment_config.get("reddit", {})
    reddit_enabled = reddit_config.get("enabled", False)
    subreddits = reddit_config.get("subreddits", [])
    posts_limit = reddit_config.get("posts_limit_per_subreddit", 10)
    comments_limit = reddit_config.get("comments_limit_per_post", 5)
    time_filter = reddit_config.get("time_filter", "day")

    try:
        analyzer = HybridSentimentAnalyzer()  # Initialize Hybrid analyzer
        listener = SocialListener()  # Initialize Reddit listener
        alerter = Alerter()  # Initialize Alerter for sentiment alerts

        if not analyzer.gemma3_analyzer:
            log.error(
                "[Sentiment] Failed to initialize Sentiment Analyzer model. Thread exiting."
            )
            return
        if reddit_enabled and not listener.reddit:
            log.error(
                "[Sentiment] Failed to initialize Reddit Listener (check credentials). Reddit source disabled."
            )
            reddit_enabled = False

        if not reddit_enabled:  # Add checks for other sources like Twitter here later
            log.warning(
                "[Sentiment] No social media sources enabled or initialized. Thread exiting."
            )
            return

        while not stop_event.is_set():
            start_time = time.time()
            log.info("[Sentiment] Starting sentiment fetch and analysis cycle...")
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "error": 0}
            texts_analyzed = 0

            if reddit_enabled:
                for sub in subreddits:
                    try:
                        posts = listener.get_subreddit_posts(
                            sub, limit=posts_limit, time_filter=time_filter
                        )
                        for post in posts:
                            texts_to_analyze = []
                            if post.get("title"):
                                texts_to_analyze.append(post["title"])
                            if post.get("selftext"):
                                texts_to_analyze.append(post["selftext"])

                            comments = listener.get_post_comments(
                                post["id"], limit=comments_limit
                            )
                            texts_to_analyze.extend(comments)

                            for text in texts_to_analyze:
                                if not text:
                                    continue  # Skip empty texts
                                result = analyzer.analyze(text)
                                if result and "sentiment" in result:
                                    sentiment = result["sentiment"].lower()
                                    if sentiment in sentiment_counts:
                                        sentiment_counts[sentiment] += 1
                                    else:
                                        log.warning(
                                            f"[Sentiment] Unknown sentiment category '{sentiment}' from model."
                                        )
                                        sentiment_counts["error"] += 1
                                    texts_analyzed += 1
                                else:
                                    sentiment_counts["error"] += 1
                                # Optional: Short sleep within loop if hitting API limits or CPU is high
                                # time.sleep(0.1)

                            # Avoid hitting Reddit API limits too aggressively
                            # between posts
                            time.sleep(0.5)
                    except praw.exceptions.PRAWException as praw_err:
                        log.error(
                            f"[Sentiment] PRAW error processing subreddit r/{sub}: {praw_err}"
                        )
                        # Consider temporary backoff for this subreddit
                    except Exception as sub_error:
                        log.error(
                            f"[Sentiment] Error processing subreddit r/{sub}: {sub_error}",
                            exc_info=True,
                        )

            # --- Calculate Continuous Sentiment Score --- #
            pos_count = sentiment_counts["positive"]
            neg_count = sentiment_counts["negative"]
            neu_count = sentiment_counts["neutral"]
            total_valid = pos_count + neg_count + neu_count

            if total_valid > 0:
                current_raw_score = (pos_count - neg_count) / total_valid
            else:
                current_raw_score = (
                    0.0  # Default to neutral if no valid sentiments found
                )

            # Update the shared sentiment score (history handles smoothing)
            update_sentiment_score(current_raw_score)
            # -------------------------------------------- #

            log.info(
                f"[Sentiment] Analysis cycle complete. Texts analyzed: {texts_analyzed}. Counts: {sentiment_counts}. Raw Score: {current_raw_score:.4f}"
            )

            # --- Check and Send Alerts using the SMOOTHED score --- #
            smoothed_score = get_latest_sentiment_score(smoothed=True)
            check_and_send_sentiment_alerts(smoothed_score, config, alerter)
            # ------------------------------------------------------ #

            elapsed_time = time.time() - start_time
            wait_time = max(0, fetch_interval_seconds - elapsed_time)
            log.debug(
                f"[Sentiment] Cycle took {elapsed_time:.2f}s. Waiting {wait_time:.2f}s for next cycle."
            )
            if wait_time > 0:
                stop_event.wait(wait_time)

    except Exception as sentiment_worker_error:
        log.exception(
            f"[Sentiment] Unhandled error in sentiment analysis worker: {sentiment_worker_error}"
        )
        try:
            Alerter().send_critical_alert(
                f"CRITICAL ERROR in Sentiment Analysis worker: {sentiment_worker_error}. Thread terminating."
            )
        except Exception as alert_err:
            log.error(f"[Sentiment] Failed to send critical error alert: {alert_err}")
    finally:
        log.warning("[Sentiment] Analysis thread stopping.")


# --- Main Application Class --- #


class TradingBot:
    def __init__(self):
        self.config = load_config()
        setup_logger("main")
        self.operation_mode = self.config.get("operation_mode", "Shadow").lower()
        log.info(f"Bot starting in {self.operation_mode.upper()} mode.")
        self.api_client = APIClient(self.config, operation_mode=self.operation_mode)
        self.alerter = Alerter(self.api_client)
        # Pass the getter function for sentiment score to PairSelector
        self.pair_selector = PairSelector(
            self.config,
            self.api_client,
            get_sentiment_score_func=get_latest_sentiment_score,
        )
        self.processes = {}
        self.stop_event = multiprocessing.Event()  # For processes
        self.thread_stop_event = threading.Event()  # For threads
        self.max_concurrent_pairs = self.config.get("trading", {}).get(
            "max_concurrent_pairs", 5
        )
        self.global_trade_counter = multiprocessing.Value("i", 0)
        self.retraining_threshold = self.config.get("rl_agent", {}).get(
            "retraining_trade_threshold", 100
        )
        self.training_process = None
        self.last_retraining_trade_count = 0
        self.sentiment_thread = None  # Add sentiment thread attribute

    def _handle_signal(self, signum, frame):
        log.warning(
            f"Received signal {signal.Signals(signum).name}. Initiating graceful shutdown..."
            + (
                " (Sentiment Analysis Active)"
                if self.config.get("sentiment_analysis", {}).get("enabled")
                else ""
            )
        )
        self.stop()

    def start(self):
        log.info(
            "Starting Trading Bot..."
            + (
                " (Sentiment Analysis Active)"
                if self.config.get("sentiment_analysis", {}).get("enabled")
                else ""
            )
        )
        sentiment_text = " with Sentiment Analysis" if self.config.get("sentiment_analysis", {}).get("enabled") else ""
        mode_text = self.operation_mode.upper()
        startup_message = f"\U0001F916 Trading Bot Starting Up - {mode_text} Mode \U0001F916{sentiment_text}"
        self.alerter.send_message(startup_message, parse_mode=None)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        # --- Start Sentiment Analysis Thread --- #
        if self.config.get("sentiment_analysis", {}).get("enabled", False):
            self._start_sentiment_thread()
        # --------------------------------------- #

        pair_update_interval = (
            self.config.get("pair_selection", {}).get("update_interval_hours", 6) * 3600
        )
        last_pair_update = 0

        while not self.stop_event.is_set():
            current_time = time.time()

            # --- Update Pair Selection Periodically (Now potentially uses sentiment) --- #
            if current_time - last_pair_update > pair_update_interval:
                log.info("Updating selected trading pairs...")
                try:
                    # Pair selector now has access to the sentiment score
                    # getter
                    selected_pairs = self.pair_selector.get_selected_pairs(
                        force_update=True
                    )
                    log.info(f"Selected pairs for trading: {selected_pairs}")
                    self._update_worker_processes(selected_pairs)
                    last_pair_update = current_time
                except Exception as e:
                    log.exception(f"Error during pair selection update: {e}")
                    self.alerter.send_critical_alert(
                        f"Error updating pair selection: {e}"
                    )

            # --- Monitor Worker Processes --- #
            self._monitor_workers()

            # --- Check for RL Retraining Trigger --- #
            self._check_and_trigger_retraining()

            # --- Monitor Sentiment Thread --- #
            self._monitor_sentiment_thread()

            monitor_interval = 60
            # Use thread_stop_event for the main loop wait if sentiment is active
            # Check both events to ensure shutdown signal from either source is
            # caught
            should_wait = True
            if self.stop_event.is_set() or self.thread_stop_event.is_set():
                should_wait = False

            if should_wait:
                # Wait for the shorter of monitor_interval or until an event is
                # set
                wait_event = (
                    self.thread_stop_event if self.sentiment_thread else self.stop_event
                )
                wait_event.wait(monitor_interval)

        log.info("Main loop exited.")
        self.stop()  # Ensure stop is called if loop exits unexpectedly

    def _start_sentiment_thread(self):
        """Starts the sentiment analysis in a separate thread."""
        if self.sentiment_thread and self.sentiment_thread.is_alive():
            log.warning("[Sentiment] Analysis thread already running.")
            return
        try:
            # Clear the event before starting the thread
            self.thread_stop_event.clear()
            self.sentiment_thread = threading.Thread(
                target=sentiment_analysis_worker,
                args=(self.config, self.thread_stop_event),
                daemon=True,
            )
            self.sentiment_thread.start()
            log.info("[Sentiment] Analysis thread started.")
        except Exception as e:
            log.exception("[Sentiment] Failed to start analysis thread: {e}")
            self.alerter.send_critical_alert(
                f"Failed to start Sentiment Analysis thread: {e}"
            )

    def _monitor_sentiment_thread(self):
        """Checks if the sentiment thread is alive and restarts if needed."""
        if not self.config.get("sentiment_analysis", {}).get("enabled", False):
            return

        if self.sentiment_thread and not self.sentiment_thread.is_alive():
            log.warning(
                "[Sentiment] Analysis thread is not alive. Attempting restart..."
            )
            self.alerter.send_critical_alert(
                "[Sentiment] Analysis thread died unexpectedly. Restarting..."
            )
            # Don't clear stop event here, restart will handle it
            self._start_sentiment_thread()

    def _update_worker_processes(self, selected_pairs):
        # ... (Worker update logic remains the same) ...
        current_symbols = set(self.processes.keys())
        target_symbols = set(selected_pairs)

        symbols_to_stop = current_symbols - target_symbols
        for symbol in symbols_to_stop:
            log.info(f"Stopping worker process for deselected pair: {symbol}")
            process = self.processes.pop(symbol)
            if process.is_alive():
                try:
                    os.kill(process.pid, signal.SIGTERM)
                    process.join(timeout=15)
                    if process.is_alive():
                        log.warning(
                            f"Process for {symbol} did not terminate gracefully after SIGTERM. Sending SIGKILL."
                        )
                        process.kill()
                        process.join(timeout=5)
                except Exception as term_err:
                    log.error(f"Error terminating process {symbol}: {term_err}")
                    if process.is_alive():
                        process.kill()
            log.info(f"Worker process for {symbol} stopped.")

        symbols_to_start = target_symbols - current_symbols
        for symbol in symbols_to_start:
            if len(self.processes) >= self.max_concurrent_pairs:
                log.warning(
                    f"Reached max concurrent pairs ({self.max_concurrent_pairs}). Cannot start worker for {symbol}."
                )
                continue
            log.info(f"Starting worker process for new pair: {symbol}")
            process = multiprocessing.Process(
                target=trading_pair_worker,
                args=(symbol, self.config, self.stop_event, self.global_trade_counter),
                daemon=True,
            )
            self.processes[symbol] = process
            process.start()

    def _monitor_workers(self):
        # ... (Worker monitoring logic remains the same) ...
        restarted_count = 0
        for symbol, process in list(self.processes.items()):
            if not process.is_alive():
                log.warning(
                    f"Worker process for {symbol} (PID: {process.pid}) is not alive. Exit code: {process.exitcode}. Attempting restart..."
                )
                self.alerter.send_critical_alert(
                    f"Worker process for {symbol} died unexpectedly (Exit code: {process.exitcode}). Restarting..."
                )
                del self.processes[symbol]
                try:
                    log.info(f"Restarting worker process for {symbol}")
                    new_process = multiprocessing.Process(
                        target=trading_pair_worker,
                        args=(
                            symbol,
                            self.config,
                            self.stop_event,
                            self.global_trade_counter,
                        ),
                        daemon=True,
                    )
                    self.processes[symbol] = new_process
                    new_process.start()
                    restarted_count += 1
                except Exception as e:
                    log.exception(f"Failed to restart worker process for {symbol}: {e}")
                    self.alerter.send_critical_alert(
                        f"FAILED to restart worker process for {symbol}: {e}"
                    )
        if restarted_count > 0:
            log.info(f"Restarted {restarted_count} worker processes.")

    def _check_and_trigger_retraining(self):
        # ... (RL retraining trigger logic remains the same) ...
        if self.retraining_threshold <= 0:
            return  # Retraining disabled

        with self.global_trade_counter.get_lock():
            current_trade_count = self.global_trade_counter.value

        trades_since_last_retrain = (
            current_trade_count - self.last_retraining_trade_count
        )

        if trades_since_last_retrain >= self.retraining_threshold:
            log.info(
                f"Trade threshold ({self.retraining_threshold}) reached. Current count: {current_trade_count}."
            )
            if self.training_process and self.training_process.is_alive():
                log.warning("Retraining already in progress. Skipping trigger.")
            else:
                log.info("Triggering RL model retraining...")
                self.last_retraining_trade_count = (
                    current_trade_count  # Reset counter base
                )
                self._start_training_process()
        else:
            log.debug(
                f"Trades since last retrain: {trades_since_last_retrain}/{self.retraining_threshold}"
            )

        # Clean up finished training process
        if self.training_process and not self.training_process.is_alive():
            log.info(
                f"RL training process finished with exit code {self.training_process.exitcode}. Joining..."
            )
            self.training_process.join()  # Ensure resources are released
            self.training_process = None

    def _start_training_process(self):
        # ... (RL training start logic remains the same) ...
        try:
            self.training_process = multiprocessing.Process(
                target=rl_training_worker,
                args=(self.config, self.stop_event),
                daemon=True,
            )
            self.training_process.start()
            log.info(f"RL training process started (PID: {self.training_process.pid}).")
        except Exception as e:
            log.exception("Failed to start RL training process: {e}")
            self.alerter.send_critical_alert(
                f"Failed to start RL training process: {e}"
            )

    def stop(self):
        if self.stop_event.is_set() and self.thread_stop_event.is_set():
            log.info("Shutdown already in progress.")
            return

        log.info("Initiating bot shutdown sequence...")
        self.stop_event.set()  # Signal processes to stop
        self.thread_stop_event.set()  # Signal threads to stop

        # Stop sentiment thread first
        if self.sentiment_thread and self.sentiment_thread.is_alive():
            log.info("Waiting for sentiment analysis thread to finish...")
            self.sentiment_thread.join(timeout=30)
            if self.sentiment_thread.is_alive():
                log.warning("[Sentiment] Analysis thread did not stop gracefully.")

        # Stop training process if running
        if self.training_process and self.training_process.is_alive():
            log.info("Terminating RL training process...")
            self.training_process.terminate()
            self.training_process.join(timeout=10)
            if self.training_process.is_alive():
                self.training_process.kill()

        # Stop worker processes
        log.info("Stopping worker processes...")
        active_processes = list(self.processes.items())
        self.processes.clear()  # Clear the dict to prevent restarts during shutdown
        for symbol, process in active_processes:
            if process.is_alive():
                log.info(f"Terminating worker process for {symbol}...")
                try:
                    os.kill(process.pid, signal.SIGTERM)
                    process.join(timeout=15)
                    if process.is_alive():
                        log.warning(
                            f"Process for {symbol} did not terminate gracefully after SIGTERM. Sending SIGKILL."
                        )
                        process.kill()
                        process.join(timeout=5)
                except ProcessLookupError:
                    log.warning(f"Process for {symbol} already terminated.")
                except Exception as term_err:
                    log.error(f"Error terminating process {symbol}: {term_err}")
                    # Attempt kill as last resort if join failed
                    try:
                        if process.is_alive():
                            process.kill()
                    except Exception as e: # Ignore errors during final kill attempt
                        log.error(f"[{symbol}] Error during final kill attempt for process {process.pid}: {e}", exc_info=True)
                        pass  # Ignore errors during final kill attempt
        log.info("All worker processes stopped.")

        self.alerter.send_message("\U0001f6d1 Trading Bot Shutting Down \U0001f6d1")
        log.info("Trading Bot shutdown complete.")
        # sys.exit(0) # Let the main thread exit naturally


# --- Main Execution --- #


if __name__ == "__main__":
    bot = TradingBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        log.warning("KeyboardInterrupt received in main. Shutting down...")
        # bot.stop() # stop() is called within start() loop exit or exception
    except Exception as main_error:
        log.exception(f"Unhandled error in main execution: {main_error}")
        try:
            bot.alerter.send_critical_alert(
                f"FATAL ERROR in main execution: {main_error}. Bot shutting down."
            )
        except Exception as alert_err:
            log.error(f"Failed to send fatal error alert: {alert_err}")
        # bot.stop() # stop() is called within start() loop exit or exception
    finally:
        # Ensure stop is called if start() exits unexpectedly
        if not bot.stop_event.is_set():
            bot.stop()
