import time
from typing import Protocol, runtime_checkable

MS_IN_SECOND = 1000

@runtime_checkable
class Clock(Protocol):
    """Source of the current time in milliseconds. The sole seam between
    time-dependent code and either the wall clock or a deterministic test double."""

    def now_ms(self) -> int: ...


class MonotonicClock:
    """Wraps time.monotonic() for production use; never fed into a test."""

    def now_ms(self) -> int:
        return round(time.monotonic() * MS_IN_SECOND)


class ManualClock:
    """Test double and server tick source: time only moves when told to."""

    def __init__(self, start_ms: int = 0):
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, ms: int) -> None:
        self._now_ms += ms
