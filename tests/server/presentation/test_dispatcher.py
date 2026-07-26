import asyncio
from unittest.mock import patch

from common.result import Result
from common.tracing import SequentialTraceIdGenerator
from kfchess.api import Position
from protocol import codec, messages as m
from server.application.auth_service import AuthenticatedUser, AuthErrorReason
from server.application.disconnect_policy import DisconnectPolicy
from server.application.matchmaking import MatchmakingService
from server.application.room_service import PlayerRef, Role, RoomErrorReason, RoomService, SequentialRoomIdGenerator
from server.domain.client_session import ClientSession, InMemoryClientSessionRegistry
from server.domain.connection_id import ConnectionId
from server.domain.room_status import RoomStatus
from server.presentation.connection import ConnectionRegistry
from server.presentation.dispatcher import MessageDispatcher, MoveRejectReason
from server.presentation.heartbeat import ConnectionMonitor


def run(coro):
    """`dispatch` is async (see its module docstring); these tests stay plain
    pytest by driving each call to completion on its own loop."""
    return asyncio.run(coro)


class FakeAuthService:
    def __init__(self, result):
        self._result = result
        self.registered = []

    def login(self, username, password):
        return self._result

    def register(self, username, password):
        self.registered.append((username, password))
        return self._result


class FakeConnection:
    def __init__(self, conn_id):
        self._connection_id = ConnectionId(conn_id)
        self.closed = False

    @property
    def connection_id(self):
        return self._connection_id

    def send(self, raw):
        pass

    def close(self):
        self.closed = True


class SpyRoom:
    def __init__(self, status, session=None):
        self.status = status
        self.session = session
        self.enqueued = []
        self.assigned_seats = []
        self.removed_seats = []

    def enqueue_move(self, pending):
        self.enqueued.append(pending)

    def assign_seat(self, role, conn_id, user_id=None):
        self.assigned_seats.append((role, conn_id, user_id))

    def remove_seat(self, conn_id):
        self.removed_seats.append(conn_id)
        return True


class FakeSession:
    def __init__(self, clock_ms=0):
        self.clock_ms = clock_ms


def make_dispatcher(
    auth_result=None, rooms=None, max_frame_bytes=16384,
    room_service=None, matchmaking_service=None, room_factory=None,
):
    auth_service = FakeAuthService(auth_result or Result.failure(AuthErrorReason.INVALID_CREDENTIALS))
    return MessageDispatcher(
        auth_service=auth_service,
        rooms=rooms if rooms is not None else {},
        client_sessions=InMemoryClientSessionRegistry(),
        websocket_manager=ConnectionRegistry(),
        connection_monitor=ConnectionMonitor(timeout_ms=10000),
        disconnect_policy=DisconnectPolicy(grace_ms=20000),
        trace_id_generator=SequentialTraceIdGenerator(),
        max_frame_bytes=max_frame_bytes,
        room_service=room_service,
        matchmaking_service=matchmaking_service,
        room_factory=room_factory,
    ), auth_service


class TestPresentationGate:
    def test_oversized_frame_is_dropped_before_codec_decode_runs(self):
        dispatcher, _ = make_dispatcher(max_frame_bytes=10)
        huge_raw = codec.encode(m.Heartbeat(client_ms=1))

        with patch("server.presentation.dispatcher.codec.decode") as decode_spy:
            result = run(dispatcher.dispatch(ConnectionId("c1"), huge_raw, now_ms=0))

        assert result is None
        decode_spy.assert_not_called()

    def test_frame_within_the_limit_is_not_dropped(self):
        dispatcher, _ = make_dispatcher(max_frame_bytes=16384)
        raw = codec.encode(m.Heartbeat(client_ms=1))

        result = run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert result is not None

    def test_malformed_json_returns_none(self):
        dispatcher, _ = make_dispatcher()
        assert run(dispatcher.dispatch(ConnectionId("c1"), "{not json", now_ms=0)) is None

    def test_unknown_message_type_returns_none(self):
        dispatcher, _ = make_dispatcher()
        raw = '{"type": "unknown_thing", "payload": {}}'
        assert run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)) is None


