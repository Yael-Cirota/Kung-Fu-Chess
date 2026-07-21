from kfchess.api import EngineEvent, EngineEventKind, Position, create_game_session
from common.events import Event, EventNames, InMemoryEventBus
from common.tracing import SequentialTraceIdGenerator
from protocol import codec, messages as m
from server.application.game_room import GameRoom, create_game_room
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove
from server.domain.room_status import RoomStatus


class FakeWebSocketManager:
    def __init__(self):
        self.sent = []  # list of (conn_id, raw)

    def register(self, conn):
        pass

    def unregister(self, conn_id):
        pass

    def send_to(self, conn_id, raw):
        self.sent.append((conn_id, raw))

    def broadcast(self, conn_ids, raw):
        for conn_id in conn_ids:
            self.send_to(conn_id, raw)

    def connection_ids(self):
        return [conn_id for conn_id, _raw in self.sent]

    def decoded(self):
        return [(conn_id, codec.decode(raw)) for conn_id, raw in self.sent]


WHITE_CONN = ConnectionId("white-conn")
BLACK_CONN = ConnectionId("black-conn")
VIEWER_CONN = ConnectionId("viewer-conn")


def make_room(board_text="wR . .\n. . .\n. . .", ws=None, bus=None, trace_ids=None, broadcast_hz=20,
              max_engine_step_ms=100):
    session = create_game_session(board_text)
    return GameRoom(
        room_id="room-1", session=session, websocket_manager=ws or FakeWebSocketManager(),
        bus=bus, trace_id_generator=trace_ids, broadcast_hz=broadcast_hz,
        max_engine_step_ms=max_engine_step_ms,
    )


class TestSeatAssignmentAndGameStarted:
    def test_room_starts_in_waiting_status(self):
        room = make_room()
        assert room.status is RoomStatus.WAITING

    def test_first_seat_does_not_start_the_game(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN)
        assert room.status is RoomStatus.WAITING

    def test_second_seat_transitions_to_running_and_broadcasts_game_started(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)

        assert room.status is RoomStatus.RUNNING
        decoded = ws.decoded()
        assert any(isinstance(msg, m.GameStarted) for _conn_id, msg in decoded)
        recipients = {conn_id for conn_id, msg in decoded if isinstance(msg, m.GameStarted)}
        assert recipients == {WHITE_CONN, BLACK_CONN}


