from server.domain.connection_id import ConnectionId
from server.presentation.heartbeat import ConnectionMonitor, DeadConnection


class TestRegisterAndTick:
    def test_freshly_registered_connection_is_not_dead(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        assert monitor.tick(5000) == []

    def test_connection_with_no_heartbeat_past_the_timeout_is_reported_dead(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        dead = monitor.tick(10001)

        assert dead == [DeadConnection(connection_id=ConnectionId("c1"), epoch=1)]

    def test_exactly_at_the_timeout_boundary_is_still_alive(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        assert monitor.tick(10000) == []

    def test_dead_connection_is_forgotten_so_it_is_not_reported_twice(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        monitor.tick(20000)
        assert monitor.tick(30000) == []


class TestOnHeartbeat:
    def test_heartbeat_resets_the_liveness_window(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        monitor.on_heartbeat(ConnectionId("c1"), now_ms=8000)

        assert monitor.tick(15000) == []
        assert monitor.tick(18001) == [DeadConnection(connection_id=ConnectionId("c1"), epoch=1)]

    def test_heartbeat_for_an_unregistered_connection_is_a_no_op(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.on_heartbeat(ConnectionId("ghost"), now_ms=0)  # must not raise
        assert monitor.tick(100000) == []


class TestForget:
    def test_forgotten_connection_is_never_reported_dead(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)

        monitor.forget(ConnectionId("c1"))

        assert monitor.tick(999999) == []

    def test_forgetting_an_unknown_connection_is_a_no_op(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.forget(ConnectionId("ghost"))  # must not raise


class TestMultipleConnections:
    def test_only_the_timed_out_connection_is_reported(self):
        monitor = ConnectionMonitor(timeout_ms=10000)
        monitor.register(ConnectionId("c1"), epoch=1, now_ms=0)
        monitor.register(ConnectionId("c2"), epoch=1, now_ms=9000)

        dead = monitor.tick(10001)

        assert dead == [DeadConnection(connection_id=ConnectionId("c1"), epoch=1)]
