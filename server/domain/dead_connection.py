from dataclasses import dataclass
from typing import List, Protocol, runtime_checkable

from server.domain.connection_id import ConnectionId


@dataclass(frozen=True)
class DeadConnection:
    connection_id: ConnectionId
    epoch: int  # epoch at registration; teardown no-ops if < the session's current epoch


@runtime_checkable
class ConnectionMonitorPort(Protocol):
    """What RoomTicker (Application) needs from ConnectionMonitor
    (Presentation) - just the tick sweep, so Application depends on this
    Protocol rather than on the presentation-layer class directly."""

    def tick(self, now_ms: int) -> List[DeadConnection]: ...
