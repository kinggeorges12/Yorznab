"""
Custom logging implementation with emoji formatting.

This module provides a CustomLogger class that extends Python's logging.Logger
with emoji-based formatting for console output and detailed file logging.
"""

import logging
import os
import sys
import tempfile
import uuid


class EmojiFormatter(logging.Formatter):
    """Custom formatter that adds emojis based on log level."""
    
    def format(self, record):
        # Add emojis based on log level
        if record.levelno == logging.DEBUG:
            record.msg = f"🔍 {record.msg}"
        elif record.levelno == logging.INFO:
            record.msg = f"💡 {record.msg}"
        elif record.levelno == logging.WARNING:
            record.msg = f"⚠️ {record.msg}"
        elif record.levelno == logging.ERROR:
            record.msg = f"❌ {record.msg}"
        elif record.levelno == logging.CRITICAL:
            record.msg = f"🚨 {record.msg}"
        
        return super().format(record)


class CustomLogger(logging.Logger):
    """Custom logger with emoji formatting and file logging support."""
    
    def __init__(self, name: str = None, noninteractive: bool = False, enable_log: bool = False, logger: logging.Logger = None):
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
            self.setLevel(logging.DEBUG)
            
            # Console handler (only if interactive)
            if not noninteractive:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(logging.INFO)
                
                console_formatter = EmojiFormatter('%(message)s')
                console_handler.setFormatter(console_formatter)
                self.addHandler(console_handler)
            
            # File handler (if logging enabled)
            if enable_log:
                temp_dir = tempfile.gettempdir()
                script_name = name
                log_id = str(uuid.uuid4())[:8]
                log_file = os.path.join(temp_dir, f"{script_name}-{log_id}.log")
                
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(logging.DEBUG)
                
                # Detailed formatter for file logging
                file_formatter = logging.Formatter(
                    '[%(asctime)s *%(levelname)s*] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
                )
                file_handler.setFormatter(file_formatter)
                self.addHandler(file_handler)
                
                self.info(f"🔒 Logging enabled: {log_file}")


def setup_logging(noninteractive: bool = False, enable_log: bool = False) -> CustomLogger:
    """Set up and return a CustomLogger instance."""
    return CustomLogger(__name__, noninteractive=noninteractive, enable_log=enable_log)