class TestLogin:
    def test_successful_login_returns_auth_ok(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.AuthOk(user_id=1, username="alice", elo=1200)

    def test_failed_login_returns_auth_error(self):
        dispatcher, _ = make_dispatcher(auth_result=Result.failure(AuthErrorReason.INVALID_CREDENTIALS))
        raw = codec.encode(m.LoginRequest(username="alice", password="wrong"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.AuthError(reason=AuthErrorReason.INVALID_CREDENTIALS)


class TestRegister:
    def test_successful_registration_returns_auth_ok(self):
        dispatcher, auth_service = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.RegisterRequest(username="alice", password="pw"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.AuthOk(user_id=1, username="alice", elo=1200)
        assert auth_service.registered == [("alice", "pw")]

    def test_failed_registration_returns_auth_error(self):
        dispatcher, _ = make_dispatcher(auth_result=Result.failure(AuthErrorReason.USERNAME_TAKEN))
        raw = codec.encode(m.RegisterRequest(username="alice", password="pw"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.AuthError(reason=AuthErrorReason.USERNAME_TAKEN)

    def test_a_successful_registration_binds_a_client_session_like_login_does(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.RegisterRequest(username="alice", password="pw"))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert dispatcher._client_sessions.get(ConnectionId("c1")) is not None


class TestReconnectionRace:
    def test_login_registers_the_connection_with_the_monitor(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert dispatcher._connection_monitor.tick(now_ms=999_999) == [
            __import__("server.presentation.heartbeat", fromlist=["DeadConnection"]).DeadConnection(
                connection_id=ConnectionId("c1"), epoch=1
            )
        ]

    def test_second_login_for_the_same_user_evicts_and_closes_the_old_connection(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        old_conn = FakeConnection("c1")
        dispatcher._websocket_manager.register(old_conn)
        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        run(dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000))

        assert old_conn.closed is True
        assert dispatcher._websocket_manager.get(ConnectionId("c1")) is None

    def test_reconnect_leaves_exactly_one_session_for_the_user(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))
        run(dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000))

        assert dispatcher._client_sessions.get(ConnectionId("c1")) is None
        assert dispatcher._client_sessions.by_user(1).connection_id == ConnectionId("c2")

    def test_reconnect_while_seated_cancels_the_disconnect_countdown_and_reassigns_the_seat(self):
        room = SpyRoom(status=RoomStatus.RUNNING)
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200)),
            rooms={"room-1": room},
        )
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )
        dispatcher._disconnect_policy.on_disconnect("room-1", "white", now_ms=0)

        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))
        run(dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=5000))

        assert dispatcher._disconnect_policy.deadline_for("room-1", "white") is None
        assert room.assigned_seats == [("white", ConnectionId("c2"), 1)]

    def test_stale_monitor_report_for_an_evicted_connection_is_a_no_op(self):
        # After eviction, ConnectionMonitor.forget() was called for the old
        # connection id, so it can never again be reported dead - the
        # eviction path itself removes the epoch race, rather than relying
        # on RoomTicker's epoch comparison to catch it after the fact.
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))
        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))
        run(dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000))

        assert dispatcher._connection_monitor.tick(now_ms=999_999) == [
            __import__("server.presentation.heartbeat", fromlist=["DeadConnection"]).DeadConnection(
                connection_id=ConnectionId("c2"), epoch=2
            )
        ]


class TestHeartbeat:
    def test_replies_with_the_same_client_ms(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.Heartbeat(client_ms=555))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=1000)))

        assert response.client_ms == 555

    def test_server_ms_defaults_to_now_ms_with_no_room(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.Heartbeat(client_ms=1))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=4242)))

        assert response.server_ms == 4242

    def test_server_ms_uses_the_rooms_game_clock_when_seated(self):
        room = SpyRoom(status=RoomStatus.RUNNING, session=FakeSession(clock_ms=777))
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )
        raw = codec.encode(m.Heartbeat(client_ms=1))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=99999)))

        assert response.server_ms == 777

    def test_updates_the_connection_monitor(self):
        dispatcher, _ = make_dispatcher()
        dispatcher._connection_monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)
        raw = codec.encode(m.Heartbeat(client_ms=1))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=5000))

        assert dispatcher._connection_monitor.tick(now_ms=5000 + 10000) == []
        assert dispatcher._connection_monitor.tick(now_ms=5000 + 10001) != []


