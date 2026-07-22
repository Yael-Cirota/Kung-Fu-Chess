from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

from kfchess.model.position import Position


class MoveOutcomeStatus(Enum):
    EXECUTED = auto()
    ABORTED_PREMOVE = auto()
    STOPPED_BY_FRIENDLY = auto()
    CAPTURED_ON_ARRIVAL = auto()


@dataclass(frozen=True)
class MoveOutcome:
    status: MoveOutcomeStatus
    piece: object
    from_pos: Position
    to_pos: Position
    captured_piece: Optional[object] = None


@dataclass
class Motion:
    """
    A move in progress. A jumping piece hops straight to its destination;
    a sliding piece advances one square of `remaining` per step, so
    `current` tracks where it actually stands mid-flight - which is the
    "preceding square" a same-colour collision makes it stop on. `seq` is
    a monotonic id that breaks ties deterministically when two motions
    are ready to step on the same simulated tick.
    """
    piece: object
    origin: Position
    current: Position
    remaining: List[Position]
    next_step_at: int
    step_duration_ms: int
    is_jump: bool
    seq: int
    started_at_ms: int = 0
    total_duration_ms: int = 0

    @property
    def target(self) -> Position:
        """The destination square this motion is ultimately headed for."""
        return self.remaining[-1] if self.remaining else self.current
