from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class MoveRejectionReason(Enum):
    OUT_OF_BOUNDS = auto()
    EMPTY_ORIGIN = auto()
    NOT_A_LEGAL_SHAPE = auto()
    BLOCKED = auto()
    FRIENDLY_FIRE = auto()
    PIECE_ALREADY_MOVING = auto()
    GAME_OVER = auto()


@dataclass(frozen=True)
class MoveValidationResult:
    legal: bool
    reason: Optional[MoveRejectionReason] = None

    @staticmethod
    def ok() -> "MoveValidationResult":
        return MoveValidationResult(legal=True, reason=None)

    @staticmethod
    def reject(reason: MoveRejectionReason) -> "MoveValidationResult":
        return MoveValidationResult(legal=False, reason=reason)
