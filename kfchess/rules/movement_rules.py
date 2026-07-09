from kfchess.model.piece import King, Rook, Bishop, Queen, Knight, Pawn
from kfchess.model.board import Board
from kfchess.model.position import Position

_SLIDING_TYPES = (Rook, Bishop, Queen)


class MovementRules:
    """
    Calculates whether a piece's geometric shape/path permits a move.
    Stateless; reads the board but never modifies it.
    """

    @staticmethod
    def is_legal_shape(board: Board, piece, from_pos: Position, to_pos: Position) -> bool:
        """Full legality of shape and (for sliding pieces) an unobstructed path."""
        if not MovementRules.geometry_matches(board, piece, from_pos, to_pos):
            return False

        if MovementRules.requires_clear_path(piece):
            return MovementRules.is_path_clear(board, from_pos, to_pos)

        return True

    @staticmethod
    def requires_clear_path(piece) -> bool:
        return isinstance(piece, _SLIDING_TYPES)

    @staticmethod
    def is_path_clear(board: Board, from_pos: Position, to_pos: Position) -> bool:
        """Checks that every square strictly between from_pos and to_pos is empty."""
        dr = to_pos.row - from_pos.row
        dc = to_pos.col - from_pos.col

        step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
        step_c = 0 if dc == 0 else (1 if dc > 0 else -1)

        curr_r, curr_c = from_pos.row + step_r, from_pos.col + step_c
        while (curr_r, curr_c) != (to_pos.row, to_pos.col):
            if board.get(Position(curr_r, curr_c)) is not None:
                return False
            curr_r += step_r
            curr_c += step_c

        return True

    @staticmethod
    def geometry_matches(board: Board, piece, from_pos: Position, to_pos: Position) -> bool:
        """
        Whether the move's shape is one this piece kind can ever make,
        ignoring whether the path is blocked. For pawns this also
        depends on destination occupancy, since forward/diagonal
        legality is inherently occupancy-dependent, not a "blocked
        path" in the sliding-piece sense.
        """
        dr = to_pos.row - from_pos.row
        dc = to_pos.col - from_pos.col

        if dr == 0 and dc == 0:
            return False

        if isinstance(piece, King):
            return abs(dr) <= 1 and abs(dc) <= 1

        if isinstance(piece, Rook):
            return dr == 0 or dc == 0

        if isinstance(piece, Bishop):
            return abs(dr) == abs(dc)

        if isinstance(piece, Queen):
            return dr == 0 or dc == 0 or abs(dr) == abs(dc)

        if isinstance(piece, Knight):
            return (abs(dr) == 2 and abs(dc) == 1) or (abs(dr) == 1 and abs(dc) == 2)

        if isinstance(piece, Pawn):
            return MovementRules._pawn_shape_matches(board, piece, from_pos, to_pos, dr, dc)

        return False

    @staticmethod
    def _pawn_shape_matches(board: Board, piece, from_pos: Position, to_pos: Position, dr: int, dc: int) -> bool:
        direction = -1 if piece.color == 'w' else 1

        if dc == 0 and dr == direction:
            return board.get(to_pos) is None

        start_row = board.rows - 1 if piece.color == 'w' else 0
        if dc == 0 and dr == 2 * direction and from_pos.row == start_row:
            mid_pos = Position(from_pos.row + direction, from_pos.col)
            return board.get(mid_pos) is None and board.get(to_pos) is None

        if abs(dc) == 1 and dr == direction:
            target = board.get(to_pos)
            return target is not None and target.color != piece.color

        return False
