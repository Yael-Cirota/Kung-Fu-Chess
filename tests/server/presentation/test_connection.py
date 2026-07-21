from server.domain.connection_id import ConnectionId
from server.presentation.connection import Connection, ConnectionRegistry, WebSocketManager


class FakeConnection:
    def __init__(self, conn_id: str):
        self._connection_id = ConnectionId(conn_id)
        self.sent = []
        self.closed = False

    @property
    def connection_id(self) -> ConnectionId:
        return self._connection_id

    def send(self, raw: str) -> None:
        self.sent.append(raw)

    def close(self) -> None:
        self.closed = True


class TestProtocols:
    def test_fake_connection_satisfies_the_protocol(self):
        assert isinstance(FakeConnection("c1"), Connection)

    def test_connection_registry_satisfies_the_websocket_manager_protocol(self):
        assert isinstance(ConnectionRegistry(), WebSocketManager)


class TestRegisterAndSendTo:
    def test_send_to_a_registered_connection_delivers_the_raw_frame(self):
        registry = ConnectionRegistry()
        conn = FakeConnection("c1")
        registry.register(conn)

        registry.send_to(ConnectionId("c1"), "hello")

        assert conn.sent == ["hello"]

    def test_send_to_an_unregistered_connection_is_a_no_op(self):
        registry = ConnectionRegistry()
        registry.send_to(ConnectionId("ghost"), "hello")  # must not raise


class TestUnregister:
    def test_unregistered_connection_no_longer_receives_frames(self):
        registry = ConnectionRegistry()
        conn = FakeConnection("c1")
        registry.register(conn)
        registry.unregister(ConnectionId("c1"))

        registry.send_to(ConnectionId("c1"), "hello")

        assert conn.sent == []

    def test_unregistering_an_unknown_connection_is_a_no_op(self):
        registry = ConnectionRegistry()
        registry.unregister(ConnectionId("ghost"))  # must not raise


class TestBroadcast:
    def test_sends_to_every_id_in_order(self):
        registry = ConnectionRegistry()
        a, b = FakeConnection("a"), FakeConnection("b")
        registry.register(a)
        registry.register(b)

        registry.broadcast([ConnectionId("a"), ConnectionId("b")], "state")

        assert a.sent == ["state"]
        assert b.sent == ["state"]


class TestGet:
    def test_returns_the_registered_connection(self):
        registry = ConnectionRegistry()
        conn = FakeConnection("c1")
        registry.register(conn)

        assert registry.get(ConnectionId("c1")) is conn

    def test_returns_none_for_an_unregistered_connection(self):
        assert ConnectionRegistry().get(ConnectionId("ghost")) is None


class TestConnectionIds:
    def test_lists_every_registered_connection(self):
        registry = ConnectionRegistry()
        registry.register(FakeConnection("a"))
        registry.register(FakeConnection("b"))

        assert set(registry.connection_ids()) == {ConnectionId("a"), ConnectionId("b")}

    def test_empty_when_nothing_registered(self):
        assert ConnectionRegistry().connection_ids() == []
