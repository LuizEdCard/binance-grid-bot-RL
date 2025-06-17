import logging
import os
import sys
import glob
import shutil
from datetime import datetime
from logging.handlers import RotatingFileHandler

import yaml

# Load configuration to get logging settings
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


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

def get_timestamped_log_path(base_path: str) -> str:
    """Generate timestamped log file path to preserve execution history"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(base_path)
    base_name = os.path.basename(base_path)
    name_without_ext = os.path.splitext(base_name)[0]
    
    # Create timestamped filename: bot_20241217_143052.log
    timestamped_name = f"{name_without_ext}_{timestamp}.log"
    timestamped_path = os.path.join(base_dir, timestamped_name)
    
    return timestamped_path

def create_execution_log_info():
    """Create execution info file with timestamp and details"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execution_info = {
            "timestamp": timestamp,
            "log_preservation": "enabled",
            "message": "Logs preserved for historical analysis"
        }
        
        info_file = os.path.join(LOG_DIR, "execution_info.txt")
        with open(info_file, "a") as f:
            f.write(f"\n=== EXECUTION START: {timestamp} ===\n")
            f.write(f"Logs will be preserved with timestamp suffix\n")
        
        print(f"📝 Execution logged at: {timestamp}")
        print("🔒 Log preservation: ENABLED (no files will be deleted)")
        
    except Exception as e:
        print(f"⚠️ Warning: Could not create execution info: {e}")

def cleanup_very_old_logs(days_to_keep: int = 7):
    """Optional: Clean logs older than specified days (default: keep 7 days)"""
    try:
        import time
        current_time = time.time()
        seconds_to_keep = days_to_keep * 24 * 60 * 60
        
        cleaned_count = 0
        for root, dirs, files in os.walk(LOG_DIR):
            for file in files:
                if file.endswith('.log'):
                    file_path = os.path.join(root, file)
                    file_age = current_time - os.path.getctime(file_path)
                    
                    if file_age > seconds_to_keep:
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                            print(f"🗑️ Removed old log (>{days_to_keep} days): {file_path}")
                        except:
                            pass
        
        if cleaned_count > 0:
            print(f"🧹 Cleaned {cleaned_count} old log files (older than {days_to_keep} days)")
        else:
            print(f"✅ No old logs to clean (keeping {days_to_keep} days of history)")
            
    except Exception as e:
        print(f"⚠️ Warning: Could not clean very old logs: {e}")

# Create execution info instead of cleaning logs
create_execution_log_info()

# Optionally clean very old logs (7+ days) - uncomment if needed
# cleanup_very_old_logs(days_to_keep=7)

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

    # File Handler with timestamped logs - Preserve execution history
    if log_file_path:
        # Generate timestamped log file path
        timestamped_log_path = get_timestamped_log_path(log_file_path)
        
        # Also create a "latest.log" symlink for easy access
        latest_log_path = os.path.join(os.path.dirname(log_file_path), "latest.log")
        
        # Create file handler with timestamped path
        fh = logging.FileHandler(timestamped_log_path)
        fh.setLevel(log_level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        # Create/update symlink to latest log for convenience
        try:
            if os.path.exists(latest_log_path) or os.path.islink(latest_log_path):
                os.remove(latest_log_path)
            os.symlink(os.path.basename(timestamped_log_path), latest_log_path)
            print(f"📝 Logs: {timestamped_log_path}")
            print(f"🔗 Latest: {latest_log_path} -> {os.path.basename(timestamped_log_path)}")
        except Exception as e:
            print(f"⚠️ Could not create latest.log symlink: {e}")
            print(f"📝 Logs: {timestamped_log_path}")

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
