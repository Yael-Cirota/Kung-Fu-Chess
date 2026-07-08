import pytest
from pieces import King, Queen, Rook, Bishop, Knight, Pawn
from game_engine import GameEngine


# ==========================================
# HELPERS
# ==========================================

def empty_board(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def make_engine(*pieces_at):
    """
    Build an 8x8 GameEngine pre-populated with pieces.
    pieces_at: sequence of ((row, col), Piece) tuples.
    """
    b = empty_board()
    for (r, c), piece in pieces_at:
        b[r][c] = piece
    return GameEngine(b)


# ==========================================
# 1. BOARD PROPERTIES
# ==========================================

class TestBoardProperties:
    def test_rows_and_cols(self):
        engine = GameEngine(empty_board(4, 6))
        assert engine.rows == 4
        assert engine.cols == 6

    def test_empty_board_cols(self):
        engine = GameEngine([])
        assert engine.cols == 0

    def test_is_within_bounds(self):
        engine = GameEngine(empty_board(8, 8))
        assert engine.is_within_bounds(0, 0) is True
        assert engine.is_within_bounds(7, 7) is True
        assert engine.is_within_bounds(8, 0) is False
        assert engine.is_within_bounds(0, 8) is False
        assert engine.is_within_bounds(-1, 0) is False


# ==========================================
# 2. CLOCK
# ==========================================

class TestClock:
    def test_advance_clock(self):
        engine = GameEngine(empty_board())
        engine.advance_clock(500)
        assert engine.clock_ms == 500

    def test_advance_clock_multiple_times(self):
        engine = GameEngine(empty_board())
        engine.advance_clock(100)
        engine.advance_clock(250)
        assert engine.clock_ms == 350


# ==========================================
# 3. HANDLE_CLICK — SELECTION
# ==========================================

class TestHandleClickSelection:
    def test_click_empty_cell_no_selection(self):
        engine = GameEngine(empty_board())
        engine.handle_click(50, 50)  # cell (0, 0)
        assert engine.selected_cell is None

    def test_click_piece_selects_it(self):
        king = King('w')
        engine = make_engine(((2, 3), king))
        engine.handle_click(350, 250)  # col=3, row=2
        assert engine.selected_cell == (2, 3)

    def test_click_outside_board_ignored(self):
        king = King('w')
        engine = make_engine(((0, 0), king))
        engine.handle_click(900, 900)  # outside 8x8 board
        assert engine.selected_cell is None

    def test_click_friendly_piece_replaces_selection(self):
        king = King('w')
        rook = Rook('w')
        engine = make_engine(((0, 0), king), ((0, 1), rook))
        engine.handle_click(50, 50)    # select king at (0,0)
        engine.handle_click(150, 50)   # click rook at (0,1)
        assert engine.selected_cell == (0, 1)

    def test_selection_cleared_after_move_attempt(self):
        king = King('w')
        engine = make_engine(((4, 4), king))
        engine.handle_click(450, 450)  # select king at (4,4)
        engine.handle_click(550, 450)  # attempt move to (4,5)
        assert engine.selected_cell is None

    def test_failsafe_clears_selection_when_selected_piece_is_missing(self):
        rook = Rook('w')
        engine = make_engine(((0, 0), rook))
        engine.handle_click(50, 50)  # select rook at (0,0)

        # Simulate an out-of-band mutation that removes the selected piece.
        engine.board[0][0] = None

        engine.handle_click(150, 50)  # click (0,1) and trigger failsafe branch
        assert engine.selected_cell is None


# ==========================================
# 4. HANDLE_CLICK — MOVEMENT
# ==========================================

class TestHandleClickMovement:
    def test_legal_move_executes(self):
        rook = Rook('w')
        engine = make_engine(((4, 0), rook))
        engine.handle_click(50, 450)   # select rook at (4,0)
        engine.handle_click(750, 450)  # move to (4,7)
        assert engine.board[4][7] is rook
        assert engine.board[4][0] is None

    def test_illegal_move_does_not_execute(self):
        rook = Rook('w')
        engine = make_engine(((4, 0), rook))
        engine.handle_click(50, 450)   # select rook at (4,0)
        engine.handle_click(150, 350)  # diagonal (3,1) — illegal for rook
        assert engine.board[4][0] is rook
        assert engine.board[3][1] is None

    def test_move_updates_has_moved_flag(self):
        rook = Rook('w')
        engine = make_engine(((4, 0), rook))
        assert rook.has_moved is False
        engine.handle_click(50, 450)
        engine.handle_click(750, 450)
        assert rook.has_moved is True

    def test_capture_enemy_piece(self):
        rook = Rook('w')
        enemy = Pawn('b')
        engine = make_engine(((4, 0), rook), ((4, 7), enemy))
        engine.handle_click(50, 450)   # select rook
        engine.handle_click(750, 450)  # capture enemy at (4,7)
        assert engine.board[4][7] is rook
        assert engine.board[4][0] is None

    def test_blocked_move_does_not_execute(self):
        rook = Rook('w')
        blocker = Pawn('b')
        engine = make_engine(((4, 0), rook), ((4, 3), blocker))
        engine.handle_click(50, 450)   # select rook
        engine.handle_click(750, 450)  # (4,7) is blocked by blocker at (4,3)
        assert engine.board[4][0] is rook  # rook did not move


# ==========================================
# 5. PRINT_BOARD (smoke test)
# ==========================================

class TestPrintBoard:
    def test_print_board_does_not_raise(self, capsys):
        king = King('w')
        engine = make_engine(((0, 0), king))
        engine.print_board()
        out = capsys.readouterr().out
        assert 'wK' in out
        assert '.' in out
