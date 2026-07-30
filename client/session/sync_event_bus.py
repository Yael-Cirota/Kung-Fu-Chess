"""A synchronous fan-out bus for the client's main thread. common.events's
EventBus went async for the server's own tick-ordering reasons; RemoteGameSession.wait()
is called synchronously from the 60fps render loop (ui/game_loop.py) and must
stay a plain function (see 'Client threading model'), so the client needs its
own bus rather than the server's. Reuses common.events's Event dataclass and
EventNames constants so audio/animation subscribers key on identical strings
regardless of which side of the wire published them."""

import logging
from typing import Callable, Dict, List

from common.events import Event

logger = logging.getLogger(__name__)

Handler = Callable[[Event], None]


class SyncEventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Handler]] = {}

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def unsubscribe(self, name: str, handler: Handler) -> None:
        handlers = self._handlers.get(name)
        if handlers is not None and handler in handlers:
            handlers.remove(handler)

    def publish(self, event: Event) -> None:
        # A bad subscriber (e.g. a broken audio callback) must not crash the
        # render loop calling wait() -> publish() every frame.
        for handler in list(self._handlers.get(event.name, [])):
            try:
                handler(event)
            except Exception:
                logger.exception("client event handler failed for %s", event.name)
