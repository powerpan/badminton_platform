from datetime import time, timedelta
from typing import Any


def time_minutes(value: Any) -> int:
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def overlaps(start: Any, end: Any, other_start: Any, other_end: Any) -> bool:
    """Half-open intervals, matching reservation_repository's SQL predicate."""
    return time_minutes(start) < time_minutes(other_end) and time_minutes(end) > time_minutes(other_start)
