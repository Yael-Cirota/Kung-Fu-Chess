import pytest
from pieces import King, Queen, Rook, Bishop, Knight, Pawn


# ==========================================
# HELPERS
# ==========================================

def empty_board(rows=8, cols=8):
    """Return an empty NxM board (all None)."""
    return [[None] * cols for _ in range(rows)]


def board_with(pieces: dict, rows=8, cols=8):
    """
    Build a board from a dict of {(row, col): Piece}.
    All other cells are None.
    """
    b = empty_board(rows, cols)
    for (r, c), piece in pieces.items():
        b[r][c] = piece
    return b


# ==========================================
# 1. KING
# ==========================================

class TestKing:
    def test_get_symbol(self):
        assert King('w').get_symbol() == 'wK'
        assert King('b').get_symbol() == 'bK'

    @pytest.mark.parametrize("dr,dc", [
        (0, 1), (0, -1), (1, 0), (-1, 0),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    ])
    def test_legal_one_step(self, dr, dc):
        king = King('w')
        b = empty_board()
        assert king.is_legal_move(b, 4, 4, 4 + dr, 4 + dc) is True

    def test_illegal_no_move(self):
        b = empty_board()
        assert King('w').is_legal_move(b, 4, 4, 4, 4) is False

    def test_illegal_two_squares(self):
        b = empty_board()
        assert King('w').is_legal_move(b, 4, 4, 4, 6) is False
        assert King('w').is_legal_move(b, 4, 4, 6, 6) is False


# ==========================================
# 2. ROOK
# ==========================================

class TestRook:
    def test_get_symbol(self):
        assert Rook('w').get_symbol() == 'wR'
        assert Rook('b').get_symbol() == 'bR'

    def test_legal_horizontal(self):
        rook = Rook('w')
        b = empty_board()
        b[4][0] = rook
        assert rook.is_legal_move(b, 4, 0, 4, 7) is True

    def test_legal_vertical(self):
        rook = Rook('w')
        b = empty_board()
        b[0][3] = rook
        assert rook.is_legal_move(b, 0, 3, 7, 3) is True

    def test_illegal_no_move(self):
        rook = Rook('w')
        b = empty_board()
        assert rook.is_legal_move(b, 3, 3, 3, 3) is False

    def test_illegal_diagonal(self):
        rook = Rook('w')
        b = empty_board()
        assert rook.is_legal_move(b, 0, 0, 3, 3) is False

    def test_blocked_path(self):
        rook = Rook('w')
        blocker = Rook('b')
        b = empty_board()
        b[4][0] = rook
        b[4][3] = blocker  # blocks path to col 7
        assert rook.is_legal_move(b, 4, 0, 4, 7) is False

    def test_capture_adjacent(self):
        rook = Rook('w')
        target = Rook('b')
        b = empty_board()
        b[4][0] = rook
        b[4][1] = target
        # Path to col 1 is clear (target is the destination, not an intermediate)
        assert rook.is_legal_move(b, 4, 0, 4, 1) is True


# ==========================================
# 3. BISHOP
# ==========================================

class TestBishop:
    def test_get_symbol(self):
        assert Bishop('w').get_symbol() == 'wB'
        assert Bishop('b').get_symbol() == 'bB'

    def test_legal_diagonal(self):
        bishop = Bishop('w')
        b = empty_board()
        b[0][0] = bishop
        assert bishop.is_legal_move(b, 0, 0, 5, 5) is True

    def test_illegal_no_move(self):
        bishop = Bishop('w')
        b = empty_board()
        assert bishop.is_legal_move(b, 3, 3, 3, 3) is False

    def test_illegal_straight(self):
        bishop = Bishop('w')
        b = empty_board()
        assert bishop.is_legal_move(b, 3, 3, 3, 6) is False
        assert bishop.is_legal_move(b, 3, 3, 6, 3) is False

    def test_blocked_path(self):
        bishop = Bishop('w')
        blocker = Bishop('b')
        b = empty_board()
        b[0][0] = bishop
        b[2][2] = blocker
        assert bishop.is_legal_move(b, 0, 0, 4, 4) is False


# ==========================================
# 4. QUEEN
# ==========================================

class TestQueen:
    def test_get_symbol(self):
        assert Queen('w').get_symbol() == 'wQ'
        assert Queen('b').get_symbol() == 'bQ'

    def test_legal_horizontal(self):
        queen = Queen('w')
        b = empty_board()
        b[4][0] = queen
        assert queen.is_legal_move(b, 4, 0, 4, 7) is True

    def test_legal_vertical(self):
        queen = Queen('w')
        b = empty_board()
        b[0][4] = queen
        assert queen.is_legal_move(b, 0, 4, 7, 4) is True

    def test_legal_diagonal(self):
        queen = Queen('w')
        b = empty_board()
        b[0][0] = queen
        assert queen.is_legal_move(b, 0, 0, 5, 5) is True

    def test_illegal_no_move(self):
        queen = Queen('w')
        b = empty_board()
        assert queen.is_legal_move(b, 3, 3, 3, 3) is False

    def test_illegal_L_shape(self):
        queen = Queen('w')
        b = empty_board()
        assert queen.is_legal_move(b, 3, 3, 5, 4) is False

    def test_blocked_path(self):
        queen = Queen('w')
        blocker = Queen('b')
        b = empty_board()
        b[0][0] = queen
        b[3][3] = blocker
        assert queen.is_legal_move(b, 0, 0, 5, 5) is False


