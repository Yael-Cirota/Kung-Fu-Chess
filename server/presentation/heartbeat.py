from typing import Dict, List

from server.domain.connection_id import ConnectionId
from server.domain.dead_connection import DeadConnection

__all__ = ["DeadConnection", "ConnectionMonitor"]


class ConnectionMonitor:
    """Tracks per-connection liveness via a synchronous tick(now_ms) sweep -
    no asyncio.sleep, no real waiting. `register` stamps the epoch current at
    registration/rebind time, so a stale connection's eventual death report
    can be told apart from a live one by the caller (see 'Reconnection
    protocol' - a session epoch makes a late teardown harmless)."""

    def __init__(self, timeout_ms: int):
        self._timeout_ms = timeout_ms
        self._last_heartbeat_ms: Dict[ConnectionId, int] = {}
        self._epochs: Dict[ConnectionId, int] = {}

    def register(self, conn_id: ConnectionId, epoch: int, now_ms: int) -> None:
        self._last_heartbeat_ms[conn_id] = now_ms
        self._epochs[conn_id] = epoch

    def on_heartbeat(self, conn_id: ConnectionId, now_ms: int) -> None:
        if conn_id in self._last_heartbeat_ms:
            self._last_heartbeat_ms[conn_id] = now_ms

    def forget(self, conn_id: ConnectionId) -> None:
        self._last_heartbeat_ms.pop(conn_id, None)
        self._epochs.pop(conn_id, None)

    def tick(self, now_ms: int) -> List[DeadConnection]:
        dead = []
        for conn_id, last_seen_ms in list(self._last_heartbeat_ms.items()):
            if now_ms - last_seen_ms > self._timeout_ms:
                dead.append(DeadConnection(connection_id=conn_id, epoch=self._epochs.get(conn_id, 0)))
                self.forget(conn_id)
        return dead
