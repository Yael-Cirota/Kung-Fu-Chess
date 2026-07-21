from dataclasses import dataclass, replace
from typing import Dict, Optional, Protocol, runtime_checkable

from common.result import Result
from server.domain.connection_id import ConnectionId


@dataclass(frozen=True)
class ClientSession:
    connection_id: ConnectionId
    user_id: int
    username: str
    elo: int
    room_id: Optional[str]
    role: Optional[str]  # "white" | "black" | "viewer" | None
    epoch: int  # bumped on every bind/rebind


@dataclass(frozen=True)
class RebindOutcome:
    """rebind() only touches the session half of reconnection. The caller -
    the dispatcher, which alone holds a WebSocketManager and a
    ConnectionMonitor - is responsible for actually closing/unregistering
    evicted_connection_id and forgetting it from the monitor, since neither
    of those concerns belongs to a session registry."""

    session: ClientSession
    evicted_connection_id: Optional[ConnectionId]


@runtime_checkable
class ClientSessionRegistry(Protocol):
    def bind(self, session: ClientSession) -> None: ...

    def get(self, conn_id: ConnectionId) -> Optional[ClientSession]: ...

    def by_user(self, user_id: int) -> Optional[ClientSession]: ...

    def update_room(self, conn_id: ConnectionId, room_id: str, role: str) -> None: ...

    def release(self, conn_id: ConnectionId) -> None: ...

    def rebind(self, user_id: int, conn_id: ConnectionId, username: str, elo: int) -> "Result[RebindOutcome]": ...


class InMemoryClientSessionRegistry:
    """The one ClientSessionRegistry. rebind() unconditionally evicts any
    existing binding for `user_id` - eviction is gated only on successful
    authentication (the caller only reaches rebind after auth succeeds),
    never on whether the old link is believed dead. This collapses
    reconnection into a single idempotent path: 'reconnect after the monitor
    noticed' and 'reconnect before the monitor noticed' are both just
    evict-then-rebind."""

    def __init__(self):
        self._by_connection: Dict[ConnectionId, ClientSession] = {}
        self._by_user: Dict[int, ConnectionId] = {}

    def bind(self, session: ClientSession) -> None:
        self._by_connection[session.connection_id] = session
        self._by_user[session.user_id] = session.connection_id

    def get(self, conn_id: ConnectionId) -> Optional[ClientSession]:
        return self._by_connection.get(conn_id)

    def by_user(self, user_id: int) -> Optional[ClientSession]:
        conn_id = self._by_user.get(user_id)
        return self._by_connection.get(conn_id) if conn_id is not None else None

    def update_room(self, conn_id: ConnectionId, room_id: str, role: str) -> None:
        session = self._by_connection.get(conn_id)
        if session is not None:
            self._by_connection[conn_id] = replace(session, room_id=room_id, role=role)

    def release(self, conn_id: ConnectionId) -> None:
        session = self._by_connection.pop(conn_id, None)
        if session is not None and self._by_user.get(session.user_id) == conn_id:
            self._by_user.pop(session.user_id, None)

    def rebind(self, user_id: int, conn_id: ConnectionId, username: str, elo: int) -> Result[RebindOutcome]:
        existing_conn_id = self._by_user.get(user_id)
        existing_session = self._by_connection.get(existing_conn_id) if existing_conn_id is not None else None

        next_epoch = existing_session.epoch + 1 if existing_session is not None else 1
        evicted_connection_id = None
        if existing_session is not None and existing_conn_id != conn_id:
            self._by_connection.pop(existing_conn_id, None)
            evicted_connection_id = existing_conn_id

        room_id = existing_session.room_id if existing_session is not None else None
        role = existing_session.role if existing_session is not None else None

        session = ClientSession(
            connection_id=conn_id,
            user_id=user_id,
            username=username,
            elo=elo,
            room_id=room_id,
            role=role,
            epoch=next_epoch,
        )
        self._by_connection[conn_id] = session
        self._by_user[user_id] = conn_id

        return Result.success(RebindOutcome(session=session, evicted_connection_id=evicted_connection_id))