class TestMoveRequestAuthorization:
    def make_move_request(self):
        return codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=2, client_seq=1))

    def test_unbound_connection_is_rejected(self):
        dispatcher, _ = make_dispatcher()
        response = codec.decode(run(dispatcher.dispatch(ConnectionId("ghost"), self.make_move_request(), now_ms=0)))

        assert response == m.MoveAck(client_seq=1, accepted=False, reason=MoveRejectReason.UNAUTHORIZED)

    def test_viewer_is_rejected(self):
        room = SpyRoom(status=RoomStatus.RUNNING)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="viewer", epoch=1)
        )

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), self.make_move_request(), now_ms=0)))

        assert response == m.MoveAck(client_seq=1, accepted=False, reason=MoveRejectReason.UNAUTHORIZED)
        assert room.enqueued == []

    def test_a_seated_player_move_is_always_resolved_to_their_own_role(self):
        # MoveRequest carries no color field at all, so there is no
        # attacker-controlled value to trust in the first place - the
        # PendingMove's color always comes from the bound session.
        room = SpyRoom(status=RoomStatus.RUNNING)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="black", epoch=1)
        )

        result = run(dispatcher.dispatch(ConnectionId("c1"), self.make_move_request(), now_ms=0))

        assert result is None  # enqueued, no immediate ack
        assert len(room.enqueued) == 1
        assert room.enqueued[0].color == "black"
        assert room.enqueued[0].from_pos == Position(0, 0)
        assert room.enqueued[0].to_pos == Position(0, 2)
        assert room.enqueued[0].trace_id is not None


class TestMoveRequestRoomLifecycleGate:
    def test_waiting_room_rejects_the_move_before_touching_the_engine(self):
        room = SpyRoom(status=RoomStatus.WAITING)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )

        response = codec.decode(run(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=7)),
            now_ms=0,
        )))

        assert response == m.MoveAck(client_seq=7, accepted=False, reason=MoveRejectReason.ROOM_NOT_RUNNING)
        assert room.enqueued == []

    def test_ended_room_rejects_the_move(self):
        room = SpyRoom(status=RoomStatus.ENDED)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )

        response = codec.decode(run(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=3)),
            now_ms=0,
        )))

        assert response.accepted is False
        assert response.reason == MoveRejectReason.ROOM_NOT_RUNNING
        assert room.enqueued == []

    def test_a_session_with_no_room_id_is_rejected_at_the_same_gate(self):
        dispatcher, _ = make_dispatcher()
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role="white", epoch=1)
        )

        response = codec.decode(run(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=3)),
            now_ms=0,
        )))

        assert response.reason == MoveRejectReason.ROOM_NOT_RUNNING


class TestPlayRequest:
    def test_with_no_matchmaking_service_wired_it_is_a_harmless_no_op(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.PlayRequest())

        assert run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)) is None

    def test_an_unbound_connection_is_a_no_op(self):
        bus_matchmaking = MatchmakingService(bus=_NullBus())
        dispatcher, _ = make_dispatcher(matchmaking_service=bus_matchmaking)
        raw = codec.encode(m.PlayRequest())

        assert run(dispatcher.dispatch(ConnectionId("ghost"), raw, now_ms=0)) is None

    def test_enqueues_the_bound_sessions_ticket(self):
        matchmaking_service = MatchmakingService(bus=_NullBus())
        dispatcher, _ = make_dispatcher(matchmaking_service=matchmaking_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role=None, epoch=1)
        )
        raw = codec.encode(m.PlayRequest())

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert 1 in matchmaking_service._queue

    def test_cancel_queue_removes_the_bound_users_ticket(self):
        matchmaking_service = MatchmakingService(bus=_NullBus())
        dispatcher, _ = make_dispatcher(matchmaking_service=matchmaking_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role=None, epoch=1)
        )
        run(dispatcher.dispatch(ConnectionId("c1"), codec.encode(m.PlayRequest()), now_ms=0))

        run(dispatcher.dispatch(ConnectionId("c1"), codec.encode(m.CancelQueueRequest()), now_ms=0))

        assert 1 not in matchmaking_service._queue

    def test_cancel_queue_with_no_matchmaking_service_wired_is_a_no_op(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.CancelQueueRequest())

        assert run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)) is None


class _NullBus:
    """A bus that is never actually published to in these tests: enqueue()
    only awaits bus.publish when a match completes, and none of the tests
    above enqueue two opposing tickets."""

    def subscribe(self, name, handler):
        pass

    def unsubscribe(self, name, handler):
        pass

    async def publish(self, event):
        raise AssertionError("no match should complete in these tests")


