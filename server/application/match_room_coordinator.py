"""Bridges MatchmakingService to room creation, as its own EventBus subscriber
(see 'Internal EventBus as the service-to-service seam'). MatchmakingService
publishes MATCH_FOUND and stays ignorant of rooms, connections, and the wire
protocol; this is the one place that turns a Match into a seated GameRoom."""

from typing import Callable, Dict

from common.events import Event, EventBus, EventNames
from protocol import codec, messages as m
from server.application.game_room import GameRoom
from server.application.matchmaking import Match
from server.application.room_service import Role
from server.domain.client_session import ClientSessionRegistry
from server.domain.websocket_port import WebSocketManager

RoomFactory = Callable[[], GameRoom]


class MatchRoomCoordinator:
    def __init__(
        self,
        bus: EventBus,
        rooms: Dict[str, GameRoom],
        websocket_manager: WebSocketManager,
        client_sessions: ClientSessionRegistry,
        room_factory: RoomFactory,
    ):
        self._rooms = rooms
        self._websocket_manager = websocket_manager
        self._client_sessions = client_sessions
        self._room_factory = room_factory
        bus.subscribe(EventNames.MATCH_FOUND, self._on_match_found)

    async def _on_match_found(self, event: Event) -> None:
        match: Match = event.payload["match"]
        room = self._room_factory()
        self._rooms[room.room_id] = room

        for role, ticket in ((Role.WHITE, match.white), (Role.BLACK, match.black)):
            session = self._client_sessions.by_user(ticket.user_id)
            if session is None:
                continue  # the ticket's connection dropped before the match completed
            self._client_sessions.update_room(session.connection_id, room.room_id, role)
            self._websocket_manager.send_to(
                session.connection_id,
                codec.encode(m.MatchFound(room_id=room.room_id, color=role)),
            )
            room.assign_seat(role, session.connection_id, user_id=ticket.user_id)
