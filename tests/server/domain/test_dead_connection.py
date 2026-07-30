from server.domain.connection_id import ConnectionId
from server.domain.dead_connection import ConnectionMonitorPort, DeadConnection


class FakeMonitor:
    def tick(self, now_ms):
        return []


def test_dead_connection_holds_connection_id_and_epoch():
    dead = DeadConnection(connection_id=ConnectionId("c1"), epoch=3)
    assert dead.connection_id == ConnectionId("c1")
    assert dead.epoch == 3


def test_fake_monitor_satisfies_the_port():
    assert isinstance(FakeMonitor(), ConnectionMonitorPort)
