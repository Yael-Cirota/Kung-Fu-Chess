from unittest.mock import patch

from common.result import Result
from common.tracing import SequentialTraceIdGenerator
from kfchess.api import Position
from protocol import codec, messages as m
from server.application.auth_service import AuthenticatedUser, AuthErrorReason
from server.application.disconnect_policy import DisconnectPolicy
from server.domain.client_session import ClientSession, InMemoryClientSessionRegistry
from server.domain.connection_id import ConnectionId
from server.domain.room_status import RoomStatus
from server.presentation.connection import ConnectionRegistry
from server.presentation.dispatcher import MessageDispatcher, MoveRejectReason
from server.presentation.heartbeat import ConnectionMonitor


class FakeAuthService:
    def __init__(self, result):
        self._result = result

    def login(self, username, password):
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

    def enqueue_move(self, pending):
        self.enqueued.append(pending)

    def assign_seat(self, role, conn_id, user_id=None):
        self.assigned_seats.append((role, conn_id, user_id))


class FakeSession:
    def __init__(self, clock_ms=0):
        self.clock_ms = clock_ms


def make_dispatcher(auth_result=None, rooms=None, max_frame_bytes=16384):
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
    ), auth_service


class TestPresentationGate:
    def test_oversized_frame_is_dropped_before_codec_decode_runs(self):
        dispatcher, _ = make_dispatcher(max_frame_bytes=10)
        huge_raw = codec.encode(m.Heartbeat(client_ms=1))

        with patch("server.presentation.dispatcher.codec.decode") as decode_spy:
            result = dispatcher.dispatch(ConnectionId("c1"), huge_raw, now_ms=0)

        assert result is None
        decode_spy.assert_not_called()

    def test_frame_within_the_limit_is_not_dropped(self):
        dispatcher, _ = make_dispatcher(max_frame_bytes=16384)
        raw = codec.encode(m.Heartbeat(client_ms=1))

        result = dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)

        assert result is not None

    def test_malformed_json_returns_none(self):
        dispatcher, _ = make_dispatcher()
        assert dispatcher.dispatch(ConnectionId("c1"), "{not json", now_ms=0) is None

    def test_unknown_message_type_returns_none(self):
        dispatcher, _ = make_dispatcher()
        raw = '{"type": "unknown_thing", "payload": {}}'
        assert dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0) is None

    def test_a_decodable_but_unrouted_message_type_returns_none(self):
        # RegisterRequest is a valid, decodable message, but this phase's
        # dispatcher only routes Login/Heartbeat/MoveRequest (see module
        # docstring) - everything else falls through to None.
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.RegisterRequest(username="alice", password="pw"))
        assert dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0) is None


class TestLogin:
    def test_successful_login_returns_auth_ok(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert response == m.AuthOk(user_id=1, username="alice", elo=1200)

    def test_failed_login_returns_auth_error(self):
        dispatcher, _ = make_dispatcher(auth_result=Result.failure(AuthErrorReason.INVALID_CREDENTIALS))
        raw = codec.encode(m.LoginRequest(username="alice", password="wrong"))

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0))

        assert response == m.AuthError(reason=AuthErrorReason.INVALID_CREDENTIALS)


class TestReconnectionRace:
    def test_login_registers_the_connection_with_the_monitor(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)

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
        dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)

        dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000)

        assert old_conn.closed is True
        assert dispatcher._websocket_manager.get(ConnectionId("c1")) is None

    def test_reconnect_leaves_exactly_one_session_for_the_user(self):
        dispatcher, _ = make_dispatcher(
            auth_result=Result.success(AuthenticatedUser(user_id=1, username="alice", elo=1200))
        )
        raw = codec.encode(m.LoginRequest(username="alice", password="pw"))

        dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)
        dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000)

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
        dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=5000)

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
        dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=0)
        dispatcher.dispatch(ConnectionId("c2"), raw, now_ms=1000)

        assert dispatcher._connection_monitor.tick(now_ms=999_999) == [
            __import__("server.presentation.heartbeat", fromlist=["DeadConnection"]).DeadConnection(
                connection_id=ConnectionId("c2"), epoch=2
            )
        ]


class TestHeartbeat:
    def test_replies_with_the_same_client_ms(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.Heartbeat(client_ms=555))

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=1000))

        assert response.client_ms == 555

    def test_server_ms_defaults_to_now_ms_with_no_room(self):
        dispatcher, _ = make_dispatcher()
        raw = codec.encode(m.Heartbeat(client_ms=1))

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=4242))

        assert response.server_ms == 4242

    def test_server_ms_uses_the_rooms_game_clock_when_seated(self):
        room = SpyRoom(status=RoomStatus.RUNNING, session=FakeSession(clock_ms=777))
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )
        raw = codec.encode(m.Heartbeat(client_ms=1))

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=99999))

        assert response.server_ms == 777

    def test_updates_the_connection_monitor(self):
        dispatcher, _ = make_dispatcher()
        dispatcher._connection_monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)
        raw = codec.encode(m.Heartbeat(client_ms=1))

        dispatcher.dispatch(ConnectionId("c1"), raw, now_ms=5000)

        assert dispatcher._connection_monitor.tick(now_ms=5000 + 10000) == []
        assert dispatcher._connection_monitor.tick(now_ms=5000 + 10001) != []


class TestMoveRequestAuthorization:
    def make_move_request(self):
        return codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=2, client_seq=1))

    def test_unbound_connection_is_rejected(self):
        dispatcher, _ = make_dispatcher()
        response = codec.decode(dispatcher.dispatch(ConnectionId("ghost"), self.make_move_request(), now_ms=0))

        assert response == m.MoveAck(client_seq=1, accepted=False, reason=MoveRejectReason.UNAUTHORIZED)

    def test_viewer_is_rejected(self):
        room = SpyRoom(status=RoomStatus.RUNNING)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="viewer", epoch=1)
        )

        response = codec.decode(dispatcher.dispatch(ConnectionId("c1"), self.make_move_request(), now_ms=0))

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

        result = dispatcher.dispatch(ConnectionId("c1"), self.make_move_request(), now_ms=0)

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

        response = codec.decode(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=7)),
            now_ms=0,
        ))

        assert response == m.MoveAck(client_seq=7, accepted=False, reason=MoveRejectReason.ROOM_NOT_RUNNING)
        assert room.enqueued == []

    def test_ended_room_rejects_the_move(self):
        room = SpyRoom(status=RoomStatus.ENDED)
        dispatcher, _ = make_dispatcher(rooms={"room-1": room})
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id="room-1", role="white", epoch=1)
        )

        response = codec.decode(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=3)),
            now_ms=0,
        ))

        assert response.accepted is False
        assert response.reason == MoveRejectReason.ROOM_NOT_RUNNING
        assert room.enqueued == []

    def test_a_session_with_no_room_id_is_rejected_at_the_same_gate(self):
        dispatcher, _ = make_dispatcher()
        dispatcher._client_sessions.bind(
            ClientSession(ConnectionId("c1"), 1, "alice", 1200, room_id=None, role="white", epoch=1)
        )

        response = codec.decode(dispatcher.dispatch(
            ConnectionId("c1"),
            codec.encode(m.MoveRequest(from_row=0, from_col=0, to_row=0, to_col=1, client_seq=3)),
            now_ms=0,
        ))

        assert response.reason == MoveRejectReason.ROOM_NOT_RUNNING
