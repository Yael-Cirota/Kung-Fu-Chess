from typing import Dict, Optional, Type

from kfchess.model.board import Board
from kfchess.model.piece import PieceKind
from kfchess.model.position import Position
from kfchess.rules.move_validation import MoveRejectionReason, MoveValidation
from kfchess.rules.piece_rules import (
    PieceRule, RookRule, BishopRule, QueenRule, KnightRule, KingRule, PawnRule,
)

DEFAULT_RULES: Dict[PieceKind, Type[PieceRule]] = {
    PieceKind.ROOK: RookRule,
    PieceKind.BISHOP: BishopRule,
    PieceKind.QUEEN: QueenRule,
    PieceKind.KNIGHT: KnightRule,
    PieceKind.KING: KingRule,
    PieceKind.PAWN: PawnRule,
}


class RuleEngine:
    """
    Answers exactly one question: does this command match the piece's
    movement *pattern*? Read-only with respect to the board - never moves
    pieces, removes captures, or otherwise mutates game state. Delegates
    destination geometry to a per-kind rule, injected at construction
    (defaults to kfchess.rules.piece_rules). Occupancy along the path and
    on the destination is deliberately *not* checked here: collisions are
    resolved dynamically by RealTimeArbiter during the move, so nothing is
    blocked at the input phase (pawns are the one exception - their
    forward/diagonal split is occupancy-dependent by nature).

    Out of scope by design: check, pins, checkmate, castling, en
    passant, and game-over handling. The only win condition (capturing
    the king) and game-over bookkeeping live in GameEngine. Promotion
    eligibility (like move legality) is delegated per-kind to a
    PieceRule; RuleEngine only dispatches, it doesn't decide.
    """

    def __init__(self, rules: Optional[Dict[PieceKind, Type[PieceRule]]] = None):
        self._rules = rules if rules is not None else DEFAULT_RULES

    def validate(self, board: Board, from_pos: Position, to_pos: Position) -> MoveValidation:
        if not board.is_within_bounds(from_pos) or not board.is_within_bounds(to_pos):
            return MoveValidation.invalid(MoveRejectionReason.OUTSIDE_BOARD)

        piece = board.get(from_pos)
        if piece is None:
            return MoveValidation.invalid(MoveRejectionReason.EMPTY_SOURCE)

        if from_pos == to_pos:
            return MoveValidation.ok()

        rule = self._rules[piece.kind]
        if to_pos in rule.legal_destinations(board, piece):
            return MoveValidation.ok()

        return MoveValidation.invalid(MoveRejectionReason.ILLEGAL_PIECE_MOVE)

    def promotion_kind(self, board: Board, piece, to_pos: Position) -> Optional[PieceKind]:
        """Returns the kind `piece` should become after landing on to_pos, or None if it doesn't promote."""
        rule = self._rules[piece.kind]
        return rule.promotion_kind(board, piece, to_pos)
