from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from kfchess.api.dto import PieceView, Position


class EngineEventKind(Enum):
    MOVE_EXECUTED = "move_executed"
    MOVE_ABORTED = "move_aborted"
    MOVE_STOPPED = "move_stopped"
    PIECE_CAPTURED = "piece_captured"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class EngineEvent:
    kind: EngineEventKind
    at_ms: int
    piece: Optional[PieceView]
    from_pos: Optional[Position]
    to_pos: Optional[Position]
    captured: Optional[PieceView]
    beneficiary_color: Optional[str]


@runtime_checkable
class EngineEventSink(Protocol):
    def emit(self, event: EngineEvent) -> None: ...
