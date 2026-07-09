from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_result import MoveRejectionReason, MoveValidationResult
from kfchess.rules.movement_rules import MovementRules


class RuleEngine:
    """
    Move validation only. Read-only with respect to the board.
    Returns a stable reason indicator instead of a plain boolean.
    """

    @staticmethod
    def validate(board: Board, from_pos: Position, to_pos: Position) -> MoveValidationResult:
        if not board.is_within_bounds(from_pos) or not board.is_within_bounds(to_pos):
            return MoveValidationResult.reject(MoveRejectionReason.OUT_OF_BOUNDS)

        piece = board.get(from_pos)
        if piece is None:
            return MoveValidationResult.reject(MoveRejectionReason.EMPTY_ORIGIN)

        if from_pos == to_pos:
            return MoveValidationResult.ok()

        if not MovementRules.geometry_matches(board, piece, from_pos, to_pos):
            return MoveValidationResult.reject(MoveRejectionReason.NOT_A_LEGAL_SHAPE)

        if MovementRules.requires_clear_path(piece) and not MovementRules.is_path_clear(board, from_pos, to_pos):
            return MoveValidationResult.reject(MoveRejectionReason.BLOCKED)

        target = board.get(to_pos)
        if target is not None and target.color == piece.color:
            return MoveValidationResult.reject(MoveRejectionReason.FRIENDLY_FIRE)

        return MoveValidationResult.ok()
