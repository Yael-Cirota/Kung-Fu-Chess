from dataclasses import dataclass

from kfchess.rules.move_validation import MoveRejectionReason


@dataclass(frozen=True)
class MoveResult:
    """
    Public result of GameEngine.request_move - the answer the Controller
    and TextTestRunner actually see. Application-level rejections
    (game over, motion already in flight on the shared track) are
    decided by GameEngine itself; rule-level rejections copy their
    reason straight from RuleEngine's MoveValidation.
    """
    is_accepted: bool
    reason: str

    @staticmethod
    def accepted() -> "MoveResult":
        return MoveResult(is_accepted=True, reason=MoveRejectionReason.OK)

    @staticmethod
    def rejected(reason: str) -> "MoveResult":
        return MoveResult(is_accepted=False, reason=reason)
