from dataclasses import dataclass


class MoveRejectionReason:
    """
    Stable, machine-readable reason codes. Values (not names) are the
    contract - GameEngine, the DSL, and tests all key off these strings.
    """
    OK = "ok"
    OUTSIDE_BOARD = "outside_board"
    EMPTY_SOURCE = "empty_source"
    FRIENDLY_DESTINATION = "friendly_destination"
    ILLEGAL_PIECE_MOVE = "illegal_piece_move"
    PIECE_ALREADY_MOVING = "piece_already_moving"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class MoveValidation:
    is_valid: bool
    reason: str

    @staticmethod
    def ok() -> "MoveValidation":
        return MoveValidation(is_valid=True, reason=MoveRejectionReason.OK)

    @staticmethod
    def invalid(reason: str) -> "MoveValidation":
        return MoveValidation(is_valid=False, reason=reason)
