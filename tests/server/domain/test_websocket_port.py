from server.domain.connection_id import ConnectionId
from server.domain.websocket_port import Connection, WebSocketManager


class FakeConnection:
    def __init__(self, conn_id):
        self._connection_id = ConnectionId(conn_id)

    @property
    def connection_id(self):
        return self._connection_id

    def send(self, raw):
        pass

    def close(self):
        pass


class FakeWebSocketManager:
    def register(self, conn):
        pass

    def unregister(self, conn_id):
        pass

    def get(self, conn_id):
        return None

    def send_to(self, conn_id, raw):
        pass

    def broadcast(self, conn_ids, raw):
        pass

    def connection_ids(self):
        return []


def test_fake_connection_satisfies_the_protocol():
    assert isinstance(FakeConnection("c1"), Connection)


def test_fake_websocket_manager_satisfies_the_protocol():
    assert isinstance(FakeWebSocketManager(), WebSocketManager)
