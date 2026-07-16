from datetime import datetime
import os
from zoneinfo import ZoneInfo


class TimezoneAware:
    """
    A class that provides timezone-aware datetime functionality.
    Can be called with a format string to get formatted output.
    """
    # Get timezone from Docker environment variable, fallback to UTC
    TIMEZONE_STR: str = os.environ.get('TZ', 'UTC')
    TIMEZONE: ZoneInfo = ZoneInfo(TIMEZONE_STR)

    def __new__(cls, format_str: str = None):
        """Create instance or return formatted datetime string."""
        if format_str is None:
            # Return the class itself for method chaining
            return super().__new__(cls)
        else:
            # Return formatted datetime string
            return cls.now().strftime(format_str)

    def __init__(self, format_str: str = None):
        """Initialize if instance is created."""
        if format_str is not None:
            # If we got a format string, we already returned a string in __new__
            # So this only runs when format_str is None (instance creation)
            pass

    @classmethod
    def now(cls) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(cls.TIMEZONE)
    
    def __str__(self) -> str:
        """Return the formatted datetime string."""
        return self.now().strftime('%Y-%m-%d_%H-%M-%S')