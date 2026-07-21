from kfchess.api import Position
from common.events import InMemoryEventBus
from protocol import codec, messages as m
from server.application.broadcast_observer import BroadcastObserver
from server.application.game_room import create_game_room
from server.domain.connection_id import ConnectionId
from server.domain.pending_move import PendingMove

WHITE_CONN = ConnectionId("white-conn")
BLACK_CONN = ConnectionId("black-conn")


class FakeWebSocketManager:
    def __init__(self):
        self.sent = []

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
        return [c for c, _ in self.sent]

    def decoded(self):
        return [(conn_id, codec.decode(raw)) for conn_id, raw in self.sent]


class TestDeltaEventOnCapture:
    def test_piece_captured_produces_an_immediate_delta_event_to_every_seat(self):
        ws = FakeWebSocketManager()
        bus = InMemoryEventBus()
        room = create_game_room(
            "room-1", "wR . bP\n. . .\n. . .", ws, bus=bus, max_engine_step_ms=5000,
        )
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        BroadcastObserver(bus, ws, {"room-1": room})
        ws.sent.clear()

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)
        room.tick(now_ms=2000)

        deltas = [msg for _c, msg in ws.decoded() if isinstance(msg, m.DeltaEvent)]
        assert len(deltas) == 2  # one per seat
        assert deltas[0].kind == "piece_captured"

    def test_delta_event_arrives_before_the_next_gated_state_update(self):
        # BroadcastObserver fires synchronously from within session.wait(),
        # which happens during 'advance' - strictly before 'broadcast' in
        # GameRoom.tick's drain -> advance -> broadcast sequence. So on the
        # same tick that matures the capture, the DeltaEvent is enqueued to
        # the fake transport ahead of that tick's StateUpdate.
        ws = FakeWebSocketManager()
        bus = InMemoryEventBus()
        room = create_game_room(
            "room-1", "wR . bP\n. . .\n. . .", ws, bus=bus, max_engine_step_ms=5000, broadcast_hz=1000,
        )
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        BroadcastObserver(bus, ws, {"room-1": room})
        ws.sent.clear()

        room.enqueue_move(PendingMove("w", Position(0, 0), Position(0, 2), client_seq=1, connection_id=WHITE_CONN))
        room.tick(now_ms=0)
        ws.sent.clear()
        room.tick(now_ms=2000)

        white_messages = [msg for conn_id, msg in ws.decoded() if conn_id == WHITE_CONN]
        delta_index = next(i for i, msg in enumerate(white_messages) if isinstance(msg, m.DeltaEvent))
        state_update_index = next(i for i, msg in enumerate(white_messages) if isinstance(msg, m.StateUpdate))
        assert delta_index < state_update_index


class TestUnrelatedRoomIsIgnored:
    def test_event_for_an_unknown_room_id_is_a_no_op(self):
        ws = FakeWebSocketManager()
        bus = InMemoryEventBus()
        BroadcastObserver(bus, ws, {})

        from common.events import Event, EventNames
        bus.publish(Event(name=EventNames.PIECE_CAPTURED, payload={"room_id": "ghost"}))  # must not raise
        assert ws.sent == []


class TestForcedResignDeltaEvent:
    def test_force_resign_game_over_produces_a_delta_event_with_no_engine_event(self):
        ws = FakeWebSocketManager()
        bus = InMemoryEventBus()
        room = create_game_room("room-1", "wR . .\n. . .\n. . .", ws, bus=bus)
        room.assign_seat("white", WHITE_CONN)
        room.assign_seat("black", BLACK_CONN)
        BroadcastObserver(bus, ws, {"room-1": room})
        ws.sent.clear()

        room.force_resign("white")

        deltas = [msg for _c, msg in ws.decoded() if isinstance(msg, m.DeltaEvent)]
        assert len(deltas) == 2
        assert deltas[0].kind == "game_over"
        assert deltas[0].beneficiary_color == "white"
