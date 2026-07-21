from kfchess.model.piece import Piece, PieceKind
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_validation import MoveRejectionReason
from kfchess.rules.rule_engine import RuleEngine
from kfchess.rules.scoring import ScoringPolicy
from kfchess.realtime.cooldown import CooldownPolicy
from kfchess.realtime.motion import MoveOutcome, MoveOutcomeStatus
from kfchess.realtime.real_time_arbiter import (
    RealTimeArbiter, JUMP_DURATION_MS, MOVE_DURATION_MS_PER_CELL as DEFAULT_MOVE_DELAY_MS,
)
from kfchess.engine.game_engine import GameEngine


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


def make_engine(board, cooldown_policy=None, scoring=None):
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board, rule_engine, cooldown_policy=cooldown_policy)
    return GameEngine(board, rule_engine, arbiter, scoring=scoring)


class TestBoardPassthroughs:
    def test_piece_at_returns_occupant(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        assert engine.piece_at(Position(4, 0)) is rook
        assert engine.piece_at(Position(0, 0)) is None

    def test_is_within_bounds_matches_board(self):
        board = board_with()
        engine = make_engine(board)

        assert engine.is_within_bounds(Position(0, 0)) is True
        assert engine.is_within_bounds(Position(8, 0)) is False



class TestRequestMoveLegal:
    def test_legal_move_returns_ok_and_schedules(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(4, 7))

        assert result.is_accepted is True
        assert engine.is_moving(rook) is True

    def test_legal_move_executes_after_clock_advances(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 0), Position(4, 7))
        engine.wait(7 * DEFAULT_MOVE_DELAY_MS)

        assert board.get(Position(4, 7)) is rook
        assert board.get(Position(4, 0)) is None


class TestRequestMoveRejections:
    def test_illegal_shape_returns_reason_without_scheduling(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(3, 1))

        assert result.is_accepted is False
        assert result.reason == MoveRejectionReason.ILLEGAL_PIECE_MOVE
        assert engine.is_moving(rook) is False

    def test_out_of_bounds_returns_reason(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(4, 8))

        assert result.reason == MoveRejectionReason.OUTSIDE_BOARD

    def test_friendly_destination_is_accepted_and_resolved_dynamically(self):
        # No longer blocked at the input phase: the command is accepted and
        # the rook stops one square short of the friendly piece in flight.
        rook = Piece('w', PieceKind.ROOK)
        friend = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), rook), ((0, 7), friend))
        engine = make_engine(board)

        result = engine.request_move(Position(0, 0), Position(0, 7))
        assert result.is_accepted is True

        engine.wait(7 * DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(0, 6)) is rook
        assert board.get(Position(0, 7)) is friend


class TestMoveLog:
    def test_empty_before_any_move(self):
        engine = make_engine(board_with())
        assert engine.move_log() == []

    def test_accepted_move_records_color_symbol_and_endpoints(self):
        knight = Piece('b', PieceKind.KNIGHT)
        board = board_with(((0, 1), knight))
        engine = make_engine(board)

        engine.request_move(Position(0, 1), Position(2, 2))

        log = engine.move_log()
        assert len(log) == 1
        record = log[0]
        assert record.color == 'b'
        assert record.symbol == 'bN'
        assert record.from_pos == Position(0, 1)
        assert record.to_pos == Position(2, 2)

    def test_rejected_move_is_not_recorded(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 0), Position(3, 1))  # illegal diagonal
        assert engine.move_log() == []

    def test_returns_a_copy_so_callers_cannot_mutate_history(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)
        engine.request_move(Position(4, 0), Position(4, 7))

        engine.move_log().clear()
        assert len(engine.move_log()) == 1


