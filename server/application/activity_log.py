import logging

from common.events import Event, EventBus, EventNames

_SUBSCRIBED_EVENTS = (
    EventNames.MOVE_LOGGED,
    EventNames.PIECE_CAPTURED,
    EventNames.GAME_STARTED,
    EventNames.GAME_OVER,
    EventNames.PLAYER_DISCONNECTED,
    EventNames.PLAYER_RECONNECTED,
)


class ActivityLog:
    """Pure EventBus subscriber: holds no reference to GameRoom, Connection,
    or the engine - only the bus and a logger. One structured JSON line per
    event, via the common.logging_setup JsonFormatter."""

    def __init__(self, bus: EventBus, logger: logging.Logger):
        self._logger = logger
        for name in _SUBSCRIBED_EVENTS:
            bus.subscribe(name, self._on_event)

    def _on_event(self, event: Event) -> None:
        self._logger.info(
            event.name,
            extra={
                "trace_id": event.trace_id,
                "room_id": event.payload.get("room_id"),
                "layer": "domain",
                "at_ms": event.payload.get("at_ms"),
            },
        )
