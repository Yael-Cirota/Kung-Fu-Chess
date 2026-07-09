from kfchess.model.piece import King, Rook, Bishop, Pawn, DEFAULT_MOVE_DELAY_MS
from kfchess.model.board import Board
from kfchess.model.position import Position
from kfchess.rules.move_result import MoveRejectionReason
from kfchess.rules.rule_engine import RuleEngine
from kfchess.realtime.real_time_arbiter import RealTimeArbiter
from kfchess.engine.game_engine import GameEngine
from kfchess.io.board_printer import BoardPrinter


def empty_grid(rows=8, cols=8):
    return [[None] * cols for _ in range(rows)]


def board_with(*pieces_at):
    grid = empty_grid()
    for (row, col), piece in pieces_at:
        grid[row][col] = piece
    return Board(grid)


def make_engine(board):
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board, rule_engine)
    return GameEngine(board, rule_engine, arbiter)


class TestBoardPassthroughs:
    def test_piece_at_returns_occupant(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        assert engine.piece_at(Position(4, 0)) is rook
        assert engine.piece_at(Position(0, 0)) is None

    def test_is_within_bounds_matches_board(self):
        board = board_with()
        engine = make_engine(board)

        assert engine.is_within_bounds(Position(0, 0)) is True
        assert engine.is_within_bounds(Position(8, 0)) is False


class TestSnapshot:
    def test_snapshot_reflects_board_and_clock_and_game_over(self):
        rook = Rook('w')
        board = board_with(((0, 0), rook))
        engine = make_engine(board)
        engine.advance_clock(250)

        snapshot = engine.snapshot()

        assert snapshot.piece_at(Position(0, 0)).symbol == "wR"
        assert snapshot.clock_ms == 250
        assert snapshot.game_over is False

    def test_snapshot_renders_like_print_board(self, capsys):
        rook = Rook('w')
        king = King('b')
        board = Board([[rook, king]])
        engine = make_engine(board)

        BoardPrinter().print(engine.snapshot())

        out = capsys.readouterr().out
        assert out == "wR bK\n"


class TestRequestMoveLegal:
    def test_legal_move_returns_ok_and_schedules(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(4, 7))

        assert result.legal is True
        assert engine.is_moving(rook) is True

    def test_legal_move_executes_after_clock_advances(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 0), Position(4, 7))
        engine.advance_clock(7 * DEFAULT_MOVE_DELAY_MS)

        assert board.get(Position(4, 7)) is rook
        assert board.get(Position(4, 0)) is None


class TestRequestMoveRejections:
    def test_illegal_shape_returns_reason_without_scheduling(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(3, 1))

        assert result.legal is False
        assert result.reason is MoveRejectionReason.NOT_A_LEGAL_SHAPE
        assert engine.is_moving(rook) is False

    def test_out_of_bounds_returns_reason(self):
        rook = Rook('w')
        board = board_with(((4, 0), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 0), Position(4, 8))

        assert result.reason is MoveRejectionReason.OUT_OF_BOUNDS

    def test_friendly_fire_returns_reason(self):
        rook = Rook('w')
        friend = Pawn('w')
        board = board_with(((0, 0), rook), ((0, 7), friend))
        engine = make_engine(board)

        result = engine.request_move(Position(0, 0), Position(0, 7))

        assert result.reason is MoveRejectionReason.FRIENDLY_FIRE


class TestClock:
    def test_clock_ms_starts_at_zero(self):
        engine = make_engine(board_with())
        assert engine.clock_ms == 0

    def test_advance_clock_updates_clock_ms(self):
        engine = make_engine(board_with())
        engine.advance_clock(500)
        engine.advance_clock(250)
        assert engine.clock_ms == 750


class TestGameOver:
    def test_capturing_king_sets_game_over(self):
        attacker = Rook('w')
        king = King('b')
        board = board_with(((0, 0), attacker), ((0, 1), king))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.advance_clock(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is True
        assert board.get(Position(0, 1)) is attacker

    def test_capturing_non_king_does_not_set_game_over(self):
        attacker = Rook('w')
        enemy = Pawn('b')
        board = board_with(((0, 0), attacker), ((0, 1), enemy))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.advance_clock(DEFAULT_MOVE_DELAY_MS)

        assert engine.game_over is False

    def test_king_capture_cancels_other_in_flight_moves(self):
        attacker = Rook('w')
        king = King('b')
        bystander = Bishop('w')
        board = board_with(((0, 0), attacker), ((0, 1), king), ((2, 2), bystander))
        engine = make_engine(board)

        engine.request_move(Position(2, 2), Position(5, 5))  # matures at 3000
        engine.request_move(Position(0, 0), Position(0, 1))  # matures at 1000, captures king

        engine.advance_clock(DEFAULT_MOVE_DELAY_MS)
        assert engine.game_over is True

        engine.advance_clock(2 * DEFAULT_MOVE_DELAY_MS)
        assert board.get(Position(2, 2)) is bystander
        assert board.get(Position(5, 5)) is None

    def test_request_move_rejected_once_game_is_over(self):
        attacker = Rook('w')
        king = King('b')
        bystander = Pawn('w')
        board = board_with(((0, 0), attacker), ((0, 1), king), ((4, 4), bystander))
        engine = make_engine(board)

        engine.request_move(Position(0, 0), Position(0, 1))
        engine.advance_clock(DEFAULT_MOVE_DELAY_MS)
        assert engine.game_over is True

        result = engine.request_move(Position(4, 4), Position(4, 5))

        assert result.legal is False
        assert result.reason is MoveRejectionReason.GAME_OVER
        assert engine.is_moving(bystander) is False


class TestJump:
    def test_jump_request_is_legal_and_lands_after_jump_duration(self):
        rook = Rook('w')
        board = board_with(((4, 4), rook))
        engine = make_engine(board)

        result = engine.request_move(Position(4, 4), Position(4, 4))
        assert result.legal is True
        assert engine.is_moving(rook) is True

        engine.advance_clock(DEFAULT_MOVE_DELAY_MS)
        assert engine.is_moving(rook) is False
        assert board.get(Position(4, 4)) is rook

    def test_jumping_while_already_moving_is_rejected(self):
        rook = Rook('w')
        board = board_with(((4, 4), rook))
        engine = make_engine(board)

        engine.request_move(Position(4, 4), Position(4, 7))
        result = engine.request_move(Position(4, 4), Position(4, 4))

        assert result.legal is False
        assert result.reason is MoveRejectionReason.PIECE_ALREADY_MOVING

    def test_king_destroyed_by_airborne_defender_sets_game_over(self):
        attacker = King('w')
        defender = Rook('b')
        board = board_with(((4, 3), attacker), ((4, 4), defender))
        engine = make_engine(board)

        engine.request_move(Position(4, 3), Position(4, 4))  # king begins walking in, matures at 1000
        engine.advance_clock(500)
        engine.request_move(Position(4, 4), Position(4, 4))  # defender jumps, matures at 1500

        engine.advance_clock(500)  # clock now 1000: king arrives while defender still airborne

        assert engine.game_over is True
        assert board.get(Position(4, 3)) is None
        assert board.get(Position(4, 4)) is defender
