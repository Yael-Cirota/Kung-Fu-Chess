import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Mapping, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class EventNames:
    """Stable event-name constants shared by server-side and client-side subscribers."""
    SCORE_CHANGED = "SCORE_CHANGED"
    MOVE_LOGGED = "MOVE_LOGGED"
    PIECE_CAPTURED = "PIECE_CAPTURED"
    MOVE_STOPPED = "MOVE_STOPPED"
    GAME_STARTED = "GAME_STARTED"
    GAME_OVER = "GAME_OVER"
    PLAYER_DISCONNECTED = "PLAYER_DISCONNECTED"
    PLAYER_RECONNECTED = "PLAYER_RECONNECTED"
    MATCH_FOUND = "MATCH_FOUND"
    MATCH_TIMED_OUT = "MATCH_TIMED_OUT"
    MOVE_REJECTED = "MOVE_REJECTED"


@dataclass(frozen=True)
class Event:
    name: str
    payload: Mapping[str, object]
    trace_id: Optional[str] = None


Handler = Callable[[Event], Awaitable[None]]


@runtime_checkable
class EventBus(Protocol):
    """`subscribe`/`unsubscribe` stay synchronous on purpose: subscribers
    register at construction time, so the composition root never needs a
    running event loop. Only `publish` is a coroutine."""

    def subscribe(self, name: str, handler: Handler) -> None: ...

    def unsubscribe(self, name: str, handler: Handler) -> None: ...

    async def publish(self, event: Event) -> None: ...


class InMemoryEventBus:
    """Async fan-out, awaited to completion before `publish` returns. Handlers
    run sequentially in subscription order and never interleave at their await
    points - fire-and-forget (`create_task`) or `gather` would make a tick's
    observable order depend on scheduling, and the engine is deterministic by
    contract. Handler exceptions are logged and swallowed so one bad subscriber
    cannot kill a game tick; `CancelledError` is a BaseException and so still
    propagates, which is what lets a shutdown actually cancel a publish."""

    def __init__(self):
        self._handlers: Dict[str, List[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        handlers = self._handlers.get(name)
        if handlers is not None and handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        # Snapshot: a handler may unsubscribe itself (or another) mid-fan-out.
        for handler in list(self._handlers.get(event.name, [])):
            try:
                await handler(event)
            except Exception:
                logger.exception("event handler failed for %s", event.name)
