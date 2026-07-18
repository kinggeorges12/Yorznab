"""
Custom logging implementation with emoji formatting.

This module provides a CustomLogger class that extends Python's logging.Logger
with emoji-based formatting for console output and file logging.
"""

import logging
import os
import sys
from datetime import datetime
import tempfile
from threading import Lock

# Import classes
from server.utils.keystore import KeyStore
from server.utils.timeformatter import TimezoneAware


class TimezoneAwareFormatter(logging.Formatter):
    """Formatter that adds timezone awareness to timestamps."""
    
    def formatTime(self, record, datefmt=None):
        """
        Format the time with timezone awareness.
        
        Args:
            record: The log record
            datefmt: Date format string (optional)
        
        Returns:
            Formatted time string
        """
        # Convert the record's created timestamp to datetime with timezone
        dt = datetime.fromtimestamp(record.created, tz=TimezoneAware.TIMEZONE)
        
        if datefmt:
            return dt.strftime(datefmt)
        else:
            # Default ISO format - the datetime already has timezone info
            return dt.isoformat()


class EmojiFormatter(logging.Formatter):
    """Formatter that adds emojis based on log level (no timestamps)."""
    
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


class CustomLogger:
    """
    Custom logger with emoji formatting and file logging support.
    Uses singleton pattern to share handlers across all logger instances.
    """
    
    _instance = None
    _lock = Lock()
    _initialized = False
    _silent = False
    _enable_log = True
    _level = os.environ.get("LOG_LEVEL", logging.DEBUG)
    _shared_handlers = []
    _log_file = None
    
    def __new__(cls, name=None, silent=None, enable_log=None): # pylint: disable=unused-argument
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, name=None, silent=None, enable_log=None):
        """
        Initialize a logger instance.
        
        Args:
            name: Logger name (defaults to calling module name)
            silent: If True, suppress console output
            enable_log: If True, enable file logging
        """
        # Set instance attributes
        if not hasattr(self, "_name"):
            self._name = name or __name__
        
        if not hasattr(self, "_logger"):
            self._logger = logging.getLogger(self._name)
        
        # Handle configuration updates
        with self.__class__._lock:
            if silent is not None:
                self.__class__._silent = silent
            if enable_log is not None:
                self.__class__._enable_log = enable_log
        
        # Initialize shared handlers if not already done
        if not self.__class__._initialized:
            self._initialize_handlers()
        
        # Clear any existing handlers on this logger
        self._logger.handlers.clear()
        
        # Attach shared handlers
        for handler in self.__class__._shared_handlers:
            self._logger.addHandler(handler)
        
        # Set log level
        self._logger.setLevel(self.__class__._level)
    
    def _initialize_handlers(self):
        """Initialize the shared handlers for all logger instances."""
        with self.__class__._lock:
            if self.__class__._initialized:
                return
            
            self.__class__._shared_handlers = []
            
            # Console handler - only emojis, no timestamps
            if not self.__class__._silent:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(self.__class__._level)
                console_formatter = EmojiFormatter('%(message)s')
                console_handler.setFormatter(console_formatter)
                self.__class__._shared_handlers.append(console_handler)
            
            # File handler - full format with timestamps
            if self.__class__._enable_log:
                app_id = KeyStore.get_key('UNIQUE_APPID')
                log_id = app_id[:6] if app_id else "unknown"
                LOG_DIR = os.getenv("LOG_DIR")
                if LOG_DIR:
                    os.makedirs(LOG_DIR, exist_ok=True)
                else:
                    LOG_DIR = tempfile.gettempdir()
                
                self.__class__._log_file = os.path.join(
                    LOG_DIR, 
                    f"{log_id}-{TimezoneAware.filename()}.log"
                )
                
                file_handler = logging.FileHandler(
                    self.__class__._log_file, 
                    encoding='utf-8'
                )
                file_handler.setLevel(self.__class__._level)
                file_formatter = TimezoneAwareFormatter(
                    '[%(asctime)s *%(levelname)s*] [%(name)s] %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S.%f%z'
                )
                file_handler.setFormatter(file_formatter)
                self.__class__._shared_handlers.append(file_handler)
            
            self.__class__._initialized = True
    
    # Delegate logging methods to the underlying logger
    def debug(self, msg, *args, **kwargs):
        """Log a debug message."""
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        """Log an info message."""
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        """Log a warning message."""
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        """Log an error message."""
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        """Log a critical message."""
        self._logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        """Log an exception message with traceback."""
        self._logger.exception(msg, *args, **kwargs)
    
    def log(self, level, msg, *args, **kwargs):
        """Log a message at the specified level."""
        self._logger.log(level, msg, *args, **kwargs)
    
    def setLevel(self, level):
        """Set the logging level."""
        self.__class__._level = level
        self._logger.setLevel(level)
        for handler in self.__class__._shared_handlers:
            handler.setLevel(level)
    
    def get_log_file(self):
        """Get the path to the current log file."""
        return self.__class__._log_file
    
    @classmethod
    def configure(cls, silent=None, enable_log=None, level=None):
        """
        Configure the logging system globally.
        
        Args:
            silent: If True, suppress console output
            enable_log: If True, enable file logging
            level: Log level (e.g., logging.DEBUG, logging.INFO)
        """
        with cls._lock:
            if silent is not None:
                cls._silent = silent
            if enable_log is not None:
                cls._enable_log = enable_log
            if level is not None:
                cls._level = level
            
            # Reset initialization to force handler recreation
            cls._initialized = False
            cls._shared_handlers = []
        
        # Get or create instance to reinitialize
        instance = cls()
        instance._initialize_handlers()
        
        # Reattach handlers to existing loggers
        for handler in cls._shared_handlers:
            handler.setLevel(cls._level)


# Convenience function for backward compatibility
def get_logger(name=None, silent=None, enable_log=None):
    """
    Convenience function to get a logger instance.
    
    Args:
        name: Logger name
        silent: If True, suppress console output
        enable_log: If True, enable file logging
    
    Returns:
        CustomLogger instance
    """
    return CustomLogger(name=name, silent=silent, enable_log=enable_log)