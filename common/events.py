import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Protocol, runtime_checkable

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


@dataclass(frozen=True)
class Event:
    name: str
    payload: Mapping[str, object]
    trace_id: Optional[str] = None


Handler = Callable[[Event], None]


@runtime_checkable
class EventBus(Protocol):
    def subscribe(self, name: str, handler: Handler) -> None: ...

    def unsubscribe(self, name: str, handler: Handler) -> None: ...

    def publish(self, event: Event) -> None: ...


class InMemoryEventBus:
    """Synchronous fan-out. Handler exceptions are logged and swallowed so one
    bad subscriber cannot kill a game tick."""

    def __init__(self):
        self._handlers: Dict[str, List[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        handlers = self._handlers.get(name)
        if handlers is not None and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: Event) -> None:
        for handler in list(self._handlers.get(event.name, [])):
            try:
                handler(event)
            except Exception:
                logger.exception("event handler failed for %s", event.name)
