"""The Presentation gatekeeper: frame-size and schema checks, TraceId
minting, and routing to Application-layer handlers. A request rejected here
or at the Application tier (room lifecycle, authorization) never reaches the
Domain (kfchess) - see 'Multi-layered fail-fast gatekeeping'.

This dispatcher implements the pieces this phase requires end-to-end:
connection auth + reconnection, heartbeats, and MoveRequest gatekeeping.
Routing for registration/matchmaking/room-creation messages is wired in the
composition root once a transport exists (Phase 4+); those application
services are already complete and independently tested."""

from typing import Dict, Optional

from kfchess.api import Position
from common.tracing import TraceIdGenerator
from protocol import codec, messages as m
from protocol.errors import ProtocolError
from server.application.auth_service import AuthService
from server.application.disconnect_policy import DisconnectPolicy
from server.application.game_room import GameRoom
from server.domain.client_session import ClientSessionRegistry
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove
from server.domain.room_status import RoomStatus
from server.presentation.connection import WebSocketManager
from server.presentation.heartbeat import ConnectionMonitor


class MoveRejectReason:
    UNAUTHORIZED = "unauthorized"
    ROOM_NOT_RUNNING = "room_not_running"


class MessageDispatcher:
    def __init__(
        self,
        auth_service: AuthService,
        rooms: Dict[str, GameRoom],
        client_sessions: ClientSessionRegistry,
        websocket_manager: WebSocketManager,
        connection_monitor: ConnectionMonitor,
        disconnect_policy: DisconnectPolicy,
        trace_id_generator: TraceIdGenerator,
        max_frame_bytes: int = 16384,
    ):
        self._auth_service = auth_service
        self._rooms = rooms
        self._client_sessions = client_sessions
        self._websocket_manager = websocket_manager
        self._connection_monitor = connection_monitor
        self._disconnect_policy = disconnect_policy
        self._trace_id_generator = trace_id_generator
        self._max_frame_bytes = max_frame_bytes

    def dispatch(self, conn_id: ConnectionId, raw: str, now_ms: int) -> Optional[str]:
        if len(raw.encode("utf-8")) > self._max_frame_bytes:
            return None  # Presentation gate: dropped before codec.decode ever runs

        try:
            message = codec.decode(raw)
        except ProtocolError:
            return None

        if isinstance(message, m.LoginRequest):
            return self._handle_login(conn_id, message, now_ms)
        if isinstance(message, m.Heartbeat):
            return self._handle_heartbeat(conn_id, message, now_ms)
        if isinstance(message, m.MoveRequest):
            return self._handle_move_request(conn_id, message)
        return None

    # --- login & reconnection ---

    def _handle_login(self, conn_id: ConnectionId, request: m.LoginRequest, now_ms: int) -> str:
        result = self._auth_service.login(request.username, request.password)
        if not result.ok:
            return codec.encode(m.AuthError(reason=result.error))

        user = result.value
        outcome = self._client_sessions.rebind(user.user_id, conn_id, user.username, user.elo).value

        if outcome.evicted_connection_id is not None:
            evicted_conn = self._websocket_manager.get(outcome.evicted_connection_id)
            if evicted_conn is not None:
                evicted_conn.close()
            self._websocket_manager.unregister(outcome.evicted_connection_id)
            self._connection_monitor.forget(outcome.evicted_connection_id)

        self._connection_monitor.register(conn_id, outcome.session.epoch, now_ms)

        if outcome.session.room_id is not None and outcome.session.role in ("white", "black"):
            self._disconnect_policy.on_reconnect(outcome.session.room_id, outcome.session.role)
            room = self._rooms.get(outcome.session.room_id)
            if room is not None:
                room.assign_seat(outcome.session.role, conn_id, user_id=outcome.session.user_id)

        return codec.encode(m.AuthOk(user_id=user.user_id, username=user.username, elo=user.elo))

    # --- heartbeat ---

    def _handle_heartbeat(self, conn_id: ConnectionId, request: m.Heartbeat, now_ms: int) -> str:
        self._connection_monitor.on_heartbeat(conn_id, now_ms)

        server_ms = now_ms
        session = self._client_sessions.get(conn_id)
        if session is not None and session.room_id is not None:
            room = self._rooms.get(session.room_id)
            if room is not None:
                server_ms = room.session.clock_ms

        return codec.encode(m.HeartbeatAck(client_ms=request.client_ms, server_ms=server_ms))

    # --- move request: Application gate (authorization + room lifecycle) + tracing ---

    def _handle_move_request(self, conn_id: ConnectionId, request: m.MoveRequest) -> Optional[str]:
        session = self._client_sessions.get(conn_id)
        if session is None or session.role is None or session.role == "viewer":
            return codec.encode(
                m.MoveAck(client_seq=request.client_seq, accepted=False, reason=MoveRejectReason.UNAUTHORIZED)
            )

        room = self._rooms.get(session.room_id) if session.room_id is not None else None
        if room is None or room.status is not RoomStatus.RUNNING:
            return codec.encode(
                m.MoveAck(client_seq=request.client_seq, accepted=False, reason=MoveRejectReason.ROOM_NOT_RUNNING)
            )

        pending = PendingMove(
            color=session.role,
            from_pos=Position(request.from_row, request.from_col),
            to_pos=Position(request.to_row, request.to_col),
            client_seq=request.client_seq,
            connection_id=conn_id,
            trace_id=self._trace_id_generator.new_id(),
        )
        room.enqueue_move(pending)
        return None
