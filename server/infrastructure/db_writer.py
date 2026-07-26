"""The seam that keeps blocking persistence off the asyncio loop and off the
per-room tick fan-out (see 'Blocking work never runs on the event loop').
`submit` is fire-and-forget: the caller does not wait for `fn` to finish."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class DbWriter(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any) -> None: ...


class InlineDbWriter:
    """Runs `fn` immediately, on the caller's thread. The default so existing
    synchronous, clock-injected tests stay deterministic without a real
    executor; production wiring swaps in ThreadPoolDbWriter instead."""

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        fn(*args)


class ThreadPoolDbWriter:  # pragma: no cover - thin executor adapter
    """max_workers=1 serializes DB access, matching sqlite3's single-writer
    model - no connection pooling or write-lock retry needed."""

    def __init__(self, executor: ThreadPoolExecutor):
        self._executor = executor

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        self._executor.submit(fn, *args)
