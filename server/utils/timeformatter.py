import contextlib
import datetime as dt
from functools import total_ordering


@total_ordering
class IsoTimeFormatter:
    """Utility for working with ISO-8601 UTC timestamps.

    - Constructor accepts an ISO string or blank string ("") for now (UTC)
    - to_string() returns ISO string for the stored datetime
    - compare() compares datetimes or ISO strings
    - subtract_days() returns a new instance shifted by the given days
    """

    def __init__(self, value: str | None = None):
        if not value:  # None or ""
            self.dt = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
        else:
            parsed: dt.datetime | None = None
            with contextlib.suppress(Exception):
                parsed = dt.datetime.fromisoformat(value)
            # Default to now if parsing failed
            if parsed is None:
                parsed = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
            # Assume UTC if tz-naive
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            self.dt = parsed

    def to_string(self) -> str:
        if self.dt is None:
            return ""
        return self.dt.isoformat()

    @staticmethod
    def compare(a: object | None, b: object | None) -> int:
        """Three-way comparison for datetimes or ISO strings.

        Returns -1 if a<b, 0 if equal, 1 if a>b. None sorts before values.
        """
        def to_dt(x: object | None) -> dt.datetime | None:
            if x is None:
                return None
            if isinstance(x, dt.datetime):
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
        return_obj.dt = (self.dt - dt.timedelta(days=days))
        return return_obj

    def _as_dt(self) -> dt.datetime | None:
        return self.dt

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (IsoTimeFormatter, dt.datetime, str, type(None))):
            return NotImplemented
        def to_dt(x):
            if isinstance(x, IsoTimeFormatter):
                return x.dt
            if isinstance(x, dt.datetime):
                return x
            if isinstance(x, str):
                return IsoTimeFormatter(x).dt
            return None
        a, b = to_dt(self), to_dt(other)
        return a == b

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (IsoTimeFormatter, dt.datetime, str, type(None))):
            return NotImplemented
        def to_dt(x):
            if isinstance(x, IsoTimeFormatter):
                return x.dt
            if isinstance(x, dt.datetime):
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


