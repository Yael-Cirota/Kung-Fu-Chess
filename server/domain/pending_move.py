from dataclasses import dataclass
from typing import Optional

from kfchess.api import Position
from server.domain.connection_id import ConnectionId


@dataclass(frozen=True)
class PendingMove:
    color: str
    from_pos: Position
    to_pos: Position
    client_seq: int
    connection_id: ConnectionId  # for routing the eventual MoveAck
    trace_id: Optional[str] = None
