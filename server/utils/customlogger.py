"""
Custom logging implementation with emoji formatting.

This module provides a CustomLogger class that extends Python's logging.Logger
with emoji-based formatting for console output and detailed file logging.
"""

import logging
import os
import sys
from datetime import datetime
import tempfile
from threading import Lock

# Import classes
from utils.keystore import KeyStore

class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emojis based on log level."""
    
    def format(self, record):
        # Add emojis based on log level
        if record.levelno == logging.DEBUG:
            record.msg = f"🔍 {record.msg}"
        elif record.levelno == logging.INFO:
            record.msg = f"ℹ️ {record.msg}"
        elif record.levelno == logging.WARNING:
            record.msg = f"⚠️ {record.msg}"
        elif record.levelno == logging.ERROR:
            record.msg = f"❌ {record.msg}"
        elif record.levelno == logging.CRITICAL:
            record.msg = f"🚨 {record.msg}"
        
        return super().format(record)


class CustomLogger(logging.Logger):
    """Custom logger with emoji formatting and file logging support."""

    _lock = Lock()
    _silent: bool = False
    _enable_log: bool = True
    _level: int = os.environ.get("LOG_LEVEL", logging.DEBUG)
    
    def __init__(self, name: str = None, silent: bool = None, enable_log: bool = None, logger: logging.Logger = None):
        with self.__class__._lock:
            if silent is not None:
                self.__class__._silent = silent
            if enable_log is not None:
                self.__class__._enable_log = enable_log

        # If a logger is provided, use it as the base
        if logger is not None:
            super().__init__(logger.name)
            # Copy the logger's configuration
            self.setLevel(logger.level)
            # Copy handlers from the provided logger
            for handler in logger.handlers:
                self.addHandler(handler)
        else:
            # Default behavior - create new logger
            super().__init__(name or __name__)
            
            # Clear any existing handlers
            self.handlers.clear()
            
            # Set log level
            self.setLevel(self.__class__._level)
            
            # Console handler (also goes to Docker logs)
            if not self.__class__._silent:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(self.__class__._level)
                
                console_formatter = EmojiFormatter('%(message)s')
                console_handler.setFormatter(console_formatter)
                self.addHandler(console_handler)
            
            # File handler (if logging enabled)
            if self.__class__._enable_log:
                app_id = KeyStore.get_key('UNIQUE_APPID')
                log_id = app_id[:6] if app_id else "unknown"  # Use first 6 chars of UNIQUE_APPID for log file naming
                LOG_DIR = os.getenv("LOG_DIR")
                if LOG_DIR:
                    os.makedirs(LOG_DIR, exist_ok=True)
                else:
                    LOG_DIR = tempfile.gettempdir()
                log_file = os.path.join(LOG_DIR, f"{log_id}-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
                
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(self.__class__._level)
                
                # Detailed formatter for file logging
                file_formatter = logging.Formatter(
                    '[%(asctime)s *%(levelname)s*] [%(name)s] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S.%SZ'
                )
                file_handler.setFormatter(file_formatter)
                self.addHandler(file_handler)
                self.debug(f"🪵 Logging started ({name}): {log_file}")