class TestLateJoinerGetsGameStartedAndStateUpdate:
    def test_viewer_joining_mid_game_gets_game_started_then_state_update(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        room.add_viewer(VIEWER_CONN)

        decoded = [msg for conn_id, msg in ws.decoded() if conn_id == VIEWER_CONN]
        assert isinstance(decoded[0], m.GameStarted)
        assert isinstance(decoded[1], m.StateUpdate)

    def test_reconnecting_player_re_seated_mid_game_also_gets_the_rebasing_pair(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        new_white_conn = ConnectionId("white-conn-2")
        room.assign_seat("white", new_white_conn)

        decoded = [msg for conn_id, msg in ws.decoded() if conn_id == new_white_conn]
        assert isinstance(decoded[0], m.GameStarted)
        assert isinstance(decoded[1], m.StateUpdate)

    def test_viewer_joining_before_the_game_starts_gets_nothing_yet(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.add_viewer(VIEWER_CONN)
        assert ws.sent == []

    def test_assign_seat_with_viewer_role_delegates_to_add_viewer(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        room.assign_seat("viewer", VIEWER_CONN)

        decoded = [msg for conn_id, msg in ws.decoded() if conn_id == VIEWER_CONN]
        assert isinstance(decoded[0], m.GameStarted)
        assert isinstance(decoded[1], m.StateUpdate)


class TestSeatedUserIds:
    def test_records_the_user_behind_each_player_seat(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN, user_id=11)
        room.assign_seat("black", BLACK_CONN, user_id=22)

        assert room.player_user_ids() == {"white": 11, "black": 22}

    def test_a_seat_assigned_without_a_user_id_is_not_recorded(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN)

        assert room.player_user_ids() == {}

    def test_a_viewer_never_occupies_a_player_seat(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN, user_id=11)
        room.assign_seat("black", BLACK_CONN, user_id=22)
        room.assign_seat("viewer", VIEWER_CONN, user_id=33)

        assert room.player_user_ids() == {"white": 11, "black": 22}

    def test_reconnecting_on_a_new_connection_keeps_the_same_user_seated(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN, user_id=11)
        room.assign_seat("black", BLACK_CONN, user_id=22)

        room.assign_seat("white", ConnectionId("white-conn-2"), user_id=11)

        assert room.player_user_ids() == {"white": 11, "black": 22}

    def test_returns_a_copy_so_callers_cannot_mutate_the_seating(self):
        room = make_room()
        room.assign_seat("white", WHITE_CONN, user_id=11)

        room.player_user_ids()["white"] = 999

        assert room.player_user_ids() == {"white": 11}


class TestQueueDraining:
    def test_move_enqueued_before_tick_is_applied_that_tick(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)

        acks = [msg for _conn_id, msg in ws.decoded() if isinstance(msg, m.MoveAck)]
        assert acks == [m.MoveAck(client_seq=1, accepted=True, reason=None)]

    def test_move_enqueued_during_drain_waits_for_the_next_tick(self):
        # Simulate a re-entrant enqueue (e.g. a second command arriving on
        # the same raw frame batch) by enqueuing from inside the fake
        # session's request_move.
        class ReentrantSession:
            def __init__(self, room):
                self._room = room
                self.request_move_calls = 0

            def request_move(self, from_pos, to_pos):
                self.request_move_calls += 1
                if self.request_move_calls == 1:
                    self._room.enqueue_move(
                        PendingMove("w", Position(0, 0), Position(0, 1), client_seq=99,
                                    connection_id=WHITE_CONN)
                    )
                from kfchess.api import MoveResult
                return MoveResult.accepted()

            def piece_at(self, pos):
                return None

            @property
            def clock_ms(self):
                return 0

            @property
            def game_over(self):
                return False

            def wait(self, ms):
                return None

            def board_snapshot(self):
                from kfchess.api import BoardSnapshot
                return BoardSnapshot(rows=1, cols=1, piece_views=[])

            def motion_for(self, piece_id):
                return None

            def move_log(self):
                return []

            def scoreboard(self):
                from kfchess.api import Scoreboard
                return Scoreboard(white=0, black=0)

        ws = FakeWebSocketManager()
        room = GameRoom(room_id="room-1", session=None, websocket_manager=ws)
        room.session = ReentrantSession(room)

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)

        acks = [msg for _conn_id, msg in ws.decoded() if isinstance(msg, m.MoveAck)]
        # Only the first move (client_seq=1) was drained this tick; the
        # reentrant one (client_seq=99) is still queued for next tick.
        assert acks == [m.MoveAck(client_seq=1, accepted=True, reason=None)]

        ws.sent.clear()
        room.tick(now_ms=10)
        acks_next_tick = [msg for _conn_id, msg in ws.decoded() if isinstance(msg, m.MoveAck)]
        assert acks_next_tick == [m.MoveAck(client_seq=99, accepted=True, reason=None)]

    def test_move_that_became_illegal_after_wait_is_rejected_via_move_ack_not_dropped(self):
        ws = FakeWebSocketManager()
        room = make_room(board_text="wR . .\n. . .\n. . .", ws=ws, max_engine_step_ms=10000)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)  # rook starts sliding, one cell per 1000ms

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=2, connection_id=WHITE_CONN))
        room.tick(now_ms=100)  # rook is still mid-flight; a second move on it must be rejected

        acks = [msg for _conn_id, msg in ws.decoded() if isinstance(msg, m.MoveAck)]
        second_ack = [ack for ack in acks if ack.client_seq == 2][0]
        assert second_ack.accepted is False
        assert second_ack.reason is not None


class TestBroadcastCadence:
    def test_state_broadcast_only_fires_once_the_interval_has_elapsed(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws, broadcast_hz=10)  # every 100ms
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        ws.sent.clear()

        room.tick(now_ms=0)  # first tick establishes the broadcast baseline, still fires once
        # One StateUpdate per seat (2 seats, no viewers here).
        state_updates_first = [msg for _c, msg in ws.decoded() if isinstance(msg, m.StateUpdate)]
        assert len(state_updates_first) == 2

        ws.sent.clear()
        room.tick(now_ms=50)  # too soon
        assert [msg for _c, msg in ws.decoded() if isinstance(msg, m.StateUpdate)] == []

        room.tick(now_ms=101)  # interval elapsed
        assert len([msg for _c, msg in ws.decoded() if isinstance(msg, m.StateUpdate)]) == 2

    def test_state_update_is_sent_to_seats_and_viewers(self):
        ws = FakeWebSocketManager()
        room = make_room(ws=ws)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        room.add_viewer(VIEWER_CONN)
        ws.sent.clear()

        room.tick(now_ms=0)

        recipients = {conn_id for conn_id, msg in ws.decoded() if isinstance(msg, m.StateUpdate)}
        assert recipients == {WHITE_CONN, BLACK_CONN, VIEWER_CONN}


