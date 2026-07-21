from server.domain.client_session import ClientSession, ClientSessionRegistry, InMemoryClientSessionRegistry
from server.domain.connection_id import ConnectionId


def make_registry():
    return InMemoryClientSessionRegistry()


class TestBindAndGet:
    def test_get_returns_none_for_unknown_connection(self):
        registry = make_registry()
        assert registry.get(ConnectionId("c1")) is None

    def test_bind_then_get_returns_the_session(self):
        registry = make_registry()
        session = ClientSession(
            connection_id=ConnectionId("c1"), user_id=1, username="alice",
            elo=1200, room_id=None, role=None, epoch=1,
        )
        registry.bind(session)
        assert registry.get(ConnectionId("c1")) == session

    def test_satisfies_the_protocol(self):
        assert isinstance(make_registry(), ClientSessionRegistry)


class TestByUser:
    def test_returns_none_when_the_user_has_no_bound_connection(self):
        registry = make_registry()
        assert registry.by_user(1) is None

    def test_returns_the_session_bound_to_that_user(self):
        registry = make_registry()
        session = ClientSession(
            connection_id=ConnectionId("c1"), user_id=1, username="alice",
            elo=1200, room_id=None, role=None, epoch=1,
        )
        registry.bind(session)
        assert registry.by_user(1) == session


class TestUpdateRoom:
    def test_sets_room_and_role_on_the_bound_session(self):
        registry = make_registry()
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, None, None, 1))
        registry.update_room(ConnectionId("c1"), "room-1", "white")

        session = registry.get(ConnectionId("c1"))
        assert session.room_id == "room-1"
        assert session.role == "white"

    def test_unknown_connection_is_a_no_op(self):
        registry = make_registry()
        registry.update_room(ConnectionId("ghost"), "room-1", "white")  # must not raise


class TestRelease:
    def test_removes_the_connection_and_user_binding(self):
        registry = make_registry()
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, None, None, 1))
        registry.release(ConnectionId("c1"))

        assert registry.get(ConnectionId("c1")) is None
        assert registry.by_user(1) is None

    def test_unknown_connection_is_a_no_op(self):
        registry = make_registry()
        registry.release(ConnectionId("ghost"))  # must not raise

    def test_does_not_clobber_a_newer_binding_for_the_same_user(self):
        # Releasing a stale connection_id must not release the *current*
        # binding if the user has since rebound to a different connection.
        registry = make_registry()
        registry.bind(ClientSession(ConnectionId("c1"), 1, "alice", 1200, None, None, 1))
        registry.rebind(1, ConnectionId("c2"), "alice", 1200)

        registry.release(ConnectionId("c1"))

        assert registry.by_user(1) is not None
        assert registry.by_user(1).connection_id == ConnectionId("c2")


class TestRebind:
    def test_first_rebind_for_a_user_has_no_eviction(self):
        registry = make_registry()
        result = registry.rebind(1, ConnectionId("c1"), "alice", 1200)

        assert result.ok is True
        assert result.value.evicted_connection_id is None
        assert result.value.session.epoch == 1

    def test_rebind_to_a_new_connection_evicts_the_old_one(self):
        registry = make_registry()
        registry.rebind(1, ConnectionId("c1"), "alice", 1200)
        result = registry.rebind(1, ConnectionId("c2"), "alice", 1200)

        assert result.value.evicted_connection_id == ConnectionId("c1")
        assert registry.get(ConnectionId("c1")) is None
        assert registry.get(ConnectionId("c2")) is not None

    def test_rebind_leaves_exactly_one_registry_entry_for_the_user(self):
        registry = make_registry()
        registry.rebind(1, ConnectionId("c1"), "alice", 1200)
        registry.rebind(1, ConnectionId("c2"), "alice", 1200)

        assert registry.by_user(1).connection_id == ConnectionId("c2")
        assert registry.get(ConnectionId("c1")) is None

    def test_rebind_bumps_the_epoch(self):
        registry = make_registry()
        first = registry.rebind(1, ConnectionId("c1"), "alice", 1200)
        second = registry.rebind(1, ConnectionId("c2"), "alice", 1200)

        assert second.value.session.epoch == first.value.session.epoch + 1

    def test_rebind_preserves_room_and_role_across_reconnect(self):
        registry = make_registry()
        registry.rebind(1, ConnectionId("c1"), "alice", 1200)
        registry.update_room(ConnectionId("c1"), "room-1", "white")

        result = registry.rebind(1, ConnectionId("c2"), "alice", 1200)

        assert result.value.session.room_id == "room-1"
        assert result.value.session.role == "white"

    def test_rebind_to_the_same_connection_id_reports_no_eviction(self):
        registry = make_registry()
        registry.rebind(1, ConnectionId("c1"), "alice", 1200)
        result = registry.rebind(1, ConnectionId("c1"), "alice", 1200)

        assert result.value.evicted_connection_id is None
