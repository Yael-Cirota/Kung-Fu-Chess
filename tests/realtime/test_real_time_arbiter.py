from kfchess.model.piece import Piece, PieceKind, PieceState
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.cooldown import (
    CooldownPolicy, DEFAULT_MOVE_COOLDOWN_MS, DEFAULT_JUMP_COOLDOWN_MS,
)
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


def make_arbiter(board, cooldown_policy=None, jump_duration_ms=None):
    return RealTimeArbiter(board, RuleEngine(), cooldown_policy=cooldown_policy, jump_duration_ms=jump_duration_ms)


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

    def test_slider_occupies_intermediate_squares_while_in_flight(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 2))

        # After one cell-duration the rook has physically advanced one square.
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(0, 0)) is None
        assert board.get(Position(0, 1)) is rook
        assert board.get(Position(0, 2)) is None
        assert arbiter.is_moving(rook) is True

        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(0, 1)) is None
        assert board.get(Position(0, 2)) is rook
        assert arbiter.is_moving(rook) is False


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

    def test_enemy_in_the_path_is_captured_and_the_slider_stops_there(self):
        rook = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((4, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(4, 0), Position(4, 7))
        board.set(Position(4, 3), enemy)  # enemy sits mid-path

        outcomes = arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is enemy
        assert board.get(Position(4, 0)) is None
        assert board.get(Position(4, 3)) is rook   # stopped on the capture square
        assert board.get(Position(4, 7)) is None

    def test_friendly_in_the_path_makes_the_slider_stop_one_square_short(self):
        rook = Piece('w', PieceKind.ROOK)
        friend = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 2))
        board.set(Position(0, 2), friend)  # friendly piece sits on the destination

        outcomes = arbiter.advance(2 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.STOPPED_BY_FRIENDLY
        assert board.get(Position(0, 1)) is rook   # preceding square
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


class TestConfigurableJumpDuration:
    def test_custom_jump_duration_is_used_instead_of_the_module_default(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board, jump_duration_ms=250)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))

        assert arbiter.advance(249) == []
        outcomes = arbiter.advance(1)
        assert len(outcomes) == 1
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED

    def test_default_jump_duration_matches_the_module_constant_when_not_given(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board)

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))

        assert arbiter.advance(JUMP_DURATION_MS - 1) == []
        assert len(arbiter.advance(1)) == 1


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

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))       # finishes at 1000
        arbiter.begin_move(bishop, Position(2, 2), Position(5, 5))     # steps at 1000/2000/3000

        arbiter.advance(DEFAULT_MOVE_DELAY_MS)  # rook finishes; bishop takes its first step to (3, 3)
        arbiter.cancel_all_pending()

        outcomes = arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes == []
        # Cancelling drops the bishop's remaining steps: it stays where it
        # had already advanced to, and never reaches its destination.
        assert board.get(Position(3, 3)) is bishop
        assert board.get(Position(5, 5)) is None


class TestNoPremoveIncidentalBehavior:
    def test_second_schedule_from_same_origin_aborts_after_first_executes(self):
        """
        No explicit guard exists against scheduling a second move from a
        piece's origin square while its first move is still in flight.
        The real behavior (which must be preserved, not "fixed"): the two
        first steps are ready on the same tick; the earlier-scheduled one
        executes first and vacates the origin, so the later one fails its
        premove-identity check on the very same tick.
        """
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.begin_move(rook, Position(0, 0), Position(0, 5))

        outcomes = arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[1].status is MoveOutcomeStatus.ABORTED_PREMOVE
        assert board.get(Position(0, 1)) is rook
        assert board.get(Position(0, 5)) is None