class TestScoring:
    def test_scores_start_at_zero(self):
        engine = make_engine(board_with())
        assert engine.scores() == {"w": 0, "b": 0}

    def test_capturing_a_pawn_credits_the_capturing_color(self):
        rook = Piece('w', PieceKind.ROOK)
        enemy_pawn = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), rook), ((0, 1), enemy_pawn))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.scores() == {"w": 1, "b": 0}

    def test_capture_value_depends_on_the_captured_kind(self):
        rook = Piece('b', PieceKind.ROOK)
        enemy_queen = Piece('w', PieceKind.QUEEN)
        board = board_with(((0, 0), rook), ((0, 1), enemy_queen))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.scores() == {"w": 0, "b": 9}

    def test_non_capturing_move_scores_nothing(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 0), Position(4, 7))
        engine.wait(7 * DEFAULT_MOVE_DELAY_MS)

        assert engine.scores() == {"w": 0, "b": 0}

    def test_scores_returns_a_copy_so_callers_cannot_mutate_state(self):
        engine = make_engine(board_with())
        engine.scores()["w"] = 99
        assert engine.scores() == {"w": 0, "b": 0}

    def test_king_capture_is_scored_despite_ending_the_game(self):
        attacker = Piece('w', PieceKind.ROOK)
        king = Piece('b', PieceKind.KING)
        board = board_with(((0, 0), attacker), ((0, 1), king))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is True
        assert engine.scores() == {"w": 10, "b": 0}

    def test_capture_on_arrival_credits_the_airborne_defenders_color(self):
        # A white rook walks onto a black bishop that is jumping in place; the
        # arriver is the loser, so black is credited the rook's value.
        attacker = Piece('w', PieceKind.ROOK)
        defender = Piece('b', PieceKind.BISHOP)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # matures at 1000
        engine.wait(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500
        engine.wait(500)  # clock 1000: rook arrives while bishop still airborne

        assert board.get(Position(4, 4)) is defender
        assert engine.scores() == {"w": 0, "b": 5}

    def test_capture_on_arrival_credits_white_when_black_is_the_arriver(self):
        # Mirror of the case above with colors swapped, so the opponent-of
        # shortcut is exercised in both directions (black arriver -> white scores).
        attacker = Piece('b', PieceKind.ROOK)
        defender = Piece('w', PieceKind.BISHOP)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # matures at 1000
        engine.wait(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500
        engine.wait(500)  # clock 1000: black rook arrives while bishop still airborne

        assert board.get(Position(4, 4)) is defender
        assert engine.scores() == {"w": 5, "b": 0}

    def test_king_captured_on_arrival_is_scored_for_the_defender(self):
        attacker = Piece('w', PieceKind.KING)
        defender = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # king walks in, matures at 1000
        engine.wait(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500
        engine.wait(500)  # clock 1000: king arrives while defender airborne

        assert engine.game_over is True
        assert engine.scores() == {"w": 0, "b": 10}


class TestClock:
    def test_clock_ms_starts_at_zero(self):
        engine = make_engine(board_with())
        assert engine.clock_ms == 0

    def test_advance_clock_updates_clock_ms(self):
        engine = make_engine(board_with())
        engine.wait(500)
        engine.wait(250)
        assert engine.clock_ms == 750


class TestGameOver:
    def test_capturing_king_sets_game_over(self):
        attacker = Piece('w', PieceKind.ROOK)
        king = Piece('b', PieceKind.KING)
        board = board_with(((0, 0), attacker), ((0, 1), king))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is True
        assert board.get(Position(0, 1)) is attacker

    def test_capturing_non_king_does_not_set_game_over(self):
        attacker = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), attacker), ((0, 1), enemy))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is False

    def test_king_capture_cancels_other_in_flight_moves(self):
        attacker = Piece('w', PieceKind.ROOK)
        king = Piece('b', PieceKind.KING)
        bystander = Piece('w', PieceKind.BISHOP)
        board = board_with(((0, 0), attacker), ((0, 1), king), ((2, 2), bystander))
        engine = make_engine(board)

        engine.request_move(Position(2, 2), Position(5, 5))  # slides, first step at 1000
        engine.request_move(Position(0, 0), Position(0, 1))  # arrives at 1000, captures king

        engine.wait(DEFAULT_MOVE_DELAY_MS)
        assert engine.game_over is True

        # Game over cancels the bystander's remaining steps: it froze on the
        # one square it had already advanced to and never reaches (5, 5).
        engine.wait(2 * DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(3, 3)) is bystander
        assert board.get(Position(5, 5)) is None

    def test_non_capturing_stop_does_not_set_game_over(self):
        king = Piece('w', PieceKind.KING)
        friend = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), king))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        board.set(Position(0, 1), friend)  # friendly piece appears first; king stops on its preceding square

        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is False
        assert board.get(Position(0, 0)) is king
        assert board.get(Position(0, 1)) is friend

    def test_request_move_rejected_once_game_is_over(self):
        attacker = Piece('w', PieceKind.ROOK)
        king = Piece('b', PieceKind.KING)
        bystander = Piece('w', PieceKind.PAWN)
        board = board_with(((0, 0), attacker), ((0, 1), king), ((4, 4), bystander))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)
        assert engine.game_over is True

        result = engine.request_move(Position(4, 4), Position(4, 5))

        assert result.is_accepted is False
        assert result.reason == MoveRejectionReason.GAME_OVER
        assert engine.is_moving(bystander) is False


class TestWinner:
    def test_winner_is_none_while_the_game_is_on(self):
        engine = make_engine(board_with())
        assert engine.winner is None

    def test_winner_is_the_capturing_color_when_the_king_is_taken_on_arrival(self):
        attacker = Piece('w', PieceKind.ROOK)
        king = Piece('b', PieceKind.KING)
        board = board_with(((0, 0), attacker), ((0, 1), king))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.winner == 'w'

    def test_winner_is_the_defending_color_when_its_king_captures_the_arriver(self):
        attacker = Piece('w', PieceKind.KING)
        defender = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # king walks in, matures at 1000
        engine.wait(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500
        engine.wait(500)  # clock 1000: king arrives while defender airborne

        assert engine.game_over is True
        assert engine.winner == 'b'

    def test_winner_stays_none_when_a_non_king_is_captured(self):
        attacker = Piece('w', PieceKind.ROOK)
        enemy = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), attacker), ((0, 1), enemy))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert engine.winner is None


