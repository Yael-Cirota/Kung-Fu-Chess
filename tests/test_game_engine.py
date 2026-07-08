import pytest
from pieces import King, Queen, Rook, Bishop, Knight, Pawn, DEFAULT_MOVE_DELAY_MS
from game_engine import GameEngine
from movement_tracker import MovementTracker


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

    def test_clicking_friendly_moving_piece_keeps_current_selection(self):
        king = King('w')
        rook = Rook('w')
        tracker = MovementTracker()
        tracker.set_moving(rook)
        engine = GameEngine(empty_board(), movement_tracker=tracker)
        engine.board[0][0] = king
        engine.board[0][1] = rook

        engine.handle_click(50, 50)   # select king at (0,0)
        engine.handle_click(150, 50)  # click moving rook at (0,1)

        # Selection does not change because target friendly piece is in transit.
        assert engine.selected_cell == (0, 0)


# ==========================================
# 4. HANDLE_CLICK — MOVEMENT
# ==========================================

class TestHandleClickMovement:
    def test_legal_move_executes(self):
        rook = Rook('w')
        engine = make_engine(((4, 0), rook))
        engine.handle_click(50, 450)   # select rook at (4,0)
        engine.handle_click(750, 450)  # move to (4,7)
        engine.advance_clock(8 * DEFAULT_MOVE_DELAY_MS)  # allow scheduled move to complete
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
        engine.advance_clock(8 * DEFAULT_MOVE_DELAY_MS)  # allow scheduled move to complete
        assert rook.has_moved is True

    def test_capture_enemy_piece(self):
        rook = Rook('w')
        enemy = Pawn('b')
        engine = make_engine(((4, 0), rook), ((4, 7), enemy))
        engine.handle_click(50, 450)   # select rook
        engine.handle_click(750, 450)  # capture enemy at (4,7)
        engine.advance_clock(8 * DEFAULT_MOVE_DELAY_MS)  # allow scheduled move to complete
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
# 5. SCHEDULE_MOVE & TIMING (New Feature)
# ==========================================

