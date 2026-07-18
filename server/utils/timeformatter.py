import contextlib
from datetime import datetime, timedelta
from functools import total_ordering
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

    def __new__(cls):
        """Create instance or return formatted datetime string."""
        return super().__new__(cls)

    def __init__(self):
        """Initialize if instance is created."""

    @classmethod
    def now(cls) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(tz=cls.TIMEZONE)
    
    @classmethod
    def filename(cls) -> str:
        """Get current time formatted for filenames."""
        return cls.strftime('%Y-%m-%d_%H-%M-%S')
    
    @classmethod
    def strftime(cls, format_str: str) -> str:
        """Get current time formatted as a string."""
        return cls.now().strftime(format_str)

    @classmethod
    def isoformat(cls, value: str | datetime = None) -> str:
        """Return the formatted datetime string."""
        return str(IsoTimeFormatter(value))

@total_ordering
class IsoTimeFormatter:
    """Utility for working with ISO-8601 UTC timestamps.

    - Constructor accepts an ISO string or blank string ("") for now (UTC)
    - __str__() returns ISO string for the stored datetime
    - compare() compares datetimes or ISO strings
    - subtract_days() returns a new instance shifted by the given days
    """

    def __init__(self, value: str | datetime = None):
        if value:
            if isinstance(value, datetime):
                self.dt = value
            elif isinstance(value, str):
                parsed: datetime | None = None
                with contextlib.suppress(Exception):
                    parsed = datetime.fromisoformat(value)
                # Default to now if parsing failed
                if parsed is None:
                    parsed = TimezoneAware.now()
                # Assume UTC if tz-naive
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=TimezoneAware.TIMEZONE)
                self.dt = parsed
        else:
           self.dt = TimezoneAware.now()

    def __str__(self) -> str:
        if self.dt is None:
            return ""
        return self.dt.isoformat()

    @staticmethod
    def compare(a: object | None, b: object | None) -> int:
        """Three-way comparison for datetimes or ISO strings.

        Returns -1 if a<b, 0 if equal, 1 if a>b. None sorts before values.
        """
        def to_dt(x: object | None) -> datetime | None:
            if x is None:
                return None
            if isinstance(x, datetime):
                return x
            if isinstance(x, IsoTimeFormatter):
                return x.dt
            if isinstance(x, str):
                return IsoTimeFormatter(x).dt
            return None

        da, db = to_dt(a), to_dt(b)
        if da is None and db is None:
            return 0
        if da is None:
            return -1
        if db is None:
            return 1
        if da < db:
            return -1
        if da > db:
            return 1
        return 0

    def subtract_days(self, days: int) -> "IsoTimeFormatter":
        if self.dt is None:
            return IsoTimeFormatter("")
        return_obj = IsoTimeFormatter()
        return_obj.dt = (self.dt - timedelta(days=days))
        return return_obj

    def _as_dt(self) -> datetime | None:
        return self.dt

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (IsoTimeFormatter, datetime, str, type(None))):
            return NotImplemented
        def to_dt(x):
            if isinstance(x, IsoTimeFormatter):
                return x.dt
            if isinstance(x, datetime):
                return x
            if isinstance(x, str):
                return IsoTimeFormatter(x).dt
            return None
        a, b = to_dt(self), to_dt(other)
        return a == b

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (IsoTimeFormatter, datetime, str, type(None))):
            return NotImplemented
        def to_dt(x):
            if isinstance(x, IsoTimeFormatter):
                return x.dt
            if isinstance(x, datetime):
                return x
            if isinstance(x, str):
                return IsoTimeFormatter(x).dt
            return None
        a, b = to_dt(self), to_dt(other)
        if a is None and b is None:
            return False
        if a is None:
            return True
        if b is None:
            return False
        return a < b


