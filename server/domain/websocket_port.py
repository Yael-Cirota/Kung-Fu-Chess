"""The transport port: pure interfaces, no socket/asyncio knowledge. Lives in
domain (not presentation) because the Application layer (GameRoom,
BroadcastObserver) depends on this Protocol to send outbound frames, and in a
layered architecture a port is owned by/below the layer that consumes it -
the concrete adapter (server/presentation/connection.py's ConnectionRegistry,
and eventually a real websockets adapter) lives in the outer layer that
fulfills it."""

from typing import List, Optional, Protocol, Sequence, runtime_checkable

from server.domain.connection_id import ConnectionId


@runtime_checkable
class Connection(Protocol):
    @property
    def connection_id(self) -> ConnectionId: ...

    def send(self, raw: str) -> None: ...  # non-blocking; adapter queues to the loop

    def close(self) -> None: ...


@runtime_checkable
class WebSocketManager(Protocol):
    def register(self, conn: Connection) -> None: ...

    def unregister(self, conn_id: ConnectionId) -> None: ...

    def get(self, conn_id: ConnectionId) -> Optional[Connection]: ...

    def send_to(self, conn_id: ConnectionId, raw: str) -> None: ...

    def broadcast(self, conn_ids: Sequence[ConnectionId], raw: str) -> None: ...

    def connection_ids(self) -> List[ConnectionId]: ...
