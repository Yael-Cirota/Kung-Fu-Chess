from typing import Dict, List

from server.application.disconnect_policy import DisconnectPolicy, ForcedResign
from server.application.game_room import GameRoom
from server.application.matchmaking import MatchmakingService
from server.domain.client_session import ClientSessionRegistry
from server.domain.dead_connection import ConnectionMonitorPort


class RoomTicker:
    """Single tick fan-out over every room plus the connection/disconnect/
    matchmaking monitors. A dead connection is only ever handed to
    DisconnectPolicy if its reported epoch is still current for that user's
    session - a stale report (superseded by a newer login) is a no-op, per
    the 'Reconnection protocol' race-safety design."""

    def __init__(
        self,
        rooms: Dict[str, GameRoom],
        connection_monitor: ConnectionMonitorPort,
        disconnect_policy: DisconnectPolicy,
        matchmaking_service: MatchmakingService,
        client_sessions: ClientSessionRegistry,
    ):
        self._rooms = rooms
        self._connection_monitor = connection_monitor
        self._disconnect_policy = disconnect_policy
        self._matchmaking_service = matchmaking_service
        self._client_sessions = client_sessions

    def tick(self, now_ms: int) -> List[ForcedResign]:
        for dead in self._connection_monitor.tick(now_ms):
            session = self._client_sessions.get(dead.connection_id)
            if session is None or dead.epoch < session.epoch:
                continue
            if session.room_id is not None and session.role in ("white", "black"):
                self._disconnect_policy.on_disconnect(session.room_id, session.role, now_ms)

        forced_resigns = self._disconnect_policy.tick(now_ms)
        for resign in forced_resigns:
            room = self._rooms.get(resign.room_id)
            if room is not None:
                room.force_resign(resign.color)

        self._matchmaking_service.tick(now_ms)

        for room in self._rooms.values():
            room.tick(now_ms)

        return forced_resigns