class TestEventBusWiring:
    def test_move_logged_is_published_via_the_bus_not_a_direct_call(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_LOGGED, received.append)

        room = create_game_room(
            "room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager(), bus=bus, max_engine_step_ms=5000,
        )
        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        assert len(received) == 1
        assert received[0].payload["room_id"] == "room-1"

    def test_piece_captured_is_published(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.PIECE_CAPTURED, received.append)

        room = create_game_room(
            "room-1", "wR . bP\n. . .\n. . .", FakeWebSocketManager(), bus=bus, max_engine_step_ms=5000,
        )
        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        assert len(received) == 1

    def test_game_over_is_published_on_a_king_capture(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.GAME_OVER, received.append)

        room = create_game_room(
            "room-1", "wR . bK\n. . .\n. . .", FakeWebSocketManager(), bus=bus, max_engine_step_ms=5000,
        )
        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        assert len(received) == 1
        assert room.status is RoomStatus.ENDED


class TestTracing:
    def test_pending_moves_trace_id_reaches_the_move_logged_event(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.MOVE_LOGGED, received.append)

        room = create_game_room(
            "room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager(), bus=bus, max_engine_step_ms=5000,
        )
        room.enqueue_move(PendingMove(
            "w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN, trace_id="trace-abc",
        ))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        assert received[0].trace_id == "trace-abc"

    def test_per_tick_fallback_trace_id_is_used_for_events_with_no_originating_pending_move(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.PIECE_CAPTURED, received.append)
        trace_ids = SequentialTraceIdGenerator()

        # request_move called directly (bypassing enqueue_move/_drain) means
        # no PendingMove.trace_id was ever recorded for this piece, so its
        # eventual capture event must fall back to the per-tick trace id.
        room = create_game_room(
            "room-1", "wR . bP\n. . .\n. . .", FakeWebSocketManager(), bus=bus, trace_id_generator=trace_ids,
            max_engine_step_ms=5000,
        )
        room.session.request_move(Position(0, 0), Position(0, 2))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        assert len(received) == 1
        assert received[-1].trace_id is not None


class TestForceResign:
    def test_ends_the_room_and_publishes_game_over(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.GAME_OVER, received.append)
        room = create_game_room("room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager(), bus=bus)

        room.force_resign("white")

        assert room.status is RoomStatus.ENDED
        assert len(received) == 1
        assert received[0].payload["resigned_color"] == "white"

    def test_force_resign_is_idempotent(self):
        bus = InMemoryEventBus()
        received = []
        bus.subscribe(EventNames.GAME_OVER, received.append)
        room = create_game_room("room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager(), bus=bus)

        room.force_resign("white")
        room.force_resign("white")

        assert len(received) == 1


class TestEmitEdgeCases:
    def test_emit_with_no_bus_is_a_no_op(self):
        room = make_room(bus=None)  # default: no bus configured
        event = EngineEvent(
            kind=EngineEventKind.MOVE_EXECUTED, at_ms=0, piece=None,
            from_pos=None, to_pos=None, captured=None, beneficiary_color=None,
        )
        room.emit(event)  # must not raise

    def test_emit_with_an_unmapped_engine_event_kind_does_not_publish(self):
        bus = InMemoryEventBus()
        received = []
        for name in (EventNames.MOVE_LOGGED, EventNames.PIECE_CAPTURED, EventNames.MOVE_STOPPED, EventNames.GAME_OVER):
            bus.subscribe(name, received.append)
        room = make_room(bus=bus)

        event = EngineEvent(
            kind=EngineEventKind.MOVE_ABORTED, at_ms=0, piece=None,
            from_pos=None, to_pos=None, captured=None, beneficiary_color=None,
        )
        room.emit(event)

        assert received == []
