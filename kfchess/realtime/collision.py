from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional


class CollisionType(Enum):
    NONE = auto()
    SAME_COLOR = auto()
    DIFFERENT_COLOR = auto()


class ResolutionAction(Enum):
    PROCEED = auto()   # the square is free - the mover enters it
    STOP = auto()      # the mover halts on its current (preceding) square
    CAPTURE = auto()   # the mover takes the occupant and enters the square


@dataclass(frozen=True)
class CollisionResolution:
    action: ResolutionAction
    captured_piece: Optional[object] = None


class CollisionDetector:
    """
    Classifies, without touching the board, what the mover finds on the
    square it is about to enter. Pure occupant/colour inspection - it
    decides nothing about the response, only the kind of collision.
    """

    def classify(self, mover, occupant: Optional[object]) -> CollisionType:
        if occupant is None:
            return CollisionType.NONE
        if occupant.color == mover.color:
            return CollisionType.SAME_COLOR
        return CollisionType.DIFFERENT_COLOR


class ResolutionStrategy(ABC):
    """One resolution behaviour, selected by collision type. Never mutates state."""

    @abstractmethod
    def resolve(self, mover, occupant: Optional[object]) -> CollisionResolution:
        raise NotImplementedError  # pragma: no cover


class ProceedResolution(ResolutionStrategy):
    def resolve(self, mover, occupant: Optional[object]) -> CollisionResolution:
        return CollisionResolution(ResolutionAction.PROCEED)


class StopResolution(ResolutionStrategy):
    """Same-colour rule: the later arriver stops on the preceding square."""

    def resolve(self, mover, occupant: Optional[object]) -> CollisionResolution:
        return CollisionResolution(ResolutionAction.STOP)


class CaptureResolution(ResolutionStrategy):
    """Different-colour rule: the later arriver captures the piece that arrived first."""

    def resolve(self, mover, occupant: Optional[object]) -> CollisionResolution:
        return CollisionResolution(ResolutionAction.CAPTURE, captured_piece=occupant)


DEFAULT_RESOLUTIONS: Dict[CollisionType, ResolutionStrategy] = {
    CollisionType.NONE: ProceedResolution(),
    CollisionType.SAME_COLOR: StopResolution(),
    CollisionType.DIFFERENT_COLOR: CaptureResolution(),
}


class CollisionResolver:
    """
    Maps a collision type to its resolution behaviour through an injected
    Strategy table (no hard-coded branching). Swapping the table changes
    the rules without touching this class or the arbiter.
    """

    def __init__(self, resolutions: Optional[Dict[CollisionType, ResolutionStrategy]] = None):
        self._resolutions = resolutions if resolutions is not None else DEFAULT_RESOLUTIONS

    def resolve(self, collision_type: CollisionType, mover, occupant: Optional[object]) -> CollisionResolution:
        return self._resolutions[collision_type].resolve(mover, occupant)
