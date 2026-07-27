"""The Presentation gatekeeper: frame-size and schema checks, TraceId
minting, and routing to Application-layer handlers. A request rejected here
or at the Application tier (room lifecycle, authorization) never reaches the
Domain (kfchess) - see 'Multi-layered fail-fast gatekeeping'.

`dispatch` is async because PlayRequest's synchronous response is "nothing
yet" - MatchmakingService.enqueue only awaits the bus when it completes a
match, and that publish is what MatchRoomCoordinator (elsewhere) turns into a
MatchFound frame pushed directly to both connections. Every other handler
here stays a plain synchronous method; only dispatch and the one handler that
calls into MatchmakingService need the `await`."""

import inspect
from typing import Any, Callable, Dict, Optional

from kfchess.api import Position
from common.tracing import TraceIdGenerator
from protocol import codec, messages as m
from protocol.errors import ProtocolError
from server.application.auth_service import AuthenticatedUser, AuthService
from server.application.disconnect_policy import DisconnectPolicy
from server.application.game_room import GameRoom
from server.application.matchmaking import MatchmakingService, MatchTicket
from server.application.room_service import PlayerRef, Role, RoomErrorReason, RoomService
from server.domain.client_session import ClientSessionRegistry
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove
from server.domain.room_status import RoomStatus
from server.presentation.connection import WebSocketManager
from server.presentation.heartbeat import ConnectionMonitor

