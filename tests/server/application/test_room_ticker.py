from common.events import InMemoryEventBus
from server.application.disconnect_policy import DisconnectPolicy
from server.application.game_room import create_game_room
from server.application.matchmaking import MatchmakingService
from server.application.room_ticker import RoomTicker
from server.domain.client_session import ClientSession, InMemoryClientSessionRegistry
from server.domain.connection_id import ConnectionId
from server.presentation.heartbeat import ConnectionMonitor


class FakeWebSocketManager:
    def register(self, conn):
        pass

    def unregister(self, conn_id):
        pass

    def send_to(self, conn_id, raw):
        pass

    def broadcast(self, conn_ids, raw):
        pass

    def connection_ids(self):
        return []


def make_ticker(rooms=None, timeout_ms=10000, grace_ms=20000):
    monitor = ConnectionMonitor(timeout_ms=timeout_ms)
    disconnect_policy = DisconnectPolicy(grace_ms=grace_ms)
    matchmaking = MatchmakingService(InMemoryEventBus())
    registry = InMemoryClientSessionRegistry()
    ticker = RoomTicker(
        rooms=rooms if rooms is not None else {},
        connection_monitor=monitor,
        disconnect_policy=disconnect_policy,
        matchmaking_service=matchmaking,
        client_sessions=registry,
    )
    return ticker, monitor, disconnect_policy, registry


class TestDeadConnectionHandling:
    def test_genuine_disconnect_starts_the_countdown(self):
        ticker, monitor, disconnect_policy, registry = make_ticker(timeout_ms=1000)
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, "room-1", "white", epoch=1))
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        ticker.tick(now_ms=1001)  # connection goes dead

        assert disconnect_policy.deadline_for("room-1", "white") is not None

    def test_stale_dead_report_is_a_no_op(self):
        # Simulate: the user reconnected (epoch bumped to 2 in the registry)
        # before the monitor noticed the old connection (epoch 1) was dead.
        ticker, monitor, disconnect_policy, registry = make_ticker(timeout_ms=1000)
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, "room-1", "white", epoch=2))
        monitor.register(ConnectionId("old-conn"), epoch=1, now_ms=0)

        ticker.tick(now_ms=1001)

        assert disconnect_policy.deadline_for("room-1", "white") is None

    def test_dead_connection_with_no_session_is_a_no_op(self):
        ticker, monitor, disconnect_policy, registry = make_ticker(timeout_ms=1000)
        monitor.register(ConnectionId("ghost"), epoch=1, now_ms=0)

        ticker.tick(now_ms=1001)  # must not raise, and nothing to assert on

    def test_viewer_disconnect_does_not_start_a_countdown(self):
        ticker, monitor, disconnect_policy, registry = make_ticker(timeout_ms=1000)
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, "room-1", "viewer", epoch=1))
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        ticker.tick(now_ms=1001)

        assert disconnect_policy.deadline_for("room-1", "viewer") is None


class TestForcedResignEndsTheRoom:
    def test_a_forced_resign_ends_the_matching_room(self):
        room = create_game_room("room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager())
        ticker, monitor, disconnect_policy, registry = make_ticker(rooms={"room-1": room}, timeout_ms=1000, grace_ms=0)
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, "room-1", "white", epoch=1))
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        forced = ticker.tick(now_ms=1001)  # disconnect starts and immediately expires (grace_ms=0)

        assert len(forced) == 1
        from server.domain.room_status import RoomStatus
        assert room.status is RoomStatus.ENDED


class TestRoomsAreTicked:
    def test_every_room_advances_its_clock(self):
        room = create_game_room("room-1", "wR . .\n. . .\n. . .", FakeWebSocketManager())
        ticker, *_ = make_ticker(rooms={"room-1": room})

        ticker.tick(now_ms=0)
        ticker.tick(now_ms=50)

        assert room.session.clock_ms > 0


class TestMatchmakingIsTicked:
    def test_matchmaking_timeouts_are_swept(self):
        bus = InMemoryEventBus()
        received = []
        from common.events import EventNames
        bus.subscribe(EventNames.MATCH_TIMED_OUT, received.append)

        monitor = ConnectionMonitor(timeout_ms=10000)
        disconnect_policy = DisconnectPolicy(grace_ms=20000)
        matchmaking = MatchmakingService(bus, timeout_ms=1000)
        registry = InMemoryClientSessionRegistry()
        ticker = RoomTicker({}, monitor, disconnect_policy, matchmaking, registry)

        from server.application.matchmaking import MatchTicket
        matchmaking.enqueue(MatchTicket(user_id=1, username="a", elo=1200), now_ms=0)

        ticker.tick(now_ms=1000)

        assert len(received) == 1
