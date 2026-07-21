from typing import Dict, List, Optional

from server.domain.connection_id import ConnectionId
from server.domain.websocket_port import Connection, WebSocketManager

__all__ = ["Connection", "WebSocketManager", "ConnectionRegistry"]


class ConnectionRegistry:
    """In-memory WebSocketManager. Transport-agnostic: it holds whatever
    Connection instances register() gives it, whether that's a real
    websockets adapter (Phase 4) or a test double."""

    def __init__(self):
        self._connections: Dict[ConnectionId, Connection] = {}

    def register(self, conn: Connection) -> None:
        self._connections[conn.connection_id] = conn

    def unregister(self, conn_id: ConnectionId) -> None:
        self._connections.pop(conn_id, None)

    def get(self, conn_id: ConnectionId) -> Optional[Connection]:
        return self._connections.get(conn_id)

    def send_to(self, conn_id: ConnectionId, raw: str) -> None:
        conn = self._connections.get(conn_id)
        if conn is not None:
            conn.send(raw)

    def broadcast(self, conn_ids, raw: str) -> None:
        for conn_id in conn_ids:
            self.send_to(conn_id, raw)

    def connection_ids(self) -> List[ConnectionId]:
        return list(self._connections)
