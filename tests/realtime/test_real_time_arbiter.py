from kfchess.model.piece import Piece, PieceKind, PieceState
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.real_time_arbiter import (
    RealTimeArbiter, MoveOutcomeStatus, JUMP_DURATION_MS, MOVE_DURATION_MS_PER_CELL as DEFAULT_MOVE_DELAY_MS,
)


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
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))

        assert arbiter.advance(DEFAULT_MOVE_DELAY_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED

    def test_chebyshev_distance_uses_max_axis_not_sum(self):
        bishop = Piece('w', PieceKind.BISHOP)
        board = board_with(((2, 2), bishop))
        arbiter = make_arbiter(board)

        # 3 cells diagonally: max(|3|, |3|) = 3, not 6.
        arbiter.begin_move(bishop, Position(2, 2), Position(5, 5))

        assert arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert board.get(Position(5, 5)) is bishop

    def test_two_phase_advance_before_and_after_arrival(self):
        rook = Piece('w', PieceKind.ROOK)
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
        rook = Piece('w', PieceKind.ROOK)
        impostor = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        board.set(Position(0, 0), impostor)  # origin no longer holds `rook`

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.ABORTED_PREMOVE
        assert board.get(Position(0, 7)) is None
        assert arbiter.is_moving(rook) is False

    def test_path_blocked_at_arrival_aborts(self):
        rook = Piece('w', PieceKind.ROOK)
        blocker = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(4, 0), Position(4, 7))
        board.set(Position(4, 3), blocker)  # blocker appears mid-flight

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.ABORTED_ILLEGAL
        assert board.get(Position(4, 0)) is rook
        assert board.get(Position(4, 7)) is None

    def test_friendly_destination_at_arrival_aborts(self):
        rook = Piece('w', PieceKind.ROOK)
        friend = Piece('w', PieceKind.PAWN)
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
        rook = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), rook), ((0, 7), enemy))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is enemy

    def test_move_to_empty_square_reports_no_capture(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].captured_piece is None


class TestJump:
    def test_jump_matures_after_exactly_jump_duration_and_lands_normally(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))

        assert arbiter.advance(JUMP_DURATION_MS - 1) == []
        outcomes = arbiter.advance(1)

        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is None
        assert board.get(Position(4, 4)) is king

    def test_piece_remains_on_its_own_cell_throughout_the_jump(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))
        arbiter.advance(JUMP_DURATION_MS // 2)

        assert board.get(Position(4, 4)) is king

    def test_is_airborne_true_during_jump_and_false_after_landing(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))

        assert arbiter.is_airborne(king) is True
        assert arbiter.is_moving(king) is True

        arbiter.advance(JUMP_DURATION_MS)

        assert arbiter.is_airborne(king) is False
        assert arbiter.is_moving(king) is False

    def test_enemy_arrival_during_jump_window_is_captured_by_airborne_defender(self):
        attacker = Piece('w', PieceKind.ROOK)
        defender = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        arbiter = make_arbiter(board)

        arbiter.begin_move(attacker, Position(4, 3), Position(4, 4))  # matures at 1000
        arbiter.advance(500)
        arbiter.begin_move(defender, Position(4, 4), Position(4, 4))  # matures at 1500

        outcomes = arbiter.advance(500)  # clock now 1000: attacker arrives, defender still airborne

        assert outcomes[0].status is MoveOutcomeStatus.CAPTURED_ON_ARRIVAL
        assert outcomes[0].piece is attacker
        assert board.get(Position(4, 3)) is None
        assert board.get(Position(4, 4)) is defender
        assert arbiter.is_moving(attacker) is False

        landing = arbiter.advance(500)  # clock now 1500: defender's jump lands, untouched

        assert landing[0].status is MoveOutcomeStatus.EXECUTED
        assert landing[0].captured_piece is None
        assert board.get(Position(4, 4)) is defender
        assert arbiter.is_airborne(defender) is False

    def test_enemy_arrival_after_jump_has_already_landed_captures_normally(self):
        attacker = Piece('w', PieceKind.ROOK)
        defender = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        arbiter = make_arbiter(board)

        arbiter.begin_move(defender, Position(4, 4), Position(4, 4))
        arbiter.advance(JUMP_DURATION_MS)  # jump lands before the attacker arrives
        assert arbiter.is_airborne(defender) is False

        arbiter.begin_move(attacker, Position(4, 3), Position(4, 4))
        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is defender
        assert board.get(Position(4, 4)) is attacker


class TestIsMovingLifecycle:
    def test_is_moving_true_immediately_after_begin_move(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))

        assert arbiter.is_moving(rook) is True

    def test_is_moving_false_after_execution(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_moving(rook) is False

    def test_is_moving_false_after_abort(self):
        rook = Piece('w', PieceKind.ROOK)
        impostor = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        board.set(Position(0, 0), impostor)
        arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_moving(rook) is False

    def test_is_moving_false_when_never_scheduled(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        assert arbiter.is_moving(rook) is False


class TestAbort:
    def test_abort_releases_piece_and_prevents_it_from_maturing(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        arbiter.abort(rook)

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes == []
        assert arbiter.is_moving(rook) is False
        assert rook.state is PieceState.IDLE
        assert board.get(Position(0, 0)) is rook
        assert board.get(Position(0, 7)) is None


class TestCancelAllPending:
    def test_cancel_all_pending_prevents_future_pending_moves_from_executing(self):
        rook = Piece('w', PieceKind.ROOK)
        bishop = Piece('w', PieceKind.BISHOP)
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
        rook = Piece('w', PieceKind.ROOK)
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


class TestPawnPromotion:
    def test_white_pawn_reaching_last_row_becomes_queen(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((1, 0), pawn))
        arbiter = make_arbiter(board)

        arbiter.begin_move(pawn, Position(1, 0), Position(0, 0))
        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert pawn.kind is PieceKind.QUEEN

    def test_black_pawn_reaching_last_row_becomes_queen(self):
        pawn = Piece('b', PieceKind.PAWN)
        board = board_with(((6, 0), pawn))
        arbiter = make_arbiter(board)

        arbiter.begin_move(pawn, Position(6, 0), Position(7, 0))
        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert pawn.kind is PieceKind.QUEEN

    def test_pawn_not_on_last_row_stays_a_pawn(self):
        pawn = Piece('w', PieceKind.PAWN)
        board = board_with(((4, 0), pawn))
        arbiter = make_arbiter(board)

        arbiter.begin_move(pawn, Position(4, 0), Position(3, 0))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert pawn.kind is PieceKind.PAWN