RoomFactory = Callable[[str], GameRoom]


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
        room_service: Optional[RoomService] = None,
        matchmaking_service: Optional[MatchmakingService] = None,
        room_factory: Optional[RoomFactory] = None,
    ):
        self._auth_service = auth_service
        self._rooms = rooms
        self._client_sessions = client_sessions
        self._websocket_manager = websocket_manager
        self._connection_monitor = connection_monitor
        self._disconnect_policy = disconnect_policy
        self._trace_id_generator = trace_id_generator
        self._max_frame_bytes = max_frame_bytes
        self._room_service = room_service
        self._matchmaking_service = matchmaking_service
        self._room_factory = room_factory

        # Dispatch table keyed by exact message type. Message dataclasses
        # never subclass one another (see protocol/messages.py), so an exact
        # type() lookup is equivalent to the isinstance chain it replaces.
        # Each handler is normalized to the (conn_id, message, now_ms)
        # signature regardless of what it actually needs; dispatch() awaits
        # the result only when it's awaitable, since _handle_play_request is
        # the sole async handler.
        self._handlers: Dict[type, Callable[[ConnectionId, Any, int], Any]] = {
            m.LoginRequest: lambda conn_id, message, now_ms: self._handle_login(conn_id, message, now_ms),
            m.RegisterRequest: lambda conn_id, message, now_ms: self._handle_register(conn_id, message, now_ms),
            m.Heartbeat: lambda conn_id, message, now_ms: self._handle_heartbeat(conn_id, message, now_ms),
            m.MoveRequest: lambda conn_id, message, now_ms: self._handle_move_request(conn_id, message),
            m.PlayRequest: lambda conn_id, message, now_ms: self._handle_play_request(conn_id, now_ms),
            m.CancelQueueRequest: lambda conn_id, message, now_ms: self._handle_cancel_queue_request(conn_id),
            m.CreateRoomRequest: lambda conn_id, message, now_ms: self._handle_create_room_request(conn_id),
            m.JoinRoomRequest: lambda conn_id, message, now_ms: self._handle_join_room_request(conn_id, message),
            m.LeaveRoomRequest: lambda conn_id, message, now_ms: self._handle_leave_room_request(conn_id, message),
        }

    async def dispatch(self, conn_id: ConnectionId, raw: str, now_ms: int) -> Optional[str]:
        if len(raw.encode("utf-8")) > self._max_frame_bytes:
            return None  # Presentation gate: dropped before codec.decode ever runs

        try:
            message = codec.decode(raw)
        except ProtocolError:
            return None

        handler = self._handlers.get(type(message))
        if handler is None:
            return None
        result = handler(conn_id, message, now_ms)
        if inspect.isawaitable(result):
            result = await result
        return result

    # --- login, registration & reconnection ---

    def _handle_login(self, conn_id: ConnectionId, request: m.LoginRequest, now_ms: int) -> str:
        result = self._auth_service.login(request.username, request.password)
        if not result.ok:
            return codec.encode(m.AuthError(reason=result.error))
        return self._bind_authenticated(conn_id, result.value, now_ms)

    def _handle_register(self, conn_id: ConnectionId, request: m.RegisterRequest, now_ms: int) -> str:
        result = self._auth_service.register(request.username, request.password)
        if not result.ok:
            return codec.encode(m.AuthError(reason=result.error))
        return self._bind_authenticated(conn_id, result.value, now_ms)

    def _bind_authenticated(self, conn_id: ConnectionId, user: AuthenticatedUser, now_ms: int) -> str:
        outcome = self._client_sessions.rebind(user.user_id, conn_id, user.username, user.elo).value

        if outcome.evicted_connection_id is not None:
            evicted_conn = self._websocket_manager.get(outcome.evicted_connection_id)
            if evicted_conn is not None:
                evicted_conn.close()
            self._websocket_manager.unregister(outcome.evicted_connection_id)
            self._connection_monitor.forget(outcome.evicted_connection_id)

        self._connection_monitor.register(conn_id, outcome.session.epoch, now_ms)

        if outcome.session.room_id is not None and outcome.session.role in (Role.WHITE, Role.BLACK):
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
        if session is None or session.role is None or session.role == Role.VIEWER:
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

    # --- matchmaking: enqueue/cancel are the synchronous response to the
    # request itself; the eventual MatchFound is a MatchRoomCoordinator push,
    # not this method's return value (see module docstring) ---

    async def _handle_play_request(self, conn_id: ConnectionId, now_ms: int) -> None:
        if self._matchmaking_service is None:
            return None
        session = self._client_sessions.get(conn_id)
        if session is None:
            return None
        ticket = MatchTicket(user_id=session.user_id, username=session.username, elo=session.elo)
        await self._matchmaking_service.enqueue(ticket, now_ms)
        return None

    def _handle_cancel_queue_request(self, conn_id: ConnectionId) -> None:
        if self._matchmaking_service is None:
            return None
        session = self._client_sessions.get(conn_id)
        if session is not None:
            self._matchmaking_service.cancel(session.user_id)
        return None

    # --- manual rooms: create/join/leave ---

    def _handle_create_room_request(self, conn_id: ConnectionId) -> str:
        session = self._client_sessions.get(conn_id)
        if session is None or self._room_service is None or self._room_factory is None:
            return codec.encode(m.RoomError(room_id=None, reason=RoomErrorReason.UNAUTHENTICATED))

        room = self._room_service.create(PlayerRef(user_id=session.user_id, username=session.username))
        game_room = self._room_factory(room.room_id)
        self._rooms[room.room_id] = game_room
        game_room.assign_seat(Role.WHITE, conn_id, user_id=session.user_id)
        self._client_sessions.update_room(conn_id, room.room_id, Role.WHITE)
        return codec.encode(m.RoomCreated(room_id=room.room_id))

    def _handle_join_room_request(self, conn_id: ConnectionId, request: m.JoinRoomRequest) -> str:
        session = self._client_sessions.get(conn_id)
        if session is None or self._room_service is None:
            return codec.encode(m.RoomError(room_id=request.room_id, reason=RoomErrorReason.UNAUTHENTICATED))

        result = self._room_service.join(
            request.room_id, PlayerRef(user_id=session.user_id, username=session.username)
        )
        if not result.ok:
            return codec.encode(m.RoomError(room_id=request.room_id, reason=result.error))

        game_room = self._rooms.get(request.room_id)
        if game_room is None:
            return codec.encode(m.RoomError(room_id=request.room_id, reason=RoomErrorReason.ROOM_NOT_FOUND))

        role = result.value.role
        game_room.assign_seat(role, conn_id, user_id=session.user_id)
        self._client_sessions.update_room(conn_id, request.room_id, role)
        room = result.value.room
        players = [p.username for p in room.players]
        if len(room.players) == 2:
            # This join is the one that fills the second seat: the matchmaking
            # path has MatchRoomCoordinator push MatchFound to both sides, but
            # a manually-created room's host only ever got RoomCreated - with
            # nothing else, they would never learn a second player showed up.
            self._notify_other_players_room_started(room, joined_conn_id=conn_id, players=players)
        return codec.encode(m.RoomJoined(room_id=request.room_id, role=role, players=players))

    def _notify_other_players_room_started(self, room, joined_conn_id: ConnectionId, players: list) -> None:
        for index, player in enumerate(room.players):
            other_session = self._client_sessions.by_user(player.user_id)
            if other_session is None or other_session.connection_id == joined_conn_id:
                continue
            other_role = room.role_for_index(index)
            self._websocket_manager.send_to(
                other_session.connection_id,
                codec.encode(m.RoomJoined(room_id=room.room_id, role=other_role, players=players)),
            )

    def _handle_leave_room_request(self, conn_id: ConnectionId, request: m.LeaveRoomRequest) -> None:
        session = self._client_sessions.get(conn_id)
        if session is None or self._room_service is None:
            return None

        self._room_service.cancel(request.room_id, session.user_id)
        game_room = self._rooms.get(request.room_id)
        if game_room is not None and game_room.status is RoomStatus.WAITING:
            if game_room.remove_seat(conn_id):
                del self._rooms[request.room_id]
        self._client_sessions.update_room(conn_id, None, None)
        return None
