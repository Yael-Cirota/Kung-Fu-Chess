from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from kfchess.model.position import Position


class MoveOutcomeStatus(Enum):
    EXECUTED = auto()
    ABORTED_PREMOVE = auto()
    ABORTED_ILLEGAL = auto()
    CAPTURED_ON_ARRIVAL = auto()


@dataclass(frozen=True)
class MoveOutcome:
    status: MoveOutcomeStatus
    piece: object
    from_pos: Position
    to_pos: Position
    captured_piece: Optional[object] = None


@dataclass
class PendingMove:
    piece: object
    from_pos: Position
    to_pos: Position
    execute_at: int