class TestCreateRoomRequest:
    def make_room_service(self):
        return RoomService(SequentialRoomIdGenerator())

    def test_with_nothing_wired_returns_unauthenticated_room_error(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.CreateRoomRequest())

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.RoomError(room_id=None, reason=RoomErrorReason.UNAUTHENTICATED)

    def test_creates_and_seats_the_host_as_white(self):
        rooms = {}
        room_service = self.make_room_service()
        created_rooms = []

        def room_factory(room_id):
            room = SpyRoom(status=RoomStatus.WAITING)
            room.room_id = room_id
            created_rooms.append(room)
            return room

        dispatcher, _ = make_dispatcher(rooms=rooms, room_service=room_service, room_factory=room_factory)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role=None, epoch=1)
        )
        raw = codec.encode(m.CreateRoomRequest())

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert isinstance(response, m.RoomCreated)
        assert rooms[response.room_id] is created_rooms[0]
        assert created_rooms[0].assigned_seats == [(Role.WHITE, ConnectionId("c1"), 1)]
        assert dispatcher._client_sessions.get(ConnectionId("c1")).room_id == response.room_id
        assert dispatcher._client_sessions.get(ConnectionId("c1")).role == Role.WHITE


class TestJoinRoomRequest:
    def test_with_nothing_wired_returns_unauthenticated_room_error(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.JoinRoomRequest(room_id="room-1"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.RoomError(room_id="room-1", reason=RoomErrorReason.UNAUTHENTICATED)

    def test_unknown_room_returns_room_not_found(self):
        room_service = RoomService(SequentialRoomIdGenerator())
        dispatcher, _ = make_dispatcher(room_service=room_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role=None, epoch=1)
        )
        raw = codec.encode(m.JoinRoomRequest(room_id="no-such-room"))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)))

        assert response == m.RoomError(room_id="no-such-room", reason=RoomErrorReason.ROOM_NOT_FOUND)

    def test_joining_seats_the_second_player_as_black(self):
        room_service = RoomService(SequentialRoomIdGenerator())
        host_room = room_service.create(PlayerRef(user_id=1, username="alice"))
        rooms = {host_room.room_id: SpyRoom(status=RoomStatus.WAITING)}
        dispatcher, _ = make_dispatcher(rooms=rooms, room_service=room_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c2"), 2, "bob", 1200, room_id=None, role=None, epoch=1)
        )
        raw = codec.encode(m.JoinRoomRequest(room_id=host_room.room_id))

        response = codec.decode(run(dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=0)))

        assert response == m.RoomJoined(room_id=host_room.room_id, role=Role.BLACK, players=["alice", "bob"])
        assert rooms[host_room.room_id].assigned_seats == [(Role.BLACK, ConnectionId("c2"), 2)]
        assert dispatcher._client_sessions.get(ConnectionId("c2")).role == Role.BLACK


class TestLeaveRoomRequest:
    def test_unbound_connection_is_a_no_op(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.LeaveRoomRequest(room_id="room-1"))

        assert run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)) is None

    def test_leaving_a_waiting_room_removes_the_seat_and_clears_the_session(self):
        room_service = RoomService(SequentialRoomIdGenerator())
        host_room = room_service.create(PlayerRef(user_id=1, username="alice"))
        room = SpyRoom(status=RoomStatus.WAITING)
        rooms = {host_room.room_id: room}
        dispatcher, _ = make_dispatcher(rooms=rooms, room_service=room_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=host_room.room_id, role="white", epoch=1)
        )
        raw = codec.encode(m.LeaveRoomRequest(room_id=host_room.room_id))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert room.removed_seats == [ConnectionId("c1")]
        assert host_room.room_id not in rooms  # room removed once left empty
        session = dispatcher._client_sessions.get(ConnectionId("c1"))
        assert session.room_id is None
        assert session.role is None

    def test_leaving_a_running_room_does_not_touch_the_game_room_seat(self):
        # A seated player in a RUNNING match leaves via disconnect/forced-resign,
        # not LeaveRoomRequest - this gate only removes a not-yet-started seat.
        room_service = RoomService(SequentialRoomIdGenerator())
        host_room = room_service.create(PlayerRef(user_id=1, username="alice"))
        room = SpyRoom(status=RoomStatus.RUNNING)
        rooms = {host_room.room_id: room}
        dispatcher, _ = make_dispatcher(rooms=rooms, room_service=room_service)
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=host_room.room_id, role="white", epoch=1)
        )
        raw = codec.encode(m.LeaveRoomRequest(room_id=host_room.room_id))

        run(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert room.removed_seats == []
        assert host_room.room_id in rooms
