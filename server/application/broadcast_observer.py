from typing import Dict

from common.events import Event, EventBus, EventNames
from protocol import codec, messages as m
from server.application.game_room import GameRoom
from server.domain.websocket_port import WebSocketManager


class BroadcastObserver:
    """Subscribes to MOVE_LOGGED/PIECE_CAPTURED/GAME_OVER and sends an
    immediate DeltaEvent to every connection in the affected room, outside
    the broadcast_hz cadence - so a capture's sound/flash doesn't wait on the
    next gated StateUpdate. Holds the WebSocketManager dependency so GameRoom
    itself never needs to import it for this."""

    def __init__(self, bus: EventBus, websocket_manager: WebSocketManager, rooms: Dict[str, GameRoom]):
        self._websocket_manager = websocket_manager
        self._rooms = rooms
        for name in (EventNames.MOVE_LOGGED, EventNames.PIECE_CAPTURED, EventNames.GAME_OVER):
            bus.subscribe(name, self._on_event)

    def _on_event(self, event: Event) -> None:
        room = self._rooms.get(event.payload.get("room_id"))
        if room is None:
            return

        engine_event = event.payload.get("engine_event")
        if engine_event is not None:
            delta = m.DeltaEvent(
                kind=engine_event.kind.value,
                trace_id=event.trace_id,
                at_ms=engine_event.at_ms,
                piece=engine_event.piece,
                from_pos=engine_event.from_pos,
                to_pos=engine_event.to_pos,
                captured=engine_event.captured,
                beneficiary_color=engine_event.beneficiary_color,
                scoreboard=room.session.scoreboard(),
            )
        else:
            # A forced-resign GAME_OVER has no EngineEvent behind it.
            delta = m.DeltaEvent(
                kind="game_over",
                trace_id=event.trace_id,
                at_ms=room.session.clock_ms,
                piece=None,
                from_pos=None,
                to_pos=None,
                captured=None,
                beneficiary_color=event.payload.get("resigned_color"),
                scoreboard=room.session.scoreboard(),
            )

        self._websocket_manager.broadcast(room.connection_ids(), codec.encode(delta))