class TestJump:
    def test_jump_request_is_legal_and_lands_after_jump_duration(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 4), Position(4, 4))
        assert result.is_accepted is True
        assert engine.is_moving(rook) is True

        engine.wait(DEFAULT_MOVE_DELAY_MS)
        assert engine.is_moving(rook) is False
        assert board.get(Position(4, 4)) is rook

    def test_jumping_while_already_moving_is_rejected(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((4, 4), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 4), Position(4, 7))
        result = engine.request_move(Position(4, 4), Position(4, 4))

        assert result.is_accepted is False
        assert result.reason == MoveRejectionReason.MOTION_IN_PROGRESS

    def test_king_destroyed_by_airborne_defender_sets_game_over(self):
        attacker = Piece('w', PieceKind.KING)
        defender = Piece('b', PieceKind.ROOK)
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # king begins walking in, matures at 1000
        engine.wait(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500

        engine.wait(500)  # clock now 1000: king arrives while defender still airborne

        assert engine.game_over is True
        assert board.get(Position(4, 3)) is None
        assert board.get(Position(4, 4)) is defender


class TestCooldown:
    def test_move_is_rejected_while_piece_is_on_post_move_cooldown(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        engine = make_engine(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)  # move lands, cooldown starts

        result = engine.request_move(Position(0, 1), Position(0, 2))

        assert result.is_accepted is False
        assert result.reason == MoveRejectionReason.COOLDOWN_ACTIVE
        assert engine.is_moving(rook) is False

    def test_move_is_accepted_again_once_cooldown_expires(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        engine = make_engine(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.wait(DEFAULT_MOVE_DELAY_MS)
        engine.wait(200)  # cooldown expires

        result = engine.request_move(Position(0, 1), Position(0, 2))

        assert result.is_accepted is True

    def test_jump_cooldown_is_independent_of_move_cooldown(self):
        king = Piece('w', PieceKind.KING)
        board = board_with(((4, 4), king))
        engine = make_engine(board, CooldownPolicy(move_cooldown_ms=200, jump_cooldown_ms=900))

        engine.request_move(Position(4, 4), Position(4, 4))  # jump in place
        engine.wait(JUMP_DURATION_MS)  # jump lands, jump cooldown starts

        engine.wait(200)  # long enough for a move cooldown, not a jump cooldown
        still_rejected = engine.request_move(Position(4, 4), Position(4, 5))
        assert still_rejected.is_accepted is False
        assert still_rejected.reason == MoveRejectionReason.COOLDOWN_ACTIVE

        engine.wait(700)  # total 900ms since landing: jump cooldown now expired
        result = engine.request_move(Position(4, 4), Position(4, 5))
        assert result.is_accepted is True


class TestWaitReturnsOutcomes:
    def test_returns_the_executed_move_outcome(self):
        rook = Piece('w', PieceKind.ROOK)
        board = board_with(((0, 0), rook))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        outcomes = engine.wait(DEFAULT_MOVE_DELAY_MS)

        assert len(outcomes) == 1
        assert isinstance(outcomes[0], MoveOutcome)
        assert outcomes[0].status is MoveOutcomeStatus.EXECUTED
        assert outcomes[0].piece is rook

    def test_returns_empty_list_when_nothing_matures(self):
        board = board_with()
        engine = make_engine(board)

        assert engine.wait(500) == []


class TestCustomScoringPolicy:
    def test_custom_point_values_are_used_for_capture_scoring(self):
        attacker = Piece('w', PieceKind.ROOK)
        target = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), attacker), ((0, 2), target))
        scoring = ScoringPolicy(point_values={PieceKind.PAWN: 100, PieceKind.KNIGHT: 3, PieceKind.BISHOP: 3, PieceKind.ROOK: 5, PieceKind.QUEEN: 9, PieceKind.KING: 10})
        engine = make_engine(board, scoring=scoring)

        engine.request_move(Position(0, 0), Position(0, 2))
        engine.wait(2 * DEFAULT_MOVE_DELAY_MS)

        assert engine.scores()['w'] == 100

    def test_default_scoring_policy_matches_module_level_point_values(self):
        attacker = Piece('w', PieceKind.ROOK)
        target = Piece('b', PieceKind.PAWN)
        board = board_with(((0, 0), attacker), ((0, 2), target))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 2))
        engine.wait(2 * DEFAULT_MOVE_DELAY_MS)

        assert engine.scores()['w'] == 1
