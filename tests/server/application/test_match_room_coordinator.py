import asyncio

from common.events import Event, EventNames, InMemoryEventBus
from protocol import codec, messages as m
from server.application.game_room import create_game_room
from server.application.match_room_coordinator import MatchRoomCoordinator
from server.application.matchmaking import Match, MatchTicket
from server.application.room_service import Role
from server.domain.client_session import ClientSession, InMemoryClientSessionRegistry
from server.domain.connection_id import ConnectionId


def publish(bus, event):
    asyncio.run(bus.publish(event))


class FakeWebSocketManager:
    def __init__(self):
        self.sent = []

    def send_to(self, conn_id, raw):
        self.sent.append((conn_id, raw))

    def broadcast(self, conn_ids, raw):
        for conn_id in conn_ids:
            self.send_to(conn_id, raw)

    def decoded(self):
        return [(conn_id, codec.decode(raw)) for conn_id, raw in self.sent]


WHITE_CONN = ConnectionId("white-conn")
BLACK_CONN = ConnectionId("black-conn")


def bound_sessions(registry):
    registry.bind(ClientSession(WHITE_CONN, 1, "alice", 1200, None, None, 1))
    registry.bind(ClientSession(BLACK_CONN, 2, "bob", 1210, None, None, 1))


def match_found_event():
    return Event(
        name=EventNames.MATCH_FOUND,
        payload={"match": Match(
            white=MatchTicket(user_id=1, username="alice", elo=1200),
            black=MatchTicket(user_id=2, username="bob", elo=1210),
        )},
    )


def make_coordinator(rooms, ws, client_sessions, room_id="room-1"):
    def room_factory():
        return create_game_room(room_id, "wR . .\n. . .\n. . .", ws)

    return MatchRoomCoordinator(
        bus=InMemoryEventBus(), rooms=rooms, websocket_manager=ws,
        client_sessions=client_sessions, room_factory=room_factory,
    ), room_factory


class TestMatchFoundCreatesAndSeatsARoom:
    def test_creates_a_room_via_the_factory(self):
        rooms = {}
        ws = FakeWebSocketManager()
        client_sessions = InMemoryClientSessionRegistry()
        bound_sessions(client_sessions)
        bus = InMemoryEventBus()
        MatchRoomCoordinator(
            bus=bus, rooms=rooms, websocket_manager=ws, client_sessions=client_sessions,
            room_factory=lambda: create_game_room("room-1", "wR . .\n. . .\n. . .", ws),
        )

        publish(bus, match_found_event())

        assert "room-1" in rooms

    def test_seats_white_and_black_by_ticket_and_updates_their_sessions(self):
        rooms = {}
        ws = FakeWebSocketManager()
        client_sessions = InMemoryClientSessionRegistry()
        bound_sessions(client_sessions)
        bus = InMemoryEventBus()
        MatchRoomCoordinator(
            bus=bus, rooms=rooms, websocket_manager=ws, client_sessions=client_sessions,
            room_factory=lambda: create_game_room("room-1", "wR . .\n. . .\n. . .", ws),
        )

        publish(bus, match_found_event())

        assert rooms["room-1"].player_user_ids() == {"white": 1, "black": 2}
        assert client_sessions.get(WHITE_CONN).room_id == "room-1"
        assert client_sessions.get(WHITE_CONN).role == Role.WHITE
        assert client_sessions.get(BLACK_CONN).room_id == "room-1"
        assert client_sessions.get(BLACK_CONN).role == Role.BLACK

    def test_sends_match_found_to_both_connections_with_their_own_color(self):
        rooms = {}
        ws = FakeWebSocketManager()
        client_sessions = InMemoryClientSessionRegistry()
        bound_sessions(client_sessions)
        bus = InMemoryEventBus()
        MatchRoomCoordinator(
            bus=bus, rooms=rooms, websocket_manager=ws, client_sessions=client_sessions,
            room_factory=lambda: create_game_room("room-1", "wR . .\n. . .\n. . .", ws),
        )

        publish(bus, match_found_event())

        match_found_messages = {conn_id: msg for conn_id, msg in ws.decoded() if isinstance(msg, m.MatchFound)}
        assert match_found_messages[WHITE_CONN] == m.MatchFound(room_id="room-1", color="white")
        assert match_found_messages[BLACK_CONN] == m.MatchFound(room_id="room-1", color="black")

    def test_a_ticket_whose_connection_already_dropped_is_skipped(self):
        rooms = {}
        ws = FakeWebSocketManager()
        client_sessions = InMemoryClientSessionRegistry()
        client_sessions.bind(ClientSession(WHITE_CONN, 1, "alice", 1200, None, None, 1))
        # bob (user_id=2) never bound a session
        bus = InMemoryEventBus()
        MatchRoomCoordinator(
            bus=bus, rooms=rooms, websocket_manager=ws, client_sessions=client_sessions,
            room_factory=lambda: create_game_room("room-1", "wR . .\n. . .\n. . .", ws),
        )

        publish(bus, match_found_event())

        assert rooms["room-1"].player_user_ids() == {"white": 1}