class TestCollisionResolution:
    def test_later_arriver_stops_one_square_short_of_a_friendly_piece(self):
        first = Piece('w', PieceKind.ROOK)
        later = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), first), ((0, 5), later))
        arbiter = make_arbiter(board)

        arbiter.begin_move(first, Position(0, 0), Position(0, 2))   # arrives at 2000
        arbiter.begin_move(later, Position(0, 5), Position(0, 2))   # would arrive at 3000

        outcomes = arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS)

        statuses = {o.piece: o.status for o in outcomes}
        assert statuses[first] is MoveOutcomeStatus.EXECUTED
        assert statuses[later] is MoveOutcomeStatus.STOPPED_BY_FRIENDLY
        assert board.get(Position(0, 2)) is first
        assert board.get(Position(0, 3)) is later  # preceding square

    def test_later_arriver_captures_an_enemy_that_arrived_first(self):
        first = Piece('w', PieceKind.ROOK)
        later = Piece('b', PieceKind.ROOK)
        board = board_with(((0, 0), first), ((0, 5), later))
        arbiter = make_arbiter(board)

        arbiter.begin_move(first, Position(0, 0), Position(0, 2))   # arrives at 2000
        arbiter.begin_move(later, Position(0, 5), Position(0, 2))   # arrives at 3000

        outcomes = arbiter.advance(3 * DEFAULT_MOVE_DELAY_MS)

        captured = {o.piece: o.captured_piece for o in outcomes}
        assert captured[later] is first
        assert board.get(Position(0, 2)) is later
        assert first.state is PieceState.CAPTURED

    def test_simultaneous_arrival_is_broken_deterministically_by_schedule_order(self):
        # Both rooks reach (0, 4) on the very same tick; the one scheduled
        # first occupies it, the later-scheduled one stops one square short.
        first = Piece('w', PieceKind.ROOK)
        second = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), first), ((4, 4), second))
        arbiter = make_arbiter(board)

        arbiter.begin_move(first, Position(0, 0), Position(0, 4))    # arrives at 4000
        arbiter.begin_move(second, Position(4, 4), Position(0, 4))   # arrives at 4000

        outcomes = arbiter.advance(4 * DEFAULT_MOVE_DELAY_MS)

        statuses = {o.piece: o.status for o in outcomes}
        assert statuses[first] is MoveOutcomeStatus.EXECUTED
        assert statuses[second] is MoveOutcomeStatus.STOPPED_BY_FRIENDLY
        assert board.get(Position(0, 4)) is first
        assert board.get(Position(1, 4)) is second

    def test_simultaneous_enemy_arrival_lets_the_later_scheduled_one_capture(self):
        first = Piece('w', PieceKind.ROOK)
        second = Piece('b', PieceKind.ROOK)
        board = board_with(((0, 0), first), ((4, 4), second))
        arbiter = make_arbiter(board)

        arbiter.begin_move(first, Position(0, 0), Position(0, 4))    # arrives at 4000
        arbiter.begin_move(second, Position(4, 4), Position(0, 4))   # arrives at 4000

        outcomes = arbiter.advance(4 * DEFAULT_MOVE_DELAY_MS)

        captured = {o.piece: o.captured_piece for o in outcomes}
        assert captured[second] is first
        assert board.get(Position(0, 4)) is second
        assert first.state is PieceState.CAPTURED

    def test_knight_blocked_by_friendly_stops_on_its_origin_square(self):
        knight = Piece('w', PieceKind.KNIGHT)
        friend = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), knight), ((6, 5), friend))
        arbiter = make_arbiter(board)

        arbiter.begin_move(knight, Position(4, 4), Position(6, 5))
        outcomes = arbiter.advance(2 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.STOPPED_BY_FRIENDLY
        assert board.get(Position(4, 4)) is knight   # departure square, never left it
        assert board.get(Position(6, 5)) is friend

    def test_knight_lands_on_enemy_capturing_it(self):
        knight = Piece('w', PieceKind.KNIGHT)
        enemy = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 4), knight), ((6, 5), enemy))
        arbiter = make_arbiter(board)

        arbiter.begin_move(knight, Position(4, 4), Position(6, 5))
        outcomes = arbiter.advance(2 * DEFAULT_MOVE_DELAY_MS)

        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].captured_piece is enemy
        assert board.get(Position(6, 5)) is knight


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


class TestCooldown:
    def test_piece_is_not_on_cooldown_before_it_has_ever_moved(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        assert arbiter.is_on_cooldown(rook) is False

    def test_piece_is_on_cooldown_immediately_after_a_move_lands(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_on_cooldown(rook) is True

    def test_move_cooldown_expires_after_its_own_configured_duration(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)  # move lands, cooldown starts

        arbiter.advance(199)
        assert arbiter.is_on_cooldown(rook) is True

        arbiter.advance(1)
        assert arbiter.is_on_cooldown(rook) is False

    def test_jump_cooldown_uses_its_own_configured_duration_not_move_duration(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        arbiter = make_arbiter(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        arbiter.begin_move(king, Position(4, 4), Position(4, 4))
        arbiter.advance(JUMP_DURATION_MS)  # jump lands, cooldown starts

        arbiter.advance(899)
        assert arbiter.is_on_cooldown(king) is True

        arbiter.advance(1)
        assert arbiter.is_on_cooldown(king) is False

    def test_default_policy_gives_jump_and_move_different_durations(self):
        assert DEFAULT_MOVE_COOLDOWN_MS != DEFAULT_JUMP_COOLDOWN_MS

        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        arbiter.advance(DEFAULT_MOVE_COOLDOWN_MS)

        assert arbiter.is_on_cooldown(rook) is False

    def test_aborted_move_does_not_start_a_cooldown(self):
        rook = Piece('w', PieceKind.ROOK)
        impostor = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board)

        arbiter.begin_move(rook, Position(0, 0), Position(0, 7))
        board.set(Position(0, 0), impostor)  # origin no longer holds `rook`
        arbiter.advance(7 * DEFAULT_MOVE_DELAY_MS)

        assert arbiter.is_on_cooldown(rook) is False

    def test_piece_on_cooldown_can_move_again_once_it_expires(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        arbiter = make_arbiter(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        arbiter.begin_move(rook, Position(0, 0), Position(0, 1))
        arbiter.advance(DEFAULT_MOVE_DELAY_MS)
        assert arbiter.is_on_cooldown(rook) is True

        arbiter.advance(200)
        assert arbiter.is_on_cooldown(rook) is False

        arbiter.begin_move(rook, Position(0, 1), Position(0, 2))
        assert arbiter.is_moving(rook) is True
