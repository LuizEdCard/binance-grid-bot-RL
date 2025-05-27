import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import yaml

# Load configuration to get logging settings
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
LOG_DIR = "/home/ubuntu/grid_trading_rl_bot/logs"


def load_config():
    """Loads the YAML configuration file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {CONFIG_PATH}", file=sys.stderr)
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}", file=sys.stderr)
        return {}


config = load_config()
log_config = config.get("logging", {})

log_level_str = log_config.get("level", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
log_to_console = log_config.get("log_to_console", True)
log_file_path = log_config.get("log_file", os.path.join(LOG_DIR, "bot.log"))

# Ensure log directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)


def setup_logger(name="grid_bot"):
    """Sets up the main logger for the application."""
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.propagate = False  # Prevent duplicate logs in parent loggers

    # Avoid adding handlers if they already exist
    if logger.hasHandlers():
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    if log_to_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(log_level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File Handler (Rotating)
    if log_file_path:
        # Rotate logs: 5 files, 5MB each
        fh = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=5)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


# Initialize the default logger
log = setup_logger()

# Example usage (can be removed or commented out)
# if __name__ == '__main__':
#     log.debug('This is a debug message.')
#     log.info('This is an info message.')
#     log.warning('This is a warning message.')
#     log.error('This is an error message.')
#     log.critical('This is a critical message.')
