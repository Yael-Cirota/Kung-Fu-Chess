from kfchess.model.board import Board
from kfchess.model.position import Position


class MovementRules:
    """
    Calculates whether a piece's geometric shape/path permits a move.
    Stateless; reads the board but never modifies it.

    Currently a facade delegating to the legacy Piece.is_legal_move.
    This is the seam through which callers get the final target API
    now, while the internal geometry implementation is migrated to
    live natively here later (see Phase 11 of the migration plan).
    """

    @staticmethod
    def is_legal_shape(board: Board, piece, from_pos: Position, to_pos: Position) -> bool:
        return piece.is_legal_move(
            board.as_grid(), from_pos.row, from_pos.col, to_pos.row, to_pos.col
        )