class TestMoveScheduling:
    def testschedule_move_distance_one(self):
        """Test that moving 1 cell schedules the move for exactly 1 delay unit."""
        rook = Rook('w')
        engine = make_engine(((0, 0), rook))
        
        # Advance clock to simulate a game already in progress
        engine.clock_ms = 500  
        
        # Schedule a move 1 cell down
        engine.schedule_move(rook, 0, 0, 1, 0)
        
        assert len(engine.pending_moves) == 1
        scheduled = engine.pending_moves[0]
        
        assert scheduled['from_row'] == 0
        assert scheduled['to_row'] == 1
        
        # Target time = current clock (500) + (1 cell * 1000ms) = 1500
        assert scheduled['execute_at'] == 1500

    def testschedule_move_calculates_distance_correctly(self):
        """Test that diagonal multi-cell distance uses the maximum axis difference (Chebyshev distance)."""
        bishop = Bishop('w')
        engine = make_engine(((2, 2), bishop))
        
        # Schedule a move 3 cells diagonally
        engine.schedule_move(bishop, 2, 2, 5, 5)
        
        # Distance = max(|5-2|, |5-2|) = 3. Target = 3 * 1000 = 3000
        assert engine.pending_moves[0]['execute_at'] == 3000

    def testschedule_move_distance_zero_fallback(self):
        """Test the safety fallback if a piece is scheduled to move to its own cell."""
        king = King('w')
        engine = make_engine(((4, 4), king))
        
        # Schedule move to the exact same spot
        engine.schedule_move(king, 4, 4, 4, 4)
        
        # Should fallback to distance 1 -> target = 1000 (prevents zero-time instant moves)
        assert engine.pending_moves[0]['execute_at'] == 1000

    def test_integration_two_cell_move_before_and_after_arrival(self):
        """
        Integration test verifying the exact VPL scenario:
        A 2-cell move takes 2000ms. Halfway through, the piece hasn't moved.
        After the full time, the piece appears at the destination.
        """
        rook = Rook('w')
        engine = make_engine(((0, 0), rook))
        
        # Click (0,0) then (0,2) -> Move 2 cells right
        engine.handle_click(50, 50)
        engine.handle_click(250, 50)
        
        # Distance is 2, so it needs 2000ms.
        # 1. Advance by 1000ms -> Move should NOT happen yet
        engine.advance_clock(1000)
        assert engine.board[0][0] is rook     # Still at start
        assert engine.board[0][2] is None     # Destination is empty
        
        # 2. Advance by another 1000ms (Total 2000) -> Move SHOULD happen
        engine.advance_clock(1000)
        assert engine.board[0][0] is None     # Left start
        assert engine.board[0][2] is rook     # Arrived at destination

    def test_execute_move_calls_tracker_set_arrived_when_origin_no_longer_has_piece(self):
        class SpyTracker:
            def __init__(self):
                self.arrivals = []

            def set_arrived(self, piece):
                self.arrivals.append(piece)

        tracker = SpyTracker()
        engine = GameEngine(empty_board(), movement_tracker=tracker)
        piece = King('w')

        # Execute move where the original square no longer contains this piece.
        engine._execute_move({
            'piece': piece,
            'execute_at': 0,
            'from_row': 0,
            'from_col': 0,
            'to_row': 0,
            'to_col': 1,
        })

        assert tracker.arrivals == [piece]

    def test_execute_move_aborts_when_path_becomes_illegal(self):
        class SpyTracker:
            def __init__(self):
                self.arrivals = []

            def set_arrived(self, piece):
                self.arrivals.append(piece)

        rook = Rook('w')
        blocker = Pawn('w')
        tracker = SpyTracker()
        engine = GameEngine(empty_board(), movement_tracker=tracker)
        engine.board[0][0] = rook

        # The move was scheduled when path was clear; then a blocker appears.
        move = {
            'piece': rook,
            'execute_at': 0,
            'from_row': 0,
            'from_col': 0,
            'to_row': 0,
            'to_col': 2,
        }
        engine.board[0][1] = blocker

        engine._execute_move(move)

        assert engine.board[0][0] is rook
        assert engine.board[0][2] is None
        assert tracker.arrivals == [rook]

    def test_execute_move_aborts_on_friendly_destination_piece(self):
        class SpyTracker:
            def __init__(self):
                self.arrivals = []

            def set_arrived(self, piece):
                self.arrivals.append(piece)

        rook = Rook('w')
        friend = Pawn('w')
        tracker = SpyTracker()
        engine = GameEngine(empty_board(), movement_tracker=tracker)
        engine.board[0][0] = rook
        engine.board[0][2] = friend

        engine._execute_move({
            'piece': rook,
            'execute_at': 0,
            'from_row': 0,
            'from_col': 0,
            'to_row': 0,
            'to_col': 2,
        })

        assert engine.board[0][0] is rook
        assert engine.board[0][2] is friend
        assert tracker.arrivals == [rook]

    def test_execute_move_without_tracker_still_executes(self):
        rook = Rook('w')
        engine = GameEngine(empty_board(), movement_tracker=None)
        engine.board[0][0] = rook

        engine._execute_move({
            'piece': rook,
            'execute_at': 0,
            'from_row': 0,
            'from_col': 0,
            'to_row': 0,
            'to_col': 1,
        })

        assert engine.board[0][0] is None
        assert engine.board[0][1] is rook

    def test_schedule_move_marks_piece_as_moving_when_tracker_exists(self):
        class SpyTracker:
            def __init__(self):
                self.moving = []

            def set_moving(self, piece):
                self.moving.append(piece)

        rook = Rook('w')
        tracker = SpyTracker()
        engine = GameEngine(empty_board(), movement_tracker=tracker)

        engine.schedule_move(rook, 0, 0, 0, 1)

        assert tracker.moving == [rook]

    def test_execute_move_success_calls_tracker_set_arrived(self):
        class SpyTracker:
            def __init__(self):
                self.arrivals = []

            def set_arrived(self, piece):
                self.arrivals.append(piece)

        rook = Rook('w')
        tracker = SpyTracker()
        engine = GameEngine(empty_board(), movement_tracker=tracker)
        engine.board[0][0] = rook

        engine._execute_move({
            'piece': rook,
            'execute_at': 0,
            'from_row': 0,
            'from_col': 0,
            'to_row': 0,
            'to_col': 1,
        })

        assert tracker.arrivals == [rook]


# ==========================================
# 6. PRINT_BOARD (smoke test)
# ==========================================

class TestPrintBoard:
    def test_print_board_does_not_raise(self, capsys):
        king = King('w')
        engine = make_engine(((0, 0), king))
        engine.print_board()
        out = capsys.readouterr().out
        assert 'wK' in out
        assert '.' in out