# ==========================================
# 5. KNIGHT
# ==========================================

class TestKnight:
    def test_get_symbol(self):
        assert Knight('w').get_symbol() == 'wN'
        assert Knight('b').get_symbol() == 'bN'

    @pytest.mark.parametrize("dr,dc", [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2),
    ])
    def test_all_legal_L_shapes(self, dr, dc):
        knight = Knight('w')
        b = empty_board()
        assert knight.is_legal_move(b, 4, 4, 4 + dr, 4 + dc) is True

    def test_illegal_no_move(self):
        knight = Knight('w')
        b = empty_board()
        assert knight.is_legal_move(b, 4, 4, 4, 4) is False

    def test_illegal_straight(self):
        knight = Knight('w')
        b = empty_board()
        assert knight.is_legal_move(b, 4, 4, 4, 6) is False

    def test_jumps_over_pieces(self):
        """Knight should be able to jump over blocking pieces."""
        knight = Knight('w')
        blocker = Rook('b')
        b = empty_board()
        b[4][4] = knight
        b[4][5] = blocker
        b[5][4] = blocker
        # L-move (2,1): should still succeed even with adjacent blockers
        assert knight.is_legal_move(b, 4, 4, 6, 5) is True


# ==========================================
# 6. PAWN
# ==========================================

class TestPawn:
    def test_get_symbol(self):
        assert Pawn('w').get_symbol() == 'wP'
        assert Pawn('b').get_symbol() == 'bP'

    def test_white_pawn_forward(self):
        pawn = Pawn('w')
        b = empty_board()
        b[4][3] = pawn
        # White moves up (decreasing row)
        assert pawn.is_legal_move(b, 4, 3, 3, 3) is True

    def test_black_pawn_forward(self):
        pawn = Pawn('b')
        b = empty_board()
        b[3][3] = pawn
        # Black moves down (increasing row)
        assert pawn.is_legal_move(b, 3, 3, 4, 3) is True

    def test_pawn_blocked_by_piece(self):
        pawn = Pawn('w')
        blocker = Pawn('b')
        b = empty_board()
        b[4][3] = pawn
        b[3][3] = blocker
        assert pawn.is_legal_move(b, 4, 3, 3, 3) is False

    def test_pawn_diagonal_capture(self):
        pawn = Pawn('w')
        target = Pawn('b')
        b = empty_board()
        b[4][3] = pawn
        b[3][4] = target
        assert pawn.is_legal_move(b, 4, 3, 3, 4) is True

    def test_pawn_cannot_capture_forward(self):
        """A pawn cannot capture a piece directly in front of it."""
        pawn = Pawn('w')
        target = Pawn('b')
        b = empty_board()
        b[4][3] = pawn
        b[3][3] = target
        assert pawn.is_legal_move(b, 4, 3, 3, 3) is False

    def test_pawn_cannot_capture_friendly(self):
        """A pawn cannot capture a friendly piece diagonally."""
        pawn = Pawn('w')
        friendly = Pawn('w')
        b = empty_board()
        b[4][3] = pawn
        b[3][4] = friendly
        assert pawn.is_legal_move(b, 4, 3, 3, 4) is False

    def test_pawn_no_diagonal_without_capture(self):
        """A pawn cannot move diagonally to an empty cell."""
        pawn = Pawn('w')
        b = empty_board()
        b[4][3] = pawn
        assert pawn.is_legal_move(b, 4, 3, 3, 4) is False

    def test_pawn_cannot_move_backward(self):
        pawn = Pawn('w')
        b = empty_board()
        b[4][3] = pawn
        assert pawn.is_legal_move(b, 4, 3, 5, 3) is False

    def test_pawn_no_double_move(self):
        """This engine does not support the pawn double-move rule."""
        pawn = Pawn('w')
        b = empty_board()
        b[6][3] = pawn
        assert pawn.is_legal_move(b, 6, 3, 4, 3) is False

    def test_pawn_no_move(self):
        pawn = Pawn('w')
        b = empty_board()
        assert pawn.is_legal_move(b, 4, 3, 4, 3) is False

    def test_pawn_has_moved_flag(self):
        pawn = Pawn('w')
        assert pawn.has_moved is False
