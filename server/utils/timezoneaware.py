
from datetime import datetime
import os
from zoneinfo import ZoneInfo


class TimezoneAware:
    """
    A mixin class that provides timezone-aware datetime functionality.
    """
    # Get timezone from Docker environment variable, fallback to UTC
    TIMEZONE_STR:str = os.environ.get('TZ', 'UTC')
    TIMEZONE:ZoneInfo = ZoneInfo(TIMEZONE_STR)
    @classmethod
    def get_now(cls) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(cls.TIMEZONE)