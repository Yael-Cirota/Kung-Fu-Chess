from pieces import King, Rook, Bishop, Pawn, DEFAULT_MOVE_DELAY_MS
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.engine.real_time_arbiter import RealTimeArbiter, MoveOutcomeStatus


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


def make_arbiter(board):
    return RealTimeArbiter(board, RuleEngine())


class TestTiming:
    def test_distance_one_matures_after_exactly_one_delay_unit(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))

        assert arbiter.advance(DEFAULT_MOVE_DELAY_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED

    def test_chebyshev_distance_uses_max_axis_not_sum(self):
        bishop = Bishop('w')
        board = board_with(((2, 2), bishop))
        arbiter = make_arbiter(board)

        # 3 cells diagonally: max(|3|, |3|) = 3, not 6.
        arbiter.begin_move(bishop, Position(2, 2), Position(5, 5))

        assert arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert board.get(Position(5, 5)) is bishop

    def test_zero_distance_schedules_using_fallback_distance_of_one(self):
        king = King('w')
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))

        assert arbiter.advance(DEFAULT_MOVE_DELAY_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1

    def test_two_phase_advance_before_and_after_arrival(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 2))

        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(0, 0)) is rook
        assert board.get(Position(0, 2)) is None

        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(0, 0)) is None
        assert board.get(Position(0, 2)) is rook


class TestAbortOutcomes:
    def test_premove_abort_when_origin_no_longer_holds_the_piece(self):
        rook = Rook('w')
        impostor = Pawn('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        board.set(Position(0, 0), impostor)  # origin no longer holds `rook`

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.ABORTED_PREMOVE
        assert board.get(Position(0, 7)) is None
        assert arbiter.is_moving(rook) is False

    def test_path_blocked_at_arrival_aborts(self):
        rook = Rook('w')
        blocker = Pawn('b')
        board = board_with(((4, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(4, 0), Position(4, 7))
        board.set(Position(4, 3), blocker)  # blocker appears mid-flight

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.ABORTED_ILLEGAL
        assert board.get(Position(4, 0)) is rook
        assert board.get(Position(4, 7)) is None

    def test_friendly_destination_at_arrival_aborts(self):
        rook = Rook('w')
        friend = Pawn('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 2))
        board.set(Position(0, 2), friend)  # friendly piece lands first

        outcomes = arbiter.advance(2 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.ABORTED_ILLEGAL
        assert board.get(Position(0, 0)) is rook
        assert board.get(Position(0, 2)) is friend


class TestCaptureReporting:
    def test_successful_capture_reports_captured_piece(self):
        rook = Rook('w')
        enemy = Pawn('b')
        board = board_with(((0, 0), rook), ((0, 7), enemy))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is enemy

    def test_move_to_empty_square_reports_no_capture(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].captured_piece is None


class TestIsMovingLifecycle:
    def test_is_moving_true_immediately_after_begin_move(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))

        assert arbiter.is_moving(rook) is True

    def test_is_moving_false_after_execution(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_moving(rook) is False

    def test_is_moving_false_after_abort(self):
        rook = Rook('w')
        impostor = Pawn('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        board.set(Position(0, 0), impostor)
        arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_moving(rook) is False

    def test_is_moving_false_when_never_scheduled(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        assert arbiter.is_moving(rook) is False


class TestCancelAllPending:
    def test_cancel_all_pending_prevents_future_pending_moves_from_executing(self):
        rook = Rook('w')
        bishop = Bishop('w')
        board = board_with(((0, 0), rook), ((2, 2), bishop))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))       # matures at 1000
        arbiter.begin_move(bishop, Position(2, 2), Position(5, 5))     # matures at 3000

        arbiter.advance(DEFAULT_MOVE_DELAY_MS)  # rook matures
        arbiter.cancel_all_pending()

        outcomes = arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes == []
        assert board.get(Position(2, 2)) is bishop
        assert board.get(Position(5, 5)) is None


class TestNoPremoveIncidentalBehavior:
    def test_second_schedule_from_same_origin_aborts_after_first_executes(self):
        """
        No explicit guard exists against scheduling a second move from a
        piece's origin square while its first move is still in flight.
        The current, real behavior (which must be preserved, not "fixed"):
        whichever move matures first wins; the later one then fails its
        premove-identity check, since the origin square no longer holds
        the piece it was scheduled against.
        """
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.begin_move(rook, Position(0, 0), Position(0, 5))

        first_outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert first_outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert board.get(Position(0, 1)) is rook

        second_outcomes = arbiter.advance(4 * DEFAULT_MOVE_DELAY_MS)
        assert second_outcomes[0].status is MoveOutcomeStatus.ABORTED_PREMOVE
        assert board.get(Position(0, 5)) is None
        assert board.get(Position(0, 1)) is rook
